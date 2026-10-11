"""
Document Rendering Engine.
Compiles structured tailored resume content into elegant print-ready HTML and PDF.
"""

from __future__ import annotations

from typing import Any

import structlog
from jinja2 import Template

from app.schemas.tailoring import TailoredResumeContent

log = structlog.get_logger(__name__)

RESUME_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{{ contact.name or contact.display_name or 'Resume' }} - Tailored Resume</title>
<style>
  @page {
    size: letter;
    margin: 0.55in 0.55in 0.55in 0.55in;
  }
  * {
    box-sizing: border-box;
  }
  body {
    font-family: "Latin Modern Roman", "Computer Modern", "Times New Roman", Times, Georgia, serif;
    color: #222222;
    background: #ffffff;
    line-height: 1.35;
    font-size: 9.5pt;
    margin: 0;
    padding: 0;
  }
  .header {
    text-align: center;
    margin-bottom: 8px;
  }
  .name {
    font-size: 21pt;
    font-weight: 700;
    color: #163A5F;
    margin-bottom: 3px;
    letter-spacing: -0.3px;
  }
  .headline {
    font-size: 10pt;
    font-weight: 600;
    color: #555555;
    margin-bottom: 3px;
  }
  .contact-line {
    font-size: 9pt;
    color: #222222;
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 6px;
  }
  .contact-line a {
    color: #163A5F;
    text-decoration: none;
  }
  .contact-line .sep {
    color: #888888;
    margin: 0 2px;
  }
  section {
    margin-top: 7px;
    margin-bottom: 6px;
  }
  .section-title {
    font-size: 11pt;
    font-weight: 700;
    color: #163A5F;
    text-transform: none;
    border-bottom: 1px solid #163A5F;
    padding-bottom: 1px;
    margin: 0 0 4px 0;
  }
  .summary-text {
    font-size: 9.3pt;
    color: #222222;
    margin: 0;
    text-align: justify;
    line-height: 1.35;
  }
  .skills-text {
    font-size: 9.2pt;
    color: #222222;
    line-height: 1.35;
    margin: 0;
  }
  .subheading-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-size: 9.5pt;
  }
  .subheading-row .title-left {
    font-weight: 700;
    color: #222222;
  }
  .subheading-row .date-right {
    font-weight: 700;
    color: #163A5F;
    font-size: 9pt;
  }
  .subheading-row .subtitle-left {
    font-style: italic;
    color: #555555;
    font-size: 9pt;
  }
  .subheading-row .loc-right {
    font-style: italic;
    color: #555555;
    font-size: 9pt;
  }
  .item-group {
    margin-bottom: 5px;
  }
  ul.bullets {
    margin: 2px 0 0 0;
    padding-left: 16px;
    list-style-type: disc;
  }
  ul.bullets li {
    font-size: 9.1pt;
    color: #222222;
    line-height: 1.32;
    margin-bottom: 1.5px;
  }
