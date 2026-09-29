# Knowledge AI

### Enterprise RAG & Agentic AI Platform

Knowledge AI is a production-oriented enterprise AI platform that combines **Retrieval-Augmented Generation (RAG), RBAC, AI guardrails, tool governance, multi-agent workflows, persistent memory, human-in-the-loop approvals, evaluation, and observability** into a single system.

The platform is designed around a simple enterprise requirement:

> Give users useful answers from private organizational knowledge while maintaining strict access control, security boundaries, and controlled agentic actions.

[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Async-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-React-black?logo=next.js)](https://nextjs.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791?logo=postgresql)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-red)](https://qdrant.tech/)
[![Redis](https://img.shields.io/badge/Redis-Queue-red?logo=redis)](https://redis.io/)
[![Docker](https://img.shields.io/badge/Docker-Containerized-2496ED?logo=docker)](https://www.docker.com/)

---

## 🚀 What Knowledge AI Does

Knowledge AI allows authenticated users to:

- Ask natural-language questions over enterprise documents
- Receive grounded answers with document citations
- Search using hybrid dense + sparse retrieval
- Use reranked enterprise search results
- Execute controlled AI agent workflows
- Delegate tasks across specialized agents
- Use approved tools through a centralized Tool Registry
- Trigger high-risk actions through human approval
- Persist and retrieve user-scoped memories
- Run long-lived background workflows
- Monitor AI activity, evaluation metrics, latency, and token usage

The platform is designed so that **LLMs propose actions, while backend-controlled services enforce authorization, security, policy, and execution boundaries.**

---

# 🏗️ Architecture

```text
                         ┌─────────────────────────┐
                         │       Knowledge AI       │
                         │       Next.js UI         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                              ┌───────────────┐
                              │ Nginx / API   │
                              │ Reverse Proxy │
                              └───────┬───────┘
                                      │
                                      ▼
                           ┌────────────────────┐
                           │    FastAPI API     │
                           │ Authentication     │
                           │ RBAC               │
                           │ Query Routing      │
                           └─────────┬──────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
                ▼                    ▼                    ▼
         ┌────────────┐       ┌────────────┐       ┌──────────────┐
         │ Direct LLM │       │ RAG Engine │       │ Agent System │
         └────────────┘       └─────┬──────┘       └──────┬───────┘
                                    │                      │
                           ┌────────┴────────┐       ┌─────┴─────────┐
                           │ Hybrid Retrieval│       │ Tool Registry │
                           │ Dense + BM25    │       │ Policy Engine │
                           │ RRF + Reranking │       │ Guardrails    │
                           └────────┬────────┘       │ Approvals     │
                                    │                └──────┬────────┘
                                    ▼                       │
                                 Qdrant                     │
                                                            │
                         ┌──────────────────────────────────┘
                         │
                ┌────────┴────────┐
                │ Multi-Agent DAG │
                │ + Memory        │
                └────────┬────────┘
                         │
              ┌──────────┼───────────┐
              ▼          ▼           ▼
         PostgreSQL    Redis       ARQ Worker
                                      │
                                      ▼
                                 NVIDIA NIM
```

---

# 🔑 Key Capabilities

## 1. Enterprise RAG

Knowledge AI uses a hybrid retrieval pipeline combining:

- Dense vector retrieval
- Sparse/BM25 retrieval
- Reciprocal Rank Fusion (RRF)
- Cross-encoder reranking
- Document/chunk metadata filtering
- RBAC-aware retrieval
- Citation validation
- Grounding verification

This allows the system to retrieve relevant enterprise knowledge while respecting document-level access boundaries.

---

## 2. Intelligent Query Routing

Incoming requests are classified before execution.

```text
                    User Query
                        │
                        ▼
                 Query Router
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Direct          RAG          Agent
          │             │             │
       LLM answer    Retrieval    Tool/Workflow
                                    execution
```

The router distinguishes between:

- General knowledge
- Conversational requests
- Enterprise knowledge queries
- Agentic tasks

This prevents unnecessary RAG or agent execution for simple requests.

---

## 3. RBAC & Enterprise Access Control

Access control is enforced server-side.

The platform supports role-aware permissions for:

- Chat
- Documents
- Document management
- User management
- Evaluation
- Enterprise resources

RBAC is enforced before protected resources are exposed to the model or user.

```text
USER
 │
 ▼
Authentication
 │
 ▼
Role / Permission Check
 │
 ├── Allowed ──► Resource
 │
 └── Denied ───► Block
```

The agent cannot elevate its own privileges or manufacture authorization.

---

# 🛡️ AI Security & Guardrails

Knowledge AI treats LLM output and external content as untrusted.

The guardrail system operates across multiple stages.

### Input Guardrails

- Input normalization
- Secret detection
- Prompt-injection detection

### Retrieved / External Context

- Indirect prompt-injection detection
- Document poisoning detection
- External-content trust boundaries

### Output Guardrails

- Secret detection
- Grounding validation
- Citation validation

The project also includes dedicated red-team datasets and automated security tests covering:

- Prompt injection
- Secret extraction
- Privilege escalation
- Approval abuse
- Memory isolation
- Tool misuse
- Unauthorized agent delegation
- Risk-policy bypass attempts

---

# 🤖 Agentic AI

Knowledge AI supports both single-agent and multi-agent workflows.

## Agent Architecture

```text
                    Supervisor
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
       Research        RAG         Analysis
        Agent          Agent         Agent
          │             │             │
          └─────────────┼─────────────┘
                        ▼
                  Synthesis Agent
```

Agents operate within explicit capability boundaries.

The platform prevents agents from:

- Calling unauthorized tools
- Escalating privileges
- Delegating to unauthorized agents
- Bypassing approval requirements
- Persisting prohibited information as durable memory
- Executing unregistered tools

---

# 🔧 Controlled Tool Execution

LLMs do not execute tools directly.

Instead:

```text
LLM
 │
 ▼
Tool Proposal
 │
 ▼
Tool Registry
 │
 ▼
Authorization
 │
 ▼
Risk / Policy Evaluation
 │
 ├── ALLOW
 ├── DENY
 ├── REQUIRES_APPROVAL
 └── BLOCKED
 │
 ▼
Guardrails
 │
 ▼
Tool Execution
 │
 ▼
Output Validation
```

The platform includes controlled tools such as:

- Enterprise search
- Document lookup
- Calculator
- Conversation search
- Web search/fetch
- Calendar operations
- Email actions

External and high-risk operations are subject to additional controls.

---

# 👤 Human-in-the-Loop Approvals

High-risk external actions can require explicit user approval.

For example:

```text
Agent
  │
  ▼
send_email
  │
  ▼
Risk Evaluation
  │
  ▼
REQUIRES_APPROVAL
  │
  ▼
Human Approval
  │
  ├── Reject ──► Stop
  │
  └── Approve
          │
          ▼
      TOCTOU Revalidation
          │
          ▼
       Execution
```

Approvals are bound to the specific:

- User
- Conversation
- Agent run
- Tool
- Tool version
- Canonicalized arguments
- Policy version
- Expiration window

Replay and argument-tampering attempts are rejected.

---

# 🧠 Persistent Memory

Knowledge AI supports persistent user-scoped memory using:

- PostgreSQL as the durable source of truth
- Qdrant for semantic retrieval
- Memory policy enforcement
- Hash-based deduplication
- User isolation
- Workflow recovery

Memory retrieval is strictly scoped to the authenticated user.

Tool outputs are not automatically promoted into durable semantic memory.

---

# ⚙️ Long-Running Workflows

Agent workflows can execute asynchronously using:

- Redis
- ARQ
- Durable PostgreSQL job state

This allows long-running agent workflows to continue independently of the HTTP request lifecycle.

The system also includes recovery handling for interrupted workflows and concurrency protection for agent execution.

---

# 📊 Evaluation & Observability

The platform includes an evaluation and reliability layer covering:

## Evaluation

- Routing accuracy
- Tool-selection accuracy
- Agent-selection accuracy
- Budget enforcement
- RAG quality
- Groundedness
- Relevance
- Completeness
- Citation quality

## Reliability

- Retry policies
- Circuit breakers
- Failure classification
- P50/P95/P99 latency
- Token usage
- LLM cost tracking
- Model routing
- Regression datasets
- Production health checks

The evaluation framework is isolated from production side effects.

---

# 🔐 Production Architecture

The production architecture uses Dockerized services with isolated networking.

```text
Internet
   │
   ▼
 HTTPS / TLS
   │
   ▼
 Nginx
   │
   ├──────────────► Frontend
   │
   ▼
 Backend API
   │
   ├──── PostgreSQL
   ├──── Qdrant
   ├──── Redis
   └──── ARQ Worker
             │
             ▼
         NVIDIA NIM
```

Internal infrastructure services are isolated from public access.

Application containers run as non-root users.

Nginx provides:

- TLS termination
- Security headers
- Rate limiting
- Reverse proxying
- API routing

---

# 🧰 Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript |
| Backend | FastAPI, Python |
| RAG | Hybrid Dense + BM25 + RRF + Reranking |
| Document Processing | Docling |
| Vector Database | Qdrant |
| Relational Database | PostgreSQL |
| ORM | SQLAlchemy |
| Migrations | Alembic |
| Cache / Queue | Redis |
| Background Jobs | ARQ |
| LLM | NVIDIA NIM / Nemotron |
| Authentication | JWT |
| Authorization | RBAC |
| Reverse Proxy | Nginx |
| Containers | Docker / Docker Compose |
| Testing | Pytest + E2E Harness |
| CI/CD | GitHub Actions |

---

# 🧪 Validation

The platform has undergone staged security, regression, and deployment validation.

## Automated Regression

```text
33 / 33 tests passing
0 failed
0 errors
0 skipped
```

Validation covered areas including:

- Authentication
- RBAC
- Guardrails
- Agent policies
- Memory isolation
- Tool execution
- Approval workflows
- Reliability
- Multi-agent security

## Staging E2E

The staging E2E harness contains 38 checks.

Current documented result:

```text
32 passed
4 harness-level assertion/path defects
2 blocked black-box agent scenarios
```

The four reported failures are documented as test-harness issues rather than application logic failures.

The two blocked scenarios involve deterministic triggering of approval/background-job behavior through black-box agent reasoning and are covered by dedicated application tests.

---

# 🚀 Local Development

## Prerequisites

- Docker
- Docker Compose V2
- NVIDIA NIM API key

## Setup

```bash
git clone <repository-url>
cd knowledge-ai

cp .env.example .env
```

Configure the required environment variables locally.

**Never commit `.env` or real API credentials.**

Start the development environment:

```bash
docker compose up --build -d
```

The application will be available through the configured frontend/API ports.

---

# 🧪 Running Tests

Run the full regression suite:

```bash
docker exec -it enterprise-rag-backend \
  python -m pytest tests/ -v
```

Run the staging E2E harness:

```bash
docker exec -it enterprise-rag-backend \
  python -m scripts.staging_e2e
```

---

# 📁 Project Structure

```text
knowledge-ai/
│
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   ├── api/
│   │   ├── core/
│   │   ├── evaluations/
│   │   ├── models/
│   │   ├── rag/
│   │   └── services/
│   │
│   ├── scripts/
│   └── tests/
│
├── frontend/
│
├── data/
│
├── docs/
│
├── nginx/
│
├── .github/
│   └── workflows/
│
├── docker-compose.yml
├── docker-compose.production.yml
└── README.md
```

---

# 📚 Documentation

Detailed operational and architectural documentation is available in `/docs`.

Important production documents include:

- `STAGE_11_DATABASE_DEPLOYMENT_RUNBOOK.md`
- `STAGE_11_BACKUP_RESTORE_RUNBOOK.md`
- `STAGE_11_ROLLBACK_RUNBOOK.md`
- `STAGE_11_PRODUCTION_GO_LIVE_AUDIT.md`

These documents cover deployment, backup/recovery, rollback procedures, and production operations.

---

# 📸 Screenshots

## Authentication

<img width="1919" height="872" alt="image" src="https://github.com/user-attachments/assets/830e7618-ac35-4186-be81-bd46be2d089a" />


## Chat & RAG

<img width="1919" height="871" alt="image" src="https://github.com/user-attachments/assets/dc90421e-24c4-4d2c-b6b0-a5d893f162e4" />


## Agent Workflow

<img width="1919" height="873" alt="image" src="https://github.com/user-attachments/assets/3aeca710-0049-41d8-8822-152ccebad51b" />


## Evaluation / Security

<img width="1918" height="872" alt="image" src="https://github.com/user-attachments/assets/c104ab7a-3baa-4117-a393-cf3298cbeea2" />


---

# 🔭 Project Status

**Current Status: Go-Live Ready with Documented Prerequisites**

The application has completed its development and staging validation lifecycle.

Production deployment still requires environment-specific infrastructure configuration, including:

- Production secrets
- Production database credentials
- LLM credentials
- Domain/DNS
- TLS certificates
- Production infrastructure provisioning
- Backup configuration

No production credentials are stored in this repository.

---

# 🔒 Security

Security is treated as a core architectural requirement.

The platform includes:

- Server-side authentication and RBAC
- Input/output guardrails
- Prompt-injection defenses
- Secret detection
- Indirect-injection detection
- Tool authorization
- Risk-based tool policies
- Human approval workflows
- User-scoped memory isolation
- Network isolation
- Non-root containers
- Security headers
- Rate limiting
- Audit telemetry
- Automated red-team testing

Security-sensitive operations are enforced by backend services rather than relying on LLM behavior.

---

# 🤝 Contributing

This repository is primarily maintained as a portfolio and engineering project.

Issues and technical discussions are welcome, but changes affecting authentication, authorization, guardrails, tool governance, or security boundaries should preserve the existing security architecture and test coverage.

---

# 📄 License

This repository is publicly visible for portfolio and educational demonstration purposes.

The source code is not licensed for commercial redistribution or reuse without permission from the author.
