import { SKILL_KEYWORDS } from '../data/jobs';

export interface ParsedResume {
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  link?: string;
  summary: string;
  skills: string;
  experience: string;
  education: string;
  projects: string;
  certs: string;
}

const SECTION_HEADERS: { key: keyof Omit<ParsedResume, 'name' | 'email' | 'phone' | 'location' | 'link'>; regex: RegExp }[] = [
  {
    key: 'summary',
    regex: /^(?:professional\s+summary|executive\s+summary|career\s+summary|career\s+objective|summary|profile|about\s+me|about|objective|personal\s+statement|overview)$/i,
  },
  {
    key: 'skills',
    regex: /^(?:technical\s+skills|core\s+competencies|key\s+skills|skills\s*(?:&|and|\/)\s*technologies|skills\s*(?:&|and|\/)\s*tools|skills|technologies|tools\s*(?:&|and|\/)\s*technologies|areas\s+of\s+expertise|tech\s+stack|competencies|programming\s+languages|software\s+skills)$/i,
  },
  {
    key: 'experience',
    regex: /^(?:work\s+experience|professional\s+experience|employment\s+history|work\s+history|career\s+history|experience|relevant\s+experience|practical\s+experience|internships?|employment)$/i,
  },
  {
    key: 'education',
    regex: /^(?:academic\s+background|educational\s+background|education\s*(?:&|and|\/)\s*credentials|education|degrees?|academics?|qualifications?|academic\s+history|education\s*(?:&|and|\/)\s*training)$/i,
  },
  {
    key: 'projects',
    regex: /^(?:technical\s+projects|personal\s+projects|key\s+projects|academic\s+projects|projects\s*(?:&|and|\/)\s*initiatives|projects|selected\s+projects|notable\s+projects|portfolio)$/i,
  },
  {
    key: 'certs',
    regex: /^(?:certifications\s*(?:&|and|\/)\s*licenses|licenses\s*(?:&|and|\/)\s*certifications|certifications|certificates|courses\s*(?:&|and|\/)\s*certifications|honors\s*(?:&|and|\/)\s*awards|achievements|awards|leadership|extracurricular)$/i,
  },
];

/**
 * Robustly parses plain resume text into individual structured sections.
 * Guarantees that education, projects, skills, and summary are never lumped into experience.
 */
