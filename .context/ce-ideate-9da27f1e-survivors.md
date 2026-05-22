# Survivor Ideas - Admin Chatbot Question Understanding
**Generated:** 2026-04-22
**Run ID:** 9da27f1e
**Focus:** Improving multi-agent text-to-SQL system

## Grounding Context
- **Project:** Python FastAPI multi-agent text-to-SQL (6 agents: Orchestrator, Query Refinement, Security, Schema Intelligence, SQL Generation, Result Formatter)
- **Pain points:** Client names like "SRF FCB" not recognized, temporal terms like "till now" missing, wrong table selection when ambiguous
- **Leverage points:** Business glossary extension, Query Refinement enhancement, Schema Intelligence tuning, missing few-shot examples
- **External research:** Hybrid retrieval (BM25 + embeddings), living glossaries, HI-SQL historical hints, self-driven exploration

## Ranked Survivors

### 1. Hybrid Static/Dynamic SQL (90% confidence, Medium complexity)
Pre-compiled queries for 20 common questions, vector-matched, fallback to dynamic generation

### 2. Embedding-Based Entity Linking (85% confidence, Low complexity)
Replace fuzzy matching with vector embeddings for client names

### 3. Query Pattern Mining → Few-Shot Library (80% confidence, Medium complexity)
Auto-generate few-shot examples from successful production queries

### 4. Temporal Metadata Injection (90% confidence, Low complexity)
Preprocess queries with current date/time context

### 5. Schema Graph Precomputation (85% confidence, Medium complexity)
Precompute JOIN paths at deployment, not per-query

### 6. Confidence-Gated Clarification (75% confidence, Medium complexity)
Ask multiple-choice questions when confidence <0.7

### 7. Session Context Memory (80% confidence, Low complexity)
Track last 3-5 queries for conversational follow-ups

## Rejection Summary
41 ideas rejected for: too risky (cold-start), too rigid (hyper-strict matching), overkill (10K glossary), too slow (60s analysis), redundant (covered by survivors), pain points without solutions, analogies that don't transfer, already implemented features.
