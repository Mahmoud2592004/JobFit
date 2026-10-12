import { SKILL_KEYWORDS } from '../data/jobs';
import type { ItemLink } from '../types';

export type { ItemLink };

export function extractItemLinks(text: string, knownUrls: string[] = []): { cleanText: string; links: ItemLink[] } {
  const links: ItemLink[] = [];

  // 1. Markdown links: [Label](url)
  const mdRegex = /\[([^\]]+)\]\(([^)]*)\)/g;
  let match;
  let hasMd = false;
  while ((match = mdRegex.exec(text)) !== null) {
    hasMd = true;
    links.push({
      label: match[1]!.trim(),
      url: match[2]!.trim(),
    });
  }

  if (hasMd) {
    const cleanText = text
      .replace(/\(\s*\[[^\]]+\]\([^)]*\)(?:\s*\|\s*\[[^\]]+\]\([^)]*\))*\s*\)/g, '')
      .replace(/\[([^\]]+)\]\([^)]*\)/g, '')
      .replace(/\(\s*\)/g, '')
      .trim();
    return { cleanText, links };
  }

  // 2. Parenthesized links like (Google Play | App Store) or (GitHub)
  const parenMatch = text.match(/\(([^)]*(?:Google Play|App Store|GitHub|GitLab|Demo|Live Demo|Play Store|AppStore|Link|Website|Portfolio)[^)]*)\)/i);
  if (parenMatch && parenMatch[1]) {
    const rawParts = parenMatch[1].split('|').map((p) => p.trim()).filter(Boolean);
    rawParts.forEach((part) => {
      const colonMatch = part.match(/^([^:]+):\s*(https?:\/\/\S+)$/i);
      if (colonMatch) {
        links.push({
          label: colonMatch[1]!.trim(),
          url: colonMatch[2]!.trim(),
        });
      } else {
        let matchedUrl = '';
        const lowLbl = part.toLowerCase();
        if (lowLbl.includes('google play') || lowLbl.includes('play store')) {
          matchedUrl = knownUrls.find((u) => u.toLowerCase().includes('play.google.com')) || '';
        } else if (lowLbl.includes('app store') || lowLbl.includes('appstore') || lowLbl.includes('apple')) {
          matchedUrl = knownUrls.find((u) => u.toLowerCase().includes('apps.apple.com')) || '';
        } else if (lowLbl.includes('github') || lowLbl.includes('code') || lowLbl.includes('repo')) {
          matchedUrl = knownUrls.find((u) => u.toLowerCase().includes('github.com')) || '';
        }
        links.push({
          label: part,
          url: matchedUrl,
        });
      }
    });

    const cleanText = text.replace(parenMatch[0], '').replace(/\(\s*\)/g, '').trim();
    return { cleanText, links };
  }

  return { cleanText: text, links: [] };
}

export function serializeItemLinks(links?: ItemLink[]): string {
  if (!links || links.length === 0) return '';
  const valid = links.filter((l) => l.label && l.label.trim());
  if (valid.length === 0) return '';
  const parts = valid.map((l) => {
    const lbl = l.label.trim();
    const url = (l.url || '').trim();
    return url ? `[${lbl}](${url})` : lbl;
  });
  return ` (${parts.join(' | ')})`;
}

export interface ParsedResume {
  name?: string;
  email?: string;
  phone?: string;
  location?: string;
  link?: string;
  github?: string;
  other_links?: string[];
  summary: string;
  skills: string;
  experience: string;
  leadership: string;
  education: string;
  projects: string;
  certs: string;
}

type SectionBucketKey = 'summary' | 'skills' | 'experience' | 'leadership' | 'education' | 'projects' | 'certs';

const SECTION_HEADERS: { key: SectionBucketKey; regex: RegExp }[] = [
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
    key: 'leadership',
    regex: /^(?:leadership(?:\s*(?:&|and|\/)\s*(?:community|extracurricular|volunteering|service))?|leadership(?:\s+activities|\s+experience|\s+roles?)?|extracurricular(?:\s+activities)?|community(?:\s+involvement|\s+service|\s+leadership)?|volunteer(?:ing|\s+experience|\s+work)?|student\s+activities)$/i,
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
    regex: /^(?:certifications\s*(?:&|and|\/)\s*licenses|licenses\s*(?:&|and|\/)\s*certifications|certifications|certificates|courses\s*(?:&|and|\/)\s*certifications|courses|training|professional\s+development|honors\s*(?:&|and|\/)\s*awards|achievements|awards)$/i,
  },
];

