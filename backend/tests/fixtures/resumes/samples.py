"""
Synthetic resume samples for testing and benchmarking.
"""

from __future__ import annotations

import io

from docx import Document

# ── Sample 1: Machine Learning Engineer ───────────────────────────────────────
SAMPLE_RESUME_MLE = """
John Doe
Email: john.doe@example.com | Phone: +1-555-0199 | Location: San Francisco, CA
LinkedIn: linkedin.com/in/johndoe | Portfolio: https://johndoe.ai

Summary:
Machine Learning Engineer with 4 years of experience building and deploying NLP models,
retrieval-augmented generation (RAG) systems, and real-time inference pipelines.

Skills:
Python, PyTorch, Hugging Face, Transformers, FastAPI, Docker, PostgreSQL, Redis, LangChain, Git

Experience:
Senior ML Engineer | Apex AI | San Francisco, CA | 2022-03 - Present
- Designed and deployed enterprise semantic search engine serving 2M daily queries.
- Fine-tuned open-source LLMs resulting in a 15% improvement in domain-specific accuracy.
- Mentored 3 junior engineers and established automated evaluation benchmarks.

Software Engineer (Data & ML) | Nova Systems | Austin, TX | 2020-01 - 2022-02
- Built scalable ETL pipelines in Python and SQL processing 50GB of streaming logs daily.
- Implemented REST APIs using FastAPI for model inference with sub-50ms latency.
- Containerized applications using Docker and automated CI/CD deployments.

Education:
B.S. in Computer Science | University of California, Berkeley | 2016-09 - 2020-05
GPA: 3.8 / 4.0

Certifications:
AWS Certified Machine Learning - Specialty | Amazon Web Services | 2022-08

Projects:
Neural Search Engine | https://github.com/johndoe/neural-search
- Built vector search engine using FastAPI and FAISS with hybrid BM25 re-ranking.
"""

# ── Sample 2: Frontend Engineer ───────────────────────────────────────────────
SAMPLE_RESUME_FRONTEND = """
Sarah Connor
Email: sarah.connor@example.com | Phone: +1-555-0248 | Location: New York, NY
Portfolio: https://sarahconnor.dev

Summary:
Frontend Engineer with 3 years of experience crafting accessible, responsive
web apps using React and TypeScript.

Skills:
React, TypeScript, Next.js, CSS, HTML5, TailwindCSS, Jest, Cypress, GraphQL

Experience:
Frontend Developer | WebCorp | New York, NY | 2021-06 - Present
- Built design system components used by 12 cross-functional product squads.
- Improved Core Web Vitals (LCP reduced by 35%) across high-traffic marketing sites.

Junior Web Developer | PixelCraft | Remote | 2020-05 - 2021-05
- Developed interactive web pages in React and Vanilla CSS.

Education:
B.A. in Digital Media | New York University | 2016-09 - 2020-05
"""

# Minimal valid PDF bytes with text stream
MINIMAL_VALID_PDF = b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
  /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj
4 0 obj << /Length 73 >> stream
BT
/F1 12 Tf
72 712 Td
(John Doe - Software Engineer with Python and FastAPI skills) Tj
ET
endstream
endobj
5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000244 00000 n
0000000368 00000 n
trailer << /Size 6 /Root 1 0 R >>
startxref
443
%%EOF"""


def make_docx_bytes(text: str) -> bytes:
    """Generate in-memory valid DOCX binary bytes."""
    doc = Document()
    for line in text.split("\n"):
        if line.strip():
            doc.add_paragraph(line.strip())
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()
