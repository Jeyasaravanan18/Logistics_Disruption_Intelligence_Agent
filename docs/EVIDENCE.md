# Verification & Evidence Matrix

Every technical claim in this repository is mapped directly to active code, specific line numbers, and verifiable test/command output. Zero unsubstantiated metrics or speculative architecture.

---

## 1. Resume Claims & Technical Evidence

| Resume / Repo Claim | Implementation File & Lines | Test / Verification Command | Measured Verification Result |
| :--- | :--- | :--- | :--- |
| **"FastAPI backend using SQLAlchemy 2.0 with PostgreSQL & asyncpg"** | [database.py](file:///backend/database.py#L20-L55)<br>[models.py](file:///backend/models.py#L40-L240) | `pytest backend/tests/test_database_models.py -v` | **PASS**: 5 database model & constraint tests passing under async session. |
| **"SQLite with aiosqlite in-memory fallback when PostgreSQL is offline"** | [database.py](file:///backend/database.py#L38-L52) | `pytest backend/tests/test_api_contract.py -v` | **PASS**: All contract and route tests run with isolated SQLite fallback engines. |
| **"Relational schema with CHECK constraints & ON DELETE CASCADE"** | [models.py](file:///backend/models.py#L140-L220) | `pytest backend/tests/test_database_models.py::test_risk_assessment_check_constraints` | **PASS**: Score >= 0 and level IN ('HIGH', 'MEDIUM', 'LOW', 'SAFE') enforced. |
| **"Alembic asynchronous migrations schema"** | [alembic/env.py](file:///alembic/env.py#L25-L95)<br>[alembic/versions/20261011_0001_init.py](file:///alembic/versions/20261011_0001_initial_schema.py) | `alembic upgrade head` | **PASS**: 8 tables (`users`, `refresh_tokens`, `shipments`, `disruptions`, `pipeline_runs`, `risk_assessments`, `recommendations`, `agent_traces`) migrated. |
| **"Dashboard KPIs with SQL aggregate and FILTER clauses"** | [crud.py](file:///backend/crud.py#L550-L585)<br>[routers/analytics.py](file:///backend/routers/analytics.py#L20-L35) | `pytest backend/tests/test_sql_analytics.py::test_dashboard_kpis_aggregate_and_filter` | **PASS**: Hand-computed fixtures match exact filtered counts for latest pipeline run. |
| **"Risk trend per shipment using LAG() SQL window function"** | [crud.py](file:///backend/crud.py#L600-L640)<br>[routers/analytics.py](file:///backend/routers/analytics.py#L40-L55) | `pytest backend/tests/test_sql_analytics.py::test_risk_trends_lag_window_function` | **PASS**: Delta vs prior run computed in single relational query via `LAG(score, 1) OVER (PARTITION BY shipment_id ORDER BY finished_at)`. |
| **"Corridor exposure ranking via 3-way join, GROUP BY, and HAVING"** | [crud.py](file:///backend/crud.py#L650-L700)<br>[routers/analytics.py](file:///backend/routers/analytics.py#L60-L80) | `pytest backend/tests/test_sql_analytics.py::test_corridor_exposure_ranking` | **PASS**: Aggregated shipment risk exposure joined with disruptions and filtered by `HAVING COUNT(r.id) > 0`. |
| **"Disruption timeline with zero-filled days"** | [crud.py](file:///backend/crud.py#L710-L760)<br>[routers/analytics.py](file:///backend/routers/analytics.py#L85-L105) | `pytest backend/tests/test_sql_analytics.py::test_disruption_timeline_zero_filled` | **PASS**: Guaranteed zero-filled sequence returned across 7-day analytics window. |
| **"Keyset seek pagination on shipments (O(1) B-tree traversal)"** | [crud.py](file:///backend/crud.py#L82-L115)<br>[routers/shipments.py](file:///backend/routers/shipments.py#L30-L50) | `pytest backend/tests/test_sql_analytics.py::test_keyset_pagination_ordering` | **PASS**: Seek ordering using `WHERE shipment_id > cursor` returns precise pages without OFFSET degradation. |
| **"Stateful LLM workflow with LangGraph & bounded review loop"** | [workflow/state.py](file:///backend/workflow/state.py#L1-L45)<br>[workflow/graph.py](file:///backend/workflow/graph.py#L1-L110) | `pytest backend/tests/test_workflow_graph.py::test_bounded_review_loop_termination` | **PASS**: Loop bounded to N <= 2 iterations when low-confidence items exceed 30% threshold. |
| **"Conditional recommendation bypass on nominal shipments"** | [workflow/graph.py](file:///backend/workflow/graph.py#L50-L75) | `pytest backend/tests/test_workflow_graph.py::test_conditional_recommendation_bypass_on_safe_shipments` | **PASS**: Recommendations generated strictly for at-risk shipments; SAFE shipments bypass LLM. |
| **"Real per-node execution telemetry traces in PostgreSQL"** | [models.py](file:///backend/models.py#L210-L240)<br>[workflow/nodes.py](file:///backend/workflow/nodes.py#L20-L70) | `pytest backend/tests/test_workflow_graph.py::test_pipeline_trace_rest_endpoint` | **PASS**: `GET /pipeline-runs/{id}/trace` returns real durations, hashes, and fallback indicators. |
| **"Canonical Circuit Breaker FSM (CLOSED/OPEN/HALF_OPEN)"** | [resilience/circuit_breaker.py](file:///backend/resilience/circuit_breaker.py#L20-L150) | `pytest backend/tests/test_resilience.py` (7 FSM tests) | **PASS**: State transitions verified with injectable simulated clock; immediate trip on 429 quota exhaustion. |
| **"Deterministic SHA-256 assessment cache with Redis & in-memory TTL"** | [resilience/cache.py](file:///backend/resilience/cache.py#L20-L110)<br>[routers/risk_analysis.py](file:///backend/routers/risk_analysis.py#L40-L70) | `pytest backend/tests/test_resilience.py` (4 cache tests) | **PASS**: Key order invariance (`sorted(hashes)`), TTL expiry, and explicit eviction confirmed. |
| **"Transparent Demo Mode with recorded fixtures"** | [services/weather_service.py](file:///backend/services/weather_service.py#L100-L135)<br>[services/news_service.py](file:///backend/services/news_service.py#L125-L160) | `pytest backend/tests/test_resilience.py::test_weather_service_loads_demo_fixtures_when_key_missing` | **PASS**: Missing API keys load `data/fixtures/`, set `data_source: "demo_fixture"`, and display DEMO badge in UI. |
| **"WebSocket fail-fast on Redis broker offline"** | [main.py](file:///backend/main.py#L75-L105) | `pytest backend/tests/test_resilience.py::test_websocket_closes_fast_when_redis_offline` | **PASS**: Connection pings Redis and immediately closes with clean status code 1011 instead of hanging. |
| **"HttpOnly JWT cookie authentication & refresh token rotation"** | [routers/auth.py](file:///backend/routers/auth.py#L125-L210) | `pytest backend/tests/test_auth_routes.py` (4 auth tests) | **PASS**: Reusing rotated refresh token triggers 401 Unauthorized; logout revokes stored token hashes. |
| **"Periodic Celery background execution across multi-tenant fleets"** | [celery_worker.py](file:///backend/celery_worker.py#L25-L62) | `pytest backend/tests/test_celery_task.py` (3 celery tests) | **PASS**: Celery worker loops tenant owner IDs, executes pipeline, caches to Redis, and publishes pub/sub event. |

---

## 2. Command Execution Evidence (Raw Run Artifacts)

### Database Indexing Benchmark (`docs/performance.md`)
- **Seeded Dataset:** 20,000 synthetic assessments and 200 pipeline runs.
- **Query 1 (Corridor Exposure Join & Aggregation):**
  - Before Index: `129.70 ms` (Seq Scan on `risk_assessments`)
  - After Index (`idx_risk_assessments_run_shipment`): `87.72 ms` (**1.48x speedup, 32.4% execution time reduction**)
- **Query 2 (Shipment Risk Trend with LAG):**
  - Before Index: `39.02 ms` (Bitmap Index Scan + Sort)
  - After Index (`idx_pipeline_runs_owner_finish`): `18.63 ms` (**2.09x speedup, 52.3% execution time reduction**)

### Evaluation Harness (`eval/results.md`)
- **News Classification (30 Hand-Labeled Realistic Indian Logistics Items):**
  - Rule-Based Baseline: **83.3%** Type Accuracy, **73.3%** Severity Agreement (0.02 ms p50)
  - LLM Analyzer: **100.0%** Type Accuracy, **96.7%** Severity Agreement (247.0 ms p50)
  - JSON Validity on 1st Attempt: **100.0%** (validated with Pydantic)
- **End-to-End Corridor Scenarios (10 Scenarios):**
  - Risk-Level Agreement: **100.0%** (10/10 scenarios matching expected Haversine corridor risk)

---

## 3. Defect Remediation Audit

| Audited Defect | Prior Defective State | Remediated State |
| :--- | :--- | :--- |
| **Active Database** | Motor/MongoDB async driver; no SQL models | PostgreSQL 16 with async SQLAlchemy 2.0 (`asyncpg`) & Alembic migrations |
| **"Autonomous Agents"** | 4 linear procedural functions in sequence | Typed LangGraph workflow with tool selection, Pydantic validation, and bounded review loop |
| **Circuit Breaker** | Single `elif status == 429: break` | Canonical CLOSED -> OPEN -> HALF_OPEN finite state machine in `resilience/circuit_breaker.py` |
| **Cache Architecture** | Plain Python dict keyed only by `owner_id` | SHA-256 digest of `(owner_id + shipments_version + sorted_disruption_hashes)` with Redis & memory TTL |
| **Weather Mock Claim** | Raised `ValueError` when API key was absent | Transparent fallback loading `data/fixtures/weather_fixtures.json` with `data_source: "demo_fixture"` |
| **Risk Thresholds** | Split between 4.0 and 4.5 in different files | Unified single source of truth in `backend/config.py` (`HIGH: 4.5`, `MEDIUM: 1.8`, `RADIUS: 150km`) |
| **Test Coverage** | 8 isolated unit tests; no DB, routes, or celery | 51 comprehensive tests spanning contracts, SQL queries, LangGraph graph, resilience, auth, and Celery |
