-- =============================================================================
-- Migration 0001: Initial Schema
-- AI Job Search & Resume Tailoring Platform
-- Apply to: clean Supabase PostgreSQL database
-- Standard PostgreSQL only — no Supabase-specific extensions
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- PROFILES
-- One row per user (1:1 with Supabase auth.users)
-- =============================================================================
CREATE TABLE profiles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    display_name    TEXT,
    contact_email   TEXT,         -- may differ from auth email
    contact_phone   TEXT,
    location        TEXT,
    linkedin_url    TEXT,
    portfolio_url   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_profiles_user_id ON profiles(user_id);

-- =============================================================================
-- RESUME_VERSIONS
-- Uploaded or pasted resumes. Each creates a new version.
-- =============================================================================
CREATE TABLE resume_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    version_number  INTEGER NOT NULL,
    source_type     TEXT NOT NULL CHECK (source_type IN ('pdf', 'docx', 'text')),
    storage_path    TEXT,         -- NULL for pasted text (stored inline)
    raw_text        TEXT,         -- extracted text (may be NULL for large files cached externally)
    file_size_bytes INTEGER,
    original_filename TEXT,       -- sanitized copy; not used for storage
    extraction_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (extraction_status IN ('pending', 'processing', 'completed', 'failed')),
    extraction_error TEXT,        -- sanitized error message only
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, version_number)
);

CREATE INDEX idx_resume_versions_user_id ON resume_versions(user_id);

-- =============================================================================
-- PROFILE_VERSIONS
-- Structured profile extracted/confirmed from a resume version.
-- Immutable once confirmed: tailored_documents reference a specific version.
-- =============================================================================
CREATE TABLE profile_versions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    resume_version_id   UUID REFERENCES resume_versions(id) ON DELETE SET NULL,
    version_number      INTEGER NOT NULL,
    is_confirmed        BOOLEAN NOT NULL DEFAULT FALSE,  -- user must explicitly confirm
    -- Structured content stored as JSONB for flexibility
    -- Schema validated in application layer
    content             JSONB NOT NULL DEFAULT '{}',
    -- content includes: summary, skills, employment_history, education,
    --   projects, certifications, achievements, target_roles,
    --   seniority_level, work_arrangement_preferences, location_preferences
    seniority_level     TEXT CHECK (seniority_level IN ('junior', 'mid', 'senior', 'lead', 'executive', 'unknown')),
    target_roles        TEXT[] NOT NULL DEFAULT '{}',
    skills              TEXT[] NOT NULL DEFAULT '{}',
    years_experience    NUMERIC(4,1),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, version_number)
);

CREATE INDEX idx_profile_versions_user_id ON profile_versions(user_id);
CREATE INDEX idx_profile_versions_resume ON profile_versions(resume_version_id);

