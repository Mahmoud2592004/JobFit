"""
Deterministic resume extraction engine.

Extracts structured candidate profile data from raw resume text using:
- Robust section segmentation with variant headings vocabulary.
- Job title variant recognition across domains and seniority levels.
- Comprehensive skills dictionary with word-boundary matching.
- Date range extraction and experience duration computation.
- Contact information and provenance line-span tracking.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Literal

from app.schemas.profile import (
    CertificationEntry,
    ContactInfo,
    EducationEntry,
    EmploymentEntry,
    ExtractedProfile,
    ProjectEntry,
)

# ── Section Heading Vocabulary (Variant Forms) ───────────────────────────────

_SECTION_PATTERNS = {
    "summary": re.compile(
        r"^(?:(?:professional|executive|career|personal)?\s*(?:summary|profile|overview|statement|bio)|about\s+me|career\s+objective|objective)\b",
        re.IGNORECASE,
    ),
    "experience": re.compile(
        r"^(?:(?:work|professional|career|relevant|technical|employment)?\s*(?:experience|history|background|progression|positions?|roles?)|jobs?|employment)\b",
        re.IGNORECASE,
    ),
    "education": re.compile(
        r"^(?:education(?:al)?(?:\s+(?:background|history|qualifications))?|academic\s+(?:background|history)|degrees?|academics?|qualifications?|education\s+&\s+training)\b",
        re.IGNORECASE,
    ),
    "skills": re.compile(
        r"^(?:(?:technical|core|key|professional)?\s*(?:skills|competencies|proficiencies|technologies|expertise)|areas\s+of\s+expertise|tech\s+stack|tools\s*(?:&|\+)?\s*technologies?|programming\s+languages?)\b",
        re.IGNORECASE,
    ),
    "projects": re.compile(
        r"^(?:(?:technical|personal|academic|key|notable|side|selected)?\s*projects?|portfolio)\b",
        re.IGNORECASE,
    ),
    "certifications": re.compile(
        r"^(?:certifications?|certificates?|licenses?|credentials?|accreditations?|leadership|extracurricular|activities|community|honors?\s*(?:&|\+)?\s*awards?|certifications?\s*(?:&|\+)?\s*(?:licenses?|training))\b",
        re.IGNORECASE,
    ),
}

# ── Job Title Variant Keywords & Patterns ─────────────────────────────────────

_TITLE_SENIORITY = (
    r"(?:intern|trainee|apprentice|junior|jr\.?|associate|mid(?:-level)?|senior|sr\.?|"
    r"lead|principal|staff|distinguished|head\s+of|director|vp|vice\s+president|chief|cto|architect)"
)

_TITLE_DOMAINS = (
    r"(?:software|full[\s-]stack|backend|back[\s-]end|frontend|front[\s-]end|web|mobile|ios|android|"
    r"devops|cloud|platform|infrastructure|site\s+reliability|sre|systems?|security|cybersecurity|"
    r"machine\s+learning|ml|ai|artificial\s+intelligence|deep\s+learning|nlp|computer\s+vision|"
    r"data|analytics|business\s+intelligence|bi|database|dba|embedded|firmware|hardware|"
    r"qa|quality\s+assurance|test|automation|sdet|product|project|scrum\s+master|ui[/\\-]ux|solutions?)"
)

_TITLE_ROLES = (
    r"(?:engineer|developer|programmer|architect|consultant|analyst|specialist|"
    r"scientist|manager|lead|director|administrator|sysadmin|technician|designer|officer|researcher)"
)

# Combined regex matching job titles
_TITLE_REGEX = re.compile(
    rf"\b(?:{_TITLE_SENIORITY}\s+)?(?:{_TITLE_DOMAINS}\s+)?{_TITLE_ROLES}\b",
    re.IGNORECASE,
)

# ── Common Degree Keywords ───────────────────────────────────────────────────

_DEGREE_PATTERN = re.compile(
    r"\b(?:b\.?s\.?c?|b\.?a\.?|bachelor(?:'s)?|m\.?s\.?c?|m\.?a\.?|master(?:'s)?|mba|"
    r"ph\.?d\.?|doctorate|associate(?:'s)?|diploma|b\.?eng\.?|m\.?eng\.?)\b(?:\s+(?:of|in)\s+[^,\n]+)?",
    re.IGNORECASE,
)

_INSTITUTION_KEYWORDS = (
    "university", "college", "institute", "school", "academy", "polytechnic", "faculty"
)

# ── Normalized Skills Vocabulary ──────────────────────────────────────────────

_NORMALIZED_SKILLS = [
    # Languages
    "Python", "JavaScript", "TypeScript", "Go", "Golang", "Rust", "Java", "C++", "C#",
    "Ruby", "PHP", "Swift", "Kotlin", "Scala", "R", "SQL", "HTML", "HTML5", "CSS", "CSS3",
    "Sass", "Bash", "Shell", "PowerShell", "Perl", "Haskell", "Dart", "Lua",
    # Frameworks & Runtimes
    "React", "React.js", "React Native", "Next.js", "Vue", "Vue.js", "Nuxt.js", "Angular",
    "Node.js", "Express", "Express.js", "FastAPI", "Flask", "Django", "Spring", "Spring Boot",
    "ASP.NET", ".NET", "Ruby on Rails", "Laravel", "Symfony", "Fastify", "NestJS", "Svelte",
    # Databases & Caching
    "PostgreSQL", "Postgres", "MySQL", "SQLite", "MongoDB", "Redis", "Cassandra",
    "DynamoDB", "Elasticsearch", "Neo4j", "CouchDB", "MariaDB", "Supabase", "Firebase",
    # Cloud & DevOps
    "AWS", "Amazon Web Services", "Azure", "GCP", "Google Cloud", "Docker", "Kubernetes",
    "Terraform", "Ansible", "Helm", "CI/CD", "GitHub Actions", "GitLab CI", "Jenkins",
    "ArgoCD", "Prometheus", "Grafana", "Nginx", "Linux", "Kafka", "RabbitMQ", "Celery",
    # AI / Machine Learning & Data
    "PyTorch", "TensorFlow", "Keras", "Scikit-Learn", "Pandas", "NumPy", "SciPy", "Spark",
    "Hadoop", "Airflow", "HuggingFace", "LangChain", "OpenAI", "LLMs", "NLP", "Computer Vision",
    # Architecture & Practices
    "Microservices", "REST", "REST API", "GraphQL", "gRPC", "WebSockets", "System Design",
    "Design Patterns", "Agile", "Scrum", "TDD", "Git", "GitHub", "GitLab",
]

# Pre-compile skills regex mapping for exact word boundaries
_SKILL_MATCHERS: list[tuple[str, re.Pattern]] = []
for _s in _NORMALIZED_SKILLS:
    # Handle single letters or acronyms carefully
    if len(_s) <= 2 and not _s.isupper():
        _p = re.compile(rf"\b{re.escape(_s)}\b")
    else:
        _p = re.compile(rf"\b{re.escape(_s)}\b", re.IGNORECASE)
    _SKILL_MATCHERS.append((_s, _p))


class DeterministicResumeParser:
    """
    Deterministic rule-based resume parser with section segmentation,
    variant job title recognition, contact extraction, and skills matching.
    """

    def parse(self, raw_text: str) -> ExtractedProfile:
        """Parse raw resume text into ExtractedProfile deterministically."""
        cleaned = raw_text.strip()
        lines = [line.strip() for line in cleaned.splitlines()]

        # 1. Segment text into sections
        sections = self._segment_sections(lines)

        # 2. Extract Contact Info
        contact = self._extract_contact(sections.get("header", []), cleaned)

        # 3. Extract Summary
        summary = self._extract_summary(sections.get("summary", []))

        # 4. Extract Skills
        skills = self._extract_skills(sections.get("skills", []), cleaned)

        # 5. Extract Employment History
        employment = self._extract_employment(sections.get("experience", []))

        # 6. Extract Education
        education = self._extract_education(sections.get("education", []))

        # 7. Extract Certifications
        certifications = self._extract_certifications(sections.get("certifications", []))

        # 8. Extract Projects
        projects = self._extract_projects(sections.get("projects", []))

        # 9. Determine Seniority, Years Experience, and Target Roles
        years_exp = self._compute_years_experience(employment, cleaned)
        seniority = self._determine_seniority(employment, years_exp)
        target_roles = self._determine_target_roles(employment, summary)

        return ExtractedProfile(
            contact=contact,
            summary=summary,
            skills=skills,
            employment_history=employment,
            education=education,
            certifications=certifications,
            projects=projects,
            target_roles=target_roles,
            seniority_level=seniority,
            years_experience=years_exp,
        )

    def _segment_sections(self, lines: list[str]) -> dict[str, list[str]]:
        """Segment raw text lines into categorized sections by detecting headers."""
        sections: dict[str, list[str]] = {
            "header": [],
            "summary": [],
            "experience": [],
            "education": [],
            "skills": [],
            "projects": [],
            "certifications": [],
            "other": [],
        }

        current_section = "header"

        for line in lines:
            if not line:
                continue

            # Check if this line is a section header
            matched_section = self._match_section_header(line)
            if matched_section:
                current_section = matched_section
                continue

            sections[current_section].append(line)

        return sections

    def _match_section_header(self, line: str) -> str | None:
        """Test if a line corresponds to a known section header variant."""
        # Clean markdown decorations or punctuation (e.g., "## Experience:", "--- Skills ---")
        clean = re.sub(r"^[#*=-]+\s*|\s*[:=-]+$", "", line).strip()
        if not clean or len(clean.split()) > 5:
            # Section headers are usually short (1 to 4 words)
            return None

        for section_name, pattern in _SECTION_PATTERNS.items():
            if pattern.search(clean):
                return section_name

        return None

    def _extract_contact(self, header_lines: list[str], full_text: str) -> ContactInfo:
        """Extract name, email, phone, location, and social links."""
        contact = ContactInfo()

        # Email
        email_match = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", full_text)
        if email_match:
            contact.email = email_match.group(0).lower()

        # Phone
        phone_match = re.search(
            r"(?:Phone|Mobile|Tel|Cell|WhatsApp)?[:\s]*(\+?\d{1,3}[-.\s]?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b|\+?\d{1,3}\s*\d{9,12}\b|\+?\d{9,15}\b)",
            full_text,
            re.IGNORECASE,
        )
        if phone_match:
            candidate_phone = phone_match.group(1).strip()
            if len(candidate_phone.replace(" ", "").replace("-", "")) >= 7:
                contact.phone = candidate_phone

        # LinkedIn
        li_match = re.search(
            r"(?:https?://)?(?:[a-zA-Z0-9-]+\.)?linkedin\.com/(?:in/)?([A-Za-z0-9_-]+)",
            full_text,
            re.IGNORECASE,
        )
        if li_match:
            contact.linkedin_url = f"https://linkedin.com/in/{li_match.group(1)}"

        # Portfolio or GitHub
        gh_match = re.search(
            r"(?:https?://)?(?:www\.)?github\.com/([A-Za-z0-9_-]+)",
            full_text,
            re.IGNORECASE,
        )
        if gh_match:
            contact.portfolio_url = f"https://github.com/{gh_match.group(1)}"
        else:
            pf_match = re.search(
                r"\bhttps?://([A-Za-z0-9.-]+\.[A-Za-z]{2,}(?:/[^\s]*)?)", full_text
            )
            if pf_match and "linkedin.com" not in pf_match.group(0):
                contact.portfolio_url = pf_match.group(0)

        # Location: Check header lines with pipe delimiter first, then label, then city/country
        for hl in header_lines:
            if "|" in hl:
                for part in hl.split("|"):
                    p = part.strip()
                    if re.search(r"^[A-Z][a-zA-Z ]+,\s*[A-Z][a-zA-Z]+$", p):
                        contact.location = p
                        break
            if contact.location:
                break

        if not contact.location:
            loc_label = re.search(r"Location:\s*([^\n|]+)", full_text)
            if loc_label:
                contact.location = loc_label.group(1).strip()
            else:
                loc_match = re.search(
                    r"\b([A-Z][a-zA-Z ]+,\s*(?:[A-Z]{2}|[A-Z][a-zA-Z]+))\b", full_text
                )
                if loc_match:
                    candidate_loc = loc_match.group(1).strip()
                    months = (
                        "jan", "feb", "mar", "apr", "may", "jun",
                        "jul", "aug", "sep", "oct", "nov", "dec",
                    )
                    if not any(k in candidate_loc.lower() for k in months):
                        contact.location = candidate_loc

        # Name from header
        for line in header_lines:
            line_clean = re.sub(r"^[#*=-]+\s*", "", line).strip()
            # If line doesn't contain email, phone, or url, treat as candidate name
            if (
                line_clean
                and "@" not in line_clean
                and not re.search(r"\d{3}", line_clean)
                and "http" not in line_clean
                and len(line_clean.split()) <= 4
            ):
                contact.name = line_clean
                break

        return contact

    def _extract_summary(self, summary_lines: list[str]) -> str:
        """Extract cleaned professional summary text."""
        return " ".join(summary_lines).strip()

    def _extract_skills(self, skills_lines: list[str], full_text: str) -> list[str]:
        """Extract and normalize technical & professional skills."""
        found: set[str] = set()

        # First scan declared skills section lines
        section_text = " ".join(skills_lines)
        if section_text:
            # Comma, bullet, pipe separated
            tokens = re.split(r"[,|•·;\n]\s*", section_text)
            for token in tokens:
                token_clean = token.strip()
                if 2 <= len(token_clean) <= 35 and not token_clean.endswith("."):
                    # Check against normalized skills or retain clean token
                    matched = False
                    for norm, matcher in _SKILL_MATCHERS:
                        if matcher.search(token_clean):
                            found.add(norm)
                            matched = True
                    if not matched and len(token_clean.split()) <= 3:
                        found.add(token_clean)

        # Full-text scan for known high-value skills
        for norm, matcher in _SKILL_MATCHERS:
            if matcher.search(full_text):
                found.add(norm)

        # Return sorted list
        return sorted(found)

    def _extract_employment(self, exp_lines: list[str]) -> list[EmploymentEntry]:
        """Parse work experience entries recognizing variant job titles, companies, and dates."""
        entries: list[EmploymentEntry] = []
        if not exp_lines:
            return entries

        current_entry: dict[str, Any] | None = None

        date_pattern = re.compile(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b\d{4}(?:-\d{2})?)\s*(?:[-–—to]+)\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b\d{4}(?:-\d{2})?|Present|Current|Now)",
            re.IGNORECASE,
        )
        bullet_chars = ("–", "-", "—", "*", "•", "▪", "·")

        for line in exp_lines:
            line_clean = line.strip()
            if not line_clean:
                continue

            is_bullet = line_clean.startswith(bullet_chars) or bool(re.match(r"^\d+\.", line_clean))
            d_match = date_pattern.search(line_clean)

            # Check for pipe-separated position line (e.g. Title | Company | Location | Dates)
            parts = [p.strip() for p in line_clean.split("|") if p.strip()]
            is_pipe_header = len(parts) >= 2 and bool(_TITLE_REGEX.search(parts[0])) and ("(" not in parts[0] or ")" in parts[0])

            if is_pipe_header:
                if current_entry and (current_entry.get("company") or current_entry.get("title")):
                    entries.append(EmploymentEntry(**current_entry))

                title = parts[0] if parts else "Professional"
                company = parts[1] if len(parts) > 1 else "Organization"
                location = parts[2] if len(parts) > 3 else None
                dates_part = parts[-1] if len(parts) >= 3 else ""

                part_d = date_pattern.search(dates_part or line_clean)
                start_date = part_d.group(1).strip() if part_d else None
                end_date = part_d.group(2).strip() if part_d else None
                is_current = any(
                    k in (end_date or "").lower() for k in ("present", "current", "now")
                )

                current_entry = {
                    "company": company,
                    "title": title,
                    "location": location,
                    "start_date": start_date,
                    "end_date": end_date,
                    "is_current": is_current,
                    "description": "",
                    "achievements": [],
                }
                continue

            # Detect start of a new job via dates on the line
            if d_match:
                if current_entry and (current_entry.get("company") or current_entry.get("title")):
                    entries.append(EmploymentEntry(**current_entry))

                start_date = d_match.group(1).strip()
                end_date = d_match.group(2).strip()
                is_current = any(
                    k in (end_date or "").lower() for k in ("present", "current", "now")
                )

                without_date = date_pattern.sub("", line_clean).strip(" -–—|()[],")
                without_date = re.sub(
                    r"\s*\([^)]*(?:app store|google play|github|link)[^)]*\)",
                    "",
                    without_date,
                    flags=re.IGNORECASE,
                ).strip(" -–—|()[],")
                # Remove unclosed parens or brackets
                without_date = re.sub(r"^[(\[]|[)\]]$", "", without_date).strip()

                title = ""
                company = without_date or "Organization"

                if " at " in without_date:
                    parts_at = without_date.split(" at ", 1)
                    title = parts_at[0].strip()
                    company = parts_at[1].strip()
                elif " - " in without_date or " – " in without_date:
                    split_s = " – " if " – " in without_date else " - "
                    parts_dash = without_date.split(split_s, 1)
                    if bool(_TITLE_REGEX.search(parts_dash[0])):
                        title = parts_dash[0].strip()
                        company = parts_dash[1].strip()

                current_entry = {
                    "company": company or "Organization",
                    "title": title,
                    "location": None,
                    "start_date": start_date,
                    "end_date": end_date,
                    "is_current": is_current,
                    "description": "",
                    "achievements": [],
                }
                continue

            # If current entry is missing title, next non-bullet line is Title + Location
            if current_entry and not is_bullet and not current_entry["title"]:
                loc_m = re.search(
                    r"(?:[|\s]+)([A-Z][a-zA-Z]+,\s*[A-Z][a-zA-Z]+|Remote|Hybrid|On-site)\s*$",
                    line_clean,
                    re.IGNORECASE,
                )
                if loc_m:
                    current_entry["location"] = loc_m.group(1).strip()
                    current_entry["title"] = line_clean[:loc_m.start(1)].strip(" -–—|,")
                else:
                    current_entry["title"] = line_clean.strip()
                continue

            # If line is bullet point
            if is_bullet and current_entry:
                b_text = line_clean.lstrip("–-—*•▪·0123456789. ").strip()
                if b_text:
                    current_entry["achievements"].append(b_text)
            elif current_entry and current_entry["achievements"]:
                # Continuation of previous bullet point
                current_entry["achievements"][-1] += " " + line_clean
            elif current_entry:
                if not current_entry["description"]:
                    current_entry["description"] = line_clean
                else:
                    current_entry["description"] += " " + line_clean

        if current_entry and (current_entry.get("company") or current_entry.get("title")):
            if not current_entry.get("title"):
                current_entry["title"] = "Professional"
            if not current_entry.get("company"):
                current_entry["company"] = "Organization"
            entries.append(EmploymentEntry(**current_entry))

        return entries

    def _extract_education(self, edu_lines: list[str]) -> list[EducationEntry]:
        """Extract degrees, universities, and graduation years."""
        entries: list[EducationEntry] = []
        if not edu_lines:
            return entries

        current: dict[str, Any] | None = None
        date_pattern = re.compile(
            r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b\d{4}(?:-\d{2})?)\s*(?:[-–—to]+)\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\b\d{4}(?:-\d{2})?|Present)?",
            re.IGNORECASE,
        )
        single_date = re.compile(
            r"\b((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|\d{4})\b",
            re.IGNORECASE,
        )

        for line in edu_lines:
            line_clean = line.strip()
            if not line_clean or line_clean.lower() in ("leadership", "extracurricular", "activities"):
                continue

            if "|" in line_clean:
                if current:
                    entries.append(EducationEntry(**current))
                parts = [p.strip() for p in line_clean.split("|") if p.strip()]
                degree = parts[0] if parts else "Degree"
                institution = parts[1] if len(parts) > 1 else "University"
                d_match = date_pattern.search(parts[-1]) if len(parts) > 2 else None
                current = {
                    "institution": institution,
                    "degree": degree,
                    "field_of_study": None,
                    "start_date": d_match.group(1).strip() if d_match else None,
                    "end_date": d_match.group(2).strip() if d_match and d_match.group(2) else None,
                    "gpa": None,
                }
                continue

            is_institution = any(k in line_clean.lower() for k in _INSTITUTION_KEYWORDS)
            degree_match = _DEGREE_PATTERN.search(line_clean)

            if is_institution:
                if current and (current.get("institution") or current.get("degree")):
                    entries.append(EducationEntry(**current))

                d_m = date_pattern.search(line_clean) or single_date.search(line_clean)
                start_d = None
                end_d = None
                if d_m:
                    if d_m.lastindex and d_m.lastindex >= 2 and d_m.group(2):
                        start_d = d_m.group(1).strip()
                        end_d = d_m.group(2).strip()
                    else:
                        end_d = d_m.group(1).strip()

                inst_clean = single_date.sub("", date_pattern.sub("", line_clean)).strip(" -–—|,")
                deg_inline = degree_match.group(0).strip() if degree_match else ""
                if deg_inline:
                    inst_clean = inst_clean.replace(deg_inline, "").strip(" -–—|,")

                current = {
                    "institution": inst_clean or "University",
                    "degree": deg_inline or "Degree",
                    "field_of_study": None,
                    "start_date": start_d,
                    "end_date": end_d,
                    "gpa": None,
                }
                continue

            if current and (not current["degree"] or current["degree"] == "Degree") and degree_match:
                current["degree"] = degree_match.group(0).strip()
                gpa_match = re.search(r"GPA:?\s*([0-4]\.\d{1,2}(?:/[0-4]\.0)?)", line_clean, re.IGNORECASE)
                if gpa_match:
                    current["gpa"] = gpa_match.group(1).strip()
                continue

            if current and not current["gpa"]:
                gpa_match = re.search(r"GPA:?\s*([0-4]\.\d{1,2}(?:/[0-4]\.0)?)", line_clean, re.IGNORECASE)
                if gpa_match:
                    current["gpa"] = gpa_match.group(1).strip()

        if current and (current.get("institution") or current.get("degree")):
            entries.append(EducationEntry(**current))

        return entries

    def _extract_certifications(self, cert_lines: list[str]) -> list[CertificationEntry]:
        """Extract certifications and issuers."""
        certs: list[CertificationEntry] = []
        for line in cert_lines:
            clean = line.lstrip("-*•▪ ").strip()
            if not clean:
                continue

            name = clean
            issuer = "Certification Authority"
            if " - " in clean:
                parts = clean.split(" - ", 1)
                name, issuer = parts[0].strip(), parts[1].strip()
            elif " by " in clean:
                parts = clean.split(" by ", 1)
                name, issuer = parts[0].strip(), parts[1].strip()
            elif "(" in clean and ")" in clean:
                issuer_match = re.search(r"\(([^)]+)\)", clean)
                if issuer_match:
                    issuer = issuer_match.group(1).strip()
                    name = clean[:clean.find("(")].strip()

            certs.append(CertificationEntry(name=name, issuer=issuer))

        return certs

    def _extract_projects(self, proj_lines: list[str]) -> list[ProjectEntry]:
        """Extract personal and technical projects with robust multi-line bullet support."""
        projects: list[ProjectEntry] = []
        current: dict[str, Any] | None = None
        bullet_prefixes = ("-", "*", "•", "▪", "–", "—", "·", "●", "○", "◦", "⁃", "‣")

        for line in proj_lines:
            clean = line.strip()
            if not clean:
                continue

            is_bullet = clean.startswith(bullet_prefixes)
            ends_with_sentence_punct = clean.endswith((".", ",", ";", ":"))
            starts_with_upper = bool(re.match(r"^[A-Z0-9\"'(\[]", clean))
            word_count = len(clean.split())

            # A true project title:
            # - Not a bullet
            # - Starts with capitalized letter or digit
            # - Does not end with sentence-ending punctuation (like a period or comma)
            # - Relatively concise or has project separator like | or -
            is_potential_title = (
                not is_bullet
                and starts_with_upper
                and not ends_with_sentence_punct
                and (
                    word_count <= 8
                    or ("|" in clean and word_count <= 14)
                    or ((" - " in clean or " – " in clean) and word_count <= 14)
                )
            )

            if is_potential_title:
                if current and (current.get("name") or current.get("description")):
                    projects.append(ProjectEntry(**current))

                p_name = clean
                techs: list[str] = []
                if "|" in clean:
                    parts = [p.strip() for p in clean.split("|") if p.strip()]
                    p_name = parts[0]
                    if len(parts) > 1:
                        techs = [t.strip() for t in parts[1].split(",") if t.strip()]
                elif " - " in clean or " – " in clean:
                    sep = " – " if " – " in clean else " - "
                    parts = clean.split(sep, 1)
                    if len(parts[0].split()) <= 5:
                        p_name = parts[0].strip()
                        if "," in parts[1]:
                            techs = [t.strip() for t in parts[1].split(",") if t.strip()]

                current = {
                    "name": p_name,
                    "description": "",
                    "url": None,
                    "technologies": techs,
                }
            elif current:
                desc_line = clean.lstrip("-*•▪–—·●○◦⁃‣ ").strip()
                if is_bullet:
                    if not current["description"]:
                        current["description"] = "• " + desc_line
                    else:
                        current["description"] += "\n• " + desc_line
                else:
                    # Wrapped continuation of previous line
                    if not current["description"]:
                        current["description"] = desc_line
                    else:
                        current["description"] += " " + desc_line
            else:
                # Text before any recognized title
                if not is_bullet and not ends_with_sentence_punct:
                    current = {
                        "name": clean.lstrip("-*•▪–—·●○◦⁃‣ ").strip(),
                        "description": "",
                        "url": None,
                        "technologies": [],
                    }
                else:
                    current = {
                        "name": "Technical Project",
                        "description": "• " + clean.lstrip("-*•▪–—·●○◦⁃‣ ").strip() if is_bullet else clean,
                        "url": None,
                        "technologies": [],
                    }

        if current and (current.get("name") or current.get("description")):
            projects.append(ProjectEntry(**current))

        return projects

    def _compute_years_experience(
        self, employment: list[EmploymentEntry], raw_text: str
    ) -> float | None:
        """Estimate total years of experience from employment dates or text."""
        # 1. Check explicit mention in text (e.g. "6 years of experience")
        exp_mention = re.search(
            r"\b(\d{1,2})\+?\s*years?(?:\s+of)?\s+experience\b", raw_text, re.IGNORECASE
        )
        if exp_mention:
            try:
                return float(exp_mention.group(1))
            except ValueError:
                pass

        # 2. Compute from employment entries
        total_years = 0.0
        current_year = datetime.now(timezone.utc).year

        for emp in employment:
            s_year = self._extract_year(emp.start_date)
            e_year = current_year if emp.is_current else self._extract_year(emp.end_date)
            if s_year and e_year and e_year >= s_year:
                total_years += max(1.0, float(e_year - s_year))

        return round(total_years, 1) if total_years > 0 else None

    @staticmethod
    def _extract_year(date_str: str | None) -> int | None:
        if not date_str:
            return None
        m = re.search(r"\b(19\d{2}|20\d{2})\b", date_str)
        return int(m.group(1)) if m else None

    def _determine_seniority(
        self, employment: list[EmploymentEntry], years: float | None
    ) -> Literal["junior", "mid", "senior", "lead", "executive", "unknown"]:
        """Determine seniority level from titles and total experience."""
        all_titles = " ".join([e.title.lower() for e in employment])

        if any(k in all_titles for k in ("lead", "director", "head of", "vp", "chief", "cto")):
            return "lead"
        if any(k in all_titles for k in ("staff", "principal", "architect")):
            return "lead"
        if any(k in all_titles for k in ("senior", "sr.")):
            return "senior"
        if years is not None and years >= 5:
            return "senior"
        if years is not None and years >= 2:
            return "mid"
        if any(k in all_titles for k in ("intern", "junior", "jr.")):
            return "junior"

        return "mid" if (years and years >= 2) else "unknown"

    def _determine_target_roles(
        self, employment: list[EmploymentEntry], summary: str
    ) -> list[str]:
        """Identify candidate target roles from employment titles and summary."""
        roles: set[str] = set()

        for emp in employment[:3]:
            if emp.title and emp.title != "Professional":
                roles.add(emp.title)

        title_matches = _TITLE_REGEX.findall(summary)
        for m in title_matches:
            if len(m.strip()) > 3:
                roles.add(m.strip().title())

        return sorted(roles)
