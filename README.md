# 🛰️ Logistics Disruption Intelligence Agent

An enterprise-grade, autonomous AI supply chain resilience platform. It ingests real-world disruption signals (live OpenWeatherMap API + live Google News RSS feeds), performs vector-based geospatial corridor risk projection against active freight fleets, and delivers actionable rerouting directives alongside an interactive **What-If Route Simulator**.

> 📚 **Interview & Architecture Guides:**
> - [🎙️ 2-Minute Interview Pitch & Q&A Playbook](INTERVIEW_2MIN_PITCH.md)
> - [🏗️ Complete System Architecture & Technical Specification](PROJECT_COMPLETE_SYSTEM_DESCRIPTION.md)

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    NEXT.JS 14 DASHBOARD (port 3000)             │
│  Enterprise SaaS UI · Leaflet Map · What-If Route Simulator     │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / WebSockets (/ws/risk-updates)
┌──────────────────────────▼──────────────────────────────────────┐
│                    FASTAPI ASYNC BACKEND (port 8000)            │
│  JWT Auth · MongoDB (Motor) · 2ms In-Memory SHA256 Cache        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
           ┌────────────────▼────────────────┐
           │         4-AGENT PIPELINE        │
           │                                 │
           │  [1] DataCollectorAgent         │
           │      ↓ Live Weather + RSS News  │
           │                                 │
           │  [2] DisruptionAnalyzerAgent    │
           │      ↓ Gemini AI + Heuristics   │
           │                                 │
           │  [3] RiskEvaluatorAgent         │
           │      ↓ Vector Corridor Math     │
           │                                 │
           │  [4] RecommendationAgent        │
           │      ↓ Detours & Delay Recovery │
           └─────────────────────────────────┘
```

---

## 📁 Project Structure

```
Logistics_Disruption_Intelligence_Agent/
├── backend/
│   ├── main.py                    # FastAPI app & ASGI entrypoint
│   ├── agents/
│   │   ├── data_collector.py      # Agent 1: Live RSS & Weather Ingestion
│   │   ├── disruption_analyzer.py # Agent 2: AI & Heuristic Severity Analyzer
│   │   ├── risk_evaluator.py      # Agent 3: Vector Route Corridor Evaluator
│   │   └── recommendation.py     # Agent 4: Rerouting Directives & Detours
│   ├── services/
│   │   ├── weather_service.py    # OpenWeatherMap API integration
│   │   ├── news_service.py       # Google News RSS live parser & geocoder
│   │   ├── geo_matcher.py        # Vector line-segment projection math
│   │   └── gemini_service.py     # Gemini 2.5/1.5 Flash + 429 Circuit Breaker
│   ├── routers/
│   │   ├── shipments.py          # GET /shipments
│   │   ├── disruptions.py        # GET /disruptions
│   │   └── risk_analysis.py      # GET /risk-analysis
│   └── data/
│       └── shipments.json        # 15 mock shipments (Indian routes)
├── frontend/
│   ├── src/                      # Next.js Source Code
│   ├── package.json              # Node dependencies
│   └── tailwind.config.js        # Cyberpunk UI Tokens
├── .env.example                  # API key template
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## 🚀 Quick Start (Local)

### 1. Clone & Setup

```bash
git clone <your-repo-url>
cd hackathon-ps4

# Create virtual environment
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure API Keys

```bash
copy .env.example .env    # Windows
# cp .env.example .env    # Linux/Mac
```

Edit `.env` with your API keys:

| Variable | Source | Required? |
|----------|--------|-----------|
| `OPENWEATHER_API_KEY` | [openweathermap.org](https://openweathermap.org/api) | Optional (mock fallback) |
| `GNEWS_API_KEY` | [gnews.io](https://gnews.io) | Optional (mock fallback) |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) | Optional (rule-based fallback) |

> **Note:** The system works fully with mock data if no API keys are provided — great for offline demos!

### 3. Start the Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

API docs available at: `http://localhost:8000/docs`

### 4. Start the Dashboard

```bash
# In a new terminal (from project root)
cd frontend
npm install
npm run dev
```

Dashboard available at: `http://localhost:3000`

---

## 🐳 Docker Deployment