/**
 * Robustly parses plain resume text into individual structured sections.
 * Guarantees that education, projects, skills, and summary are never lumped into experience.
 */
export function parseResumeSections(rawText: string): ParsedResume {
  const lines = rawText.split(/\r?\n/).map((l) => l.trim());

  const buckets: Record<SectionBucketKey, string[]> = {
    summary: [],
    skills: [],
    experience: [],
    leadership: [],
    education: [],
    projects: [],
    certs: [],
  };

  type BucketKey = SectionBucketKey;
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

  // 4. Link extraction (LinkedIn, GitHub, and additional URLs)
  let extractedLink: string | undefined;
  let extractedGithub: string | undefined;
  const rawOtherLinks: string[] = [];

  const allUrls = rawText.match(/(?:https?:\/\/[^\s)\]>"]+|(?<!@)(?:www\.)[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+(?:\/[^\s)\]>"]*)?|github\.com\/[^\s)\]>"]+|linkedin\.com\/[^\s)\]>"]+)/gi) || [];
  for (const rawUrl of allUrls) {
    const cleanUrl = rawUrl.replace(/[),|.]+$/, '');
    const fullUrl = cleanUrl.startsWith('http') ? cleanUrl : `https://${cleanUrl}`;
    const low = fullUrl.toLowerCase();
    if (/linkedin\.com/i.test(low)) {
      if (!extractedLink) extractedLink = fullUrl;
    } else if (/github\.com/i.test(low)) {
      const ghUser = low.replace(/https?:\/\/(?:www\.)?github\.com\/?/i, '').replace(/\/$/, '');
      if (!ghUser.includes('/')) {
        if (!extractedGithub) extractedGithub = fullUrl;
      } else if (!rawOtherLinks.includes(fullUrl)) {
        rawOtherLinks.push(fullUrl);
      }
    } else if (!rawOtherLinks.includes(fullUrl)) {
      rawOtherLinks.push(fullUrl);
    }
  }

  const extractedOtherLinks = rawOtherLinks.filter((l) => {
    const low = l.toLowerCase();
    if (low.includes('linkedin.com')) return false;
    const ghClean = low.replace(/^https?:\/\/(?:www\.)?github\.com\/?/, '').replace(/\/$/, '');
    if (ghClean && !ghClean.includes('/')) return false;
    if (extractedLink && l === extractedLink) return false;
    if (extractedGithub && l === extractedGithub) return false;
    return true;
  });

  if (!extractedLink && extractedOtherLinks.length > 0) {
    extractedLink = extractedOtherLinks[0];
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
    github: extractedGithub,
    other_links: extractedOtherLinks,
    summary: summaryText,
    skills: skillsText,
    experience: buckets.experience.join('\n').trim(),
    leadership: buckets.leadership.join('\n').trim(),
    education: buckets.education.join('\n').trim(),
    projects: buckets.projects.join('\n').trim(),
    certs: buckets.certs
      .filter((l) => !/^https?:\/\//i.test(l.trim()) && !/^links:?$/i.test(l.trim()))
      .join('\n')
      .trim(),
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

  const formatRoleList = (list: any[]) => {
    return Array.isArray(list) && list.length > 0
      ? list
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
              ? e.achievements.map((a: string) => `• ${a.trim().replace(/^[-•*▪·\s]+/, '')}`).join('\n')
              : '';

            const contentLines = [desc, achs].filter(Boolean).join('\n');
            return contentLines ? `${headerLine}\n${contentLines}` : headerLine;
          })
          .join('\n\n')
      : '';
  };

  // 1. Format employment history (strictly work experience)
  const rawEmp = content.employment_history || activeVer.employment_history || profile.employment_history || [];
  const expStr = formatRoleList(rawEmp) || (typeof profile.experience === 'string' ? profile.experience : '');

  // 1b. Format leadership & volunteering (distinct section!)
  const rawLead = content.leadership || activeVer.leadership || profile.leadership || [];
  const leadStr = formatRoleList(rawLead) || (typeof profile.leadership === 'string' ? profile.leadership : '');

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

  // 4. Format certs (filtering out URLs, headers, and avoiding placeholder text)
  const certList = content.certifications || activeVer.certifications || profile.certifications || [];
  const certStr = Array.isArray(certList) && certList.length > 0
    ? certList
        .filter((c: any) => {
          const n = (c.name || '').trim();
          if (!n || /^https?:\/\//i.test(n) || /^links:?$/i.test(n) || n.includes('@')) return false;
          return true;
        })
        .map((c: any) => {
          const name = (c.name || '').trim();
          const issuer = c.issuer && c.issuer !== 'Certification Authority' ? ` - ${c.issuer.trim()}` : '';
          const date = c.issue_date ? ` (${c.issue_date.trim()})` : '';
          return `${name}${issuer}${date}`.trim();
        })
        .filter(Boolean)
        .join('\n')
    : typeof profile.certs === 'string'
    ? profile.certs
        .split('\n')
        .filter((l: string) => {
          const cleanL = l.trim();
          if (!cleanL) return false;
          if (/^https?:\/\//i.test(cleanL) || /^links:?$/i.test(cleanL)) return false;
          return true;
        })
        .map((l: string) => l.replace(/\s*-\s*Certification Authority/gi, '').trim())
        .filter(Boolean)
        .join('\n')
    : '';

  // 5. Format skills
  const skillsList = content.skills || activeVer.skills || profile.skills || [];
  const skillsStr = Array.isArray(skillsList) ? skillsList.join(', ') : String(skillsList || '');

  // 6. Summary
  const summaryStr = content.summary || activeVer.summary || profile.summary || '';

  // 7. Links - filter out LinkedIn and GitHub from additional links
  const allLinks: string[] = Array.isArray(contact.links) ? contact.links : [];
  const githubLink = contact.github_url || profile.github || '';
  const linkedinLink = contact.linkedin_url || contact.portfolio_url || profile.linkedin || profile.linkedin_url || '';
  const cleanOtherLinks = allLinks.filter((l) => {
    if (!l) return false;
    const low = l.toLowerCase();
    if (low.includes('linkedin.com')) return false;
    if (linkedinLink && low === linkedinLink.toLowerCase()) return false;
    if (githubLink && low === githubLink.toLowerCase()) return false;
    const ghClean = low.replace(/^https?:\/\/(?:www\.)?github\.com\/?/, '').replace(/\/$/, '');
    if (ghClean && !ghClean.includes('/')) return false;
    return true;
  });

  return {
    name: contact.name || profile.display_name || defaultName,
    email: contact.email || profile.email || defaultEmail,
    phone: contact.phone || profile.phone || profile.contact_phone || '',
    location: contact.location || profile.location || '',
    link: linkedinLink,
    github: githubLink,
    other_links: cleanOtherLinks,
    summary: summaryStr,
    skills: skillsStr,
    experience: expStr,
    leadership: leadStr,
    education: eduStr,
    projects: projStr,
    certs: certStr,
    years_experience:
      activeVer.years_experience != null
        ? Number(activeVer.years_experience)
        : content.years_experience != null
        ? Number(content.years_experience)
        : profile.years_experience != null
        ? Number(profile.years_experience)
        : undefined,
    confirmed: {
      summary: !!summaryStr,
      skills: !!skillsStr,
      experience: !!expStr,
      leadership: !!leadStr,
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
  links?: ItemLink[];
}

export const DEFAULT_EXPERIENCE_CARDS: ExperienceCardItem[] = [
  {
    id: 'exp-default-1',
    title: 'Co-Founder and AI Engineer',
    company: 'MedDigi-Verse',
    location: 'Alexandria, Egypt',
    mode: 'Remote',
    startDate: 'Jan 2024',
    endDate: 'Present',
    isCurrent: true,
    links: [
      { label: 'Google Play', url: 'https://play.google.com/store/apps/details?id=com.meddigiverse.meddigig' },
      { label: 'App Store', url: 'https://apps.apple.com/app/atlas-doctors-pharmacists/id6805466076' },
    ],
    bullets: [
      'Shipped an AI-powered pharmacy assistant to Google Play and App Store featuring prescription OCR with 92%+ accuracy and semantic product search over 25K+ items.',
      'Orchestrated cross-functional collaboration across a 20-member startup team spanning machine learning and full-stack development.',
    ],
  },
  {
    id: 'exp-default-2',
    title: 'Software Engineering Intern',
    company: 'Edafa Telecom Solutions',
    location: 'Cairo, Egypt',
    mode: 'Hybrid',
    startDate: 'Jan 2025',
    endDate: 'Jan 2025',
    isCurrent: false,
    bullets: [
      'Engineered a real-time health monitoring dashboard using Flutter, Spring Boot, and PostgreSQL with RESTful APIs.',
      'Devised a multi-role market simulation system supporting five user roles with role-based access control and scalable backend architecture.',
    ],
  },
];

/**
 * Parses raw or formatted experience text into discrete LinkedIn-styled cards.
 */
export function parseExperienceToCards(text: string): ExperienceCardItem[] {
  if (!text || !text.trim()) {
    return DEFAULT_EXPERIENCE_CARDS;
  }

  // Pre-split glued bullet points like ". –Orchestrated" or ". - Orchestrated"
  const normalized = text
    .replace(/\r\n/g, '\n')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\.\s*([–—\-•*▪·]\s*[A-Z])/g, '.\n$1');

  // Split into entry chunks either by double newlines or by lines that clearly start a new position
  const rawBlocks = normalized.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const cards: ExperienceCardItem[] = [];

  const datePattern = /(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{4}\s*[-–—]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(?:\d{4}|Present|Current|Now)/i;
  const modePattern = /\b(Remote|Hybrid|On-site)\b/i;
  const locPattern = /\b([A-Z][a-zA-Z\s]+,\s*(?:[A-Z][a-zA-Z\s]+|[A-Z]{2}))\b/;

  rawBlocks.forEach((block, idx) => {
    const rawLines = block.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (rawLines.length === 0) return;

    // Expand lines if bullet point is inline with header (e.g. "Software Engineering Intern Cairo, Egypt - Engineered...")
    const lines: string[] = [];
    rawLines.forEach((l) => {
      const inlineBulletIdx = l.search(/\s+[-•*▪·]\s*[A-Z]/);
      if (inlineBulletIdx !== -1 && !/^[-•*▪·]/.test(l)) {
        lines.push(l.slice(0, inlineBulletIdx).trim());
        lines.push(l.slice(inlineBulletIdx).trim());
      } else {
        lines.push(l);
      }
    });

    let headerLine = lines[0] || '';
    let subHeaderLine = '';
    const bulletLines: string[] = [];

    // Check if line 2 is part of header
    if (lines.length > 1 && !lines[1]!.startsWith('-') && !lines[1]!.startsWith('•') && !lines[1]!.startsWith('*')) {
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

    // Extract location
    let location = '';
    const locMatch = headerLine.match(locPattern) || (subHeaderLine ? subHeaderLine.match(locPattern) : null);
    if (locMatch && locMatch[1] && !locMatch[1].toLowerCase().includes('present')) {
      location = locMatch[1].trim();
    }

    // Extract Title and Company
    let title = '';
    let company = '';

    const cleanHeader = headerLine
      .replace(/\((?:[^)]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Remote|Hybrid|Present)[^)]*)\)/gi, '')
      .replace(/\s+at\s+Company\b/gi, '')
      .replace(/\(\s*\)/g, '')
      .trim();

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

    // Extract attached item links
    let links: ItemLink[] = [];
    if (company) {
      const ext = extractItemLinks(company);
      company = ext.cleanText;
      if (ext.links.length > 0) links = ext.links;
    }
    if (links.length === 0 && title) {
      const ext = extractItemLinks(title);
      title = ext.cleanText;
      if (ext.links.length > 0) links = ext.links;
    }

    // Cleanup artifacts
    title = title.replace(/\s+at\s+Company\b/gi, '').replace(/\(\s*\)/g, '').replace(/^[·\-,|\s]+|[·\-,|\s]+$/g, '').trim();
    company = company.replace(/^(?:Company|Organization)$/i, '').replace(/\(\s*\)/g, '').replace(/^[·\-,|\s]+|[·\-,|\s]+$/g, '').trim();
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
      links: links.length > 0 ? links : undefined,
    });
  });

  return cards.length > 0 ? cards : DEFAULT_EXPERIENCE_CARDS;
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

      const linksStr = serializeItemLinks(c.links);
      const companyWithLinks = c.company ? `${c.company}${linksStr}` : linksStr ? `${c.title}${linksStr}` : '';
      const roleParts = c.company ? [c.title, companyWithLinks].filter(Boolean) : [c.title + linksStr].filter(Boolean);
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