</style>
</head>
<body>
  <div class="header">
    <div class="name">{{ contact.name or contact.display_name or 'Candidate Name' }}</div>
    {% if content.headline %}
    <div class="headline">{{ content.headline }}</div>
    {% endif %}
    <div class="contact-line">
      {% if contact.location %}<span>{{ contact.location }}</span>{% endif %}
      {% if contact.phone %}<span class="sep">|</span><span>{{ contact.phone }}</span>{% endif %}
      {% if contact.email or contact.contact_email %}
        <span class="sep">|</span>
        <a href="mailto:{{ contact.email or contact.contact_email }}">
          {{- contact.email or contact.contact_email -}}
        </a>
      {% endif %}
      {% if contact.linkedin_url %}
        <span class="sep">|</span>
        <a href="{{ contact.linkedin_url }}">LinkedIn</a>
      {% endif %}
      {% if contact.github_url %}
        <span class="sep">|</span>
        <a href="{{ contact.github_url }}">GitHub</a>
      {% endif %}
    </div>
  </div>

  {% if content.summary %}
  <section>
    <div class="section-title">Summary</div>
    <p class="summary-text">{{ content.summary }}</p>
  </section>
  {% endif %}

  {% if content.skills %}
  <section>
    <div class="section-title">Skills</div>
    <p class="skills-text">{{ content.skills | join(', ') }}</p>
  </section>
  {% endif %}

  {% if content.experience %}
  <section>
    <div class="section-title">Experience</div>
    {% for exp in content.experience %}
    <div class="item-group">
      <div class="subheading-row">
        <span class="title-left">{{ exp.company }}</span>
        <span class="date-right">
          {%- if exp.start_date and exp.end_date -%}
            {{ exp.start_date }} – {{ exp.end_date }}
          {%- elif exp.start_date -%}
            {{ exp.start_date }} – Present
          {%- elif exp.end_date -%}
            {{ exp.end_date }}
          {%- endif -%}
        </span>
      </div>
      <div class="subheading-row">
        <span class="subtitle-left">{{ exp.title }}</span>
        <span class="loc-right">{{ exp.location or '' }}</span>
      </div>
      {% if exp.bullet_points %}
      <ul class="bullets">
        {% for bullet in exp.bullet_points %}
        <li>{{ bullet }}</li>
        {% endfor %}
      </ul>
      {% endif %}
    </div>
    {% endfor %}
  </section>
  {% endif %}

  {% if content.projects %}
  <section>
    <div class="section-title">Projects</div>
    {% for proj in content.projects %}
    <div class="item-group">
      <div class="subheading-row">
        <span class="title-left">
          {% if proj.url %}
            <a href="{{ proj.url }}" style="color: #222222; text-decoration: none;">
              {{- proj.name -}}
            </a>
          {% else %}
            {{- proj.name -}}
          {% endif %}
        </span>
        <span class="date-right">{{ proj.date or '' }}</span>
      </div>
      {% if proj.bullet_points %}
      <ul class="bullets">
        {% for b in proj.bullet_points %}
        <li>{{ b }}</li>
        {% endfor %}
      </ul>
      {% elif proj.description %}
      <ul class="bullets">
        <li>{{ proj.description }}</li>
      </ul>
      {% endif %}
    </div>
    {% endfor %}
  </section>
  {% endif %}

  {% if content.education %}
  <section>
    <div class="section-title">Education</div>
    {% for edu in content.education %}
    <div class="item-group">
      <div class="subheading-row">
        <span class="title-left">{{ edu.institution }}</span>
        <span class="date-right">
          {%- if edu.start_date and edu.end_date -%}
            {{ edu.start_date }} – {{ edu.end_date }}
          {%- elif edu.end_date or edu.start_date -%}
            {{ edu.end_date or edu.start_date }}
          {%- endif -%}
        </span>
      </div>
      <div class="subheading-row">
        <span class="subtitle-left">
          {{- edu.degree -}}
          {%- if edu.field_of_study %} in {{ edu.field_of_study }}{% endif -%}
          {%- if edu.gpa %}, GPA {{ edu.gpa }}{% endif -%}
        </span>
        <span class="loc-right">{{ edu.location or '' }}</span>
      </div>
      {% if edu.coursework %}
      <ul class="bullets">
        <li>Relevant Coursework: {{ edu.coursework | join(', ') }}</li>
      </ul>
      {% endif %}
    </div>
    {% endfor %}
  </section>
  {% endif %}

  {% if content.certifications %}
  <section>
    <div class="section-title">Certifications</div>
    <ul class="bullets">
      {% for cert in content.certifications %}
      <li>{{ cert.name if cert is mapping else cert }}</li>
      {% endfor %}
    </ul>
  </section>
  {% endif %}