export function parseResumeSections(rawText: string): ParsedResume {
  const lines = rawText.split(/\r?\n/).map((l) => l.trim());

  const buckets: Record<keyof Omit<ParsedResume, 'name' | 'email' | 'phone' | 'location' | 'link'>, string[]> = {
    summary: [],
    skills: [],
    experience: [],
    education: [],
    projects: [],
    certs: [],
  };

  type BucketKey = keyof typeof buckets;
  let activeBucket: BucketKey | null = null;
  const headerLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]!;
    if (!line) continue;

    // Clean decorations: leading markdown hashes, asterisks, bullets, numbers, brackets and trailing colons/dashes
    const cleaned = line
      .replace(/^[#*=\-–—_•·▪\d.)\s\[]+/, '')
      .replace(/[:\-–—=*_#\]\s]+$/, '')
      .trim();
    const isShortHeader = cleaned.length > 0 && cleaned.length < 50 && !cleaned.includes('.');

    let matchedKey: BucketKey | null = null;
    if (isShortHeader) {
      for (const sh of SECTION_HEADERS) {
        if (sh.regex.test(cleaned)) {
          matchedKey = sh.key;
          break;
        }
      }
    }

    if (matchedKey) {
      activeBucket = matchedKey;
      continue;
    }

    if (!activeBucket) {
      headerLines.push(line);
    } else {
      buckets[activeBucket].push(line);
    }
  }

  // 1. Email extraction
  const emailMatch = rawText.match(/[\w.+-]+@[\w-]+\.[\w.-]+/);

  // 2. Phone extraction (supporting Egyptian and international formats with or without spaces/dashes)
  let extractedPhone: string | undefined;
  const phoneCandidates = [
    /(?:phone|mobile|tel|cell|whatsapp)?[:\s]*(\+?\d{1,3}[-.\s]?(?:\(?\d{2,4}\)?[-.\s]?)?\d{3,4}[-.\s]?\d{3,4}\b)/i,
    /(?:phone|mobile|tel|cell|whatsapp)?[:\s]*(\+?\d{1,3}\s*\d{9,12}\b)/i,
    /(\+?\d{9,15}\b)/,
  ];
  for (const pr of phoneCandidates) {
    const m = rawText.match(pr);
    if (m && m[1]) {
      const cleanedNum = m[1].trim();
      // Ensure it's not a year range like 2020-2024
      if (!/^\d{4}\s*[-–—]\s*\d{4}$/.test(cleanedNum) && cleanedNum.replace(/\D/g, '').length >= 7) {
        extractedPhone = cleanedNum;
        break;
      }
    }
  }

  // 3. Location extraction (from header pipe segments or standard city/country format)
  let extractedLocation: string | undefined;
  for (const hl of headerLines) {
    if (hl.includes('|')) {
      const parts = hl.split('|').map((p) => p.trim());
      for (const p of parts) {
        if (/^[A-Z][a-zA-Z ]+,\s*[A-Z][a-zA-Z]+$/.test(p) && !p.includes('@')) {
          extractedLocation = p;
          break;
        }
      }
    }
    if (extractedLocation) break;
  }
  if (!extractedLocation) {
    const locMatch = rawText.match(/\b([A-Z][a-zA-Z ]+,\s*(?:[A-Z]{2}|[A-Z][a-zA-Z]+))\b/);
    if (locMatch && !/^(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)/i.test(locMatch[1])) {
      extractedLocation = locMatch[1].trim();
    }
  }

  // 4. LinkedIn / Portfolio extraction
  let extractedLink: string | undefined;
  const liMatch = rawText.match(/(?:https?:\/\/)?(?:[a-zA-Z0-9-]+\.)?linkedin\.com\/(?:in\/)?[A-Za-z0-9_-]+/i);
  if (liMatch) {
    const url = liMatch[0].replace(/[),|]+$/, '');
    extractedLink = url.startsWith('http') ? url : `https://${url}`;
  } else {
    const ghMatch = rawText.match(/(?:https?:\/\/)?(?:www\.)?github\.com\/[A-Za-z0-9_-]+/i);
    if (ghMatch) {
      const url = ghMatch[0].replace(/[),|]+$/, '');
      extractedLink = url.startsWith('http') ? url : `https://${url}`;
    }
  }

  // 5. Name candidate: first non-empty line of header that isn't email, phone, location or link
  let extractedName = '';
  for (const h of headerLines) {
    if (
      h.length > 1 &&
      h.length < 50 &&
      !h.includes('@') &&
      !h.match(/\d{4}/) &&
      !h.includes('http') &&
      !h.includes('|')
    ) {
      extractedName = h;
      break;
    }
  }

  // 6. Format skills: clean bullets and combine into comma-separated list
  let skillsText = buckets.skills
    .join(', ')
    .replace(/[•*·▪\-–—]/g, '')
    .split(/[,|•\n\t]+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 1 && s.length < 40 && !s.includes(':'))
    .join(', ');

  // If skills section was not labeled or sparse, search full text for known technical skills
  if (skillsText.length < 15) {
    const foundSkills = SKILL_KEYWORDS.filter((k) =>
      new RegExp(`\\b${k.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'i').test(rawText),
    );
    if (foundSkills.length > 0) {
      const existing = new Set(skillsText.split(',').map((s) => s.trim().toLowerCase()));
      const added = foundSkills.filter((k) => !existing.has(k.toLowerCase()));
      skillsText = skillsText ? `${skillsText}, ${added.join(', ')}` : added.join(', ');
    }
  }

  // 7. If summary was not labeled, check if header contains an introductory description
  let summaryText = buckets.summary.join('\n').trim();
  if (!summaryText && headerLines.length > 1) {
    const candidateSummary = headerLines.slice(1).filter((l) => l.length > 40 && !l.includes('|')).join('\n');
    if (candidateSummary) summaryText = candidateSummary;
  }

  return {
    name: extractedName || undefined,
    email: emailMatch ? emailMatch[0] : undefined,
    phone: extractedPhone,
    location: extractedLocation,
    link: extractedLink,
    summary: summaryText,
    skills: skillsText,
    experience: buckets.experience.join('\n').trim(),
    education: buckets.education.join('\n').trim(),
    projects: buckets.projects.join('\n').trim(),
    certs: buckets.certs.join('\n').trim(),
  };
}

/**
 * Format backend ExtractedProfile response into frontend Profile shape.
 * Robustly reads both active_version.content JSONB and active_version top-level attributes.
 */
export function formatBackendProfileToState(backendData: any, defaultName = 'Candidate', defaultEmail = ''): any {
  const profile = backendData.profile || backendData || {};
  const activeVer = backendData.active_version || {};
  const content = activeVer.content || activeVer || {};
  const contact = content.contact || activeVer.contact || profile.contact || {};

  // 1. Format employment history
  const employmentList = content.employment_history || activeVer.employment_history || profile.employment_history || [];
  const expStr = Array.isArray(employmentList) && employmentList.length > 0
    ? employmentList
        .filter((e: any) => {
          const t = (e.title || '').trim().toLowerCase();
          const c = (e.company || '').trim().toLowerCase();
          if (!t && !c) return false;
          if (t === 'professional' && (!c || c === 'company' || c === 'organization')) return false;
          return true;
        })
        .map((e: any) => {
          const rawTitle = (e.title || e.job_title || '').replace(/^Professional$/i, '').trim();
          let rawComp = (e.company || '').replace(/^(?:Company|Organization)$/i, '').trim();
          rawComp = rawComp.replace(/\s*\([^)]*(?:app store|google play|github|link)[^)]*\)/gi, '').trim();
          rawComp = rawComp.replace(/^[(\[]|[)\]]$/g, '').trim();

          const dates = [e.start_date, e.end_date || (e.is_current ? 'Present' : '')].filter(Boolean).join(' - ');
          const loc = e.location ? e.location.trim() : '';

          const roleParts = [rawTitle, rawComp].filter(Boolean);
          const metaParts = [dates, loc].filter(Boolean);

          let headerLine = roleParts.join(' · ');
          if (metaParts.length > 0) {
            headerLine += ` (${metaParts.join(' · ')})`;
          }

          const desc = e.description ? e.description.trim() : '';
          const achs = Array.isArray(e.achievements) && e.achievements.length > 0
            ? e.achievements.map((a: string) => `• ${a.trim()}`).join('\n')
            : '';

          const contentLines = [desc, achs].filter(Boolean).join('\n');
          return contentLines ? `${headerLine}\n${contentLines}` : headerLine;
        })
        .join('\n\n')
    : typeof profile.experience === 'string' ? profile.experience : '';

  // 2. Format education
  const eduList = content.education || activeVer.education || profile.education || [];
  const eduStr = Array.isArray(eduList) && eduList.length > 0
    ? eduList
        .filter((ed: any) => {
          const d = (ed.degree || '').trim().toLowerCase();
          const i = (ed.institution || '').trim().toLowerCase();
          if (!d && !i) return false;
          if (d === 'degree' && (!i || i === 'university')) return false;
          return true;
        })
        .map((ed: any) => {
          const rawDeg = (ed.degree || '').replace(/^Degree$/i, '').trim();
          const rawField = (ed.field_of_study || '').trim();
          const deg = [rawDeg, rawField].filter(Boolean).join(' in ');
          let inst = (ed.institution || '').replace(/^University$/i, '').trim();

          if (deg && inst.toLowerCase().includes(deg.toLowerCase())) {
            inst = inst.replace(new RegExp(deg.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i'), '').replace(/^[\s,·\-]+|[\s,·\-]+$/g, '').trim();
          }

          const dates = [ed.start_date, ed.end_date].filter(Boolean).join(' - ');
          const gpa = ed.gpa ? `GPA: ${ed.gpa}` : '';
          const metaParts = [dates, gpa].filter(Boolean);

          const mainParts = [deg, inst].filter(Boolean);
          let eduLine = mainParts.join(' · ');
          if (metaParts.length > 0) {
            eduLine += ` (${metaParts.join(' · ')})`;
          }
          return eduLine;
        })
        .join('\n\n')
    : typeof profile.education === 'string' ? profile.education : '';

  // 3. Format projects
  const projList = content.projects || activeVer.projects || profile.projects || [];
  const projStr = Array.isArray(projList) && projList.length > 0
    ? projList
        .map((p: any) => {
          const name = p.name || '';
          const techs = Array.isArray(p.technologies) && p.technologies.length > 0 ? ` [${p.technologies.join(', ')}]` : '';
          const desc = p.description || '';
          return `${name}${techs}\n${desc}`.trim();
        })
        .join('\n\n')
    : typeof profile.projects === 'string' ? profile.projects : '';

  // 4. Format certs
  const certList = content.certifications || activeVer.certifications || profile.certifications || [];
  const certStr = Array.isArray(certList) && certList.length > 0
    ? certList
        .map((c: any) => `${c.name || ''}${c.issuer ? ' - ' + c.issuer : ''}${c.issue_date ? ' (' + c.issue_date + ')' : ''}`.trim())
        .join('\n')
    : typeof profile.certs === 'string' ? profile.certs : '';

  // 5. Format skills
  const skillsList = content.skills || activeVer.skills || profile.skills || [];
  const skillsStr = Array.isArray(skillsList) ? skillsList.join(', ') : String(skillsList || '');

  // 6. Summary
  const summaryStr = content.summary || activeVer.summary || profile.summary || '';

  return {
    name: contact.name || profile.display_name || defaultName,
    email: contact.email || profile.email || defaultEmail,
    phone: contact.phone || profile.phone || profile.contact_phone || '',
    location: contact.location || profile.location || '',
    link: contact.linkedin_url || contact.portfolio_url || profile.linkedin || profile.linkedin_url || '',
    summary: summaryStr,
    skills: skillsStr,
    experience: expStr,
    education: eduStr,
    projects: projStr,
    certs: certStr,
    years_experience: activeVer.years_experience ?? content.years_experience ?? profile.years_experience,
    confirmed: {
      summary: !!summaryStr,
      skills: !!skillsStr,
      experience: !!expStr,
      education: !!eduStr,
      projects: !!projStr,
      certs: !!certStr,
    },
    created: new Date().toLocaleDateString(),
  };
}

export interface ExperienceCardItem {
  id: string;
  title: string;
  company: string;
  location: string;
  mode: string;
  startDate: string;
  endDate: string;
  isCurrent: boolean;
  bullets: string[];
}

/**
 * Parses raw or formatted experience text into discrete LinkedIn-styled cards.
 */
export function parseExperienceToCards(text: string): ExperienceCardItem[] {
  if (!text || !text.trim()) return [];

  // Split into entry chunks either by double newlines or by lines that clearly start a new position
  const rawBlocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const cards: ExperienceCardItem[] = [];

  const datePattern = /(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{4}\s*[-–—]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(?:\d{4}|Present|Current|Now)/i;
  const modePattern = /\b(Remote|Hybrid|On-site)\b/i;

  rawBlocks.forEach((block, idx) => {
    const lines = block.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;

    let headerLine = lines[0] || '';
    let subHeaderLine = '';
    const bulletLines: string[] = [];

    // Check if line 2 is part of header (e.g. Title & Location when line 1 was Company & Dates)
    if (lines.length > 1 && !lines[1]!.startsWith('-') && !lines[1]!.startsWith('•') && !lines[1]!.startsWith('–') && !lines[1]!.startsWith('*')) {
      subHeaderLine = lines[1]!;
      for (let i = 2; i < lines.length; i++) {
        bulletLines.push(lines[i]!);
      }
    } else {
      for (let i = 1; i < lines.length; i++) {
        bulletLines.push(lines[i]!);
      }
    }

    // Extract dates
    let startDate = '';
    let endDate = '';
    let isCurrent = false;

    const dateMatch = headerLine.match(datePattern) || (subHeaderLine ? subHeaderLine.match(datePattern) : null);
    if (dateMatch) {
      const parts = dateMatch[0].split(/[-–—]/).map((p) => p.trim());
      startDate = parts[0] || '';
      endDate = parts[1] || '';
      if (/present|current|now/i.test(endDate)) {
        isCurrent = true;
        endDate = 'Present';
      }
    }

    // Extract workplace mode (Remote, Hybrid, On-site)
    let mode = '';
    const modeMatch = headerLine.match(modePattern) || (subHeaderLine ? subHeaderLine.match(modePattern) : null);
    if (modeMatch && modeMatch[1]) {
      mode = modeMatch[1].charAt(0).toUpperCase() + modeMatch[1].slice(1).toLowerCase();
    }

    // Extract location (e.g. "Cairo, Egypt", "Alexandria, Egypt")
    let location = '';
    const locMatch = headerLine.match(/\b([A-Z][a-zA-Z\s]+,\s*(?:[A-Z][a-zA-Z\s]+|[A-Z]{2}))\b/)
      || (subHeaderLine ? subHeaderLine.match(/\b([A-Z][a-zA-Z\s]+,\s*(?:[A-Z][a-zA-Z\s]+|[A-Z]{2}))\b/) : null);
    if (locMatch && locMatch[1] && !locMatch[1].toLowerCase().includes('present')) {
      location = locMatch[1].trim();
    }

    // Extract Title and Company
    let title = '';
    let company = '';

    // Strip paren metadata from headerLine: e.g. "Title · Company (Dates · Location · Mode)"
    const cleanHeader = headerLine.replace(/\((?:[^)]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Remote|Hybrid|Present)[^)]*)\)/gi, '').trim();

    if (cleanHeader.includes(' · ')) {
      const parts = cleanHeader.split(' · ').map((p) => p.trim());
      title = parts[0] || '';
      company = parts.slice(1).join(' · ');
    } else if (cleanHeader.includes(' at ')) {
      const parts = cleanHeader.split(' at ').map((p) => p.trim());
      title = parts[0] || '';
      company = parts[1] || '';
    } else if (subHeaderLine) {
      if (cleanHeader.match(datePattern)) {
        company = cleanHeader.replace(datePattern, '').replace(/^[(\[]|[)\]]$/g, '').trim();
        title = subHeaderLine.replace(/\b(?:Remote|Hybrid|On-site)\b/i, '').replace(/^[·\-,|]+|[·\-,|]+$/g, '').trim();
      } else {
        title = cleanHeader;
        company = subHeaderLine;
      }
    } else {
      title = cleanHeader;
    }

    // Cleanup artifacts like "at Company" or empty parens
    title = title.replace(/\s+at\s+Company\b/gi, '').replace(/\(\s*\)/g, '').trim();
    company = company.replace(/^(?:Company|Organization)$/i, '').replace(/\(\s*\)/g, '').trim();
    if (!title && company) {
      title = company;
      company = '';
    }
    if (!title) {
      title = `Position ${idx + 1}`;
    }

    // Clean bullets
    const bullets = bulletLines
      .map((b) => b.replace(/^[\u2013\u2014\-*•▪·\d.)\s]+/, '').trim())
      .filter(Boolean);

    cards.push({
      id: `exp-${idx}-${Date.now()}`,
      title,
      company,
      location,
      mode,
      startDate,
      endDate: endDate || (isCurrent ? 'Present' : ''),
      isCurrent,
      bullets,
    });
  });

  return cards;
}

/**
 * Serializes discrete experience cards back into standard ATS multi-line format.
 */
export function serializeCardsToExperience(cards: ExperienceCardItem[]): string {
  return cards
    .map((c) => {
      const metaParts: string[] = [];
      const dateStr = [c.startDate, c.endDate || (c.isCurrent ? 'Present' : '')].filter(Boolean).join(' - ');
      if (dateStr) metaParts.push(dateStr);
      if (c.location) metaParts.push(c.location);
      if (c.mode) metaParts.push(c.mode);

      const roleParts = [c.title, c.company].filter(Boolean);
      let header = roleParts.join(' · ');
      if (metaParts.length > 0) {
        header += ` (${metaParts.join(' · ')})`;
      }

      const achs = c.bullets
        .filter(Boolean)
        .map((b) => (b.startsWith('-') || b.startsWith('•') || b.startsWith('–') ? b : `- ${b}`))
        .join('\n');

      return achs ? `${header}\n${achs}` : header;
    })
    .join('\n\n');
}
