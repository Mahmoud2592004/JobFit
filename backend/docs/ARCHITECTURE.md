# Architecture — AI Job Search & Resume Tailoring Backend

> **Phase 0 Document** — Approved before any implementation begins.

## 1. System Overview

This is a **modular monolith** FastAPI backend designed for a multi-user AI job-search and resume-tailoring platform. It is built for portability: no single free-tier provider is assumed to remain free. The architecture is layered and follows strict separation of concerns.

```
+---------------------------------------------------------+
|                   Client (Frontend)                      |
|             REST / HTTP  (versioned /api/v1/*)           |
+-------------------------+-------------------------------+
                          | HTTPS + CORS allowlist
+---------------------------------------------------------+
|                  FastAPI + Uvicorn                       |
|  Routes -> Dependencies -> Services -> Repositories      |
|           Supabase Auth (JWT validation)                 |
+----------+---------------------------+------------------+
           |                          |
+----------+----------+   +-----------+----------------+
| Supabase PostgreSQL |   | Supabase Storage (private)  |
| (RLS on every table)|   | (resume uploads, PDFs)      |
+---------------------+   +-----------------------------+
           |
+----------+--------------------------------------------------+
|                   Background Worker                         |
|  PostgreSQL-backed task queue (tasks table + SKIP LOCKED)  |
|  Handles: job-search runs, resume tailoring, PDF gen       |
+------+-------------------------------------+---------------+
       |                                     |
+------+----------+               +----------+----------+
|  Job Providers  |               |   LLM Provider      |
|  - Remotive API |               |   (Gemini Flash /   |
|  - Arbeitnow    |               |    provider-indep.  |
+-----------------+               |    adapter)         |
                                  +---------------------+
```

## 2. Module Structure

```
backend/
app/
  main.py                    # FastAPI app factory, lifespan
  api/
    v1/
      routes/
        health.py
        profile.py
        resumes.py
        search_runs.py
        jobs.py
        job_matches.py
        tailored_documents.py
        applications.py
      router.py
    dependencies.py          # Auth, DB, ownership resolvers
  core/
    config.py                # Pydantic Settings, fail-fast validation
    security.py              # JWT validation, auth helpers
    logging.py               # Structured JSON logging (no PII)
    exceptions.py            # Domain exceptions -> HTTP responses
  schemas/                   # Pydantic I/O schemas (request/response)
    profile.py
    resume.py
    job.py
    match.py
    document.py
    application.py
  domain/                    # Business domain models (internal)
    profile.py
    job.py
    match.py
    document.py
  repositories/              # Data-access layer (SQL only, no business logic)
    base.py
    profile_repo.py
    resume_repo.py
    job_repo.py
    match_repo.py
    document_repo.py
    application_repo.py
    search_run_repo.py
    task_repo.py
  services/                  # Business logic (no SQL, no HTTP routes)
    resume_parser.py
    profile_service.py
    job_discovery.py
    job_matching.py
    resume_tailoring.py
    document_renderer.py
    application_service.py
  providers/
    jobs/
      base.py                # JobProviderAdapter protocol
      remotive.py
      arbeitnow.py
    llm/
      base.py                # LLMAdapter protocol
      gemini.py              # Default implementation
    storage/
      supabase_storage.py
  workers/
    runner.py                # Worker loop (asyncio)
    handlers/
      search_handler.py
      tailoring_handler.py
db/
  client.py                  # Supabase client initialization
tests/
  unit/
  integration/
  security/
  fixtures/
    resumes/                 # 30+ synthetic benchmark resumes
    jobs/                    # Provider fixture responses
  benchmarks/
    resume_extraction/
    job_matching/
    resume_tailoring/
docs/
  ARCHITECTURE.md
  SECURITY.md
  EVALUATION.md
  API_CONTRACTS.md
  PROJECT_STATUS.md
  decisions/
supabase/
  migrations/
pyproject.toml
.env.example
.gitignore
```

## 3. Data Flow — Job Search Run