</body>
</html>
"""


class DocumentRenderer:
    """Renderer for high-quality tailored resumes in HTML and PDF formats."""

    @staticmethod
    def render_html(
        content: TailoredResumeContent,
        contact: dict[str, Any] | None = None,
    ) -> str:
        """Render tailored resume to clean HTML string using Jinja2."""
        template = Template(RESUME_HTML_TEMPLATE)
        return template.render(
            content=content,
            contact=contact or {},
        )

    @staticmethod
    def render_pdf_reportlab(
        content: TailoredResumeContent,
        contact: dict[str, Any] | None = None,
    ) -> bytes:
        """Render a clean, professional ATS-compatible PDF using ReportLab matching LaTeX layout."""
        import io

        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import (
            HRFlowable,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        color_accent = colors.HexColor("#163A5F")
        color_dark = colors.HexColor("#222222")
        color_muted = colors.HexColor("#555555")

        name_style = ParagraphStyle(
            "CandidateName",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            alignment=1,  # Centered
            textColor=color_accent,
        )
        headline_style = ParagraphStyle(
            "CandidateHeadline",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            alignment=1,
            textColor=color_muted,
            spaceBefore=1,
        )
        contact_style = ParagraphStyle(
            "CandidateContact",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=12,
            alignment=1,
            textColor=color_dark,
            spaceBefore=2,
        )
        section_heading = ParagraphStyle(
            "SectionHeading",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=color_accent,
            spaceBefore=6,
            spaceAfter=1,
        )
        body_style = ParagraphStyle(
            "ResumeBody",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.8,
            leading=12,
            textColor=color_dark,
        )
        sub_left_bold = ParagraphStyle(
            "SubLeftBold",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=color_dark,
        )
        sub_right_accent = ParagraphStyle(
            "SubRightAccent",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=12,
            alignment=2,  # Right
            textColor=color_accent,
        )
        sub_left_italic = ParagraphStyle(
            "SubLeftItalic",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=11,
            textColor=color_muted,
        )
        sub_right_italic = ParagraphStyle(
            "SubRightItalic",
            parent=styles["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8.5,
            leading=11,
            alignment=2,  # Right
            textColor=color_muted,
        )
        bullet_style = ParagraphStyle(
            "ResumeBullet",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            leftIndent=12,
            textColor=color_dark,
            spaceAfter=1.5,
        )

        contact_dict = contact or {}
        name = contact_dict.get("display_name") or contact_dict.get("name") or "Candidate Name"
        email = contact_dict.get("contact_email") or contact_dict.get("email") or ""
        phone = contact_dict.get("phone") or ""
        location = contact_dict.get("location") or ""
        linkedin = contact_dict.get("linkedin_url") or ""
        github = contact_dict.get("github_url") or ""

        contact_parts = [p for p in [location, phone, email] if p]
        if linkedin:
            contact_parts.append("LinkedIn")
        if github:
            contact_parts.append("GitHub")

        story = []

        # 1. Header
        story.append(Paragraph(name, name_style))
        if content.headline:
            story.append(Paragraph(content.headline, headline_style))
        if contact_parts:
            story.append(Paragraph(" | ".join(contact_parts), contact_style))
        story.append(Spacer(1, 3))

        def make_section(title: str):
            story.append(Paragraph(title, section_heading))
            story.append(
                HRFlowable(
                    width="100%", thickness=1, color=color_accent, spaceAfter=3, spaceBefore=1
                )
            )

        # 2. Professional Summary
        if content.summary:
            make_section("Summary")
            story.append(Paragraph(content.summary, body_style))

        # 3. Skills
        if content.skills:
            make_section("Skills")
            skills_text = ", ".join(content.skills)
            story.append(Paragraph(skills_text, body_style))

        table_tstyle = TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )

        # 4. Experience
        if content.experience:
            make_section("Experience")
            for exp in content.experience:
                date_sep = " – " if exp.start_date else ""
                end_str = exp.end_date if exp.end_date else "Present"
                date_str = f"{exp.start_date or ''}{date_sep}{end_str}"
                row1 = [
                    Paragraph(exp.company, sub_left_bold),
                    Paragraph(date_str, sub_right_accent),
                ]
                row2 = [
                    Paragraph(exp.title, sub_left_italic),
                    Paragraph(exp.location or "", sub_right_italic),
                ]
                t = Table([row1, row2], colWidths=[390, 150])
                t.setStyle(table_tstyle)
                story.append(t)

                for bullet in exp.bullet_points:
                    story.append(Paragraph(f"• {bullet}", bullet_style))
                story.append(Spacer(1, 3))

        # 5. Projects
        if content.projects:
            make_section("Projects")
            for proj in content.projects:
                p_name = (
                    proj.get("name", "") if isinstance(proj, dict) else getattr(proj, "name", "")
                )
                p_date = (
                    proj.get("date", "") if isinstance(proj, dict) else getattr(proj, "date", "")
                )
                p_desc = (
                    proj.get("description", "")
                    if isinstance(proj, dict)
                    else getattr(proj, "description", "")
                )
                p_bullets = (
                    proj.get("bullet_points", [])
                    if isinstance(proj, dict)
                    else getattr(proj, "bullet_points", [])
                )

                row = [
                    Paragraph(p_name, sub_left_bold),
                    Paragraph(str(p_date or ""), sub_right_accent),
                ]
                t = Table([row], colWidths=[390, 150])
                t.setStyle(table_tstyle)
                story.append(t)

                if p_bullets:
                    for b in p_bullets:
                        story.append(Paragraph(f"• {b}", bullet_style))
                elif p_desc:
                    story.append(Paragraph(f"• {p_desc}", bullet_style))
                story.append(Spacer(1, 3))

        # 6. Education
        if content.education:
            make_section("Education")
            for edu in content.education:
                e_inst = (
                    edu.get("institution", "")
                    if isinstance(edu, dict)
                    else getattr(edu, "institution", "")
                )
                e_date = (
                    (edu.get("end_date") or edu.get("start_date") or "")
                    if isinstance(edu, dict)
                    else (getattr(edu, "end_date", "") or getattr(edu, "start_date", "") or "")
                )
                study_field = (
                    edu.get("field_of_study")
                    if isinstance(edu, dict)
                    else getattr(edu, "field_of_study", "")
                )
                field_str = f" in {study_field}" if study_field else ""
                deg_base = (
                    edu.get("degree", "Degree")
                    if isinstance(edu, dict)
                    else getattr(edu, "degree", "Degree")
                )
                deg = f"{deg_base}{field_str}"
                e_loc = (
                    edu.get("location", "")
                    if isinstance(edu, dict)
                    else getattr(edu, "location", "")
                )

                row1 = [
                    Paragraph(e_inst, sub_left_bold),
                    Paragraph(str(e_date), sub_right_accent),
                ]
                row2 = [
                    Paragraph(deg, sub_left_italic),
                    Paragraph(str(e_loc or ""), sub_right_italic),
                ]
                t = Table([row1, row2], colWidths=[390, 150])
                t.setStyle(table_tstyle)
                story.append(t)

                coursework = (
                    edu.get("coursework", [])
                    if isinstance(edu, dict)
                    else getattr(edu, "coursework", [])
                )
                if coursework:
                    story.append(
                        Paragraph(f"• Relevant Coursework: {', '.join(coursework)}", bullet_style)
                    )
                story.append(Spacer(1, 2))

        # 7. Certifications
        if content.certifications:
            make_section("Certifications")
            for cert in content.certifications:
                c_name = cert.get("name") if isinstance(cert, dict) else str(cert)
                story.append(Paragraph(f"• {c_name}", bullet_style))

        doc.build(story)
        return buf.getvalue()

    @staticmethod
    def render_pdf(
        content: TailoredResumeContent,
        contact: dict[str, Any] | None = None,
    ) -> tuple[bytes, str]:
        """
        Compile tailored resume to PDF bytes.
        Attempts WeasyPrint first, then ReportLab pure-python engine.
        Returns (document_bytes, content_type).
        """
        html_str = DocumentRenderer.render_html(content, contact)

        try:
            from weasyprint import HTML  # type: ignore[import-untyped]

            pdf_bytes = HTML(string=html_str).write_pdf()
            if pdf_bytes is not None:
                return pdf_bytes, "application/pdf"
        except Exception as exc:
            log.info(
                "weasyprint_pdf_render_fallback_to_reportlab",
                reason=f"WeasyPrint native compiler not available: {exc}. Using ReportLab engine.",
            )

        try:
            rl_pdf = DocumentRenderer.render_pdf_reportlab(content, contact)
            return rl_pdf, "application/pdf"
        except Exception as exc:
            log.warning(
                "reportlab_pdf_render_fallback",
                reason=f"ReportLab failed: {exc}. Falling back to HTML format.",
            )
            return html_str.encode("utf-8"), "text/html; charset=utf-8"

