"""
Security & Governance Agent

This agent enforces security policies with unconditional veto power.
It validates queries against:
- Dangerous operations (DROP, DELETE, UPDATE, etc.)
- PII column access based on user role
- Role-based access control (RBAC) for tables and columns
- Risk scoring based on query characteristics

This is a policy-based agent (no LLM calls) for deterministic, auditable
security decisions.
"""

import re
import time
import yaml
from pathlib import Path
from typing import List, Tuple, Dict, Set, Optional
from agents.base import BaseAgent, AgentExecutionError
from agents.models.security_models import SecurityRequest, SecurityResponse
from config.logging_config import get_logger

logger = get_logger(__name__)


class SecurityGovernanceAgent(BaseAgent):
    """
    Security & Governance agent with policy-based validation.
    
    Validates queries against security policies loaded from YAML configuration.
    Provides unconditional veto power to halt dangerous operations.
    
    Attributes:
        name: Agent name
        logger: Logger instance
        policies: Security policies loaded from YAML
        pii_columns: Set of PII column names (table.column format)
        blocked_operations: Set of dangerous SQL operations
        role_permissions: Dict of role-based permissions
        risk_weights: Dict of risk scoring weights
    """
    
    def __init__(self):
        """Initialize the Security & Governance agent."""
        super().__init__(name="SecurityGovernanceAgent")
        
        # Load security policies from YAML
        self.policies = self._load_security_policies()
        
        # Cache policy components for fast validation
        self.pii_columns = set(self.policies.get('pii_columns', []))
        self.blocked_operations = set(self.policies.get('blocked_operations', []))
        self.role_permissions = self.policies.get('role_permissions', {})
        self.risk_weights = self.policies.get('risk_weights', {})
        
        self.logger.info(
            f"Security policies loaded: {len(self.pii_columns)} PII columns, "
            f"{len(self.blocked_operations)} blocked operations, "
            f"{len(self.role_permissions)} roles"
        )
    
    def _load_security_policies(self) -> Dict:
        """
        Load security policies from YAML configuration file.
        
        Returns:
            Dict containing security policies
            
        Raises:
            AgentExecutionError: If policies file cannot be loaded
        """
        # Find policies file relative to this module
        policies_path = Path(__file__).parent / 'config' / 'security_policies.yaml'
        
        if not policies_path.exists():
            raise AgentExecutionError(
                f"Security policies file not found: {policies_path}"
            )
        
        try:
            with open(policies_path, 'r') as f:
                policies = yaml.safe_load(f)
            
            self.logger.info(f"Loaded security policies from {policies_path}")
            return policies
            
        except Exception as e:
            raise AgentExecutionError(
                f"Failed to load security policies: {e}"
            )
    
    def execute(self, request: SecurityRequest) -> SecurityResponse:
        """
        Execute security validation with veto power.
        
        Validation checks (in order):
        1. Check for dangerous operations in refined query and SQL
        2. Check for PII column access based on user role
        3. Validate user role has permission for requested tables
        4. Calculate risk score based on checks
        5. Return approved=True if all checks pass, approved=False with veto_reason if any check fails
        
        Args:
            request: SecurityRequest with refined query, user role, and optional SQL
            
        Returns:
            SecurityResponse with approval decision, risk score, and veto reason
            
        Raises:
            AgentValidationError: If request validation fails
        """
        start_time = time.time()
        
        # Validate request
        self._validate_request(request)
        
        self.logger.info(
            f"Validating security for user role '{request.user_role}': {request.refined_query[:100]}"
        )
        
        # Collect all violations
        violations = []
        risk_score = 0.0
        alternative_suggestions = []
        
        # Check 1: Dangerous operations
        dangerous_ops = self._check_dangerous_operations(
            request.refined_query,
            request.generated_sql
        )
        if dangerous_ops:
            violations.extend(dangerous_ops)
            risk_score = 1.0  # Automatic critical risk
            alternative_suggestions.append(
                "Only SELECT queries are allowed for data retrieval"
            )
        
        # Check 2: PII column access
        pii_violations = self._check_pii_access(
            request.refined_query,
            request.generated_sql,
            request.user_role
        )
        if pii_violations:
            violations.extend(pii_violations)
            risk_score = max(risk_score, self.risk_weights.get('pii_access', 0.5))
            alternative_suggestions.append(
                "Request aggregated statistics instead of individual records"
            )
            alternative_suggestions.append(
                "Contact admin for PII access approval"
            )
        
        # Check 3: Table access permissions
        table_violations = self._check_table_access(
            request.refined_query,
            request.generated_sql,
            request.user_role
        )
        if table_violations:
            violations.extend(table_violations)
            risk_score = max(risk_score, 0.7)
            alternative_suggestions.append(
                f"User role '{request.user_role}' has limited table access"
            )
        
        # Check 4: Additional risk factors (if no critical violations)
        if not violations:
            risk_score = self._calculate_risk_score(
                request.refined_query,
                request.generated_sql
            )
        
        # Determine approval
        approved = len(violations) == 0
        veto_reason = None
        
        if not approved:
            veto_reason = "; ".join(violations)
            self.logger.warning(
                f"Security VETO for user role '{request.user_role}': {veto_reason}"
            )
        else:
            self.logger.info(
                f"Security APPROVED for user role '{request.user_role}' "
                f"with risk score {risk_score:.2f}"
            )
        
        self._log_execution_time("Security validation", start_time)
        
        return SecurityResponse(
            success=True,
            approved=approved,
            risk_score=risk_score,
            veto_reason=veto_reason,
            alternative_suggestions=alternative_suggestions,
            confidence=1.0,  # Policy-based validation is always confident
            metadata={
                "execution_time": time.time() - start_time,
                "user_role": request.user_role,
                "violations_count": len(violations)
            }
        )
    
    def _check_dangerous_operations(
        self,
        refined_query: str,
        generated_sql: Optional[str]
    ) -> List[str]:
        """
        Check for dangerous SQL operations.
        
        Args:
            refined_query: Refined query text
            generated_sql: Optional generated SQL
            
        Returns:
            List of violation messages
        """
        violations = []
        
        # Check both refined query and SQL
        texts_to_check = [refined_query]
        if generated_sql:
            texts_to_check.append(generated_sql)
        
        for text in texts_to_check:
            text_upper = text.upper()
            
            for operation in self.blocked_operations:
                # Use word boundary to avoid false positives
                if re.search(r'\b' + operation + r'\b', text_upper):
                    violations.append(f"Dangerous operation: {operation}")
        
        return violations
    
    def _check_pii_access(
        self,
        refined_query: str,
        generated_sql: Optional[str],
        user_role: str
    ) -> List[str]:
        """
        Check for PII column access based on user role.
        
        Args:
            refined_query: Refined query text
            generated_sql: Optional generated SQL
            user_role: User role for RBAC
            
        Returns:
            List of violation messages
        """
        violations = []
        
        # Admin role has access to all columns including PII
        if user_role == 'admin':
            return violations
        
        # Get role permissions
        role_perms = self.role_permissions.get(user_role, {})
        excluded_columns = set(role_perms.get('excluded_columns', []))
        
        # Check both refined query and SQL
        texts_to_check = [refined_query]
        if generated_sql:
            texts_to_check.append(generated_sql)
        
        # Find PII columns mentioned in query
        pii_accessed = set()
        
        for text in texts_to_check:
            text_lower = text.lower()
            
            # Check each PII column
            for pii_col in self.pii_columns:
                # Extract table and column name
                if '.' in pii_col:
                    table, column = pii_col.split('.', 1)
                else:
                    column = pii_col
                
                # Check if column is mentioned (case-insensitive)
                if column.lower() in text_lower:
                    # Check if this column is excluded for the role
                    if pii_col in excluded_columns or column in excluded_columns:
                        pii_accessed.add(pii_col)
        
        if pii_accessed:
            pii_list = ', '.join(sorted(pii_accessed))
            violations.append(f"PII access denied: {pii_list}")
        
        return violations
    
    def _check_table_access(
        self,
        refined_query: str,
        generated_sql: Optional[str],
        user_role: str
    ) -> List[str]:
        """
        Check for table access permissions based on user role.
        
        Args:
            refined_query: Refined query text
            generated_sql: Optional generated SQL
            user_role: User role for RBAC
            
        Returns:
            List of violation messages
        """
        violations = []
        
        # Get role permissions
        role_perms = self.role_permissions.get(user_role, {})
        allowed_tables = role_perms.get('tables', [])
        
        # Admin role has access to all tables
        if allowed_tables == 'all':
            return violations
        
        # Convert to set for fast lookup
        allowed_tables_set = set(allowed_tables) if allowed_tables else set()
        
        # Extract tables from SQL (if available)
        tables_accessed = set()
        
        if generated_sql:
            tables_accessed = self._extract_tables_from_sql(generated_sql)
        else:
            # Try to extract table names from refined query
            tables_accessed = self._extract_tables_from_text(refined_query)
        
        # Check if all accessed tables are allowed
        unauthorized_tables = tables_accessed - allowed_tables_set
        
        if unauthorized_tables:
            table_list = ', '.join(sorted(unauthorized_tables))
            violations.append(
                f"Unauthorized table access: {table_list}"
            )
        
        return violations
    
    def _extract_tables_from_sql(self, sql: str) -> Set[str]:
        """
        Extract table names from SQL query.
        
        Args:
            sql: SQL query
            
        Returns:
            Set of table names
        """
        tables = set()
        
        patterns = [
            r'\bFROM\s+(\w+)',
            r'\bJOIN\s+(\w+)',
            r'\bINNER\s+JOIN\s+(\w+)',
            r'\bLEFT\s+JOIN\s+(\w+)',
            r'\bRIGHT\s+JOIN\s+(\w+)',
            r'\bFULL\s+JOIN\s+(\w+)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, sql, re.IGNORECASE)
            tables.update(matches)
        
        return tables
    
    def _extract_tables_from_text(self, text: str) -> Set[str]:
        """
        Extract potential table names from text.
        
        This is a heuristic approach for refined queries without SQL.
        
        Args:
            text: Refined query text
            
        Returns:
            Set of potential table names
        """
        tables = set()
        
        # Known table names from schema (hardcoded for now)
        known_tables = {
            'iso_tank', 'service_tank', 'vehicle_in', 'vehicle_out',
            'survey_form', 'SurakshaClientEmail', 'visitor'
        }
        
        text_lower = text.lower()
        
        for table in known_tables:
            if table.lower() in text_lower:
                tables.add(table)
        
        return tables
    
    def _calculate_risk_score(
        self,
        refined_query: str,
        generated_sql: Optional[str]
    ) -> float:
        """
        Calculate risk score based on query characteristics.
        
        Risk factors:
        - PII access: +0.5
        - Cross-domain JOIN: +0.2
        - Large result set (no LIMIT): +0.1
        - Dangerous operation: 1.0 (automatic block)
        
        Args:
            refined_query: Refined query text
            generated_sql: Optional generated SQL
            
        Returns:
            Risk score between 0.0 and 1.0
        """
        risk_score = 0.0
        
        # Check for cross-domain JOIN
        if generated_sql and self._has_cross_domain_join(generated_sql):
            risk_score += self.risk_weights.get('cross_domain_join', 0.2)
        
        # Check for large result set (no LIMIT)
        if generated_sql and not self._has_limit_clause(generated_sql):
            risk_score += self.risk_weights.get('large_result_set', 0.1)
        
        # Ensure risk score stays in valid range
        return min(1.0, risk_score)
    
    def _has_cross_domain_join(self, sql: str) -> bool:
        """
        Check if SQL has cross-domain JOIN.
        
        Cross-domain means joining tables from different business domains
        (e.g., iso_tank + visitor).
        
        Args:
            sql: SQL query
            
        Returns:
            True if cross-domain JOIN found
        """
        # Extract tables
        tables = self._extract_tables_from_sql(sql)
        
        # Define domain groups
        tank_domain = {'iso_tank', 'service_tank'}
        vehicle_domain = {'vehicle_in', 'vehicle_out'}
        visitor_domain = {'visitor', 'SurakshaClientEmail'}
        survey_domain = {'survey_form'}
        
        domains = [tank_domain, vehicle_domain, visitor_domain, survey_domain]
        
        # Check if tables span multiple domains
        domains_accessed = []
        for domain in domains:
            if tables & domain:
                domains_accessed.append(domain)
        
        return len(domains_accessed) > 1
    
    def _has_limit_clause(self, sql: str) -> bool:
        """
        Check if SQL has LIMIT clause.
        
        Args:
            sql: SQL query
            
        Returns:
            True if LIMIT clause found
        """
        return bool(re.search(r'\bLIMIT\s+\d+', sql, re.IGNORECASE))
