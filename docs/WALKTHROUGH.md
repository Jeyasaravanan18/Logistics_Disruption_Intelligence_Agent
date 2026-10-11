# Technical Walkthrough & Interview Guide

This guide explains the architecture, design tradeoffs, and operational mechanics of the **Logistics Disruption Intelligence System**, followed by 15 high-signal technical interview questions with concise, code-backed answers.

---

## 1. System Architecture Overview

The system is a production-grade multi-tenant freight monitoring backend. It correlates live weather and news anomalies across Indian transport corridors with active cargo shipments to quantify freight delays and trigger automated mitigation workflows.

### High-Level Component Layout
```
[ Next.js 14 Frontend (SaaS UI) ]
         │ (HTTP REST / Cookies / WebSockets)
         ▼
[ FastAPI Application Gateway (main.py) ]
    ├── Auth Router: HttpOnly Cookie Rotation & bcrypt ([routers/auth.py](file:///backend/routers/auth.py))
    ├── Shipments Router: Keyset Seek Pagination ([routers/shipments.py](file:///backend/routers/shipments.py))
    ├── Analytics Router: Relational Window Functions & Aggregates ([routers/analytics.py](file:///backend/routers/analytics.py))
    ├── Risk Router: SHA-256 Cache & LangGraph Trigger ([routers/risk_analysis.py](file:///backend/routers/risk_analysis.py))
    └── WebSocket: Real-time Pub/Sub Gateway with Fail-Fast Ping ([main.py](file:///backend/main.py))
         │
         ├──► [ PostgreSQL 16 (asyncpg + SQLAlchemy 2.0) ]
         │     ├── Shipments, Disruptions, Pipeline Runs
         │     ├── Risk Assessments & Recommendations
         │     └── Agent Telemetry Traces
         │
         ├──► [ Redis 7 (Caching & Pub/Sub) ]
         │     ├── SHA-256 Assessment Cache (TTL Expiry)
         │     ├── Circuit Breaker Distributed FSM State
         │     └── Real-time Channel: risk_updates
         │
         ├──► [ Celery 5.3 Background Worker ([celery_worker.py](file:///backend/celery_worker.py)) ]
         │     └── Periodic Tenant Fleet Monitoring
         │
         └──► [ LangGraph Orchestration Engine ([workflow/graph.py](file:///backend/workflow/graph.py)) ]
               ├── 1. plan: Dynamic collector & regional query generation
               ├── 2. collect_weather / collect_news: Tool calls & SQL content-hash dedup
               ├── 3. analyze: Structured Pydantic LLM analysis with 2x retry & rule fallback
               ├── 4. score: Deterministic Haversine corridor risk calculation
               ├── 5. review (conditional edge): Bounded review loop (N <= 2) on low confidence
               ├── 6. recommend (conditional edge): LLM batch guidance for at-risk shipments
               └── 7. persist_finish: Closes pipeline run & writes per-node agent_traces
```

---

## 2. Core Modules Explained

### A. Database Layer (`models.py`, `database.py`, `crud.py`)
- **Engine Abstraction:** Utilizes async SQLAlchemy 2.0 with `asyncpg` for PostgreSQL connection pooling and a transparent fallback to `sqlite+aiosqlite` for isolated unit tests or offline local development.
- **Relational Integrity:** Strict foreign keys with `ON DELETE CASCADE` on tenant users, `CHECK (score >= 0)`, and `CHECK (level IN ('HIGH', 'MEDIUM', 'LOW', 'SAFE'))`.
- **Deduplication:** Disruptions are deduplicated by a deterministic SHA-256 `content_hash` over `(type, subtype, location, coordinates, description[:50])` to prevent duplicate alerts.
- **Keyset Seek Pagination:** Replaces `OFFSET` pagination on the shipments table with B-tree seek indexing (`WHERE shipment_id > cursor ORDER BY shipment_id ASC LIMIT :limit`), maintaining $O(1)$ query complexity regardless of page depth.
- **Advanced SQL Analytics:**
  - **KPIs:** Aggregates risk levels using SQL `FILTER(WHERE level = 'HIGH')`.
  - **Trends:** Calculates deltas across consecutive pipeline runs per shipment in a single relational query using the `LAG(score, 1) OVER (PARTITION BY shipment_id ORDER BY finished_at)` window function.
  - **Corridor Ranking:** Identifies vulnerable routes by joining `shipments`, `risk_assessments`, and `disruptions` with `GROUP BY` and `HAVING COUNT(r.id) > 0`.