// ---- Leadership Cards -------------------------------------------------------

export interface LeadershipCardItem {
  id: string;
  title: string;
  organization: string;
  location?: string;
  startDate?: string;
  endDate?: string;
  isCurrent?: boolean;
  bullets: string[];
  links?: ItemLink[];
}

export function parseLeadershipToCards(text: string): LeadershipCardItem[] {
  if (!text || !text.trim()) return [];

  const normalized = text
    .replace(/\r\n/g, '\n')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\.\s*([–—\-•*▪·]\s*[A-Z])/g, '.\n$1');

  const rawBlocks = normalized.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const cards: LeadershipCardItem[] = [];

  const datePattern = /(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{4}\s*[-–—]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(?:\d{4}|Present|Current|Expected\s+\d{4})/i;
  const singleYearPattern = /\b(20\d{2}|19\d{2})\b/;
  const locPattern = /\b([A-Z][a-zA-Z\s]+,\s*(?:[A-Z]{2}|[A-Z][a-zA-Z]+))\b/;

  rawBlocks.forEach((block, idx) => {
    const lines = block.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;

    let headerLine = lines[0] || '';
    let subHeaderLine = '';
    const bulletLines: string[] = [];

    if (lines.length > 1 && !lines[1]!.startsWith('-') && !lines[1]!.startsWith('•') && !lines[1]!.startsWith('*')) {
      subHeaderLine = lines[1]!;
      for (let i = 2; i < lines.length; i++) bulletLines.push(lines[i]!);
    } else {
      for (let i = 1; i < lines.length; i++) bulletLines.push(lines[i]!);
    }

    let startDate = '';
    let endDate = '';
    let isCurrent = false;

    const dateMatch = headerLine.match(datePattern) || (subHeaderLine ? subHeaderLine.match(datePattern) : null);
    if (dateMatch) {
      const parts = dateMatch[0].split(/[-–—]/).map((p) => p.trim());
      startDate = parts[0] || '';
      endDate = parts[1] || '';
      if (/present|current/i.test(endDate)) {
        isCurrent = true;
        endDate = 'Present';
      }
    } else {
      const singleMatch = headerLine.match(singleYearPattern);
      if (singleMatch) {
        startDate = singleMatch[1] || '';
      }
    }

    let location = '';
    const locMatch = headerLine.match(locPattern) || (subHeaderLine ? subHeaderLine.match(locPattern) : null);
    if (locMatch && locMatch[1]) {
      location = locMatch[1].trim();
    }

    let cleanHeader = headerLine
      .replace(/\((?:[^)]*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|\d{4}|Present)[^)]*)\)/gi, '')
      .replace(/\(\s*\)/g, '')
      .trim();

    let title = '';
    let organization = '';

    if (cleanHeader.includes(' · ')) {
      const parts = cleanHeader.split(' · ').map((p) => p.trim());
      title = parts[0] || '';
      organization = parts.slice(1).join(' · ');
    } else if (cleanHeader.includes(' at ')) {
      const parts = cleanHeader.split(' at ').map((p) => p.trim());
      title = parts[0] || '';
      organization = parts[1] || '';
    } else if (subHeaderLine) {
      title = cleanHeader;
      organization = subHeaderLine;
    } else {
      title = cleanHeader;
    }

    let links: ItemLink[] = [];
    if (organization) {
      const ext = extractItemLinks(organization);
      organization = ext.cleanText;
      if (ext.links.length > 0) links = ext.links;
    }
    if (links.length === 0 && title) {
      const ext = extractItemLinks(title);
      title = ext.cleanText;
      if (ext.links.length > 0) links = ext.links;
    }

    const bullets = bulletLines
      .map((b) => b.replace(/^[\u2013\u2014\-*•▪·\d.)\s]+/, '').trim())
      .filter(Boolean);

    cards.push({
      id: `lead-${idx}-${Date.now()}`,
      title: title || `Leadership Role ${idx + 1}`,
      organization,
      location,
      startDate,
      endDate: endDate || (isCurrent ? 'Present' : ''),
      isCurrent,
      bullets,
      links: links.length > 0 ? links : undefined,
    });
  });

  return cards;
}

