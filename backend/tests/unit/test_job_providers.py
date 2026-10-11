"""Unit tests for Remotive and Arbeitnow job aggregator providers."""

from __future__ import annotations

import httpx
import pytest
import respx

from app.providers.jobs.arbeitnow import ARBEITNOW_API_URL, ArbeitnowProvider
from app.providers.jobs.remotive import (
    REMOTIVE_API_URL,
    RemotiveProvider,
    _parse_salary,
)


def test_parse_salary():
    assert _parse_salary(None) == (None, None, None)
    assert _parse_salary("$120k - $150k") == (120000, 150000, "USD")
    assert _parse_salary("€80,000 - €95,000") == (80000, 95000, "EUR")
    assert _parse_salary("£50k") == (50000, None, "GBP")
    assert _parse_salary("Competitive") == (None, None, None)


@pytest.mark.asyncio
@respx.mock
async def test_remotive_fetch_jobs_success():
    mock_payload = {
        "jobs": [
            {
                "id": 101,
                "url": "https://remotive.com/jobs/101",
                "title": "Backend Python Engineer",
                "company_name": "Apex Cloud",
                "candidate_required_location": "USA Only",
                "job_type": "full_time",
                "publication_date": "2026-10-01T10:00:00Z",
                "salary": "$130k - $160k",
                "description": "<p>Build high-scale APIs with FastAPI.</p>",
            }
        ]
    }
    respx.get(REMOTIVE_API_URL).respond(status_code=200, json=mock_payload)

    provider = RemotiveProvider()
    jobs = await provider.fetch_jobs(query="Python", limit=10)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_name == "remotive"
    assert job.source_job_id == "101"
    assert job.title == "Backend Python Engineer"
    assert job.employer == "Apex Cloud"
    assert job.work_arrangement == "remote"
    assert job.employment_type == "full_time"
    assert job.salary_min == 130000
    assert job.salary_max == 160000
    assert job.salary_currency == "USD"
    assert "FastAPI" in job.description


@pytest.mark.asyncio
@respx.mock
async def test_remotive_fetch_jobs_error_handling():
    # 500 error
    respx.get(REMOTIVE_API_URL).respond(status_code=500, text="Internal Server Error")
    provider = RemotiveProvider()
    jobs = await provider.fetch_jobs(query="Fail")
    assert jobs == []

    # Network timeout exception
    respx.get(REMOTIVE_API_URL).mock(side_effect=httpx.ConnectTimeout("Connection timed out"))
    jobs_timeout = await provider.fetch_jobs(query="Timeout")
    assert jobs_timeout == []


@pytest.mark.asyncio
@respx.mock
async def test_arbeitnow_fetch_jobs_success():
    mock_payload = {
        "data": [
            {
                "slug": "senior-frontend-developer-99",
                "company_name": "VentureLab",
                "title": "Senior Frontend Developer",
                "description": "<p>React & TypeScript mastery required.</p>",
                "remote": True,
                "url": "https://arbeitnow.com/jobs/99",
                "tags": ["react", "typescript"],
                "job_types": ["Full Time"],
                "location": "Berlin, Germany",
                "created_at": 1728561600,
            }
        ]
    }
    respx.get(ARBEITNOW_API_URL).respond(status_code=200, json=mock_payload)

    provider = ArbeitnowProvider()
    jobs = await provider.fetch_jobs(query="React", limit=10)

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_name == "arbeitnow"
    assert job.source_job_id == "senior-frontend-developer-99"
    assert job.title == "Senior Frontend Developer"
    assert job.employer == "VentureLab"
    assert job.work_arrangement == "remote"
    assert job.employment_type == "full_time"
    assert "React & TypeScript" in job.description


@pytest.mark.asyncio
@respx.mock
async def test_arbeitnow_fetch_jobs_error_handling():
    respx.get(ARBEITNOW_API_URL).respond(status_code=429, text="Too Many Requests")
    provider = ArbeitnowProvider()
    jobs = await provider.fetch_jobs(query="RateLimited")
    assert jobs == []

    respx.get(ARBEITNOW_API_URL).mock(side_effect=httpx.NetworkError("Network down"))
    jobs_err = await provider.fetch_jobs(query="NetworkErr")
    assert jobs_err == []