-- =============================================================================
-- PROFILE_EVIDENCE
-- Provenance tracking for extracted claims.
-- Each row links a claim to the source text that supports it.
-- =============================================================================
CREATE TABLE profile_evidence (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    profile_version_id  UUID NOT NULL REFERENCES profile_versions(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    claim_type          TEXT NOT NULL,  -- e.g. 'skill', 'employer', 'degree', 'certification', 'achievement'
    claim_value         TEXT NOT NULL,
    confidence          TEXT NOT NULL CHECK (confidence IN ('explicit', 'confirmed', 'inferred', 'uncertain')),
    source_text         TEXT,           -- verbatim excerpt from resume (may be NULL for confirmed facts)
    source_location     TEXT,           -- e.g. 'page 1, section "Experience"'
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_profile_evidence_version ON profile_evidence(profile_version_id);
CREATE INDEX idx_profile_evidence_user ON profile_evidence(user_id);

-- =============================================================================
-- SEARCH_PREFERENCES
-- User's job search settings, persisted across sessions.
-- =============================================================================
CREATE TABLE search_preferences (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
    target_roles        TEXT[] NOT NULL DEFAULT '{}',
    locations           TEXT[] NOT NULL DEFAULT '{}',
    work_arrangements   TEXT[] NOT NULL DEFAULT '{}',  -- 'remote', 'hybrid', 'onsite'
    seniority_levels    TEXT[] NOT NULL DEFAULT '{}',
    min_salary          INTEGER,
    salary_currency     TEXT DEFAULT 'USD',
    excluded_employers  TEXT[] NOT NULL DEFAULT '{}',
    keywords_include    TEXT[] NOT NULL DEFAULT '{}',
    keywords_exclude    TEXT[] NOT NULL DEFAULT '{}',
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- SEARCH_RUNS
-- Tracks each job search operation.
-- =============================================================================
CREATE TABLE search_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    profile_version_id UUID REFERENCES profile_versions(id) ON DELETE SET NULL,
    preferences_snapshot JSONB NOT NULL DEFAULT '{}',  -- copy of preferences at run time
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    providers_used  TEXT[] NOT NULL DEFAULT '{}',
    jobs_found      INTEGER,
    matches_created INTEGER,
    error_summary   TEXT,         -- sanitized, no stack traces
    retry_count     INTEGER NOT NULL DEFAULT 0,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_search_runs_user_id ON search_runs(user_id);
CREATE INDEX idx_search_runs_status ON search_runs(status);

-- =============================================================================
-- JOBS
-- Normalized job store. A job can be shared across users.
-- User-specific state is in job_matches.
-- =============================================================================
CREATE TABLE jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Source identity
    source_name     TEXT NOT NULL,        -- 'remotive', 'arbeitnow', etc.
    source_job_id   TEXT NOT NULL,        -- provider's own ID
    canonical_url   TEXT NOT NULL,        -- direct application URL
    -- Content
    title           TEXT NOT NULL,
    employer        TEXT NOT NULL,
    location        TEXT,
    work_arrangement TEXT,                -- 'remote', 'hybrid', 'onsite'
    employment_type  TEXT,                -- 'full_time', 'part_time', 'contract', etc.
    seniority       TEXT,
    description     TEXT NOT NULL,
    salary_min      INTEGER,
    salary_max      INTEGER,
    salary_currency TEXT,
    -- Metadata
    published_at    TIMESTAMPTZ,
    retrieved_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_expired      BOOLEAN NOT NULL DEFAULT FALSE,
    attribution     TEXT NOT NULL,        -- attribution text per provider ToS
    -- Deduplication: unique per source
    UNIQUE (source_name, source_job_id)
);

CREATE INDEX idx_jobs_source ON jobs(source_name, source_job_id);
CREATE INDEX idx_jobs_retrieved_at ON jobs(retrieved_at);
CREATE INDEX idx_jobs_employer ON jobs(employer);

-- =============================================================================
-- JOB_MATCHES
-- User-specific match scores and explanations for a job.
-- =============================================================================
CREATE TABLE job_matches (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id              UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    search_run_id       UUID REFERENCES search_runs(id) ON DELETE SET NULL,
    profile_version_id  UUID REFERENCES profile_versions(id) ON DELETE SET NULL,
    -- Scores (deterministic, versioned)
    overall_score       NUMERIC(5,2) NOT NULL,
    scoring_version     TEXT NOT NULL,       -- e.g. 'v1.0.0'
    -- Breakdown stored as JSONB
    score_breakdown     JSONB NOT NULL DEFAULT '{}',
    -- Explanations
    matching_evidence   JSONB NOT NULL DEFAULT '[]',   -- list of positive match reasons
    missing_requirements JSONB NOT NULL DEFAULT '[]',  -- required skills not found
    uncertain_factors   JSONB NOT NULL DEFAULT '[]',   -- unclear eligibility factors
    freshness_warning   TEXT,                           -- if job is old or expired
    evaluated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- User actions
    is_saved            BOOLEAN NOT NULL DEFAULT FALSE,
    saved_at            TIMESTAMPTZ,
    UNIQUE (user_id, job_id, scoring_version)  -- one match per scoring version
);

CREATE INDEX idx_job_matches_user_id ON job_matches(user_id);
CREATE INDEX idx_job_matches_search_run ON job_matches(search_run_id);
CREATE INDEX idx_job_matches_score ON job_matches(user_id, overall_score DESC);
CREATE INDEX idx_job_matches_saved ON job_matches(user_id, is_saved);

-- =============================================================================
-- TAILORED_DOCUMENTS
-- Generated tailored resumes. Each references a specific job and profile version.
-- =============================================================================
CREATE TABLE tailored_documents (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id              UUID NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
    profile_version_id  UUID NOT NULL REFERENCES profile_versions(id) ON DELETE RESTRICT,
    -- Status
    status              TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'generating', 'review_required', 'approved', 'failed')),
    -- Content
    structured_content  JSONB,          -- structured resume data (before PDF render)
    storage_path        TEXT,           -- path to PDF in Supabase Storage (private)
    -- Validation
    flagged_claims      JSONB NOT NULL DEFAULT '[]',  -- claims requiring user review
    validation_passed   BOOLEAN,
    validation_version  TEXT,
    -- Provenance
    scoring_version     TEXT,
    template_version    TEXT,
    model_used          TEXT,
    generation_latency_ms INTEGER,
    error_summary       TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tailored_documents_user_id ON tailored_documents(user_id);
CREATE INDEX idx_tailored_documents_job ON tailored_documents(job_id);
CREATE INDEX idx_tailored_documents_profile_version ON tailored_documents(profile_version_id);

-- =============================================================================
-- APPLICATIONS
-- Application tracking per user per job.
-- =============================================================================
CREATE TYPE application_status AS ENUM (
    'saved', 'preparing', 'applied', 'interviewing', 'offered', 'rejected', 'withdrawn', 'archived'
);

CREATE TABLE applications (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    job_id                  UUID NOT NULL REFERENCES jobs(id) ON DELETE RESTRICT,
    tailored_document_id    UUID REFERENCES tailored_documents(id) ON DELETE SET NULL,
    status                  application_status NOT NULL DEFAULT 'saved',
    notes                   TEXT,
    applied_at              TIMESTAMPTZ,    -- NULL until user manually marks as applied
    follow_up_date          TIMESTAMPTZ,
    offer_amount            INTEGER,
    offer_currency          TEXT,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, job_id)  -- one application record per job per user
);