export function serializeCardsToLeadership(cards: LeadershipCardItem[]): string {
  return cards
    .map((c) => {
      const metaParts: string[] = [];
      const dateStr = [c.startDate, c.endDate || (c.isCurrent ? 'Present' : '')].filter(Boolean).join(' - ');
      if (dateStr) metaParts.push(dateStr);
      if (c.location) metaParts.push(c.location);

      const linksStr = serializeItemLinks(c.links);
      const orgWithLinks = c.organization ? `${c.organization}${linksStr}` : linksStr ? `${c.title}${linksStr}` : '';
      const roleParts = c.organization ? [c.title, orgWithLinks].filter(Boolean) : [c.title + linksStr].filter(Boolean);
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

// ---- Education Cards --------------------------------------------------------

export interface EducationCardItem {
  id: string;
  degree: string;
  institution: string;
  location?: string;
  startDate?: string;
  endDate?: string;
  isCurrent?: boolean;
  gpa?: string;
  bullets: string[];
  links?: ItemLink[];
}

export const DEFAULT_EDUCATION_CARDS: EducationCardItem[] = [
  {
    id: 'edu-1',
    degree: 'Bachelor of Science in Computer Science & Artificial Intelligence',
    institution: 'Faculty of Computers and Artificial Intelligence',
    location: 'Cairo, Egypt',
    startDate: '2020',
    endDate: '2024',
    isCurrent: false,
    gpa: '3.7 / 4.0',
    bullets: [
      'Graduation Project: End-to-End Medical AI Diagnosis System (Grade: Excellent / A+)',
      'Relevant coursework: Machine Learning, Natural Language Processing, Algorithms, Distributed Systems',
    ],
  },
];

export function parseEducationToCards(text: string): EducationCardItem[] {
  if (!text || !text.trim()) {
    return DEFAULT_EDUCATION_CARDS;
  }

  const normalized = text
    .replace(/\r\n/g, '\n')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\.\s*([–—\-•*▪·]\s*[A-Z])/g, '.\n$1');

  const rawBlocks = normalized.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const cards: EducationCardItem[] = [];

  const datePattern = /(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?\d{4}\s*[-–—]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?(?:\d{4}|Present|Current|Expected\s+\d{4})/i;

  rawBlocks.forEach((block, idx) => {
    const lines = block.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;

    let headerLine = lines[0] || '';
    let subHeaderLine = '';
    const bullets: string[] = [];

    if (lines.length > 1 && !lines[1]!.startsWith('-') && !lines[1]!.startsWith('•') && !lines[1]!.startsWith('*')) {
      subHeaderLine = lines[1]!;
      for (let i = 2; i < lines.length; i++) bullets.push(lines[i]!);
    } else {
      for (let i = 1; i < lines.length; i++) bullets.push(lines[i]!);
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
      if (/present|current/i.test(endDate)) {
        isCurrent = true;
        endDate = 'Present';
      }
    }

    // Extract GPA if present
    let gpa = '';
    const gpaMatch = headerLine.match(/GPA[:\s]+([\d\.\/]+)/i) || (subHeaderLine ? subHeaderLine.match(/GPA[:\s]+([\d\.\/]+)/i) : null);
    if (gpaMatch) {
      gpa = gpaMatch[1] || '';
    }

    // Clean header
    let cleanHeader = headerLine
      .replace(/\((?:[^)]*(?:\d{4}|GPA|Present)[^)]*)\)/gi, '')
      .replace(/\(\s*\)/g, '')
      .trim();

    let degree = '';
    let institution = '';

    if (cleanHeader.includes(' · ')) {
      const parts = cleanHeader.split(' · ').map((p) => p.trim());
      degree = parts[0] || '';
      institution = parts.slice(1).join(' · ');
    } else if (cleanHeader.includes(' at ')) {
      const parts = cleanHeader.split(' at ').map((p) => p.trim());
      degree = parts[0] || '';
      institution = parts[1] || '';
    } else if (cleanHeader.includes(' - ')) {
      const parts = cleanHeader.split(' - ').map((p) => p.trim());
      degree = parts[0] || '';
      institution = parts[1] || '';
    } else if (subHeaderLine) {
      degree = cleanHeader;
      institution = subHeaderLine;
    } else {
      degree = cleanHeader;
      institution = 'University / Academic Institution';
    }

    let links: ItemLink[] = [];
    if (institution) {
      const ext = extractItemLinks(institution);
      institution = ext.cleanText;
      if (ext.links.length > 0) links = ext.links;
    }
    if (links.length === 0 && degree) {
      const ext = extractItemLinks(degree);
      degree = ext.cleanText;
      if (ext.links.length > 0) links = ext.links;
    }

    cards.push({
      id: `edu-${idx + 1}-${Date.now()}`,
      degree: degree || 'Degree',
      institution: institution || 'Institution',
      startDate,
      endDate,
      isCurrent,
      gpa,
      bullets: bullets.map((b) => b.replace(/^[-•*▪·\s]+/, '').trim()).filter(Boolean),
      links: links.length > 0 ? links : undefined,
    });
  });

  return cards.length > 0 ? cards : DEFAULT_EDUCATION_CARDS;
}

export function serializeCardsToEducation(cards: EducationCardItem[]): string {
  return cards
    .map((c) => {
      const metaParts: string[] = [];
      const dateStr = [c.startDate, c.endDate || (c.isCurrent ? 'Present' : '')].filter(Boolean).join(' - ');
      if (dateStr) metaParts.push(dateStr);
      if (c.location) metaParts.push(c.location);
      if (c.gpa) metaParts.push(`GPA: ${c.gpa}`);

      const linksStr = serializeItemLinks(c.links);
      const instWithLinks = c.institution ? `${c.institution}${linksStr}` : linksStr ? `${c.degree}${linksStr}` : '';
      const mainParts = c.institution ? [c.degree, instWithLinks].filter(Boolean) : [c.degree + linksStr].filter(Boolean);
      let header = mainParts.join(' · ');
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

// ---- Project Cards ----------------------------------------------------------

export interface ProjectCardItem {
  id: string;
  title: string;
  roleOrSubtitle?: string;
  technologies?: string;
  link?: string;
  date?: string;
  bullets: string[];
  links?: ItemLink[];
}

export const DEFAULT_PROJECT_CARDS: ProjectCardItem[] = [
  {
    id: 'proj-1',
    title: 'MedDigi-Verse Assistant',
    roleOrSubtitle: 'Lead AI Engineer',
    technologies: 'Flutter, Python, FastAPI, Hugging Face, PostgreSQL',
    link: 'play.google.com/store/apps',
    date: 'Jan 2024 - Present',
    bullets: [
      'Shipped an AI-powered healthcare assistant serving 5,000+ active users with instant medical prescription OCR extraction.',
      'Reduced token latencies by 38% using vector caching and quantized embeddings.',
    ],
  },
  {
    id: 'proj-2',
    title: 'JobFit Autonomous Agent',
    roleOrSubtitle: 'Creator & Developer',
    technologies: 'React, TypeScript, FastAPI, Gemini 2.5 Flash, Supabase',
    link: 'github.com/Mahmoud2592004/JobFit',
    date: '2024',
    bullets: [
      'Architected full-stack career agent integrating Apify LinkedIn scraper with Gemini structured recruiter evaluation.',
      'Built interactive truth-verification engine validating ATS skill match without hallucinating false claims.',
    ],
  },
];

export function parseProjectsToCards(text: string): ProjectCardItem[] {
  if (!text || !text.trim()) {
    return DEFAULT_PROJECT_CARDS;
  }

  const normalized = text
    .replace(/\r\n/g, '\n')
    .replace(/[\u2013\u2014]/g, '-')
    .replace(/\.\s*([–—\-•*▪·]\s*[A-Z])/g, '.\n$1');

  const rawBlocks = normalized.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const cards: ProjectCardItem[] = [];

  rawBlocks.forEach((block, idx) => {
    const lines = block.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (lines.length === 0) return;

    let headerLine = lines[0] || '';
    let subHeaderLine = '';
    const bullets: string[] = [];

    if (lines.length > 1 && !lines[1]!.startsWith('-') && !lines[1]!.startsWith('•') && !lines[1]!.startsWith('*')) {
      subHeaderLine = lines[1]!;
      for (let i = 2; i < lines.length; i++) bullets.push(lines[i]!);
    } else {
      for (let i = 1; i < lines.length; i++) bullets.push(lines[i]!);
    }

    // Extract technologies in brackets e.g. [React, Python, AWS]
    let technologies = '';
    const techMatch = headerLine.match(/\[([^\]]+)\]/) || (subHeaderLine ? subHeaderLine.match(/\[([^\]]+)\]/) : null);
    if (techMatch) {
      technologies = techMatch[1] || '';
    }

    // Extract dates in parentheses e.g. (2024 - Present)
    let date = '';
    const dateMatch = headerLine.match(/\((?:[^)]*\d{4}[^)]*)\)/);
    if (dateMatch) {
      date = dateMatch[0].replace(/[()]/g, '').trim();
    }

    // Extract links
    let link = '';
    const linkMatch = headerLine.match(/(?:https?:\/\/|github\.com\/|bit\.ly\/)\S+/i) || (subHeaderLine ? subHeaderLine.match(/(?:https?:\/\/|github\.com\/|bit\.ly\/)\S+/i) : null);
    if (linkMatch) {
      link = linkMatch[0].trim();
    }

    let cleanTitle = headerLine
      .replace(/\[[^\]]+\]/g, '')
      .replace(/\((?:[^)]*\d{4}[^)]*)\)/g, '')
      .replace(/(?:https?:\/\/|github\.com\/)\S+/gi, '')
      .replace(/^[–—\-•*▪·\s|]+|[–—\-•*▪·\s|]+$/g, '')
      .trim();

    let links: ItemLink[] = [];
    const ext = extractItemLinks(cleanTitle);
    cleanTitle = ext.cleanText;
    if (ext.links.length > 0) links = ext.links;

    let roleOrSubtitle = subHeaderLine;
    if (cleanTitle.includes(' · ')) {
      const parts = cleanTitle.split(' · ').map((p) => p.trim());
      cleanTitle = parts[0] || 'Project';
      roleOrSubtitle = parts.slice(1).join(' · ');
    } else if (cleanTitle.includes(' | ')) {
      const parts = cleanTitle.split(' | ').map((p) => p.trim());
      cleanTitle = parts[0] || 'Project';
      roleOrSubtitle = parts.slice(1).join(' | ');
    }

    cards.push({
      id: `proj-${idx + 1}-${Date.now()}`,
      title: cleanTitle || 'Project',
      roleOrSubtitle: roleOrSubtitle || undefined,
      technologies: technologies || undefined,
      link: link || undefined,
      date: date || undefined,
      bullets: bullets.map((b) => b.replace(/^[-•*▪·\s]+/, '').trim()).filter(Boolean),
      links: links.length > 0 ? links : undefined,
    });
  });

  return cards.length > 0 ? cards : DEFAULT_PROJECT_CARDS;
}