### B. Stateful Workflow Engine (`workflow/graph.py`, `workflow/state.py`, `workflow/nodes.py`)
- **Justification for Graph over Pipeline:** Instead of a procedural sequence of functions, LangGraph provides:
  1. **Typed State:** Every step receives and modifies an immutable `WorkflowState` model.
  2. **Bounded Review Loop:** If more than 30% of analyzed disruption signals have low confidence (< 0.60), a conditional edge re-executes collection/analysis with refined search queries up to $N=2$ times.
  3. **Conditional Execution Branching:** The recommendation generator is computationally expensive and rate-limited. The graph conditionally executes it only for shipments facing `HIGH` or `MEDIUM` risk, while nominal `SAFE` shipments bypass the LLM.
  4. **Observable Telemetry:** Every node execution writes an `AgentTrace` record to PostgreSQL capturing elapsed time, token estimates, input hash, and fallback flags.

### C. Resilience & Reliability (`resilience/circuit_breaker.py`, `resilience/cache.py`)
- **Canonical Circuit Breaker:** Implements a finite state machine (`CLOSED` -> `OPEN` -> `HALF_OPEN`). When upstream Gemini API calls encounter rate limit errors (HTTP 429), it trips directly to `OPEN` without exhausting quota. During `OPEN`, requests fail fast to deterministic rule baselines without network delays. After a 30s cooldown, it enters `HALF_OPEN` to test upstream health.
- **SHA-256 Assessment Cache:** Derives cache keys from `sha256(owner_id + shipments_version + sorted_disruption_content_hashes)`. Because disruption hashes are canonically sorted, ordering variations never cause cache misses. Stores payloads in Redis with in-memory TTL fallback.
- **Transparent Demo Mode:** If external API keys are omitted or networks fail, the collectors automatically read recorded payloads from `data/fixtures/` and tag records with `data_source: "demo_fixture"`, displaying a visible DEMO badge in the UI.

---

## 3. 15 Technical Interview Questions & Answers

### Q1: Why did you choose async SQLAlchemy 2.0 with asyncpg instead of Motor/MongoDB?
**Answer:** Freight logistics is inherently relational: shipments belong to tenant users, disruptions intersect transit corridors, and risk assessments associate specific shipments to disruptions. Relational constraints (`ON DELETE CASCADE`, unique compound indexes, and CHECK constraints) prevent orphaned or corrupt assessments. Furthermore, analytics like shipment risk trends across runs are computed orders of magnitude faster using SQL window functions (`LAG()`) and indexed 3-way joins than multi-stage document aggregations.

