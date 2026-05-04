<p align="center">
  <img src="assets/fasttrade-logo.svg" alt="FastTrade logo" width="860" />
</p>

<p align="center">
  Full-stack AI and ML trading platform for Indian markets, with web and mobile apps, broker integration, live data, scanners, strategy workflows, and portfolio intelligence.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/React-Web-61DAFB?logo=react&logoColor=111827" />
  <img alt="React Native" src="https://img.shields.io/badge/React%20Native-Mobile-20232A?logo=react&logoColor=61DAFB" />
  <img alt="PostgreSQL" src="https://img.shields.io/badge/PostgreSQL-Data-336791?logo=postgresql&logoColor=white" />
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white" />
</p>

<p align="center">
  <a href="docs/README.md">Documentation</a> •
  <a href="docs/QUICK_START.md">Quick Start</a> •
  <a href="docs/API.md">API</a> •
  <a href="docs/SECURITY.md">Security</a>
</p>

## Why FastTrade

FastTrade is designed as a unified platform for analysis, execution, risk control, and post-trade learning.

- Multi-agent AI analysis pipeline with technical, sentiment, news, fundamentals, bull and bear research
- Real-time monitoring through WebSocket streams
- Automated watchlist workflows with pre-market analysis and suggestions
- Web dashboard plus React Native mobile app
- Broker connectivity and execution controls for Indian markets
- Built-in decision memory and outcome reflection loop

## Core Capabilities

### Trading Intelligence

- AI analysis pipeline with structured reports and final decision output
- Scanner-driven signal workflows
- Decision history with outcome evaluation and reflections
- Watchlist prioritization for pre-market planning

### Risk and Execution

- Confirmation-gated live trade flows
- Guardrail-aware order handling
- Position and portfolio overview tooling
- Configurable schedule-based automation

### Product Surfaces

- Web app for operations, monitoring, and analytics
- Mobile app for on-the-go workflows and watchlist management
- API-first backend with FastAPI and interactive docs

## Architecture

- Backend: FastAPI + SQLAlchemy + APScheduler
- Data: PostgreSQL
- Web: React + TypeScript
- Mobile: React Native (Expo)
- Integrations: Broker APIs, sentiment/news feeds, ML models

High-level flow:

Web and Mobile clients -> FastAPI backend -> Database + schedulers + external market providers

## Important Flow Diagram

```mermaid
flowchart LR
  A[Web App and Mobile App] --> B[FastAPI Gateway]
  B --> C[Market Data Layer\nCandles, News, Sentiment, Broker Quotes]
  C --> D[AI Agent Pipeline\nTechnical, News, Sentiment, Fundamentals]
  D --> E[Bull and Bear Research]
  E --> F[Trader Decision]
  F --> G[Risk and Portfolio Guards]
  G --> H[Execution Engine\nPaper or Live]
  H --> I[Broker API]
  F --> J[Decision Memory and Reflection]
  J --> D
  K[Watchlist Scheduler] --> D
```

## Repository Layout

- backend: API, services, schedulers, models, tests
- web: React web client
- mobile: React Native client
- docs: setup guides, API docs, architecture, security, references
- test_scripts: utility and diagnostics scripts

## Quick Start

### Option 1: Docker Compose

1. Configure backend environment file at backend/.env
2. Start services:
   docker compose up --build
3. Open:
   - Web: http://localhost:3000
   - API docs: http://localhost:8000/docs

### Option 2: Local Development

Backend

1. cd backend
2. python -m venv venv
3. Activate venv
4. pip install -r requirements.txt
5. uvicorn app.main:app --reload --port 8000

Web

1. cd web
2. npm install
3. npm run dev

Mobile

1. cd mobile
2. npm install
3. npx expo start

You can also use setup scripts at project root:

- setup.bat (Windows)
- setup.sh (macOS/Linux)

## Configuration

See detailed setup guides in docs:

- docs/SELF_HOST_SETUP.md
- docs/QUICK_START.md
- docs/ZERODHA_SETUP_GUIDE.md
- docs/AUTHENTICATION_DEPLOYMENT_GUIDE.md

Recommended first-run safety:

- Start in paper-trading mode
- Enable authentication and set strong secrets
- Configure conservative risk limits before live execution

## Documentation

Start here:

- docs/README.md

Useful references:

- docs/API.md
- docs/FUNCTIONAL_SPEC.md
- docs/SYSTEM_ARCHITECTURE_DIAGRAM.md
- docs/SECURITY.md
- docs/CHANGELOG.md

## Contributing

Contributions are welcome.

1. Create a feature branch
2. Keep changes scoped and tested
3. Open a pull request with a clear description

## Disclaimer

This project is for research and educational use. It is not financial advice. Trading involves risk, including possible loss of capital.