def test_parse_linkedin_salary():
    from app.providers.jobs.linkedin_apify import parse_linkedin_salary

    assert parse_linkedin_salary(None) == (None, None, None)
    assert parse_linkedin_salary(["$120,000", "$150,000"]) == (120000, 150000, "USD")
    assert parse_linkedin_salary(["$17.00", "$19.00"]) == (17, 19, "USD")
    assert parse_linkedin_salary("€90k - €110k") == (90000, 110000, "EUR")
    assert parse_linkedin_salary("Competitive") == (None, None, None)


def test_parse_linkedin_date():
    from app.providers.jobs.linkedin_apify import parse_linkedin_date

    assert parse_linkedin_date(None) is None
    dt1 = parse_linkedin_date("2026-10-01")
    assert dt1 is not None and dt1.year == 2026 and dt1.month == 10 and dt1.day == 1

    dt2 = parse_linkedin_date(None, posted_timestamp=1728561600000)
    assert dt2 is not None


def test_linkedin_build_actor_input_preferences_optimization():
    from app.providers.jobs.linkedin_apify import LinkedInApifyProvider

    provider = LinkedInApifyProvider(api_token="test-token")
    preferences = {
        "target_roles": ["Python Developer"],
        "years_experience": 6.0,
        "seniority_level": "senior",
        "skills": ["FastAPI", "PostgreSQL"],
        "work_arrangements": ["remote"],
        "locations": ["United States"],
        "date_posted": "pastWeek",
        "under_10_applicants": True,
    }

    actor_input = provider.build_actor_input(
        query="Backend Engineer",
        limit=25,
        preferences=preferences,
    )

    assert actor_input["urls"] == []
    # AI search keyword optimization
    keywords = actor_input["keywords"]
    assert "Senior" in keywords
    assert "Backend Engineer" in keywords
    assert "FastAPI" in keywords
    assert "Remote" in keywords

    assert actor_input["location"] == "United States"
    assert actor_input["datePosted"] == "pastWeek"
    assert actor_input["under10Applicants"] is True
    assert actor_input["autoConvertToAiSearch"] is True
    assert actor_input["scrapeCompany"] is False
    assert actor_input["limitPerSource"] == 10


@pytest.mark.asyncio
async def test_linkedin_apify_missing_token_returns_empty():
    from app.providers.jobs.linkedin_apify import LinkedInApifyProvider

    provider = LinkedInApifyProvider(api_token="")
    jobs = await provider.fetch_jobs(query="Python")
    assert jobs == []


@pytest.mark.asyncio
@respx.mock
async def test_linkedin_apify_fetch_jobs_success():
    from app.providers.jobs.linkedin_apify import LinkedInApifyProvider

    mock_items = [
        {
            "id": "3692563200",
            "link": "https://www.linkedin.com/jobs/view/3692563200",
            "title": "Senior Python Backend Engineer",
            "companyName": "TechCorp",
            "location": "Remote, USA",
            "salaryInfo": ["$140,000", "$175,000"],
            "postedAt": "2026-10-05",
            "postedAtTimestamp": 1728129600000,
            "descriptionText": "Build resilient distributed microservices in Python.",
            "seniorityLevel": "Senior",
            "employmentType": "Full-time",
            "workRemoteAllowed": True,
            "workplaceTypes": ["Remote"],
        }
    ]

    apify_url = "https://api.apify.com/v2/acts/curious_coder~linkedin-jobs-scraper/run-sync-get-dataset-items"
    respx.post(apify_url).respond(status_code=200, json=mock_items)

    provider = LinkedInApifyProvider(api_token="valid-token")
    jobs = await provider.fetch_jobs(
        query="Python",
        limit=10,
        preferences={"work_arrangements": ["remote"]},
    )

    assert len(jobs) == 1
    job = jobs[0]
    assert job.source_name == "linkedin_apify"
    assert job.source_job_id == "3692563200"
    assert job.title == "Senior Python Backend Engineer"
    assert job.employer == "TechCorp"
    assert job.work_arrangement == "remote"
    assert job.employment_type == "full_time"
    assert job.seniority == "Senior"
    assert job.salary_min == 140000
    assert job.salary_max == 175000
    assert job.salary_currency == "USD"
    assert "Python" in job.description
    assert job.attribution == "LinkedIn via Apify (curious_coder/linkedin-jobs-scraper)"


