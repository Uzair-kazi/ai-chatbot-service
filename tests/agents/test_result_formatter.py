"""
Tests for Result Formatter Agent

Test coverage:
- Happy path: Template-based and LLM-based formatting
- Error path: SQL execution errors, formatting failures
- Edge cases: Empty results, single values, large datasets
- Integration: MCP client integration with fallback
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from agents.result_formatter import ResultFormatterAgent
from agents.models.formatter_models import FormatterRequest, FormatterResponse
from agents.base import AgentValidationError
from agents.mcp_client import MCPConnectionError, MCPQueryError, MCPTimeoutError, QueryResult
from services.sql_executor import QueryTimeoutError, DatabaseConnectionError, SQLSyntaxError, PermissionDeniedError


class TestResultFormatterAgent:
    """Test suite for ResultFormatterAgent."""
    
    @pytest.fixture
    def agent(self):
        """Create ResultFormatterAgent instance with mocked dependencies."""
        with patch('agents.result_formatter.MCPClient') as mock_mcp_class, \
             patch('agents.result_formatter.get_executor') as mock_executor_func, \
             patch('agents.result_formatter.ai_client') as mock_ai_client:
            
            # Mock MCP client
            mock_mcp = Mock()
            mock_mcp.is_connected.return_value = False  # Default to fallback mode
            mock_mcp_class.return_value = mock_mcp
            
            # Mock SQL executor
            mock_executor = Mock()
            mock_executor_func.return_value = mock_executor
            
            agent = ResultFormatterAgent()
            agent.mcp_client = mock_mcp
            agent.sql_executor = mock_executor
            agent.ai_client = mock_ai_client
            
            return agent
    
    @pytest.fixture
    def sample_request(self):
        """Create sample FormatterRequest."""
        return FormatterRequest(
            question="How many ISO tanks are in 'IN' status?",
            sql="SELECT COUNT(*) FROM iso_tank WHERE iso_tank_status = 'IN';"
        )
    
    @pytest.fixture
    def count_result(self):
        """Sample COUNT query result."""
        return {
            "columns": ["count"],
            "rows": [{"count": 47}],
            "row_count": 1
        }
    
    @pytest.fixture
    def list_result(self):
        """Sample list query result."""
        return {
            "columns": ["tank_number", "status"],
            "rows": [
                {"tank_number": "T001", "status": "IN"},
                {"tank_number": "T002", "status": "IN"},
                {"tank_number": "T003", "status": "OUT"}
            ],
            "row_count": 3
        }
    
    @pytest.fixture
    def empty_result(self):
        """Sample empty query result."""
        return {
            "columns": ["tank_number"],
            "rows": [],
            "row_count": 0
        }
    
    @pytest.fixture
    def large_result(self):
        """Sample large query result (>10 rows)."""
        rows = [{"client_name": f"Client {i}", "tank_count": i * 5} for i in range(1, 16)]
        return {
            "columns": ["client_name", "tank_count"],
            "rows": rows,
            "row_count": 15
        }
    
    # Happy path tests - Template-based formatting
    
    def test_format_count_query_template(self, agent, sample_request, count_result):
        """Test formatting COUNT query with template-based approach."""
        # Mock SQL execution
        agent.sql_executor.execute_query.return_value = count_result
        
        response = agent.execute(sample_request)
        
        assert response.success is True
        assert response.answer == "The answer is 47."
        assert response.sql == sample_request.sql
        assert response.rows_count == 1
        assert response.formatting_method == "template"
        assert response.confidence == 1.0
        assert response.execution_time > 0
    
    def test_format_count_query_with_large_number(self, agent, count_result):
        """Test formatting COUNT query with large number (comma formatting)."""
        # Large count result
        count_result["rows"] = [{"count": 12345}]
        agent.sql_executor.execute_query.return_value = count_result
        
        request = FormatterRequest(
            question="How many total tanks?",
            sql="SELECT COUNT(*) FROM iso_tank;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.answer == "The answer is 12,345."
        assert response.formatting_method == "template"
    
    def test_format_empty_result_template(self, agent, empty_result):
        """Test formatting empty result set."""
        agent.sql_executor.execute_query.return_value = empty_result
        
        request = FormatterRequest(
            question="Show tanks with invalid status",
            sql="SELECT tank_number FROM iso_tank WHERE status = 'INVALID';"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.answer == "No results found for your query."
        assert response.rows_count == 0
        assert response.formatting_method == "template"
    
    def test_format_single_row_multiple_columns(self, agent):
        """Test formatting single row with multiple columns."""
        result = {
            "columns": ["tank_number", "status", "client"],
            "rows": [{"tank_number": "T001", "status": "IN", "client": "ACME Corp"}],
            "row_count": 1
        }
        agent.sql_executor.execute_query.return_value = result
        
        request = FormatterRequest(
            question="Show details for tank T001",
            sql="SELECT tank_number, status, client FROM iso_tank WHERE tank_number = 'T001';"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "tank_number: T001" in response.answer
        assert "status: IN" in response.answer
        assert "client: ACME Corp" in response.answer
        assert response.formatting_method == "template"
    
    def test_format_simple_list_template(self, agent, list_result):
        """Test formatting simple list with template approach."""
        agent.sql_executor.execute_query.return_value = list_result
        
        request = FormatterRequest(
            question="Show tank numbers and status",
            sql="SELECT tank_number, status FROM iso_tank LIMIT 3;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.rows_count == 3
        assert response.formatting_method == "template"
        assert "3 records" in response.answer or "3 fields" in response.answer
    
    def test_format_single_column_list(self, agent):
        """Test formatting single column list."""
        result = {
            "columns": ["tank_number"],
            "rows": [{"tank_number": "T001"}, {"tank_number": "T002"}, {"tank_number": "T003"}],
            "row_count": 3
        }
        agent.sql_executor.execute_query.return_value = result
        
        request = FormatterRequest(
            question="List tank numbers",
            sql="SELECT tank_number FROM iso_tank LIMIT 3;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "T001, T002, T003" in response.answer
        assert response.formatting_method == "template"
    
    # Happy path tests - LLM-based formatting
    
    def test_format_large_result_llm(self, agent, large_result):
        """Test formatting large result set with LLM approach."""
        agent.sql_executor.execute_query.return_value = large_result
        
        # Mock AI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "The top clients by tank count are Client 15 (75 tanks), Client 14 (70 tanks), and Client 13 (65 tanks). Showing 10 of 15 total results."
        mock_response.usage = Mock()
        mock_response.usage.prompt_tokens = 150
        mock_response.usage.completion_tokens = 50
        mock_response.usage.total_tokens = 200
        
        agent.ai_client.chat.completions.create.return_value = mock_response
        agent.sdk_type = "openai_compatible"
        
        request = FormatterRequest(
            question="Which clients have the most tanks?",
            sql="SELECT client_name, COUNT(*) as tank_count FROM iso_tank GROUP BY client_name ORDER BY tank_count DESC;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert "Client 15" in response.answer
        assert response.rows_count == 15
        assert response.formatting_method == "llm"
        assert response.confidence == 0.9
        
        # Verify AI was called
        agent.ai_client.chat.completions.create.assert_called_once()
    
    def test_format_complex_aggregation_llm(self, agent):
        """Test formatting complex aggregation with LLM."""
        result = {
            "columns": ["status", "avg_days", "tank_count"],
            "rows": [
                {"status": "IN", "avg_days": 15.5, "tank_count": 25},
                {"status": "OUT", "avg_days": 8.2, "tank_count": 12},
                {"status": "MAINTENANCE", "avg_days": 45.0, "tank_count": 3}
            ],
            "row_count": 3
        }
        agent.sql_executor.execute_query.return_value = result
        
        # Mock AI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Tank status analysis shows: IN status tanks average 15.5 days (25 tanks), OUT status tanks average 8.2 days (12 tanks), and MAINTENANCE tanks average 45 days (3 tanks)."
        agent.ai_client.chat.completions.create.return_value = mock_response
        agent.sdk_type = "openai_compatible"
        
        request = FormatterRequest(
            question="What's the average time by tank status?",
            sql="SELECT status, AVG(days_in_depot) as avg_days, COUNT(*) as tank_count FROM iso_tank GROUP BY status;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.formatting_method == "llm"
        assert "15.5 days" in response.answer
    
    # Error path tests - SQL execution errors
    
    def test_sql_timeout_error(self, agent, sample_request):
        """Test handling SQL timeout error."""
        agent.sql_executor.execute_query.side_effect = QueryTimeoutError("Query timeout")
        
        response = agent.execute(sample_request)
        
        assert response.success is False
        assert "took too long" in response.answer
        assert response.formatting_method == "error"
        assert response.confidence == 0.0
        assert response.metadata["error_type"] == "timeout"
    
    def test_sql_syntax_error(self, agent, sample_request):
        """Test handling SQL syntax error."""
        agent.sql_executor.execute_query.side_effect = SQLSyntaxError("Invalid syntax")
        
        response = agent.execute(sample_request)
        
        assert response.success is False
        assert "Invalid SQL query" in response.answer
        assert response.metadata["error_type"] == "syntax"
    
    def test_permission_denied_error(self, agent, sample_request):
        """Test handling permission denied error."""
        agent.sql_executor.execute_query.side_effect = PermissionDeniedError("Access denied")
        
        response = agent.execute(sample_request)
        
        assert response.success is False
        assert "Access denied" in response.answer
        assert response.metadata["error_type"] == "permission"
    
    def test_database_connection_error(self, agent, sample_request):
        """Test handling database connection error."""
        agent.sql_executor.execute_query.side_effect = DatabaseConnectionError("Connection failed")
        
        response = agent.execute(sample_request)
        
        assert response.success is False
        assert "temporarily unavailable" in response.answer
        assert response.metadata["error_type"] == "connection"
    
    def test_unexpected_error(self, agent, sample_request):
        """Test handling unexpected error."""
        agent.sql_executor.execute_query.side_effect = ValueError("Unexpected error")
        
        response = agent.execute(sample_request)
        
        assert response.success is False
        assert "unexpected error" in response.answer
        assert response.metadata["error_type"] == "unexpected"
    
    # Error path tests - Request validation
    
    def test_empty_question_validation(self, agent):
        """Test validation with empty question."""
        request = FormatterRequest(question="", sql="SELECT * FROM iso_tank;")
        
        with pytest.raises(AgentValidationError, match="Question cannot be empty"):
            agent.execute(request)
    
    def test_empty_sql_validation(self, agent):
        """Test validation with empty SQL."""
        request = FormatterRequest(question="Show tanks", sql="")
        
        with pytest.raises(AgentValidationError, match="SQL cannot be empty"):
            agent.execute(request)
    
    def test_non_select_sql_validation(self, agent):
        """Test validation with non-SELECT SQL."""
        request = FormatterRequest(
            question="Delete tanks",
            sql="DELETE FROM iso_tank WHERE status = 'OLD';"
        )
        
        with pytest.raises(AgentValidationError, match="Only SELECT queries are allowed"):
            agent.execute(request)
    
    # Integration tests - MCP client
    
    def test_mcp_client_success(self, agent, sample_request, count_result):
        """Test successful execution via MCP client."""
        # Enable MCP mode
        agent.mcp_client.is_connected.return_value = True
        
        # Mock MCP result
        mcp_result = QueryResult(
            success=True,
            rows=count_result["rows"],
            row_count=count_result["row_count"],
            columns=count_result["columns"],
            execution_time=0.1
        )
        agent.mcp_client.execute_query.return_value = mcp_result
        
        response = agent.execute(sample_request)
        
        assert response.success is True
        assert response.answer == "The answer is 47."
        assert response.metadata["mcp_used"] is True
        
        # Verify MCP was called, not direct executor
        agent.mcp_client.execute_query.assert_called_once_with(sample_request.sql)
        agent.sql_executor.execute_query.assert_not_called()
    
    def test_mcp_client_fallback_on_error(self, agent, sample_request, count_result):
        """Test fallback to direct executor when MCP fails."""
        # Enable MCP mode but make it fail
        agent.mcp_client.is_connected.return_value = True
        agent.mcp_client.execute_query.side_effect = MCPConnectionError("MCP failed")
        
        # Mock successful direct executor
        agent.sql_executor.execute_query.return_value = count_result
        
        response = agent.execute(sample_request)
        
        assert response.success is True
        assert response.answer == "The answer is 47."
        assert response.metadata["mcp_used"] is True  # Was attempted
        
        # Verify both were called
        agent.mcp_client.execute_query.assert_called_once()
        agent.sql_executor.execute_query.assert_called_once()
    
    def test_mcp_timeout_error(self, agent, sample_request):
        """Test MCP timeout error handling."""
        agent.mcp_client.is_connected.return_value = True
        agent.mcp_client.execute_query.side_effect = MCPTimeoutError("MCP timeout")
        # Don't let it fall back to direct executor - should catch MCP timeout directly
        
        response = agent.execute(sample_request)
        
        assert response.success is False
        assert "took too long" in response.answer
        assert response.metadata["error_type"] == "timeout"
    
    def test_mcp_query_error(self, agent, sample_request):
        """Test MCP query error handling."""
        agent.mcp_client.is_connected.return_value = True
        agent.mcp_client.execute_query.side_effect = MCPQueryError("Invalid query")
        # Don't let it fall back to direct executor - should catch MCP query error directly
        
        response = agent.execute(sample_request)
        
        assert response.success is False
        assert "Invalid SQL query" in response.answer
        assert response.metadata["error_type"] == "syntax"
    
    # Edge case tests - Formatting strategy
    
    def test_determine_formatting_method_empty(self, agent):
        """Test formatting method determination for empty results."""
        method = agent._determine_formatting_method(
            {"row_count": 0, "columns": ["count"], "rows": []},
            "How many tanks?",
            "SELECT COUNT(*) FROM iso_tank WHERE status = 'INVALID';"
        )
        assert method == "template"
    
    def test_determine_formatting_method_single_aggregation(self, agent):
        """Test formatting method determination for single aggregation."""
        method = agent._determine_formatting_method(
            {"row_count": 1, "columns": ["count"], "rows": [{"count": 47}]},
            "How many tanks?",
            "SELECT COUNT(*) FROM iso_tank;"
        )
        assert method == "template"
    
    def test_determine_formatting_method_simple_list(self, agent):
        """Test formatting method determination for simple list."""
        method = agent._determine_formatting_method(
            {"row_count": 5, "columns": ["tank_number"], "rows": []},
            "List tanks",
            "SELECT tank_number FROM iso_tank LIMIT 5;"
        )
        assert method == "template"
    
    def test_determine_formatting_method_large_result(self, agent):
        """Test formatting method determination for large result."""
        method = agent._determine_formatting_method(
            {"row_count": 15, "columns": ["client", "count"], "rows": []},
            "Which clients have most tanks?",
            "SELECT client, COUNT(*) FROM iso_tank GROUP BY client;"
        )
        assert method == "llm"
    
    def test_determine_formatting_method_complex_join(self, agent):
        """Test formatting method determination for complex JOIN."""
        method = agent._determine_formatting_method(
            {"row_count": 5, "columns": ["tank", "client"], "rows": []},
            "Show tanks and clients",
            "SELECT it.tank_number, vi.client FROM iso_tank it JOIN vehicle_in vi ON it.vehicle_in_id = vi.id;"
        )
        assert method == "llm"
    
    def test_determine_formatting_method_group_by(self, agent):
        """Test formatting method determination for GROUP BY."""
        method = agent._determine_formatting_method(
            {"row_count": 3, "columns": ["status", "count"], "rows": []},
            "Count by status",
            "SELECT status, COUNT(*) FROM iso_tank GROUP BY status;"
        )
        assert method == "llm"
    
    # Edge case tests - LLM formatting
    
    def test_llm_formatting_fallback_on_error(self, agent, large_result):
        """Test LLM formatting falls back to template on AI error."""
        agent.sql_executor.execute_query.return_value = large_result
        agent.ai_client.chat.completions.create.side_effect = Exception("AI error")
        agent.sdk_type = "openai_compatible"
        
        request = FormatterRequest(
            question="Which clients have most tanks?",
            sql="SELECT client, COUNT(*) FROM iso_tank GROUP BY client ORDER BY COUNT(*) DESC;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.formatting_method == "llm"  # Attempted LLM
        # Should contain fallback template response
        assert "15 rows" in response.answer or "15" in response.answer
    
    def test_anthropic_ai_provider(self, agent, large_result):
        """Test LLM formatting with Anthropic provider."""
        agent.sql_executor.execute_query.return_value = large_result
        
        # Mock Anthropic response
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "Analysis shows 15 clients with varying tank counts."
        mock_response.content = [mock_content]
        agent.ai_client.messages.create.return_value = mock_response
        agent.sdk_type = "anthropic"
        
        request = FormatterRequest(
            question="Analyze client tank distribution",
            sql="SELECT client, COUNT(*) FROM iso_tank GROUP BY client;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.formatting_method == "llm"
        assert "15 clients" in response.answer
        
        # Verify Anthropic API was called
        agent.ai_client.messages.create.assert_called_once()
    
    def test_unsupported_sdk_type(self, agent, large_result):
        """Test error handling for unsupported SDK type."""
        agent.sql_executor.execute_query.return_value = large_result
        agent.sdk_type = "unsupported"
        
        request = FormatterRequest(
            question="Test query",
            sql="SELECT * FROM iso_tank;"
        )
        
        response = agent.execute(request)
        
        # Should fall back to template formatting
        assert response.success is True
        assert response.formatting_method == "llm"  # Attempted LLM but failed
    
    # Integration tests - Full workflow
    
    def test_full_workflow_template_based(self, agent, sample_request, count_result):
        """Test full workflow with template-based formatting."""
        agent.sql_executor.execute_query.return_value = count_result
        
        response = agent.execute(sample_request)
        
        assert response.success is True
        assert response.answer == "The answer is 47."
        assert response.sql == sample_request.sql
        assert response.rows_count == 1
        assert response.execution_time > 0
        assert response.formatting_method == "template"
        assert response.confidence == 1.0
        assert response.metadata["original_question"] == sample_request.question
        assert response.metadata["mcp_used"] is False
    
    def test_full_workflow_llm_based(self, agent, large_result):
        """Test full workflow with LLM-based formatting."""
        agent.sql_executor.execute_query.return_value = large_result
        
        # Mock AI response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Top clients analysis complete."
        agent.ai_client.chat.completions.create.return_value = mock_response
        agent.sdk_type = "openai_compatible"
        
        request = FormatterRequest(
            question="Analyze top clients",
            sql="SELECT client, COUNT(*) FROM iso_tank GROUP BY client ORDER BY COUNT(*) DESC;"
        )
        
        response = agent.execute(request)
        
        assert response.success is True
        assert response.formatting_method == "llm"
        assert response.confidence == 0.9
        assert response.rows_count == 15
        assert "Top clients" in response.answer
    
    def test_format_rows_for_prompt_single_row(self, agent):
        """Test formatting rows for LLM prompt - single row."""
        rows = [{"tank_number": "T001", "status": "IN"}]
        columns = ["tank_number", "status"]
        
        result = agent._format_rows_for_prompt(rows, columns)
        
        assert "tank_number: T001" in result
        assert "status: IN" in result
    
    def test_format_rows_for_prompt_multiple_rows(self, agent):
        """Test formatting rows for LLM prompt - multiple rows."""
        rows = [
            {"tank_number": "T001", "status": "IN"},
            {"tank_number": "T002", "status": "OUT"}
        ]
        columns = ["tank_number", "status"]
        
        result = agent._format_rows_for_prompt(rows, columns)
        
        assert "tank_number | status" in result
        assert "T001 | IN" in result
        assert "T002 | OUT" in result
    
    def test_format_rows_for_prompt_empty(self, agent):
        """Test formatting empty rows for LLM prompt."""
        result = agent._format_rows_for_prompt([], ["tank_number"])
        assert result == "(No rows)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])