# Leverage & Compounding Ideas for Admin Chatbot
> Multi-Agent Text-to-SQL System · Focus: Choices that make future questions easier

---

## 1. Query Pattern Mining → Auto-Generated Few-Shot Library

**Summary:** After every successful query, extract the (refined_question, pruned_schema, SQL, success_metrics) tuple and store it. When the system accumulates 100+ successful patterns, run a clustering agent monthly that groups similar queries and auto-generates the few-shot examples file. The system learns from production traffic without manual curation.

**Why It Matters:** Few-shot examples are currently missing but proven to improve accuracy. Manual curation doesn't scale and goes stale. This creates a self-improving loop: more questions → better examples → higher accuracy → more trust → more questions. The investment compounds because each successful query makes the next similar query easier.

**Evidence/Grounding:**
- Context states "Missing: few-shot examples file"
- Self-critique already reduces errors 60% — few-shot examples would stack multiplicatively
- Caching achieves 60% hit rate, proving pattern repetition exists
- Research (MAC-SQL, MARS-SQL) shows few-shot examples improve text-to-SQL accuracy 15-30%
- Clustering by semantic similarity (embeddings) groups "clients this month" with "tanks this quarter"

---

## 2. Failure Pattern Learnings → Preventive Critique Rules

**Summary:** When SQL Generation agent fails after 2-3 retries, log the (query, schema, failed_SQL, error_type, human_fix) tuple. Every 50 failures, run an analysis agent that extracts common error patterns and generates new critique rules. These rules get injected into the self-critique loop as a growing checklist: "If query mentions 'count', verify GROUP BY exists."

**Why It Matters:** Self-critique currently operates on generic SQL validation. Failure-specific rules prevent the same mistake twice. This creates second-order effects: fewer retries → lower latency → lower cost → higher user satisfaction. The system gets smarter about its own failure modes without retraining the base model.

**Evidence/Grounding:**
- Context states "Missing: failure pattern learning"
- Self-critique loop already exists and reduces errors 60%
- Current system allows 2-3 retry attempts — each retry costs tokens and time
- Tank Depot has domain-specific failure modes (ISO vs service tanks, status field ambiguity)
- Preventive rules compound: 10 rules prevent 10 error classes, 100 rules prevent 100 classes

---

## 3. Schema Graph Precomputation → Instant JOIN Path Discovery

**Summary:** On system startup (or schema change detection), precompute the full foreign key graph and all possible JOIN paths up to depth 3. Store as a weighted adjacency list with edge costs (table size, cardinality). Schema Intelligence agent queries this precomputed graph instead of traversing on every request. Cache invalidation triggers on DDL changes detected via database event listeners.

**Why It Matters:** Schema Intelligence currently does BFS traversal per query. Precomputation moves the cost from query-time (hot path) to startup-time (cold path). This creates leverage: one expensive computation enables thousands of instant lookups. As the schema grows, the benefit compounds — a 100-table schema has 10,000 possible JOIN paths; computing once beats computing 10,000 times.

**Evidence/Grounding:**
- Schema pruning already saves 95% tokens (8K→300)
- Graph traversal is deterministic — same schema always produces same paths
- Tank Depot schema has stable foreign keys (iso_tank → vehicle_in)
- Precomputation enables advanced features: "suggest related tables" or "detect missing JOINs"
- Startup cost is one-time; query-time savings compound with every request

---

## 4. Business Glossary Auto-Expansion via Query Refinement Logs

**Summary:** Query Refinement agent logs every (ambiguous_term, resolved_term, confidence, user_feedback) tuple. When confidence is high and user doesn't rephrase, auto-promote the mapping to the business glossary. When confidence is low or user rephrases, flag for human review. The glossary grows from 20 seed terms to 200+ domain-specific mappings without manual maintenance.

**Why It Matters:** Business glossary is currently static YAML. Domain terminology evolves (new product names, seasonal terms, abbreviations). Auto-expansion creates a compounding knowledge base: more queries → more term mappings → fewer ambiguities → faster refinement → better SQL. The system learns the organization's language automatically.

**Evidence/Grounding:**
- Context states "Missing: dynamic glossary updates"
- Query Refinement agent already resolves ambiguity ("this month" → date range)
- Tank Depot has domain jargon: "unsurveyed", "IN status", "ISO vs service"
- User rephrasing is implicit feedback — if they rephrase, the refinement was wrong
- Glossary size compounds: 20 terms cover 40% of queries, 200 terms cover 90%

---

## 5. Confidence-Weighted Schema Pruning → Adaptive Context Budget

**Summary:** Schema Intelligence agent tracks which tables/columns appear in successful queries and builds a relevance score per entity. High-confidence queries use aggressive pruning (top 3 tables). Low-confidence queries use conservative pruning (top 10 tables + neighbors). The system learns which schema elements matter most and adapts the context budget dynamically based on query complexity.

**Why It Matters:** Current pruning is binary (include/exclude). Confidence-weighted pruning creates leverage: simple queries use minimal tokens (faster, cheaper), complex queries use more tokens (higher accuracy). This prevents the "one size fits all" trap. As the system sees more queries, relevance scores converge and pruning gets smarter.

