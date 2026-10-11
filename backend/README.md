# JobFit Backend

AI job-search and resume-tailoring backend built with FastAPI, PostgreSQL/Supabase, and Gemini.

## Requirements
- Python >= 3.10, < 3.14
- `uv` package manager

## Setup
```bash
# Install dependencies
uv sync

# Run development server
uv run uvicorn app.main:create_app --factory --reload --port 8000

# Run tests
uv run pytest
```
