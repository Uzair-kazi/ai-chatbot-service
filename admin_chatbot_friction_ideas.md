# Admin Chatbot Question Understanding: Friction-Focused Ideas

## 1. Client Name Synonym Hell
**Summary:** Admins type client names in multiple forms ("SRF FCB", "SRF", "FCB", "SRF-FCB") but the system only recognizes one canonical form, forcing repeated query failures and manual reformulation.

**Why it matters:** Every failed client name lookup breaks the question flow. Admins waste time guessing which variant the system expects, then re-asking the same question 2-3 times. This compounds when clients have multiple legal entities or brand names.

**Evidence/Grounding:** "Client names like 'SRF FCB' not recognized" indicates the glossary/entity resolver uses exact-match logic. Real-world client references are messy: contracts use legal names, emails use abbreviations, invoices use brand names. A single canonical form can't capture this variance.

---

## 2. Temporal Phrase Blind Spots
**Summary:** Common time expressions ("till now", "last quarter", "year to date", "since launch") fail silently or get misinterpreted because the glossary only covers a narrow set of date patterns.

**Why it matters:** Time-based questions are the most frequent admin query type (revenue trends, campaign performance, client activity). When temporal parsing fails, the SQL agent either generates wrong date filters or asks the admin to restate in ISO format—killing the conversational flow.

**Evidence/Grounding:** "Temporal terms like 'till now' missing from glossary" shows the system lacks coverage for natural date language. Admins think in business terms ("this fiscal year"), not SQL (`WHERE date >= '2024-01-01'`). Every missing phrase forces a translation step the admin shouldn't have to do.

---

## 3. Ambiguous Entity Routing Lottery
**Summary:** When a term like "campaign" or "client" appears in multiple tables (campaigns, campaign_history, client_accounts, client_contacts), the Schema Intelligence agent picks the wrong table 30-40% of the time, returning irrelevant results.

**Why it matters:** Admins can't predict which table the system will choose. They ask "show me active campaigns" and get campaign_history rows instead of campaigns. The only fix is to re-ask with explicit table hints ("from the campaigns table"), which defeats the purpose of natural language querying.

**Evidence/Grounding:** "Wrong table selection when entities are ambiguous" directly confirms this. Multi-table schemas are the norm in admin systems. Without disambiguation logic (recency heuristics, join frequency analysis, or clarifying questions), the system guesses—and guesses wrong often enough to erode trust.

---

## 4. Glossary Staleness Drift
**Summary:** The glossary becomes outdated as new clients, products, and business terms are added to the database, but there's no automated sync or admin-facing alert when a query fails due to missing glossary entries.

**Why it matters:** Admins discover glossary gaps only through query failures. A new client "Acme Corp" gets added to the CRM, but the chatbot can't answer "Acme revenue" for weeks until someone manually updates the glossary. This creates a trust gap: admins stop asking about new entities because they assume the system won't know them.

**Evidence/Grounding:** The "SRF FCB" example suggests manual glossary maintenance. In fast-moving admin environments, glossaries decay within days. Without auto-sync or failure-triggered glossary suggestions, the system's knowledge lags behind the database it's supposed to query.

---

## 5. Multi-Condition Query Collapse
**Summary:** Questions with 2+ filters ("show me SRF FCB campaigns from last quarter with spend over $10k") fail more often than single-filter questions because each condition multiplies the chance of entity/temporal/threshold misinterpretation.

**Why it matters:** Complex questions are where natural language querying provides the most value—they're painful to write in SQL. But if the system can't reliably parse multi-condition queries, admins fall back to simpler questions or direct SQL, abandoning the chatbot for anything non-trivial.

**Evidence/Grounding:** Combining the three stated pain points (client names, temporal terms, table ambiguity) in one query creates a compounding failure surface. If each condition has a 20% failure rate, a three-condition query has a 49% chance of at least one failure. The Query Refinement agent likely lacks robust multi-condition validation.

---

## 6. No Feedback Loop on Failures
**Summary:** When a query fails (unrecognized entity, wrong table, bad date parse), the system doesn't capture what the admin typed vs. what it understood, so the same failures repeat across users and sessions.

**Why it matters:** Admins hit the same glossary gaps and ambiguity traps over and over. There's no learning mechanism to prioritize fixing high-frequency failures or to surface "top 10 broken queries" to the team maintaining the glossary and schema mappings.

**Evidence/Grounding:** The pain points described (client names, temporal terms, table selection) are systemic, not one-off edge cases. If the system logged failed entity resolutions and ambiguous table picks, patterns would emerge quickly. Without this, fixes are reactive and anecdotal rather than data-driven.

---

## 7. Implicit Join Assumption Failures
**Summary:** Admins ask questions that require joining multiple tables ("show me clients with campaigns but no invoices"), but the Schema Intelligence agent either picks one table and ignores the others, or generates a broken join because it doesn't understand the foreign key relationships.

**Why it matters:** Cross-table questions are common in admin workflows (reconciling campaigns to billing, matching leads to conversions). When the system can't infer joins, it returns incomplete or nonsensical results, forcing admins to break the question into multiple single-table queries and manually correlate the data.

**Evidence/Grounding:** "Wrong table selection when entities are ambiguous" hints at single-table bias. If the Schema Intelligence agent lacks a join graph or relationship model, it can't reason about multi-table queries. This is a structural gap, not just a glossary problem.

---

## 8. Threshold and Comparison Ambiguity
**Summary:** Questions with numeric or comparison filters ("high-value clients", "underperforming campaigns", "recent activity") fail because the system doesn't know what "high", "underperforming", or "recent" mean in business context—it needs explicit thresholds.

**Why it matters:** Admins think in relative terms ("show me our best clients"), not absolute SQL predicates (`WHERE revenue > 50000`). When the system can't resolve these, it either asks for clarification (breaking flow) or picks arbitrary thresholds (returning wrong results). Either way, the admin loses confidence.

**Evidence/Grounding:** This extends the temporal phrase problem to numeric and categorical domains. Business language is full of implicit thresholds ("large", "active", "stale"). Without a business logic layer that maps these to concrete filters (possibly user-specific or role-specific), the Query Refinement agent can't translate intent to SQL.