@pytest.mark.asyncio
@respx.mock
async def test_linkedin_apify_fetch_jobs_errors():
    from app.providers.jobs.linkedin_apify import LinkedInApifyProvider

    apify_url = "https://api.apify.com/v2/acts/curious_coder~linkedin-jobs-scraper/run-sync-get-dataset-items"

    # 401 unauthorized
    respx.post(apify_url).respond(status_code=401, text="Unauthorized: invalid token")
    provider = LinkedInApifyProvider(api_token="bad-token")
    assert await provider.fetch_jobs(query="Python") == []

    # 500 error
    respx.post(apify_url).respond(status_code=500, text="Apify Error")
    assert await provider.fetch_jobs(query="Python") == []

    # Timeout
    respx.post(apify_url).mock(side_effect=httpx.TimeoutException("Apify timed out"))
    assert await provider.fetch_jobs(query="Python") == []

    # Non-list response
    respx.post(apify_url).respond(status_code=200, json={"message": "unexpected"})
    assert await provider.fetch_jobs(query="Python") == []

    # General network exception
    respx.post(apify_url).mock(side_effect=httpx.ConnectError("Network failure"))
    assert await provider.fetch_jobs(query="Python") == []


def test_linkedin_normalization_edge_cases():
    from app.providers.jobs.linkedin_apify import (
        LinkedInApifyProvider,
        parse_linkedin_date,
        parse_linkedin_salary,
    )

    provider = LinkedInApifyProvider(api_token="test-token")

    # Salary parsing variants
    assert parse_linkedin_salary(12345) == (None, None, None)
    assert parse_linkedin_salary("no salary numbers") == (None, None, None)
    assert parse_linkedin_salary(["$50,000"]) == (50000, None, "USD")
    assert parse_linkedin_salary("£60k - £80k") == (60000, 80000, "GBP")

    # Date parsing variants
    assert parse_linkedin_date(None, posted_timestamp="invalid-timestamp") is None
    assert parse_linkedin_date("invalid-date-string") is None
    dt_iso = parse_linkedin_date("2026-10-10T12:00:00Z")
    assert dt_iso is not None and dt_iso.year == 2026

    # Normalization of hybrid, onsite, contract, intern, html description
    item1 = {
        "title": "Onsite Engineer",
        "workplaceTypes": "On-site",
        "employmentType": "Contract",
        "descriptionHtml": "<p>Direct HTML</p>",
    }
    j1 = provider.normalize_job(item1)
    assert j1.work_arrangement == "onsite"
    assert j1.employment_type == "contract"
    assert "Direct HTML" in j1.description

    item2 = {
        "title": "Hybrid Architect",
        "workplaceTypes": ["Hybrid"],
        "employmentType": "Part-time",
    }
    j2 = provider.normalize_job(item2)
    assert j2.work_arrangement == "hybrid"
    assert j2.employment_type == "part_time"

    item3 = {
        "title": "Software Intern",
        "location": "Remote - Germany",
        "employmentType": "Internship",
    }
    j3 = provider.normalize_job(item3)
    assert j3.work_arrangement == "remote"
    assert j3.employment_type == "internship"


def test_linkedin_build_actor_input_fallbacks():
    from app.providers.jobs.linkedin_apify import LinkedInApifyProvider

    provider = LinkedInApifyProvider(api_token="test-token")

    # Empty query & no roles -> defaults to Software Engineer
    res1 = provider.build_actor_input(query="", limit=0, preferences=None)
    assert "Software Engineer" in res1["keywords"]
    assert res1["location"] == "Remote"
    assert res1["limitPerSource"] == 1
    assert res1["datePosted"] == "pastMonth"

    # Junior candidate with location & non-remote
    res2 = provider.build_actor_input(
        query=None,
        limit=50,
        preferences={
            "target_roles": ["DevOps Specialist"],
            "years_experience": 1.5,
            "seniority_level": "junior",
            "work_arrangements": ["onsite"],
            "location": "Berlin, Germany",
            "date_posted": "invalidOption",
        },
    )
    assert "Junior" in res2["keywords"]
    assert "DevOps Specialist" in res2["keywords"]
    assert res2["location"] == "Berlin, Germany"
    assert res2["datePosted"] == "pastMonth"
    assert res2["limitPerSource"] == 10
