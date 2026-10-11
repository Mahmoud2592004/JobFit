"""Tests for resume parser service."""

from __future__ import annotations

import pytest

from app.core.exceptions import (
    FileTooLargeError,
    MalformedFileError,
    UnsupportedFileTypeError,
)
from app.services.deterministic_parser import DeterministicResumeParser
from app.services.resume_parser import ResumeParserService
from tests.fixtures.resumes.samples import (
    MINIMAL_VALID_PDF,
    SAMPLE_RESUME_MLE,
    make_docx_bytes,
)


def test_validate_file_size():
    svc = ResumeParserService()
    # 5 MB is valid
    svc.validate_file_size(5 * 1024 * 1024)

    # 15 MB exceeds default 10MB
    with pytest.raises(FileTooLargeError):
        svc.validate_file_size(15 * 1024 * 1024)


def test_detect_file_type():
    svc = ResumeParserService()
    assert svc.detect_file_type("resume.pdf", b"%PDF-1.4...") == "pdf"
    assert svc.detect_file_type("resume.docx", b"PK\x03\x04...") == "docx"

    with pytest.raises(UnsupportedFileTypeError):
        svc.detect_file_type("script.py", b"print('hello')")

    with pytest.raises(UnsupportedFileTypeError):
        # Extension .pdf but not pdf bytes
        svc.detect_file_type("fake.pdf", b"NOT_A_PDF")

    with pytest.raises(UnsupportedFileTypeError):
        # Extension .docx but not docx bytes
        svc.detect_file_type("fake.docx", b"NOT_A_DOCX")


def test_parse_pdf():
    svc = ResumeParserService()
    text = svc.parse_pdf(MINIMAL_VALID_PDF)
    assert "John Doe" in text
    assert "Python" in text


def test_parse_pdf_malformed():
    svc = ResumeParserService()
    with pytest.raises(MalformedFileError):
        svc.parse_pdf(b"%PDF-corrupted-bytes-12345")


def test_parse_docx():
    svc = ResumeParserService()
    docx_bytes = make_docx_bytes(SAMPLE_RESUME_MLE)
    text = svc.parse_docx(docx_bytes)
    assert "John Doe" in text
    assert "PyTorch" in text


def test_parse_docx_malformed():
    svc = ResumeParserService()
    with pytest.raises(MalformedFileError):
        svc.parse_docx(b"PK\x03\x04corrupted-zip-stream")


def test_clean_text():
    svc = ResumeParserService()
    valid_text = "This is a valid resume text with sufficient length for extraction."
    cleaned = svc.clean_text(f"  {valid_text}  ")
    assert cleaned == valid_text

    with pytest.raises(MalformedFileError):
        svc.clean_text("too short")


def test_deterministic_parser_variant_titles_and_sections():
    from app.services.deterministic_parser import DeterministicResumeParser

    parser = DeterministicResumeParser()

    resume_text = """
    Elena Rostova
    Email: elena.rostova@example.com | Phone: +1 415-555-0182 | Location: Seattle, WA
    LinkedIn: linkedin.com/in/elenarostova | Portfolio: https://github.com/erostova

    Professional Profile:
    Results-driven Lead Cloud Architect and Staff Full-Stack Engineer with 8 years of experience.

    Core Competencies:
    Go, Python, TypeScript, React, Kubernetes, Docker, AWS, PostgreSQL, Kafka, Terraform

    Career Progression:
    Staff Full-Stack Architect at CloudFrontier Systems (2021-04 to Present)
    - Designed distributed multi-region backend microservices in Go and Python.
    - Led architectural migration of frontend to TypeScript and React.

    Senior Software Developer at DataPulse Technologies (2017-06 to 2021-03)
    - Engineered high-throughput data processing services using Python and PostgreSQL.

    Academic Background:
    Master of Science in Software Engineering from University of Washington (2015 to 2017)
    Bachelor of Science in Computer Science from Seattle University (2011 to 2015)

    Certifications & Credentials:
    AWS Certified Solutions Architect - Professional by Amazon Web Services (2022)
    """

    profile = parser.parse(resume_text)

    # 1. Contact Info
    assert profile.contact.name == "Elena Rostova"
    assert profile.contact.email == "elena.rostova@example.com"
    assert profile.contact.phone == "+1 415-555-0182"
    assert profile.contact.location == "Seattle, WA"
    assert "elenarostova" in (profile.contact.linkedin_url or "")

    # 2. Variant Section Recognition
    assert len(profile.skills) >= 8
    assert "Go" in profile.skills
    assert "Python" in profile.skills
    assert "Kubernetes" in profile.skills
    assert "Terraform" in profile.skills

    # 3. Variant Job Titles
    assert len(profile.employment_history) == 2
    assert "Staff Full-Stack Architect" in profile.employment_history[0].title
    assert "CloudFrontier Systems" in profile.employment_history[0].company
    assert profile.employment_history[0].is_current is True

    assert "Senior Software Developer" in profile.employment_history[1].title
    assert "DataPulse Technologies" in profile.employment_history[1].company

    # 4. Education
    assert len(profile.education) == 2
    assert "University of Washington" in profile.education[0].institution

    # 5. Seniority & Years Experience
    assert profile.years_experience is not None and profile.years_experience >= 7.0
    assert profile.seniority_level in ("lead", "senior")


def test_project_parsing_with_wrapped_lines_and_endash():
    parser = DeterministicResumeParser()
    text = """
    John Doe
    Email: john@example.com

    Technical Projects:
    LLM Quantization Pipeline | Python, PyTorch
    –Built automated real-time inference
    pipelines.
    –Hardened Qwen2.5-1.5B for production via fine-tuning on 10K QA samples with pruning and quantization, reducing model memory
    footprint from 6GB to 1.2GB.
    """
    profile = parser.parse(text)
    assert len(profile.projects) == 1
    proj = profile.projects[0]
    assert "LLM Quantization Pipeline" in proj.name
    assert "Qwen2.5-1.5B" in (proj.description or "")
    assert "footprint from 6GB to 1.2GB" in (proj.description or "")
    assert "inference pipelines" in (proj.description or "")

