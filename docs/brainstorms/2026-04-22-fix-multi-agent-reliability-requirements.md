---
date: 2026-04-22
topic: fix-multi-agent-text-to-sql-reliability
status: draft
---

# Fix Multi-Agent Text-to-SQL Reliability

## Problem Statement

The admin chatbot's multi-agent text-to-SQL system is unreliable across all AI models (DeepSeek, Groq, Gemini). Admins should be able to ask **any question** about their data in natural language and get accurate answers, but currently the system generates incorrect SQL with hallucinated table names.

**Example Failure:**
- Admin asks: "How many ISO tanks are currently in?"
- System generates: `SELECT COUNT(*) FROM iso_tanks LIMIT 100;`
- Actual table name: `iso_tank` (singular, not plural)
- Result: SQL error, no answer

**Root Cause:** Schema Intelligence Agent is not pruning the schema effectively. The SQL Generation Agent receives 32,524 characters of schema (50+ tables) instead of 300 characters (2-3 relevant tables), causing it to hallucinate table names.

## User Goal

**Primary:** Admin can chat with AI and ask **anything** about the database - "How many tanks currently in?", "Which clients have the most tanks?", "Show me unsurveyed tanks from last month" - and get accurate answers.

**Non-Goal:** Limiting questions to predefined templates or hardcoded queries. The system must remain fully dynamic and conversational.

## Current Architecture

Multi-agent pipeline (6 agents):
1. **Orchestrator** - Routes queries and forms dynamic teams
2. **Query Refinement** - Resolves ambiguity (temporal terms, business terminology)
3. **Security & Governance** - RBAC, PII blocking, read-only enforcement
4. **Schema Intelligence** - Should prune schema 8K→300 tokens (NOT WORKING)
5. **SQL Generation** - Generates SQL with self-critique loop
6. **Result Formatter** - Natural language answers

**Files:**
- `agents/schema_intelligence.py` - Schema pruning agent (broken)
- `agents/sql_generation.py` - SQL generation with few-shot examples
- `services/schema.py` - Database schema introspection (32K chars)
- `config/ai_provider.py` - Swappable AI models

## Success Criteria

### Must Have (P0)
1. **95%+ SQL accuracy** - Generates correct table/column names for realistic admin questions
2. **Schema pruning works** - Reduces 32K schema → 300 tokens (2-3 relevant tables only)
3. **Validation layer** - Catches hallucinated table/column names before execution
4. **Works across models** - Reliable with DeepSeek, Groq, Gemini, GPT, Claude

### Should Have (P1)
5. **Conversational context** - Remembers last 3-5 questions for follow-ups
6. **Self-healing** - Automatically retries with better prompts when validation fails
7. **Confidence scoring** - Returns confidence level with each answer

### Nice to Have (P2)
8. **Query pattern learning** - Learns from successful queries to improve over time
9. **Clarification questions** - Asks user when query is ambiguous
10. **Performance** - <3s response time at p95

## Constraints

- **Must remain dynamic** - No hardcoded SQL templates or predefined queries
- **Read-only database** - Security layer must prevent all write operations
- **Swappable AI models** - Solution must work with any OpenAI-compatible or Anthropic model
- **Production quality** - Bulletproof reliability for real admin users

## Approach: Fix the Multi-Agent Pipeline

### Phase 1: Fix Schema Intelligence Agent (Highest Priority)
**Problem:** Agent extracts entities but doesn't effectively prune schema
**Solution:** 
- Improve entity extraction (handle multi-word phrases like "ISO tanks")
- Better fuzzy matching (embeddings instead of Levenshtein distance)
- Aggressive pruning (only include matched tables + 1-hop foreign keys)
- Validate pruning output (ensure <500 tokens)

**Expected Impact:** SQL agent sees `iso_tank, vehicle_in` (300 chars) instead of 50 tables (32K chars)

### Phase 2: Add SQL Validation Layer
**Problem:** No validation before execution - hallucinations cause SQL errors
**Solution:**
- New validation step after SQL generation
- Check all table names exist in schema
- Check all column names exist in selected tables
- Auto-retry with error feedback if validation fails

**Expected Impact:** Catch 100% of hallucinations before they cause errors