CREATE INDEX idx_applications_user_id ON applications(user_id);
CREATE INDEX idx_applications_status ON applications(user_id, status);
CREATE INDEX idx_applications_job ON applications(job_id);

-- =============================================================================
-- APPLICATION_EVENTS
-- Immutable audit trail for application status transitions.
-- =============================================================================
CREATE TABLE application_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id  UUID NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    from_status     application_status,
    to_status       application_status NOT NULL,
    note            TEXT,
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_application_events_application ON application_events(application_id);

-- =============================================================================
-- TASKS
-- PostgreSQL-backed durable task queue (replaces Redis/Celery for free tier)
-- =============================================================================
CREATE TABLE tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    task_type       TEXT NOT NULL,   -- 'search_run', 'resume_extraction', 'tailoring'
    reference_id    UUID,            -- search_run_id or tailored_document_id
    payload         JSONB NOT NULL DEFAULT '{}',
    idempotency_key TEXT UNIQUE,     -- prevents duplicate task submission
    status          TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    retry_count     INTEGER NOT NULL DEFAULT 0,
    max_retries     INTEGER NOT NULL DEFAULT 3,
    error_summary   TEXT,
    worker_id       TEXT,            -- identifies claiming worker instance
    claimed_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    run_after       TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- supports delayed execution
);

CREATE INDEX idx_tasks_status_run_after ON tasks(status, run_after)
    WHERE status IN ('pending', 'failed');
CREATE INDEX idx_tasks_user_id ON tasks(user_id);

