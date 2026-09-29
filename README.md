# Enterprise RAG + Agentic AI Platform

A production-grade, highly secure **Retrieval-Augmented Generation (RAG) and Agent Swarm** platform designed for enterprise document intelligence. 

The platform allows users to upload documents, securely ask natural-language questions, receive grounded answers with citations, and execute multi-step agentic workflows with human-in-the-loop approvals.

**Current Release:** Stage 11 — Production Go-Live Ready

---

## 🏗 Architecture & Features

- **Frontend:** Next.js React application with secure JWT-based authentication.
- **Backend API:** FastAPI (Async) with strict Pydantic validation.
- **Agent Orchestration:** Custom Multi-Agent Swarm supporting single-agent and DAG-based reasoning.
- **RAG Pipeline:** Hybrid Retrieval (Dense + Sparse) with document chunking (Docling) and re-ranking.
- **LLM Provider:** NVIDIA NIM (`nvidia/nemotron-3-super-120b-a12b`) for state-of-the-art secure inference.
- **Vector Database:** Qdrant (Isolated internal network).
- **Relational Database:** PostgreSQL (Async SQLAlchemy, Alembic migrations).
- **Background Worker:** ARQ (Redis) for long-running workflows, evaluations, and asynchronous agent tasks.
- **Security:** Strict Role-Based Access Control (RBAC), LLM Input/Output Guardrails, isolated Docker networks, and TLS-terminating Nginx reverse proxy.
- **Approvals:** High-risk external actions (e.g., sending emails) trigger Human-in-the-Loop approval workflows.

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Docker and Docker Compose V2
- A valid NVIDIA API Key (NIM)

### Setup

```bash
# 1. Clone the repository
git clone <repo-url>
cd enterprise-rag

# 2. Configure Environment
cp .env.example .env
# Edit .env and insert your API credentials
# LLM_API_KEY=nvapi-...

# 3. Start Development Services
docker compose up --build -d

# 4. Access the Application
# Frontend: http://localhost:3000
# Backend Swagger Docs: http://localhost:8000/docs
```

---

## 🔒 Production Deployment

The production topology securely isolates all databases inside an internal Docker network. The application is fronted by an Nginx reverse proxy that terminates TLS and handles static asset routing.

### 1. Provision Secrets
```bash
cp .env.example .env.production
```
Edit `.env.production`:
- Set `APP_ENV=production`
- Generate a secure `SECRET_KEY` (e.g., `openssl rand -hex 32`)
- Use strong passwords for `POSTGRES_PASSWORD`
- Supply the production `LLM_API_KEY`

### 2. Launch Production Infrastructure
```bash
# Start the databases first
docker compose -f docker-compose.production.yml up -d postgres qdrant redis

# Run database migrations
docker compose -f docker-compose.production.yml run --rm backend alembic upgrade head

# Seed core RBAC roles
docker compose -f docker-compose.production.yml run --rm backend python scripts/seed_rbac.py

# Launch all remaining services
docker compose -f docker-compose.production.yml up -d
```

### 3. Verify Health
Execute the production smoke test to ensure API routing and LLM connectivity are intact:
```bash
docker exec -it enterprise-rag-backend python scripts/production_go_live_smoke_test.py
```

---

## 🧪 Testing

The repository contains extensive unit, integration, and security regression tests.

```bash
# Run the full Pytest suite
docker exec -it enterprise-rag-backend python -m pytest tests/ -v

# Run the Staging E2E Acceptance harness
docker exec -it enterprise-rag-backend python -m scripts.staging_e2e
```

---

## 📚 Runbooks & Documentation

The `/artifacts` directory (or repository root if exported) contains critical operational runbooks generated during the Stage 11 Audit:
- `STAGE_11_DATABASE_DEPLOYMENT_RUNBOOK.md`
- `STAGE_11_BACKUP_RESTORE_RUNBOOK.md`
- `STAGE_11_ROLLBACK_RUNBOOK.md`
- `STAGE_11_PRODUCTION_GO_LIVE_AUDIT.md`

Please consult the Backup & Restore Runbook prior to initiating any major version upgrades.

---

## ⚖️ License
Private — Enterprise Use Only.
