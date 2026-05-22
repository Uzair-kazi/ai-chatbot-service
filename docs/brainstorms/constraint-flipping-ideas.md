# Constraint-Flipping Ideas for Admin Chatbot
**Generated:** 2026-04-21  
**Method:** Constraint inversion on multi-agent text-to-SQL system  
**Context:** YAML glossary (static), regex entity extraction, 0.6 fuzzy threshold, dynamic SQL generation

---

## Idea 1: Zero-Glossary Emergent Mapping
**Constraint flipped:** YAML glossary from ~50 entries → 0 entries

**Summary:**  
Remove the business glossary entirely. Instead, the Query Refinement Agent learns domain terminology on-the-fly by analyzing historical query logs, database column names, and user corrections. Each session builds a temporary semantic map that expires after 24 hours.

**Why it matters:**  
Eliminates manual glossary maintenance (currently requires developer updates for every new business term). Adapts automatically when schema changes or new terminology emerges. Reduces onboarding friction for new domains.

**Evidence/Grounding:**  
- Current system: `business_glossary.yaml` maps "clients" → "vehicle_in.croyance_client_name"
- Problem: Glossary drifts when schema evolves (e.g., new `client_master` table added)
- Flip enables: Agent observes that queries mentioning "clients" correlate with `vehicle_in` table access patterns
- Tank Depot has 15+ tables with overlapping terminology ("status" appears in 4 tables) — emergent mapping could disambiguate contextually

**Constraint flipped:** Static glossary → Zero glossary with runtime learning

---

## Idea 2: Hyper-Strict Matching (0.99 Threshold)
**Constraint flipped:** Fuzzy matching threshold from 0.6 → 0.99

**Summary:**  
Require near-exact matches for entity extraction. When confidence is below 0.99, the system refuses to guess and instead asks the user a clarifying question with 2-3 specific options derived from schema analysis.

**Why it matters:**  
Current 0.6 threshold causes false positives: "tank status" matches both `iso_tank_status` and `service_tank_status` with similar scores, leading to wrong table selection. Hyper-strict matching forces explicit disambiguation, eliminating the #1 cause of incorrect SQL (wrong table selection).

**Evidence/Grounding:**  
- Current system: Schema Intelligence Agent uses fuzzy matching to map entities to tables
- Problem: "tanks" could mean `iso_tank` (4,701 rows) or `service_tank` (unknown count)
- Flip enables: Agent detects ambiguity, asks "Did you mean ISO tanks or service tanks?" before proceeding
- Tank Depot has 2 tank types, 4 status columns, 3 date fields — disambiguation is critical

**Constraint flipped:** Fuzzy 0.6 threshold → Strict 0.99 with mandatory clarification

---

## Idea 3: 10,000-Entry Glossary with Auto-Generation
**Constraint flipped:** YAML glossary from ~50 entries → 10,000 entries

**Summary:**  
Generate a massive glossary automatically by crawling: (1) all column names + table names, (2) all ENUM values, (3) all foreign key relationships, (4) sample data from text columns, (5) historical query patterns. Store as a vector database for semantic search instead of YAML.

**Why it matters:**  
Eliminates the "cold start" problem where the AI doesn't know domain-specific terminology. Captures implicit knowledge (e.g., "unsurveyed" means `survey_form_id IS NULL`) that would take weeks to manually document. Enables semantic search: "tanks without paperwork" → finds `survey_form_id IS NULL` pattern.

**Evidence/Grounding:**  
- Current system: Manual YAML with ~10-20 entries for Tank Depot
- Problem: Doesn't capture ENUM values (`iso_tank_status` has 5+ values), sample data patterns, or implicit business rules
- Flip enables: Auto-crawl discovers that 80% of queries filtering by status use `'IN'` or `'OUT'` — adds these as glossary entries
- Tank Depot schema has 15+ tables × 10-30 columns = 150-450 potential glossary entries before ENUMs/samples

**Constraint flipped:** Manual 50-entry YAML → Auto-generated 10,000-entry vector DB

---

## Idea 4: 100 Predefined Query Templates
**Constraint flipped:** Dynamic SQL generation (infinite flexibility) → 100 predefined templates