-- =============================================================================
-- AUDIT_EVENTS
-- Security-relevant events (auth failures, admin actions, deletions).
-- user_id is nullable to support post-deletion anonymization.
-- =============================================================================
CREATE TABLE audit_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID,            -- NULL after account deletion
    action          TEXT NOT NULL,   -- 'login', 'logout', 'download', 'delete_account', etc.
    resource_type   TEXT,
    resource_id     UUID,
    ip_address      TEXT,            -- hashed, not raw IP, for privacy
    success         BOOLEAN NOT NULL DEFAULT TRUE,
    metadata        JSONB NOT NULL DEFAULT '{}',  -- no PII; IDs and action details only
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_events_user_id ON audit_events(user_id);
CREATE INDEX idx_audit_events_action ON audit_events(action);
CREATE INDEX idx_audit_events_occurred_at ON audit_events(occurred_at);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

-- Enable RLS on all user-data tables
ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE resume_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE profile_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE search_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE job_matches ENABLE ROW LEVEL SECURITY;
ALTER TABLE tailored_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE application_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_events ENABLE ROW LEVEL SECURITY;
-- jobs table is shared; no RLS needed (read-only for users, written by service role)

-- profiles
CREATE POLICY "profiles_select_own" ON profiles FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "profiles_insert_own" ON profiles FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "profiles_update_own" ON profiles FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "profiles_delete_own" ON profiles FOR DELETE USING (auth.uid() = user_id);

-- resume_versions
CREATE POLICY "resume_versions_select_own" ON resume_versions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "resume_versions_insert_own" ON resume_versions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "resume_versions_update_own" ON resume_versions FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "resume_versions_delete_own" ON resume_versions FOR DELETE USING (auth.uid() = user_id);

-- profile_versions
CREATE POLICY "profile_versions_select_own" ON profile_versions FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "profile_versions_insert_own" ON profile_versions FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "profile_versions_update_own" ON profile_versions FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "profile_versions_delete_own" ON profile_versions FOR DELETE USING (auth.uid() = user_id);

-- profile_evidence
CREATE POLICY "evidence_select_own" ON profile_evidence FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "evidence_insert_own" ON profile_evidence FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "evidence_delete_own" ON profile_evidence FOR DELETE USING (auth.uid() = user_id);

-- search_preferences
CREATE POLICY "prefs_select_own" ON search_preferences FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "prefs_insert_own" ON search_preferences FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "prefs_update_own" ON search_preferences FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "prefs_delete_own" ON search_preferences FOR DELETE USING (auth.uid() = user_id);

-- search_runs
CREATE POLICY "search_runs_select_own" ON search_runs FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "search_runs_insert_own" ON search_runs FOR INSERT WITH CHECK (auth.uid() = user_id);

-- job_matches
CREATE POLICY "job_matches_select_own" ON job_matches FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "job_matches_insert_own" ON job_matches FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "job_matches_update_own" ON job_matches FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "job_matches_delete_own" ON job_matches FOR DELETE USING (auth.uid() = user_id);

-- tailored_documents
CREATE POLICY "documents_select_own" ON tailored_documents FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "documents_insert_own" ON tailored_documents FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "documents_delete_own" ON tailored_documents FOR DELETE USING (auth.uid() = user_id);

-- applications
CREATE POLICY "applications_select_own" ON applications FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "applications_insert_own" ON applications FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "applications_update_own" ON applications FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "applications_delete_own" ON applications FOR DELETE USING (auth.uid() = user_id);

-- application_events
CREATE POLICY "app_events_select_own" ON application_events FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "app_events_insert_own" ON application_events FOR INSERT WITH CHECK (auth.uid() = user_id);

-- tasks: users can see their own tasks; workers use service role
CREATE POLICY "tasks_select_own" ON tasks FOR SELECT USING (auth.uid() = user_id);

-- audit_events: users can see their own; service role sees all
CREATE POLICY "audit_events_select_own" ON audit_events FOR SELECT USING (auth.uid() = user_id);

-- =============================================================================
-- DELETION BEHAVIOR SUMMARY (see SECURITY.md for full policy)
-- auth.users DELETE CASCADE -> profiles, resume_versions, profile_versions,
--   profile_evidence, search_preferences, search_runs, job_matches,
--   tailored_documents, applications, application_events, tasks
-- audit_events: user_id set to NULL (audit trail preserved, anonymized)
-- jobs: kept (shared; user references via job_matches and applications)
-- tailored_documents storage files: scheduled for async deletion via task
-- =============================================================================