export function serializeCardsToProjects(cards: ProjectCardItem[]): string {
  return cards
    .map((c) => {
      const linksStr = serializeItemLinks(c.links);
      let header = `${c.title}${linksStr}`;
      if (c.technologies) {
        header += ` [${c.technologies}]`;
      }
      if (c.date) {
        header += ` (${c.date})`;
      }

      const metaLines: string[] = [];
      if (c.roleOrSubtitle) metaLines.push(c.roleOrSubtitle);
      if (c.link && (!c.links || c.links.length === 0)) metaLines.push(c.link);

      const achs = c.bullets
        .filter(Boolean)
        .map((b) => (b.startsWith('-') || b.startsWith('•') || b.startsWith('–') ? b : `- ${b}`))
        .join('\n');

      const parts = [header, ...metaLines, achs].filter(Boolean);
      return parts.join('\n');
    })
    .join('\n\n');
}

// ---- Certification Cards ----------------------------------------------------

export interface CertCardItem {
  id: string;
  name: string;
  authority?: string;
  links?: ItemLink[];
}

export function parseCertsToCards(text: string): CertCardItem[] {
  if (!text || !text.trim()) return [];
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .filter((l) => !/^https?:\/\//i.test(l) && !/^links:?$/i.test(l));

  return lines.map((line, idx) => {
    const cleanL = line.replace(/^[-•*▪·–—\d.)\s]+/, '').replace(/\s*-\s*Certification Authority/gi, '').trim();
    const { cleanText, links } = extractItemLinks(cleanL);
    let name = cleanText;
    let authority = '';
    if (cleanText.includes(' - ')) {
      const parts = cleanText.split(' - ').map((p) => p.trim());
      name = parts[0] || '';
      authority = parts.slice(1).join(' - ');
    } else if (cleanText.includes(' · ')) {
      const parts = cleanText.split(' · ').map((p) => p.trim());
      name = parts[0] || '';
      authority = parts.slice(1).join(' · ');
    }
    return {
      id: `cert-${idx + 1}-${Date.now()}`,
      name: name || `Certification ${idx + 1}`,
      authority: authority || undefined,
      links: links.length > 0 ? links : undefined,
    };
  });
}

export function serializeCardsToCerts(cards: CertCardItem[]): string {
  return cards
    .map((c) => {
      const main = [c.name, c.authority].filter(Boolean).join(' - ');
      const linksStr = serializeItemLinks(c.links);
      return `${main}${linksStr}`;
    })
    .filter(Boolean)
    .join('\n');
}

