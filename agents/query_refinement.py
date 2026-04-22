"""
Query Refinement Agent

This agent transforms natural language queries using business glossary and LLM.
It resolves temporal ambiguity, maps business terminology to database concepts,
and clarifies ambiguous intent.

Key features:
- Loads business glossary from YAML configuration
- Uses AI provider (OpenAI-compatible or Anthropic) for query transformation
- Resolves temporal terms ("this month" → DATE_TRUNC)
- Maps business entities ("clients" → vehicle_in.croyance_client_name)
- Returns clarification questions for ambiguous queries
- Confidence scoring based on query clarity
"""

import time
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from agents.base import BaseAgent, AgentExecutionError
from agents.models.refinement_models import RefinementRequest, RefinementResponse
from config.ai_provider import ai_client, model_name, SDK_TYPE
from config.logging_config import get_logger

logger = get_logger(__name__)


class QueryRefinementAgent(BaseAgent):
    """
    Query Refinement agent with LLM-based transformation.
    
    Transforms natural language queries using business glossary and AI.
    Resolves temporal ambiguity and maps business terminology to database concepts.
    
    Attributes:
        name: Agent name
        logger: Logger instance
        ai_client: AI provider client
        model_name: AI model name
        sdk_type: SDK type (openai_compatible or anthropic)
        business_glossary: Business glossary loaded from YAML
        temporal_terms: Temporal term mappings
        entity_mappings: Business entity mappings
    """
    
    def __init__(self):
        """Initialize the Query Refinement agent."""
        super().__init__(name="QueryRefinementAgent")
        
        # AI provider configuration
        self.ai_client = ai_client
        self.model_name = model_name
        self.sdk_type = SDK_TYPE
        
        # Load business glossary from YAML
        self.business_glossary = self._load_business_glossary()
        self.temporal_terms = self.business_glossary.get('temporal_terms', {})
        self.entity_mappings = self.business_glossary.get('entity_mappings', {})
        
        self.logger.info(
            f"Query Refinement agent initialized with {len(self.temporal_terms)} temporal terms "
            f"and {len(self.entity_mappings)} entity mappings"
        )
    
    def _load_business_glossary(self) -> Dict:
        """
        Load business glossary from YAML configuration file.
        
        Returns:
            Dict containing business glossary
            
        Raises:
            AgentExecutionError: If glossary file cannot be loaded
        """
        # Find glossary file relative to this module
        glossary_path = Path(__file__).parent / 'config' / 'business_glossary.yaml'
        
        if not glossary_path.exists():
            raise AgentExecutionError(
                f"Business glossary file not found: {glossary_path}"
            )
        
        try:
            with open(glossary_path, 'r') as f:
                glossary = yaml.safe_load(f)
            
            self.logger.info(f"Loaded business glossary from {glossary_path}")
            return glossary
            
        except Exception as e:
            raise AgentExecutionError(
                f"Failed to load business glossary: {e}"
            )
    
    def execute(self, request: RefinementRequest) -> RefinementResponse:
        """
        Execute query refinement with LLM and business glossary.
        
        Workflow:
        1. Validate request
        2. Build system prompt with business glossary context
        3. Call AI provider to refine query
        4. Parse response and determine confidence
        5. Return refined query with confidence and clarification questions
        
        Args:
            request: RefinementRequest with raw question and business glossary
            
        Returns:
            RefinementResponse with refined query, confidence, and clarification questions
            
        Raises:
            AgentValidationError: If request validation fails
        """
        start_time = time.time()
        
        # Validate request (inherited from BaseAgent)
        self._validate_request(request)
        
        self.logger.info(f"Refining query: {request.question}")
        
        try:
            # Use business glossary from request if provided, otherwise use loaded glossary
            glossary_to_use = request.business_glossary if request.business_glossary else self.business_glossary
            
            # Build system prompt with business glossary context
            system_prompt = self._build_system_prompt(
                glossary_to_use,
                request.current_datetime
            )
            
            # Call AI provider to refine query
            refined_query = self._call_ai_provider(
                system_prompt,
                request.question,
                temperature=0.3  # Balance determinism and creativity
            )
            
            # Analyze response and determine confidence
            confidence, clarification_questions = self._analyze_refinement_quality(
                request.question,
                refined_query
            )
            
            self._log_execution_time("Query refinement", start_time)
            
            self.logger.info(
                f"Query refinement completed with confidence {confidence:.2f}: "
                f"{refined_query[:100]}..."
            )
            
            return RefinementResponse(
                success=True,
                refined_query=refined_query,
                confidence=confidence,
                clarification_questions=clarification_questions,
                metadata={
                    "execution_time": time.time() - start_time,
                    "original_question": request.question,
                    "glossary_terms_used": self._count_glossary_terms_used(
                        request.question, glossary_to_use
                    )
                }
            )
            
        except Exception as e:
            self.logger.error(f"Query refinement error: {e}", exc_info=True)
            self._log_execution_time("Query refinement (error)", start_time)
            
            return RefinementResponse(
                success=False,
                refined_query="",
                confidence=0.0,
                clarification_questions=[],
                error=f"Query refinement failed: {str(e)}",
                metadata={
                    "execution_time": time.time() - start_time,
                    "error_type": type(e).__name__
                }
            )
    
    def _build_system_prompt(
        self,
        business_glossary: Dict,
        current_datetime: datetime
    ) -> str:
        """
        Build system prompt with business glossary context.
        
        Args:
            business_glossary: Business glossary with temporal terms and entity mappings
            current_datetime: Current datetime for temporal resolution
            
        Returns:
            System prompt string
        """
        temporal_terms = business_glossary.get('temporal_terms', {})
        entity_mappings = business_glossary.get('entity_mappings', {})
        
        prompt = f"""You are a query refinement agent for a tank depot management system.

Your task is to transform natural language questions into refined queries with explicit intent.
Use the business glossary below to resolve ambiguity and map business terminology to database concepts.

CURRENT DATE/TIME: {current_datetime.strftime('%Y-%m-%d %H:%M:%S')}

TEMPORAL TERMS (resolve time-related phrases):
"""
        
        for term, sql_clause in temporal_terms.items():
            prompt += f"- '{term}' → {sql_clause}\n"
        
        prompt += "\nENTITY MAPPINGS (map business terms to database concepts):\n"
        
        for entity, mapping in entity_mappings.items():
            prompt += f"- '{entity}' → {mapping}\n"
        
        prompt += """
INSTRUCTIONS:
1. Resolve temporal ambiguity using the temporal terms above
2. Map business terminology to database concepts using entity mappings
3. Make implicit intent explicit (e.g., "most tanks" → "COUNT(*) ORDER BY count DESC")
4. If the query is ambiguous and needs clarification, include [CLARIFICATION_NEEDED] followed by specific questions
5. Return only the refined query with explicit intent - no markdown, no explanation

EXAMPLES:
Input: "Which clients have the most tanks this month?"
Output: "Retrieve count of ISO tanks grouped by croyance_client_name WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE) ORDER BY count DESC"

Input: "Show me tanks from today"
Output: "Retrieve tank_number and iso_tank_status from iso_tank WHERE DATE(created_at) = CURRENT_DATE"

Input: "How many unsurveyed tanks?"
Output: "Retrieve COUNT(*) from iso_tank WHERE survey_form_id IS NULL"

Input: "Show me the best products"
Output: "[CLARIFICATION_NEEDED] Do you mean best by revenue, quantity, or another metric? What time period should be considered?"

USER QUESTION:
"""
        
        return prompt
    
    def _call_ai_provider(
        self,
        system_prompt: str,
        question: str,
        temperature: float
    ) -> str:
        """
        Call AI provider to refine query.
        
        Args:
            system_prompt: System prompt with business glossary
            question: User question to refine
            temperature: AI temperature
            
        Returns:
            Refined query from AI
        """
        if self.sdk_type == "openai_compatible":
            # OpenAI-compatible API
            response = self.ai_client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=temperature,
                max_tokens=300
            )
            
            refined_query = response.choices[0].message.content.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                self.logger.info(
                    f"Token usage - prompt: {response.usage.prompt_tokens}, "
                    f"completion: {response.usage.completion_tokens}, "
                    f"total: {response.usage.total_tokens}"
                )
            
            return refined_query
            
        elif self.sdk_type == "anthropic":
            # Anthropic API
            response = self.ai_client.messages.create(
                model=self.model_name,
                max_tokens=300,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": question}
                ]
            )
            
            refined_query = response.content[0].text.strip()
            
            # Log token usage
            if hasattr(response, 'usage'):
                self.logger.info(
                    f"Token usage - input: {response.usage.input_tokens}, "
                    f"output: {response.usage.output_tokens}"
                )
            
            return refined_query
        
        else:
            raise AgentExecutionError(f"Unsupported SDK type: {self.sdk_type}")
    
    def _analyze_refinement_quality(
        self,
        original_question: str,
        refined_query: str
    ) -> tuple[float, List[str]]:
        """
        Analyze refinement quality and determine confidence score.
        
        Args:
            original_question: Original user question
            refined_query: Refined query from AI
            
        Returns:
            Tuple of (confidence_score, clarification_questions)
        """
        clarification_questions = []
        
        # Check if AI requested clarification
        if "[CLARIFICATION_NEEDED]" in refined_query:
            # Extract clarification questions
            parts = refined_query.split("[CLARIFICATION_NEEDED]", 1)
            if len(parts) > 1:
                clarification_text = parts[1].strip()
                # Split by question marks and filter empty strings
                questions = [q.strip() + "?" for q in clarification_text.split("?") if q.strip()]
                clarification_questions = questions
            
            # Remove clarification marker from refined query
            refined_query = parts[0].strip()
            
            return 0.5, clarification_questions  # Low confidence when clarification needed
        
        # Analyze transformation quality
        original_lower = original_question.lower()
        refined_lower = refined_query.lower()
        
        # High confidence indicators
        high_confidence_indicators = [
            "date_trunc" in refined_lower,  # Temporal resolution
            "current_date" in refined_lower,  # Date functions
            "count(*)" in refined_lower,  # Aggregation
            "group by" in refined_lower,  # Grouping
            "order by" in refined_lower,  # Sorting
            any(entity in refined_lower for entity in self.entity_mappings.keys())  # Entity mapping
        ]
        
        # Medium confidence indicators
        medium_confidence_indicators = [
            len(refined_query) > len(original_question) * 1.2,  # Significant expansion
            "retrieve" in refined_lower,  # Explicit action
            "where" in refined_lower,  # Filtering
        ]
        
        # Low confidence indicators
        low_confidence_indicators = [
            refined_query.lower() == original_question.lower(),  # No transformation
            len(refined_query) < 10,  # Too short
            "unclear" in refined_lower or "ambiguous" in refined_lower  # Uncertainty
        ]
        
        # Calculate confidence score
        if any(low_confidence_indicators):
            confidence = 0.5
        elif sum(high_confidence_indicators) >= 2:
            confidence = 0.9
        elif sum(high_confidence_indicators) >= 1 or sum(medium_confidence_indicators) >= 2:
            confidence = 0.8
        elif sum(medium_confidence_indicators) >= 1:
            confidence = 0.7
        else:
            confidence = 0.6
        
        return confidence, clarification_questions
    
    def _count_glossary_terms_used(
        self,
        question: str,
        business_glossary: Dict
    ) -> int:
        """
        Count how many glossary terms were found in the question.
        
        Args:
            question: Original user question
            business_glossary: Business glossary
            
        Returns:
            Number of glossary terms found
        """
        question_lower = question.lower()
        terms_found = 0
        
        # Check temporal terms
        temporal_terms = business_glossary.get('temporal_terms', {})
        for term in temporal_terms.keys():
            if term.replace('_', ' ') in question_lower:
                terms_found += 1
        
        # Check entity mappings
        entity_mappings = business_glossary.get('entity_mappings', {})
        for entity in entity_mappings.keys():
            if entity in question_lower:
                terms_found += 1
        
        return terms_found