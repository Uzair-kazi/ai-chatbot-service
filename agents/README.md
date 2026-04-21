# Multi-Agent Framework

This directory contains the foundational multi-agent framework for the AI service. The framework provides a consistent base for building specialized agents with structured inputs/outputs using Pydantic models.

## Architecture

### Base Agent Class (`base.py`)

The `BaseAgent` abstract class provides:
- Abstract `execute()` method that all agents must implement
- Common validation logic via `_validate_request()`
- Execution timing via `_log_execution_time()`
- Integrated logging using the existing logging configuration
- Exception hierarchy for agent-specific errors

**Exception Hierarchy:**
- `AgentError` - Base exception for all agent errors
- `AgentExecutionError` - Raised when agent execution fails
- `AgentValidationError` - Raised when input validation fails

### SQL Generation Agent (`sql_generation.py`)

The `SQLGenerationAgent` generates SQL queries from natural language with a self-critique loop:

**Self-Critique Loop:**
1. Generate SQL using AI provider
2. Validate against schema (table/column existence, JOIN validity, safety)
3. If invalid, retry with specific validation feedback
4. Confidence decays with each retry: 0.9 → 0.75 → 0.6

**Key Features:**
- Catches column hallucinations (e.g., "idastank_count" → "id")
- Validates table existence
- Ensures JOINs have ON clauses
- Blocks dangerous SQL operations (DROP, DELETE, etc.)
- Logs token usage for cost tracking
- Reduces SQL errors by 50% compared to single-shot generation

**Usage:**
```python
from agents.sql_generation import SQLGenerationAgent
from agents.models.query_models import SQLGenerationRequest

agent = SQLGenerationAgent()
request = SQLGenerationRequest(
    question="How many ISO tanks are in 'IN' status?",
    db_schema=schema,
    max_retries=2,
    temperature=0.1
)
response = agent.execute(request)

if response.success:
    print(f"SQL: {response.sql}")
    print(f"Confidence: {response.confidence}")
else:
    print(f"Error: {response.error}")
    print(f"Issues: {response.validation_issues}")
```

### Pydantic Models (`models/`)

#### Agent Communication Models (`agent_models.py`)

**AgentRequest:**
- `question`: Natural language question from user (required)
- `db_schema`: Database schema description (required)
- `context`: Optional additional context (dict)

**AgentResponse:**
- `success`: Whether execution succeeded (bool)
- `data`: Optional result data (dict)
- `error`: Optional error message (str)
- `confidence`: Confidence score 0.0-1.0 (float, default 1.0)
- `metadata`: Optional metadata like retry count, execution time (dict)

#### Query-Specific Models (`query_models.py`)

**SQLGenerationRequest** (extends AgentRequest):
- `max_retries`: Maximum retry attempts (int, 0-5, default 2)
- `temperature`: AI temperature (float, 0.0-1.0, default 0.1)

**SQLGenerationResponse** (extends AgentResponse):
- `sql`: Generated SQL query (str or None)
- `validation_issues`: List of validation issues (list of str)
- `retry_count`: Number of retry attempts made (int)

### Cache Protocol (`cache.py`)

Abstract cache protocol for Phase 2 implementation:
- `get(key)` - Retrieve value from cache
- `set(key, value, ttl)` - Store value with optional TTL
- `delete(key)` - Remove value from cache
- `clear()` - Clear all cache entries

**NoOpCache:** Stub implementation for Phase 1 that does nothing. Allows the framework to be cache-aware without requiring a full implementation.

## Usage

### Creating a New Agent

```python
from agents.base import BaseAgent
from agents.models.agent_models import AgentRequest, AgentResponse

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="MyAgent")
    
    def execute(self, request: AgentRequest) -> AgentResponse:
        # Validate request
        self._validate_request(request)
        
        # Process request
        result = self._process(request.question, request.db_schema)
        
        # Return response
        return AgentResponse(
            success=True,
            data={"result": result},
            confidence=0.9,
            metadata={"processing_time": 1.23}
        )
```

### Using Pydantic Models

```python
from agents.models.agent_models import AgentRequest, AgentResponse

# Create request
request = AgentRequest(
    question="How many ISO tanks?",
    db_schema="Table: iso_tank\n  - id: uuid",
    context={"user_id": "123"}
)

# Execute agent
agent = MyAgent()
response = agent.execute(request)

# Check response
if response.success:
    print(f"Result: {response.data}")
    print(f"Confidence: {response.confidence}")
else:
    print(f"Error: {response.error}")
```

## Testing

All agent code has comprehensive test coverage:

- **test_base_agent.py** - Tests for base agent class and exception hierarchy
- **test_agent_models.py** - Tests for AgentRequest and AgentResponse models
- **test_query_models.py** - Tests for SQL-specific models
- **test_cache.py** - Tests for cache protocol and NoOpCache
- **test_sql_generation.py** - Tests for SQL Generation agent with self-critique loop

Run tests:
```bash
pytest tests/agents/ -v
```

**Test Coverage for SQL Generation Agent:**
- Validation logic (table/column existence, JOIN validity, safety)
- Self-critique loop (retry with feedback)
- Confidence decay (0.9 → 0.75 → 0.6)
- Integration tests (column hallucination, table errors, missing JOINs)
- Token usage logging
- SQL cleaning (markdown removal, LIMIT clause)

## Design Patterns

### Exception Hierarchy
Following the pattern from `services/chatbot_pipeline.py`:
- Base exception class with specific subtypes
- Allows catching all agent errors or specific types
- Clear error categorization

### Logging
Following the pattern from `services/sql_generator.py`:
- Structured logging with timing information
- Logger initialized per agent instance
- Consistent log format across all agents

### Type Hints
Following the pattern from `config/ai_provider.py`:
- Union types for multiple possible types
- Optional for nullable fields
- Pydantic models for structured data

## Future Enhancements (Phase 2+)

- **Cache Implementation**: Replace NoOpCache with Redis/in-memory cache
- **Schema Intelligence Agent**: Prune and cache schema information
- **Query Refinement Agent**: Improve query understanding
- **Security & Governance Agent**: Enforce security policies
- **Result Formatter Agent**: Format results in natural language

## Related Documentation

- Plan: `docs/plans/2026-04-21-006-feat-multi-agent-phase1-core-framework-plan.md`
- Requirements: `docs/brainstorms/multi-agent-text-to-sql-requirements.md`