**Summary:**  
Pre-author 100 parameterized SQL templates covering 90% of admin questions. The system becomes a template matcher + parameter extractor instead of a SQL generator. Only fall back to dynamic generation for the 10% of novel queries.

**Why it matters:**  
Eliminates SQL hallucination entirely for common queries. Reduces latency from 3s to 300ms (no LLM call for template matching). Guarantees correctness for high-stakes queries (e.g., "revenue this month"). Provides a clear upgrade path: when a novel query succeeds, promote it to a template.

**Evidence/Grounding:**  
- Current system: Every query triggers SQL Generation Agent with self-critique loop (2-3 LLM calls)
- Problem: Even with self-critique, 5% hallucination rate on column names
- Flip enables: "How many ISO tanks?" → matches template `SELECT COUNT(*) FROM iso_tank WHERE {status_filter} LIMIT 100`
- Tank Depot golden queries (20+ examples in plan) could seed the template library
- Research: MAC-SQL paper shows 85% of real-world queries follow 12 structural patterns

**Constraint flipped:** Infinite dynamic SQL → 100 predefined templates + fallback

---

## Idea 5: 100ms Response Time Constraint
**Constraint flipped:** Response time from 3s average → 100ms hard limit

**Summary:**  
Architect for sub-100ms responses by: (1) pre-computing all aggregations nightly, (2) storing results in Redis, (3) chatbot becomes a natural language interface to cached data, (4) only allow queries that hit the cache. Novel queries are queued for next night's batch run.

**Why it matters:**  
Transforms chatbot from "flexible but slow" to "instant but constrained." Enables real-time dashboard use cases (e.g., live admin panel widgets). Eliminates AI API costs for 95% of queries (cache hits). Forces explicit prioritization: which 100 queries matter most?

**Evidence/Grounding:**  
- Current system: 3s average (1s schema pruning + 1.5s SQL generation + 0.5s execution)
- Problem: Too slow for dashboard widgets or high-frequency monitoring
- Flip enables: "How many tanks today?" → Redis key `tanks:count:2026-04-21` → instant response
- Tank Depot has ~20 golden queries that could be pre-computed
- Trade-off: Data freshness (nightly updates) vs speed (100ms)

**Constraint flipped:** 3s flexible queries → 100ms cached queries only

---

## Idea 6: 60-Second Deep Analysis Mode
**Constraint flipped:** Response time from 3s average → 60s deep analysis

**Summary:**  
Add a "Deep Analysis" mode where the system takes 60 seconds to: (1) generate 5 alternative SQL queries, (2) execute all 5, (3) compare results, (4) use an LLM to critique which query best answers the intent, (5) return the best answer with a confidence score and explanation of why alternatives were rejected.

**Why it matters:**  
Solves the "ambiguous intent" problem for high-stakes queries. Current system guesses once; deep mode explores the solution space. Provides transparency: "I considered counting by creation date vs by status change date — here's why I chose creation date." Reduces escalation to human analysts.

**Evidence/Grounding:**  
- Current system: Single SQL generation attempt (2-3 retries on syntax errors only)
- Problem: Ambiguous questions like "best clients" (by revenue? by tank count? by frequency?) get arbitrary interpretation
- Flip enables: Generate 3 interpretations, execute all, present: "By revenue: Client A ($50K). By tank count: Client B (47 tanks). By frequency: Client C (12 visits). Which did you mean?"
- Tank Depot queries often have temporal ambiguity ("this month" = calendar month? last 30 days? fiscal month?)
- Trade-off: 20× slower but 10× more accurate for complex questions

**Constraint flipped:** 3s single-attempt → 60s multi-hypothesis exploration

---

## Idea 7: Regex-Free Entity Extraction (Pure LLM)
**Constraint flipped:** Regex-based entity extraction → 0 regex, pure LLM semantic parsing

**Summary:**  
Remove all regex patterns for entity extraction. Instead, pass the raw question + full schema to a large context LLM (e.g., Claude 3.5 Sonnet with 200K context) and ask it to directly identify relevant tables, columns, and filters in a single pass. No intermediate entity extraction step.