### Phase 3: Improve SQL Generation Prompts
**Problem:** Prompts don't emphasize exact table names strongly enough
**Solution:**
- Add explicit table name list to prompt
- Strengthen few-shot examples
- Add negative examples (common mistakes to avoid)

**Expected Impact:** Reduce hallucination rate by 50%

### Phase 4: Add Conversational Context (Optional)
**Problem:** Each query is independent - no follow-up capability
**Solution:**
- Track last 3-5 queries in session
- Pass context to Query Refinement agent
- Enable follow-ups like "What about last month?" or "Show me more details"

**Expected Impact:** Better UX, 40-60% of queries are follow-ups

## Out of Scope

- Hardcoded SQL templates or predefined queries
- Switching to tool-based architecture (LangChain style)
- Complete architectural redesign
- Frontend UI changes
- Database schema changes
- Adding new AI models beyond existing swappable config

## Technical Decisions

### Schema Pruning Strategy
**Decision:** Use embedding-based entity matching + graph traversal
**Rationale:** More robust than regex + fuzzy matching, handles synonyms and multi-word phrases
**Alternative considered:** Pure LLM semantic parsing (rejected: higher cost, no proven benefit)

### Validation Approach
**Decision:** Pre-execution validation against schema
**Rationale:** Catches errors before they happen, provides clear feedback for retry
**Alternative considered:** Post-execution error handling (rejected: poor UX, wastes DB queries)

### Model Choice
**Decision:** Keep swappable config, test with multiple models
**Rationale:** No single model is perfect, flexibility is valuable
**Alternative considered:** Mandate specific model (rejected: vendor lock-in, cost constraints)

## Dependencies

- Existing multi-agent architecture (agents/, services/)
- Database schema introspection (services/schema.py)
- AI provider abstraction (config/ai_provider.py)
- Business glossary (agents/config/business_glossary.yaml)

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Schema Intelligence still doesn't prune effectively | High | Add fallback: if pruning fails, use top 5 most common tables |
| Validation is too strict, blocks valid queries | Medium | Tune validation rules, add override for admin users |
| Performance degrades with validation layer | Low | Optimize validation (cache schema metadata), run in parallel |
| Edge cases still fail (complex JOINs, subqueries) | Medium | Comprehensive test suite, gradual rollout with monitoring |

## Testing Strategy

1. **Golden query suite** - 50+ realistic admin questions covering all domains
2. **Adversarial testing** - Intentionally ambiguous questions, edge cases
3. **Cross-model testing** - Run same queries on DeepSeek, Groq, Gemini, GPT
4. **Schema change testing** - Verify system adapts when tables/columns are renamed
5. **Performance testing** - Measure latency at p50, p95, p99

## Success Metrics

- **SQL accuracy:** 95%+ correct table/column names (currently ~50%)
- **Schema pruning:** <500 tokens per query (currently 32K)
- **Validation catch rate:** 100% of hallucinations caught before execution
- **Response time:** <3s at p95 (currently ~5s)
- **User satisfaction:** Admins trust the system enough to use it daily

## Next Steps

1. **Review this document** - Confirm requirements are complete
2. **Create implementation plan** - Break down into tasks with estimates
3. **Set up testing infrastructure** - Golden query suite, test harness
4. **Implement Phase 1** - Fix Schema Intelligence Agent
5. **Iterate** - Test, measure, improve

---

## Appendix: Debugging Findings

**Test Results (2026-04-22):**
- Model: DeepSeek-chat
- Question: "How many ISO tanks are there?"
- Generated SQL: `SELECT COUNT(*) FROM iso_tanks LIMIT 100;`
- Actual table: `iso_tank` (singular)
- Schema size: 32,524 characters
- Issue: Model adds 's' for plural, doesn't use exact table name from schema

**Models Tested:**
- DeepSeek: Hallucinated `iso_tanks`
- Groq: Same issue (per user report)
- Gemini: Same issue (per user report)
- Conclusion: Problem is architectural, not model-specific

**Schema Intelligence Agent Status:**
- Code exists: `agents/schema_intelligence.py`
- Supposed to prune 8K→300 tokens (95% reduction)
- Currently not working effectively
- Needs investigation and fixes
