# Security Architecture & Threat Model

> **Phase 0 Document** — Covers every trust boundary before implementation begins.

## 1. Threat Model Summary

| Asset | Sensitivity | Primary Threats |
|-------|-------------|-----------------|
| Resume/CV content | High (PII, career history) | Unauthorized read, cross-user leak |
| Generated PDF documents | High | Cross-user download, public storage exposure |
| Auth tokens / JWTs | Critical | Token theft, replay, forged claims |
| Profile evidence records | High (PII) | IDOR, mass extraction |
| Job application status/notes | Medium | Cross-user read/write |
| LLM API keys | Critical | Exposure in logs/code/bundles |
| Supabase service role key | Critical | Exposure grants full DB access |
| Job provider credentials | Medium | Rate-limit abuse if leaked |
| Task queue contents | Medium | Task injection, result spoofing |
| Audit event log | Medium | Tampering to hide unauthorized access |

## 2. Trust Boundaries

```
[Internet / Untrusted]
    |
    | HTTPS only
    v
[FastAPI App — Partially Trusted]
    - Validates Supabase JWT on every protected request
    - Enforces ownership in every repository query
    - Treats all request body fields as untrusted
    - Never exposes stack traces in HTTP responses
    |
    | Internal (service role key, server-side only)
    v
[Supabase PostgreSQL — Trusted only via service role]
    - RLS enforced as defense-in-depth (not sole protection)
    - Service role key NEVER leaves the server environment
    |
    v
[Supabase Storage — Private bucket]
    - Files never publicly accessible
    - Signed URLs expire in 1 hour (configurable)
    |
    v
[External APIs — Untrusted]
    - Job providers: responses validated before persistence
    - LLM provider: outputs validated before use as claims
    - All responses treated as potentially malicious/malformed
```

## 3. Authentication & Authorization

### 3.1 Auth Flow
- Supabase Auth issues JWTs on successful login
- Backend validates JWT signature using Supabase public key on every request
- `user_id` is extracted from the **validated JWT** only — never from request body
- Sessions expired server-side are rejected (Supabase handles token revocation)

### 3.2 Authorization Rules
Every protected resource follows the same pattern:
```python
# CORRECT: ownership from verified auth context
async def get_document(doc_id: UUID, user_id: UUID = Depends(get_current_user)):
    doc = await document_repo.get(doc_id)
    if doc.owner_id != user_id:
        raise HTTPException(403)
    return doc


# WRONG (never do this): trust body
async def get_document(doc_id: UUID, body: Body):
    doc = await document_repo.get(body.user_id, doc_id)  # NO
```

### 3.3 Row Level Security Policies
RLS is enabled on every table. The service role key is used exclusively server-side and enforces ownership in application code in addition to RLS. This is defense-in-depth.

Example pattern (actual SQL in migrations):
```sql
-- profiles: user can only read/write their own row
CREATE POLICY "profiles_owner" ON profiles
  USING (auth.uid() = user_id);
```

### 3.4 Service Role Key Protection
- Stored only in server environment variables
- Never in client code, frontend bundles, API responses, or logs
- Never in source control (`.env.example` shows variable names only)
- Rotated if ever suspected to be exposed

## 4. Input Validation

| Source | Threat | Mitigation |
|--------|--------|------------|
| Resume file uploads | Malformed PDF/DOCX, decompression bomb, macro execution | File-size limit (10 MB), MIME + magic-bytes check, no macro execution, filename sanitization, processing timeout |
| Pasted resume text | XSS, injection, oversized payload | Max length (100 KB), no HTML rendering of raw text |
| Job descriptions from providers | Injection, oversized content | Schema validation, max field lengths, sanitize before storage |
| LLM outputs | Hallucinated claims, schema violations | Pydantic schema validation on every LLM response; deterministic claim checker |
| Task inputs from DB | Stale/corrupted task inputs | Validate on claim; idempotency keys prevent duplicate execution |
| URL parameters / UUIDs | IDOR | Ownership check after every ID lookup |

## 5. File Security