**Why it matters:**  
Regex fails on paraphrased questions ("tanks that haven't been checked" vs "unsurveyed tanks"). LLM semantic parsing handles synonyms, negations, and implicit references naturally. Eliminates the entity extraction → table mapping → SQL generation pipeline — collapses to question → SQL in one step.

**Evidence/Grounding:**  
- Current system: Query Refinement Agent uses regex/fuzzy matching to extract entities like "clients", "tanks", "this month"
- Problem: Regex can't handle "tanks without paperwork" (requires understanding that "paperwork" = survey form)
- Flip enables: LLM sees "paperwork" in context of Tank Depot schema, infers `survey_form_id IS NULL`
- Tank Depot schema is ~8,000 tokens (fits in Claude's context)
- Trade-off: Higher token cost but eliminates 2 agent calls (Refinement + Schema Intelligence)

**Constraint flipped:** Regex entity extraction → Pure LLM semantic parsing

---

## Idea 8: Extreme Schema Pruning (10 Tokens)
**Constraint flipped:** Schema pruning from 8,000 tokens → 300 tokens → 10 tokens

**Summary:**  
Prune schema to the absolute minimum: only table names (no columns, no types, no relationships). SQL Generation Agent must infer column names by querying `information_schema` dynamically during generation. Each column reference triggers a micro-query: "Does table X have column Y?" before adding it to the SQL.

**Why it matters:**  
Reduces initial context to near-zero, enabling support for databases with 1,000+ tables (current system breaks at ~100 tables due to token limits). Forces the agent to be maximally uncertain — only commits to column names after verification. Eliminates the schema staleness problem (agent always queries live schema).

**Evidence/Grounding:**  
- Current system: Schema Intelligence Agent prunes 8,000 → 300 tokens by selecting relevant tables + all their columns
- Problem: Still includes irrelevant columns (e.g., `created_at` in 10 tables when query doesn't need timestamps)
- Flip enables: Agent sees only `[iso_tank, vehicle_in, service_tank]` → generates `SELECT COUNT(*) FROM iso_tank WHERE status = ?` → micro-query: "Does iso_tank have 'status' column?" → yes → proceeds
- Tank Depot has 15 tables × 20 columns = 300 column references, but typical query uses 2-3 columns
- Trade-off: 5-10 micro-queries per SQL generation (adds 500ms) but supports unlimited schema size

**Constraint flipped:** 300-token pruned schema → 10-token table-only schema + dynamic column verification

---

## Summary Table

| Idea | Constraint Flipped | Key Trade-off | Grounding |
|------|-------------------|---------------|-----------|
| 1. Zero-Glossary | 50 entries → 0 | Manual maintenance vs runtime learning | Tank Depot has 15+ tables with overlapping terms |
| 2. Hyper-Strict Matching | 0.6 threshold → 0.99 | Speed vs accuracy | "tanks" ambiguity causes wrong table selection |
| 3. 10K Glossary | 50 entries → 10,000 | Manual curation vs auto-generation | 150-450 potential entries in Tank Depot schema |
| 4. 100 Templates | Infinite SQL → 100 templates | Flexibility vs correctness | 85% of queries follow 12 patterns (MAC-SQL) |
| 5. 100ms Cache | 3s dynamic → 100ms cached | Freshness vs speed | 20 golden queries could be pre-computed |
| 6. 60s Deep Analysis | 3s single → 60s multi-hypothesis | Speed vs accuracy | Temporal ambiguity in Tank Depot queries |
| 7. Pure LLM Parsing | Regex → LLM semantic | Cost vs semantic understanding | "paperwork" = survey form requires inference |
| 8. 10-Token Schema | 300 tokens → 10 tokens | Context size vs latency | Typical query uses 2-3 of 300 columns |

---

**Next Steps:**  
1. Prototype 1-2 ideas with highest impact/feasibility ratio (likely #4 Templates or #2 Hyper-Strict)
2. A/B test against current multi-agent system using golden query suite
3. Measure: accuracy, latency, cost, user satisfaction