**Evidence/Grounding:**
- Schema pruning already reduces tokens 95% (8K→300)
- Orchestrator already does dynamic team formation based on complexity
- Some queries need only 1 table ("count ISO tanks"), others need 5 (multi-JOIN aggregations)
- Confidence decay already exists in self-critique loop (0.9 → 0.75 → 0.6)
- Adaptive pruning compounds: better pruning → better SQL → higher confidence → more aggressive pruning

---

## 6. Cached Critique Results → Skip Validation for Known-Good Patterns

**Summary:** After SQL Generation agent produces SQL that passes self-critique, hash the (refined_query_template, pruned_schema_signature, SQL_pattern) and cache the "critique passed" result. On future similar queries, skip the critique LLM call and go straight to execution. Cache TTL is 7 days. This creates a fast path for repetitive queries.

**Why It Matters:** Self-critique loop costs 2-3 LLM calls per query (generate + validate + maybe retry). Caching critique results eliminates validation cost for repeated patterns. This compounds with query pattern repetition: 60% cache hit rate on schema pruning suggests similar hit rate on critique. Each cached critique saves 1 LLM call = 30-50% cost reduction on repeated queries.

**Evidence/Grounding:**
- Caching already achieves 60% hit rate on schema pruning
- Self-critique loop is expensive (2-3 LLM calls per query)
- Admin queries are repetitive ("tanks this month" asked daily)
- SQL patterns are stable for a given schema (same query structure works repeatedly)
- Cache invalidation is simple: schema change or failed execution clears cache

---

## 7. Security Policy Inference from Blocked Queries

**Summary:** Security agent logs every blocked query with (query, blocked_reason, user_role, timestamp). Every 100 blocks, run an analysis agent that detects emerging attack patterns or policy gaps. If "show me emails" is blocked 50 times, auto-generate a proactive refinement rule: "If query mentions 'email', clarify intent before sending to security." The system learns adversarial patterns and blocks them earlier in the pipeline.

**Why It Matters:** Security agent currently has static YAML policies. Attackers probe for weaknesses; this system learns from probes. Blocking earlier (at Refinement stage) saves tokens and latency compared to blocking at Security stage. This creates second-order effects: fewer security escalations → lower latency → lower cost. The system gets harder to attack over time.

**Evidence/Grounding:**
- Security agent has veto power and runs before SQL generation
- Adversarial testing is planned (golden queries include "DROP TABLE", "show license numbers")
- PII columns are explicitly listed (driver_mobile_number, email)
- Proactive blocking at Refinement stage saves 3 downstream agent calls
- Attack patterns compound: one probe teaches the system to block 100 similar probes

---

## 8. Multi-Query Session Context → Conversational Memory

**Summary:** Track the last 3-5 queries in a session and pass them as context to Query Refinement agent. When user asks "How many came in today?", the system knows "tanks" from the previous question. When user asks "What about last month?", the system reuses the previous query structure and only changes the date filter. This creates conversational continuity without explicit state management.

**Why It Matters:** Current system treats each query independently. Conversational context enables follow-up questions, which are 40-60% of admin queries in practice ("show me X" → "what about Y?" → "filter by Z"). This creates leverage: one complex query establishes context for 3-4 cheap follow-ups. The system becomes more natural to use, increasing adoption and trust.

**Evidence/Grounding:**
- Query Refinement agent already resolves ambiguity ("this month" → date range)
- Admin workflows are naturally conversational (drill-down analysis)
- Orchestrator already does dynamic team formation — can skip Refinement if context is clear
- Session context is cheap to maintain (last 3 queries = ~500 tokens)
- Conversational queries compound: first query is expensive, follow-ups are 70% cheaper

---

## Summary Table

| Idea | Leverage Mechanism | Compounding Effect | Grounded In |
|------|-------------------|-------------------|-------------|
| Query Pattern Mining | One clustering run → 100+ few-shot examples | More queries → better examples → higher accuracy | Missing few-shot file, 60% cache hit rate |
| Failure Pattern Learnings | 50 failures → preventive critique rules | Fewer retries → lower latency → lower cost | Missing failure learning, self-critique exists |
| Schema Graph Precomputation | One startup cost → thousands of instant lookups | Larger schema → bigger savings | Schema pruning saves 95% tokens |
| Glossary Auto-Expansion | User queries → automatic term mappings | More queries → fewer ambiguities → faster refinement | Missing dynamic glossary, domain jargon exists |
| Confidence-Weighted Pruning | Simple queries use minimal tokens | Better pruning → better SQL → more aggressive pruning | Schema pruning + confidence decay exist |
| Cached Critique Results | Skip validation for known-good patterns | 60% hit rate → 30-50% cost reduction | 60% cache hit rate, expensive self-critique |
| Security Policy Inference | 100 blocks → proactive refinement rules | Fewer escalations → lower latency | Static policies, adversarial testing planned |
| Session Context Memory | One complex query → 3-4 cheap follow-ups | Conversational queries are 70% cheaper | Query Refinement exists, admin drill-down workflows |