### Q2: How does keyset pagination work in this repository, and why is it superior to OFFSET pagination?
**Answer:** Implemented in [crud.py:L82-L115](file:///backend/crud.py#L82-L115). Standard `OFFSET 10000` forces the database to read, sort, and discard 10,000 index entries ($O(N)$). Keyset seek pagination uses the primary key index directly (`WHERE shipment_id > :cursor ORDER BY shipment_id ASC LIMIT 50`), allowing the database engine to perform an $O(1)$ B-tree seek directly to the next page boundary.

### Q3: Why is LangGraph justified here rather than four sequential Python functions?
**Answer:** Documented in [docs/adr-langgraph.md](file:///docs/adr-langgraph.md). Sequential functions cannot handle conditional branching or feedback loops cleanly. In our workflow, we have a **bounded review loop** ($N \le 2$) that re-queries the collector when analysis confidence is low, and a **conditional branch** that skips LLM recommendations for nominal shipments. LangGraph provides typed state transitions, cycle bounds, and per-node telemetry persistence without messy procedural spaghetti.

### Q4: How do you prevent infinite loops in the LangGraph workflow?
**Answer:** In [workflow/state.py](file:///backend/workflow/state.py) and [workflow/graph.py](file:///backend/workflow/graph.py), the `review_loop_count` is tracked in the typed state. The conditional edge checks `state["review_loop_count"] < 2`. Once the loop counter reaches 2, the edge deterministically forces transition to the `score` node, guaranteeing that execution terminates regardless of model output.

### Q5: How does the Circuit Breaker handle Google Gemini API rate limits (HTTP 429)?
**Answer:** In [resilience/circuit_breaker.py:L131-L148](file:///backend/resilience/circuit_breaker.py#L131-L148), when `record_failure(is_quota_error=True)` is called upon receiving HTTP 429, the breaker immediately trips to `OPEN` rather than waiting to hit the normal failure threshold. While `OPEN`, all subsequent calls fail fast within 0.01ms and fall back to rule-based templates, preserving network resources until the cooldown period expires.

### Q6: How do you test time-dependent circuit breaker transitions without flaky `time.sleep()` calls?
**Answer:** In [resilience/circuit_breaker.py](file:///backend/resilience/circuit_breaker.py#L43-L50) and [tests/test_resilience.py](file:///backend/tests/test_resilience.py#L30-L40), the `CircuitBreaker` accepts an injectable `clock` callable. In tests, we inject a `FakeClock` with an `.advance(seconds)` method. This allows deterministic, millisecond-fast time-travel testing of cooldowns and state transitions without sleeping.

### Q7: How does your SHA-256 caching ensure cache hits even if external disruptions arrive out of order?
**Answer:** In [resilience/cache.py:L35-L55](file:///backend/resilience/cache.py#L35-L55), before hashing, the list of disruption content hashes is canonically sorted: `sorted(disruption_hashes)`. If collector A returns items `[X, Y]` and collector B returns items `[Y, X]`, the serialized input is identical, generating the exact same SHA-256 digest and guaranteeing cache reuse.

### Q8: How is disruption deduplication handled across different data sources?
**Answer:** In [crud.py:L368-L417](file:///backend/crud.py#L368-L417), each incoming disruption is assigned a SHA-256 `content_hash` computed over its normalized attributes (`type:subtype:location:lat:lon:description[:50]`). The database table enforces `UNIQUE(content_hash)`. Before insertion, existing hashes are queried and duplicate inserts are skipped.

### Q9: How does the system handle demo environments where external API keys are not supplied?
**Answer:** In [services/weather_service.py](file:///backend/services/weather_service.py) and [services/news_service.py](file:///backend/services/news_service.py), when API keys are empty or set to defaults, the services gracefully load recorded payloads from `data/fixtures/` and tag each item with `data_source: "demo_fixture"`. The frontend inspects this flag and displays a clear `DEMO` badge in the feed, eliminating false claims about mock data while ensuring full system functionality.

### Q10: How does the risk calculation combine geospatial distance with shipment and disruption attributes?
**Answer:** In [services/geo_matcher.py:L122-L150](file:///backend/services/geo_matcher.py#L122-L150), great-circle Haversine distance is calculated between the disruption and shipment coordinates. The proximity factor is computed as $\max(0, 1 - \frac{\text{dist}}{\text{radius}})$. This factor scales the product of `severity_weight` (HIGH=3, MEDIUM=2, LOW=1) and `priority_weight` (CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1). If the score $\ge 4.5$, risk is HIGH; if $\ge 1.8$, MEDIUM; otherwise LOW.

### Q11: Why are JWT tokens delivered via HttpOnly cookies rather than LocalStorage?
**Answer:** In [routers/auth.py:L150-L165](file:///backend/routers/auth.py#L150-L165), tokens are set using `response.set_cookie(..., httponly=True, samesite="lax")`. Storing JWTs in browser LocalStorage exposes them to Cross-Site Scripting (XSS) extraction via malicious scripts. HttpOnly cookies prevent JavaScript access, mitigating token theft.

### Q12: How does refresh token rotation work, and how does it detect replay attacks?
**Answer:** In [routers/auth.py:L170-L210](file:///backend/routers/auth.py#L170-L210), when `/auth/refresh` is called, the database looks up the hashed token. If the token is found and not revoked, the current token is marked `revoked=True`, a new refresh token is generated, its SHA-256 hash is inserted, and new cookies are set. If an attacker attempts to reuse an old token, it will be found as revoked, triggering an immediate 401 Unauthorized.

### Q13: What happens to the WebSocket connection if the Redis broker goes offline?
**Answer:** In [main.py:L75-L100](file:///backend/main.py#L75-L100), upon accepting a WebSocket connection, the endpoint immediately performs an `await redis_client.ping()` with a 1-second timeout. If Redis is unreachable, it catches the exception and closes the socket immediately with code `1011` (Server Error) rather than hanging indefinitely.

### Q14: What measured database indexing improvements did you achieve?
**Answer:** Documented in [docs/performance.md](file:///docs/performance.md). On a PostgreSQL table seeded with 20,000 risk assessments:
- **Corridor Exposure Ranking:** Decreased query execution time from `129.70 ms` (sequential scan) to `87.72 ms` (index scan on `(run_id, shipment_id)`), achieving a **1.48x speedup**.
- **Shipment Risk Trends (LAG):** Decreased execution time from `39.02 ms` to `18.63 ms` using an index on `(owner_id, finished_at DESC)`, achieving a **2.09x speedup (52.3% reduction)**.

### Q15: How does your evaluation harness benchmark the rule baseline against the LLM?
**Answer:** Implemented in [eval/run_eval.py](file:///eval/run_eval.py) over 30 hand-labeled realistic news items. It measures type accuracy, severity agreement, first-try JSON validity, fallback rate, and p50/p95 latency. Results in [eval/results.md](file:///eval/results.md) demonstrate that while the rule baseline operates in 0.02ms with 83.3% accuracy, the LLM provides 100% type accuracy and 96.7% severity agreement, handling semantic nuances (e.g. multi-modal river ferry suspensions or port software backlogs) that keyword heuristics misclassify.