```bash
# Copy and fill in your .env
copy .env.example .env

# Build and run both services
docker-compose up --build

# Stop
docker-compose down
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |

---

## ☁️ Cloud Deployment (Render)

1. Push to GitHub
2. Create two Render Web Services — one for backend, one for frontend
3. **Backend:**
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. **Frontend:**
   - Build command: `pip install -r requirements.txt`
   - Start command: `streamlit run frontend/dashboard.py --server.port $PORT --server.address 0.0.0.0 --server.headless true`
5. Add all API keys as environment variables in Render dashboard
6. Set `BACKEND_URL` in the frontend service to point to the deployed backend URL

---

## 🔌 API Reference

### `GET /shipments`
Returns all 15 mock shipments with route details.

### `GET /disruptions`
Runs Agents 1 & 2 — collects and analyzes disruption signals.
```json
{
  "total": 8,
  "weather_count": 4,
  "news_count": 4,
  "disruptions": [...]
}
```

### `GET /risk-analysis`
Runs the full 4-agent pipeline.
```json
{
  "pipeline": {
    "disruptions_collected": 8,
    "shipments_evaluated": 15,
    "risk_breakdown": { "HIGH": 4, "MEDIUM": 3, "LOW": 1, "SAFE": 7 }
  },
  "recommendations": [
    {
      "shipment_id": "S101",
      "risk_level": "HIGH",
      "reason": "Heavy rainfall detected 23.4km from Chennai origin...",
      "suggested_action": "Halt shipment. Reroute via NH77...",
      "alternate_route": "NH75 or NH48",
      "estimated_delay_hours": 8,
      "customer_message": "Your shipment S101 may experience..."
    }
  ]
}
```

---

## 🤖 AI Agent Detail

| Agent | Role | Technology |
|-------|------|------------|
| **DataCollectorAgent** | Fetches weather + news signals | OpenWeatherMap, GNews |
| **DisruptionAnalyzerAgent** | Classifies severity, transport impact | Gemini 1.5 Flash / Rule-based |
| **RiskEvaluatorAgent** | Haversine geomatching, risk scoring | Pure Python (math) |
| **RecommendationAgent** | Generates actions + customer messages | Gemini 1.5 Flash / Templates |

### Risk Score Formula
```
risk_score = severity_weight × priority_weight × proximity_factor
  where proximity_factor = 1 - (distance_km / radius_km)

HIGH risk:   score ≥ 5
MEDIUM risk: score ≥ 2
LOW risk:    score < 2
```

---

## 🧪 Sample Output

```json
{
  "shipment_id": "S101",
  "origin": "Chennai",
  "destination": "Madurai",
  "route_highway": "NH44",
  "cargo_type": "Pharmaceuticals",
  "delivery_priority": "HIGH",
  "risk_level": "HIGH",
  "disruption_type": "Heavy Rain",
  "distance_to_disruption_km": 23.4,
  "reason": "Heavy rainfall (82mm) detected 23.4km from shipment origin (Chennai). NH44 potentially impacted. Cargo: Pharmaceuticals | Priority: HIGH.",
  "suggested_action": "Halt shipment and wait for weather clearance. Reroute via nearest alternative highway. Notify customer of 6-12 hour delay.",
  "alternate_route": "NH75 or NH48",
  "estimated_delay_hours": 8,
  "customer_message": "Your shipment S101 from Chennai to Madurai may experience a delay of ~8 hours due to Heavy Rain near Chennai."
}
```

---

- **🗺️ Geolocational Matrix** — Leaflet map showing shipment risk levels and cyber disruption zones
- **📦 Threat Matrix** — Filterable fleet view with priority and probability color coding
- **⚡ Anomalies** — Live disruption signals from weather & news APIs
- **🤖 AI Agent Strategy** — Per-shipment recommendations (rerouting, delays) with agent pipeline trace

---

## 🛠️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend API | FastAPI + Uvicorn |
| AI Agents | Google Gemini 1.5 Flash |
| Weather Data | OpenWeatherMap API |
| News Data | GNews API |
| Async Jobs | Celery + Redis |
| Database | PostgreSQL (SQLAlchemy) |
| Geospatial | Haversine formula (pure Python) |
| Dashboard | Next.js (React) + Tailwind CSS |
| Visualization | Leaflet.js |
| Containerization | Docker + Docker Compose |
