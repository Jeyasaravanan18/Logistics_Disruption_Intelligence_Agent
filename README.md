# Logistics Disruption Intelligence Agent

A production-grade, observable multi-tenant freight disruption intelligence platform deployed across **Vercel**, **Render**, and **Neon PostgreSQL**. 

Built with **FastAPI**, **Neon Serverless PostgreSQL 16** (async **SQLAlchemy 2.0** + **Alembic**), **LangGraph**, **Google Gemini 3.8 Flash**, **OpenWeatherMap**, **GNews**, and **Next.js 14** on **OpenStreetMap**.

Monitors real-time weather anomalies and transport incident news across freight logistics corridors, calculates freight risk via Haversine route corridor math, and triggers an observable stateful LLM workflow with tool selection, bounded review loops, and per-node telemetry.

---

## 🌐 Live Cloud Deployments

| Component | Platform / Host | Technology / URL | Status |
| :--- | :--- | :--- | :--- |
| **Frontend SaaS Dashboard** | **Vercel** | [Live App](https://logisticsdisruptionintelligenceagen.vercel.app) | 🟢 Live |
| **Backend REST & WebSocket API** | **Render** | FastAPI 0.110 on Python 3.11 / Uvicorn ASGI | 🟢 Online |
| **Relational Database** | **Neon.tech** | Serverless PostgreSQL 16 (`asyncpg` SSL connection) | 🟢 Healthy |
| **Interactive Cartography** | **OpenStreetMap** | Leaflet with Zero-Watermark Open Cartography | 🟢 Integrated |
| **Primary LLM Reasoning** | **Google AI Studio** | Gemini 3.8 Flash (Automatic cascade fallback) | 🟢 Active |
| **Weather Hazard Radar** | **OpenWeatherMap** | Live Global Current & Hazard Observation API | 🟢 Connected |
| **Disruption News Feed** | **GNews API** | Real-time logistics, port, and border incident feed | 🟢 Connected |

---

## System Architecture

```mermaid
flowchart TD
    subgraph Edge["Client & Edge Presentation Layer (Vercel)"]
        Browser["User Browser"]
        NextApp["Next.js 14 SaaS Dashboard"]
        NextRewrites["Next.js Serverless Proxy (/api/*)"]
        OSM["OpenStreetMap Free Tile Servers"]
    end

    subgraph CloudAPI["Backend Services (Render Cloud)"]
        FastAPIGateway["FastAPI Application Gateway"]
        AuthRouter["/auth (JWT Secure Cookies)"]
        ShipmentRouter["/shipments (Keyset Seek Pagination)"]
        AnalyticsRouter["/analytics (LAG Window Functions)"]
        RiskRouter["/risk-analysis (Resilience Cache)"]
        WSEndpoint["/ws/risk-updates (Real-time Broadcast)"]
    end

    subgraph DataPersistence["Managed Persistence (Neon)"]
        NeonPG[("Neon Serverless PostgreSQL 16\n(asyncpg + SQLAlchemy 2.0)")]
        LocalCache["In-Memory TTL / Redis 7 Broker"]
    end

    subgraph AIWorkflow["LangGraph Stateful Agent Pipeline"]
        PlanNode["plan (Dynamic Query & Tool Selection)"]
        WeatherAgent["collect_weather (OpenWeather API + Fixture Fallback)"]
        NewsAgent["collect_news (GNews API + Semantic Parsing)"]
        AnalyzeNode["analyze (Pydantic Schema Validation)"]
        ScoreNode["score (Deterministic Haversine Geometry)"]
        ReviewLoop{"Review Loop\n(Confidence < 0.60?)"}
        RiskLevelBranch{"Risk Level\n(HIGH / MEDIUM?)"}
        GeminiNode["recommend (Gemini 3.8 Flash Batch Prompt)"]
        PersistNode["persist_finish (AgentTrace Telemetry Recording)"]
    end

    subgraph ExternalServices["External Intelligence Providers"]
        GeminiAPI["Google Gemini 3.8 Flash\n(Fallback: 2.5-Flash / 2.0-Flash / Rules)"]
        OpenWeatherAPI["OpenWeatherMap REST API"]
        GNewsAPI["GNews International Headlines"]
    end

    Browser -->|HTTPS| NextApp
    Browser -->|Map Tiles| OSM
    Browser -->|Cookie Auth API Calls| NextRewrites
    NextRewrites -->|Reverse Proxy| FastAPIGateway
    Browser -.->|WebSocket wss://| WSEndpoint

    FastAPIGateway --> AuthRouter & ShipmentRouter & AnalyticsRouter & RiskRouter & WSEndpoint
    FastAPIGateway --> NeonPG
    FastAPIGateway --> LocalCache

    RiskRouter --> AIWorkflow
    PlanNode --> WeatherAgent & NewsAgent
    WeatherAgent -.-> OpenWeatherAPI
    NewsAgent -.-> GNewsAPI

    WeatherAgent & NewsAgent --> AnalyzeNode
    AnalyzeNode --> ReviewLoop
    ReviewLoop -- "Low Confidence (Max N=2)" --> PlanNode
    ReviewLoop -- "Acceptable" --> ScoreNode

    ScoreNode --> RiskLevelBranch
    RiskLevelBranch -- "HIGH / MEDIUM" --> GeminiNode
    RiskLevelBranch -- "SAFE / LOW" --> PersistNode

    GeminiNode -.-> GeminiAPI
    GeminiNode --> PersistNode
    PersistNode --> NeonPG
    PersistNode -.-> LocalCache
```

---

## Technical Stack

| Layer | Technology | Purpose |
| :--- | :--- | :--- |
| **Frontend Hosting** | **Vercel** | Global edge distribution, Serverless Next.js rendering, automatic SSL |
| **Backend Hosting** | **Render** | Fully-managed Python 3.11 Web Service running Uvicorn ASGI |
| **Database** | **Neon PostgreSQL 16** | Cloud-native serverless PostgreSQL with `asyncpg` connection pooling |
| **Cartography** | **OpenStreetMap** | Zero-API-key, watermark-free high-precision global Leaflet map tiles |
| **Primary LLM** | **Gemini 3.8 Flash** | High-speed multi-step disruption reasoning, structured JSON schemas |
| **LLM Cascade Fallback** | Gemini 2.5 / 2.0 / 1.5 Flash | Resilient fallback tier if primary quota or capacity is saturated |
| **Workflow Engine** | **LangGraph 0.2** | Stateful graph execution, bounded review loops, conditional routing |
| **API Gateway** | **FastAPI 0.110** | High-performance async endpoints, cookie authentication, CORS control |
| **ORM & Migrations** | **SQLAlchemy 2.0 + Alembic** | Strictly typed async database queries and versioned migrations |
| **Live External Signals**| **OpenWeatherMap & GNews** | Real-time weather hazard radar & international transport incident news |
| **Resilience System** | **CircuitBreaker FSM + Cache** | Finite State Machine preventing cascading LLM quota trips |

---

## Measured Performance & Evaluation Benchmarks

Every metric presented below is derived directly from benchmark scripts executed in this repository.

### 1. Database Indexing Benchmark (20,000 Synthetic Assessments)
Full methodology and raw execution plans recorded in [docs/performance.md](file:///docs/performance.md).

| Query Operation | Sequential Scan (Before Index) | Index Scan (After Index) | Speedup Factor | Execution Reduction |
| :--- | :--- | :--- | :--- | :--- |
| **Corridor Exposure Ranking** (3-Way Join + Aggregation) | `129.70 ms` | `87.72 ms` | **1.48x** | **32.4% faster** |
| **Shipment Risk Trend** (`LAG()` Window Function) | `39.02 ms` | `18.63 ms` | **2.09x** | **52.3% faster** |

### 2. Disruption Classification Benchmark (30 Hand-Labeled Items)
Full run report generated by `make eval` recorded in [eval/results.md](file:///eval/results.md).

| Metric | Rule-Based Baseline | LLM Analyzer (Gemini 3.8 Flash / Cascade) | Benefit |
| :--- | :--- | :--- | :--- |
| **Disruption Type Accuracy** | 83.3% (25/30) | **100.0%** (30/30) | +16.7% semantic precision |
| **Severity Agreement** | 73.3% (22/30) | **96.7%** (29/30) | +23.3% nuance handling |
| **JSON Validity on 1st Attempt** | 100.0% (deterministic) | **100.0%** | Guaranteed by Pydantic validation |
| **Fallback Rate** | 0.0% | **0.0%** | Resilient rule fallback on API quota trip |
| **Latency p50 / p95** | 0.02 ms / 0.03 ms | 247 ms / 277 ms | Sub-second async batched calls |
| **End-to-End Scenarios Agreement** | — | **100.0%** (10/10 Passed) | Verified corridor risk agreement |

---

## Observability: Real Telemetry Traces

Rather than simulated logs, every execution of the LangGraph workflow records atomic execution telemetry in the PostgreSQL `agent_traces` table.

### Schema Fields
- `run_id`: UUID linking the trace to the specific `pipeline_runs` table row.
- `node`: Name of the executed workflow step (`plan`, `collect_weather`, `analyze`, `score`, `recommend`, etc.).
- `started_at` & `duration_ms`: Real execution start timestamp and elapsed milliseconds.
- `input_hash`: SHA-256 digest of the node's input state for auditability.
- `output_summary`: Structured string summarizing node outputs and decisions.
- `used_llm`: Boolean indicating whether an external LLM was invoked.
- `fallback_used`: Boolean indicating whether validation failed and rule fallback was engaged.
- `tokens_estimate`: Estimated prompt and completion token consumption.
- `error`: Captured error message or `None`.

Exposed via `GET /pipeline-runs/{run_id}/trace` and rendered dynamically in the UI's `AgentTrace` component.

---

## Resilience & Production Hardening

1. **Finite State Machine Circuit Breaker:**
   - Canonical `CLOSED` -> `OPEN` -> `HALF_OPEN` states.
   - Trips immediately upon HTTP 429 rate limit or 3 consecutive network failures.
   - In `OPEN` state, remote calls fail fast in `< 0.02ms` to expert rules.
   - Cooldown period (30s) tested deterministically with an injectable fake clock.
2. **Deterministic SHA-256 Cache:**
   - Key: `sha256(owner_id + shipments_version + sorted_disruption_content_hashes)`.
   - Stored in Redis / In-memory dictionary with 180s TTL.
   - Ordering invariance ensures cache hits regardless of signal arrival order.
3. **Transparent Demo Mode:**
   - If external API keys are omitted, services load recorded payloads from `data/fixtures/`.
   - Signals are explicitly tagged with `data_source: "demo_fixture"`, displaying a visible `DEMO` badge in the UI.
4. **WebSocket Fail-Fast:**
   - On connection, `/ws/risk-updates` verifies broker connectivity.
   - Closes cleanly with status code `1011` rather than idling indefinitely.

---

## Local Setup & Development

### 1. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Populate your `.env` with:
```ini
ENVIRONMENT=development
JWT_SECRET_KEY=dev-secret-key-replace-in-production
DATABASE_URL=postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/logistics
SQLITE_FALLBACK_URL=sqlite+aiosqlite:///./logistics.db

# Live External APIs (Optional - falls back to fixtures if blank)
GEMINI_API_KEY=AIzaSy...
OPENWEATHER_API_KEY=...
GNEWS_API_KEY=...
```

### 2. Run Backend
```bash
# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
API docs available at `http://127.0.0.1:8000/docs`.

### 3. Run Frontend
```bash
cd frontend
npm install
npm run dev
```
Dashboard available at `http://localhost:3000`.

---

## Verification & Testing Commands

To reproduce all verified test results:

```bash
# Run complete test suite (51 tests spanning routes, models, analytics, workflow, and resilience)
python -m pytest backend/tests/ -v

# Run the 20k-row PostgreSQL EXPLAIN ANALYZE benchmark
python backend/scripts/benchmark_sql.py

# Run the 30-item evaluation harness and regenerate eval/results.md
make eval
# Or directly:
python eval/run_eval.py
```

---

## Documentation Index

- [docs/EVIDENCE.md](file:///docs/EVIDENCE.md): Exhaustive claim-to-code mapping matrix with line numbers.
- [docs/WALKTHROUGH.md](file:///docs/WALKTHROUGH.md): Plain-language system architecture walkthrough and 15 technical interview Q&As.
- [docs/adr-langgraph.md](file:///docs/adr-langgraph.md): Architecture Decision Record justifying LangGraph vs procedural pipelines.
- [docs/performance.md](file:///docs/performance.md): Raw `EXPLAIN (ANALYZE, BUFFERS)` execution plans before and after B-tree indexing.
- [eval/results.md](file:///eval/results.md): Complete evaluation output comparing Rule Baseline vs LLM Analyzer.