- **Private storage**: All uploaded and generated files are in private Supabase Storage buckets (not public)
- **Signed URLs**: Download endpoints return short-lived signed URLs (default: 1 hour TTL), not direct file references
- **Filename sanitization**: User-supplied filenames are rejected; server-generated UUIDs used for storage paths
- **File-type validation**: Extension + Content-Type header + magic bytes (PDF: `%PDF`, DOCX: ZIP magic `PK\x03\x04`)
- **Size limits**: Configurable `MAX_UPLOAD_SIZE_MB` (default: 10 MB); enforced before any parsing begins
- **Processing timeout**: Resume parsing kills after `MAX_PARSE_SECONDS` (default: 30 s)
- **No macro execution**: python-docx reads structure only; no VBA/macro engine invoked

## 6. Secrets Management

| Secret | Storage | Rotation Plan |
|--------|---------|---------------|
| `SUPABASE_SERVICE_ROLE_KEY` | Server env var only | Rotate via Supabase dashboard; requires redeploy |
| `SUPABASE_JWT_SECRET` | Server env var only | Rotate requires user re-auth |
| `GEMINI_API_KEY` (or equivalent) | Server env var only | Rotate in provider dashboard |
| `ADZUNA_APP_ID` / `APP_KEY` | Server env var only | Rotate in Adzuna dashboard |
| `SECRET_KEY` (app signing) | Server env var only | Rotate requires redeploy |

**Never in**: source code, git history, `.env` (only `.env.example`), Docker images, CI logs, or error responses.

## 7. Network Security

- **CORS**: Explicit `ALLOWED_ORIGINS` allowlist (not `*`)
- **HTTPS only**: HTTP requests rejected or redirected in production
- **Bounded timeouts**: All external HTTP requests (providers, LLM) use `httpx` with configurable connect/read timeouts (default: connect 5 s, read 30 s)
- **Rate limiting**: API-level rate limiting per user (planned Phase 9; interim: Supabase Auth's built-in throttle)
- **CSRF**: Not applicable (Bearer token auth, no cookie-based session)

## 8. Privacy & Data Handling

- **Resume content**: Never logged; stored encrypted at rest (Supabase provides this)
- **LLM inputs**: Full resume text NOT sent to LLM tracing/observability providers by default; only structured metadata sent
- **Audit events**: Record action type, resource ID, user ID, timestamp — not document content
- **Account deletion**: Cascades to all owned resources; storage files are scheduled for deletion; audit events are anonymized (user_id set to NULL)
- **Gemini free tier data policy**: On the free tier, Google may use prompts for model improvement. **Mitigation**: Do not send full resume text to Gemini in free-tier deployments; use structured extracted data only. Document this limitation. Recommend upgrading to a paid Gemini tier for privacy-sensitive production use.

## 9. Security Test Requirements

The following must pass before any public release:

| Test ID | Description |
|---------|-------------|
| SEC-AUTH-01 | Unauthenticated request to every protected endpoint returns 401 |
| SEC-AUTH-02 | Expired JWT returns 401 |
| SEC-AUTH-03 | Forged JWT (wrong signature) returns 401 |
| SEC-AUTHZ-01 | User A cannot read User B's profile |
| SEC-AUTHZ-02 | User A cannot read User B's resumes |
| SEC-AUTHZ-03 | User A cannot read User B's job matches |
| SEC-AUTHZ-04 | User A cannot download User B's tailored documents |
| SEC-AUTHZ-05 | User A cannot update User B's application status |
| SEC-AUTHZ-06 | User A cannot delete User B's profile |
| SEC-AUTHZ-07 | Forged user_id in request body does not grant access |
| SEC-AUTHZ-08 | Valid token for resource belonging to another user returns 403 |
| SEC-FILE-01 | Oversized file (>MAX_UPLOAD_SIZE_MB) returns 413 |
| SEC-FILE-02 | Non-PDF/DOCX extension returns 422 |
| SEC-FILE-03 | File with wrong magic bytes (MIME spoofing) returns 422 |
| SEC-FILE-04 | Zero-byte file returns 422 |
| SEC-FILE-05 | Malformed PDF returns 422, not 500 |
| SEC-FILE-06 | Download without auth returns 401 |
| SEC-FILE-07 | Direct storage path access (bypassing signed URL) is blocked |
| SEC-SECRET-01 | No secrets present in repository (git-secrets scan) |
| SEC-SECRET-02 | No secrets in test logs (log output scan) |
| SEC-SECRET-03 | Service role key absent from any HTTP response |
| SEC-LLM-01 | LLM output that fails schema validation is rejected, not executed |
| SEC-LLM-02 | LLM output cannot trigger privileged actions |

**Release gate**: 100% of the above tests must pass. Any cross-user data access is a release blocker.
