"""
AI-Tailored Cover Letter Generation Service.

Leverages Google Gemini to craft highly personalized, compelling, authentic,
and natural cover letters. Explicitly instructs the model to search and research
the company first, avoiding robotic AI tropes, and anchoring every claim
strictly in verified candidate facts.
"""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
import structlog

from app.core.config import get_settings
from app.providers.llm.base import LLMAdapter
from app.schemas.tailoring import CoverLetterContent

log = structlog.get_logger(__name__)

_COVER_LETTER_SYSTEM_PROMPT = """
You are an elite career strategist, executive talent agent, and natural communications specialist.
Your mission is to write a deeply personalized, authentic, and natural cover letter tailored specifically to the target company and job opening.

CORE PRINCIPLES & DIRECTIVES:

1. SEARCH & RESEARCH THE COMPANY FIRST (MANDATORY):
- Before drafting a single sentence, you MUST search and research the target company thoroughly.
- Investigate their core mission, key products, engineering/tech stack, culture, customer impact, recent public developments, and industry challenges.
- Use this company research to show genuine, insider-level understanding of what makes this company unique.
- NEVER use generic company compliments (e.g., "as a market leader", "your innovative organization", "at the forefront of tech"). Instead, reference their specific product domain, engineering challenges, architecture scale, or mission.

2. DEEPLY PERSONALIZED & NATURAL HUMAN VOICE (MANDATORY):
- The letter MUST sound like an articulate, thoughtful, and passionate human engineer/professional speaking directly to a future colleague or team lead.
- STRICTLY BAN ALL ROBOTIC AI TROPES:
  * NEVER begin with clichés: "I am writing to express my enthusiastic interest...", "I am thrilled to apply for...", "Please accept my application for...", "In today's fast-paced digital landscape...", or "With great excitement...".
  * Avoid buzzword stuffing: "synergistic", "spearheaded cross-functional paradigms", "results-oriented visionary".
- Open with an authentic hook: a compelling statement connecting the candidate's real-world engineering achievements with the exact problems this company solves.
- Maintain a warm, confident, conversational yet professional cadence. Every sentence should feel purposeful and human.

3. STRICT FACTUAL GROUNDING (ZERO HALLUCINATION):
- Every skill, past company, project, metric, and degree mentioned MUST be strictly grounded in the candidate's verified profile facts provided.
- DO NOT fabricate employers, degrees, unearned metrics, or technologies not present in the candidate facts.
- Highlight the 2 to 3 most relevant, high-impact achievements from the candidate's history that directly solve needs described in the job listing.

4. STRUCTURE & FLOW (1 Page, 3-4 Concise Paragraphs):
- Salutation: Warm, professional, and targeted (e.g. "Dear [Company] Engineering Team,").
- Opening Hook: Direct and punchy, demonstrating immediate familiarity with the company's work and enthusiasm for the specific role.
- Body Paragraphs (2 to 3):
  * Detail concrete verified accomplishments that solve key challenges in the job listing.
  * Connect candidate's engineering philosophy with the company's product vision and team culture.
- Call to Action: Confident, forward-looking invitation for discussion, free of desperation or submissiveness.
- Signoff & Name: Professional signoff with candidate's full name.
"""