```
User -> POST /api/v1/search-runs
  -> Auth middleware validates Supabase JWT
  -> SearchRunService creates task record (status=pending)
  -> Returns {task_id, search_run_id} immediately (202 Accepted)

Worker loop polls task queue every N seconds:
  -> Claims task atomically (SELECT FOR UPDATE SKIP LOCKED)
  -> Marks task in_progress
  -> Calls JobDiscovery.run() in parallel:
      - RemotiveProvider.fetch()
      - ArbeitnowProvider.fetch()
  -> Deduplicates and normalizes JobRecord list
  -> Upserts into jobs table
  -> Runs JobMatcher.score_all(profile, jobs)
  -> Persists job_matches per user
  -> Marks search_run complete / failed (sanitized error)
  -> Marks task done

User -> GET /api/v1/search-runs/{id}   (polls status)
     -> GET /api/v1/job-matches?search_run_id={id}  (ranked results)
```

## 4. Data Flow — Resume Tailoring

```
User -> POST /api/v1/tailored-documents
  {job_id, profile_version_id}
  -> Validates ownership of both resources
  -> Creates task (status=pending)
  -> Returns {task_id, document_id} (202 Accepted)

Worker:
  -> Loads confirmed profile version (immutable snapshot)
  -> Loads job description
  -> Loads evidence records for profile version
  -> Calls ResumeTailoring.generate(profile, job, evidence)
      -> LLM generates structured resume data (NOT raw HTML)
      -> Deterministic validator checks claims vs evidence
      -> Flags unsupported claims for user review
  -> Calls DocumentRenderer.to_pdf(structured_data, template)
  -> Uploads PDF to Supabase Storage (private bucket)
  -> Persists tailored_document record with storage path
  -> Marks task done

User -> GET /api/v1/tailored-documents/{id}/download
  -> Validates ownership
  -> Returns short-lived signed URL (never raw file path)
```

## 5. Key Architectural Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| API framework | FastAPI + Uvicorn | Type-safe, async, OpenAPI-native |
| Auth | Supabase Auth (JWT) | Handles signup/login/reset; RLS integrates natively |
| Database | Supabase PostgreSQL | Free tier, RLS, managed, portable SQL |
| DB access | supabase-py (service role, server-side only) | Official SDK; ownership enforced in code |
| Background tasks | PostgreSQL task queue (SKIP LOCKED) | Durable, no extra infra, free |
| Job source 1 | Remotive API | Free, no auth, remote-focused, attribution required |
| Job source 2 | Arbeitnow API | Free, no auth, international, attribution required |
| LLM provider | Gemini Flash 1.5 (default) | 1,500 req/day free; swappable via adapter |
| PDF rendering | Jinja2 HTML + weasyprint | No external service dependency, deterministic |
| Observability | structlog + request IDs | No PII in logs, correlatable across services |
| Deployment (beta) | Render.com (web service) + Supabase | $0 to launch |

## 6. Layer Responsibilities

| Layer | What It Can Access | What It Cannot Do |
|-------|-------------------|--------------------|
| Routes | Schemas, Dependencies, Services | Direct SQL, external HTTP calls |
| Dependencies | Auth context, DB session | Business logic |
| Services | Repositories, Providers, Domain | Direct SQL, HTTP routes |
| Repositories | DB session | Business logic, external HTTP |
| Providers | External APIs (bounded) | DB access, route handling |
| Workers | Services, Repositories | Direct route access |

## 7. Deployment Topology (Beta Phase)

```
Render.com (free web service, 512 MB RAM)
  FastAPI app (Uvicorn, single worker)
    In-process asyncio background task (polls task queue)
    [Phase 8 upgrades to separate Render worker service]

Supabase (free tier)
  PostgreSQL (500 MB)
  Storage (1 GB private)
  Auth (50,000 MAU)
```

**Known Free-Tier Constraints (documented):**
- Render: spins down after 15 min inactivity; cold start ~30-60 s
- Supabase: project pauses after 1 week idle; no auto-backup
- Gemini: 1,500 req/day; data used for training in free tier
- Remotive: max 4 fetches/day recommended; 24-hour job delay
- Arbeitnow: no stated rate limit; "as is" service; revocable access

**Portability path**: All SQL is standard PostgreSQL. Replacing Supabase requires only changing the connection string and swapping supabase-py for asyncpg/psycopg3. No provider-specific SQL extensions are used.