class CoverLetterService:
    """Service orchestrating AI-driven personalized cover letter generation."""

    def __init__(self, llm: LLMAdapter) -> None:
        self.llm = llm
        self.settings = get_settings()

    async def _fetch_company_search_context(self, company_name: str) -> str:
        """
        Attempt a brief external web search/lookup for the company to provide
        up-to-the-minute context to Gemini alongside internal model knowledge.
        Fails gracefully with empty string if unreachable.
        """
        if not company_name or len(company_name.strip()) < 2:
            return ""

        query = f"{company_name.strip()} company mission products overview"
        try:
            async with httpx.AsyncClient(timeout=3.0, follow_redirects=True) as client:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JobFit/1.0"},
                )
                if resp.status_code == 200:
                    text = resp.text
                    # Extract snippet texts from duckduckgo result snippets
                    snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', text, re.DOTALL)
                    clean_snippets = [
                        re.sub(r"<[^>]+>", "", s).strip()
                        for s in snippets[:3]
                        if len(s.strip()) > 20
                    ]
                    if clean_snippets:
                        return "\n".join(f"- {s}" for s in clean_snippets)
        except Exception as exc:
            log.debug("cover_letter_web_search_skipped", reason=str(exc))

        return ""

    async def generate_cover_letter(
        self,
        job: dict[str, Any],
        candidate_profile: dict[str, Any],
        target_role_notes: str | None = None,
        tone: str = "natural_conversational",
    ) -> CoverLetterContent:
        """
        Generate a personalized, authentic cover letter using Gemini.
        Instructs the model to search/research first about the company,
        maintains a natural human voice, and adheres strictly to verified facts.
        """
        company_name = (
            job.get("employer")
            or job.get("company")
            or "the hiring organization"
        ).strip()
        job_title = job.get("title", "Position").strip()
        job_description = job.get("description") or (
            "\n".join(job.get("requirements", [])) if job.get("requirements") else ""
        )

        candidate_name = candidate_profile.get("name") or "Candidate"

        # 1. Fetch search context if reachable
        search_snippets = await self._fetch_company_search_context(company_name)
        search_section = (
            f"=== REAL-TIME WEB SEARCH & COMPANY DISCOVERY SNIPPETS ===\n"
            f"Target Company: {company_name}\n"
            f"{search_snippets}\n\n"
            if search_snippets
            else ""
        )

        notes_section = (
            f"Candidate Custom Instructions & Focus Notes: {target_role_notes}\n\n"
            if target_role_notes
            else ""
        )

        prompt = (
            f"=== TARGET COMPANY & JOB POSTING ===\n"
            f"Company: {company_name}\n"
            f"Role Title: {job_title}\n"
            f"Job Description / Requirements:\n{job_description}\n\n"
            f"{search_section}"
            f"=== CANDIDATE VERIFIED FACTS & BACKGROUND ===\n"
            f"{json.dumps(candidate_profile, indent=2)}\n\n"
            f"{notes_section}"
            f"=== MISSION & TASK INSTRUCTIONS ===\n"
            f"Write an exceptional, deeply personalized, and natural cover letter for {candidate_name} applying to {company_name}.\n\n"
            f"1. SEARCH & RESEARCH FIRST:\n"
            f"   - Search and research first about {company_name} (their core mission, primary products/platforms, engineering culture, and industry domain).\n"
            f"   - Incorporate key insights in `company_research_summary` and weave authentic knowledge into the letter's opening hook and body.\n\n"
            f"2. MAKE IT DEEPLY PERSONALIZED AND NATURAL AS MUCH AS POSSIBLE:\n"
            f"   - Tone requested: {tone} (authentic, engaging, human, conversational, articulate).\n"
            f"   - Ban all robotic clichés (no 'I am writing to express my interest', no 'I am thrilled to apply', no empty flattery).\n"
            f"   - Connect candidate's specific past engineering accomplishments to the company's real products and technical hurdles.\n\n"
            f"3. STRICT FACTUAL ACCURACY:\n"
            f"   - Only mention technologies, employers, and achievements present in candidate verified facts.\n\n"
            f"4. OUTPUT FORMAT:\n"
            f"   - Provide structured components (`recipient`, `company_name`, `salutation`, `opening_hook`, `body_paragraphs`, `call_to_action`, `signoff`, `candidate_name`, `company_research_summary`).\n"
            f"   - Also generate `full_text` containing the complete formatted cover letter."
        )

        letter_content = await self.llm.extract_structured(
            prompt=prompt,
            response_model=CoverLetterContent,
            system_instruction=_COVER_LETTER_SYSTEM_PROMPT,
            temperature=0.5,
        )

        # Ensure candidate_name and company_name are populated
        if not letter_content.candidate_name:
            letter_content.candidate_name = candidate_name
        if not letter_content.company_name:
            letter_content.company_name = company_name

        # Assemble full_text if missing or partial
        if not letter_content.full_text or len(letter_content.full_text.strip()) < 50:
            paragraphs = [letter_content.salutation, letter_content.opening_hook]
            paragraphs.extend([p.strip() for p in letter_content.body_paragraphs if p.strip()])
            paragraphs.append(letter_content.call_to_action)
            paragraphs.append(f"{letter_content.signoff}\n{letter_content.candidate_name}")
            letter_content.full_text = "\n\n".join(paragraphs).strip()

        return letter_content
