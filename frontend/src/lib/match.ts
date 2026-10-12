import { getCountryName } from '../data/countries';
import { JOBS, LEVELS, SKILL_KEYWORDS } from '../data/jobs';
import type { AppState, Draft, FitTone, Job, JobFilters, Match, Prefs, Profile, Level } from '../types';

export const today = (): string => new Date().toISOString().slice(0, 10);

export const splitSentences = (text: string): string[] =>
  text
    .replace(/\.\s+/g, '.\n')
    .split('\n')
    .map((s) => s.trim())
    .filter(Boolean);

export const splitList = (text: string): string[] =>
  text
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);

export function extractSkills(text: string): string {
  const lower = text.toLowerCase();
  return SKILL_KEYWORDS.filter((k) => lower.includes(k.toLowerCase())).join(', ');
}

export function inferSeniorityLevel(seniority?: string | null, title?: string | null): Level {
  const s = (seniority || '').toLowerCase();
  const t = (title || '').toLowerCase();
  if (
    s.includes('senior') || s.includes('lead') || s.includes('principal') || s.includes('staff') || s.includes('exec') ||
    t.includes('senior') || t.includes('lead') || t.includes('principal') || t.includes('staff') || t.includes('head')
  ) {
    return 'Senior';
  }
  if (
    s.includes('entry') || s.includes('junior') || s.includes('intern') || s.includes('associate') ||
    t.includes('junior') || t.includes('entry') || t.includes('intern') || t.includes('graduate') || t.includes('trainee')
  ) {
    return 'Entry-level';
  }
  return 'Mid';
}

/** Score a job against the confirmed profile. Missing info is never treated as proof of a missing skill. */
export function matchJob(job: Job, profile: Profile, prefs: Prefs): Match {
  const skills = profile.skills.toLowerCase();
  const text = [profile.summary, profile.experience, profile.projects].join(' ').toLowerCase();
  const strong: string[] = [];
  const partial: string[] = [];
  const gaps: string[] = [];
  for (const r of job.requirements) {
    const k = r.toLowerCase();
    if (skills.includes(k)) strong.push(r);
    else if (text.includes(k)) partial.push(r);
    else gaps.push(r);
  }
  const skillScore = Math.round(((strong.length + partial.length * 0.5) / job.requirements.length) * 100);
  const d = Math.abs(LEVELS.indexOf(job.level) - LEVELS.indexOf(prefs.level));
  const seniority = d === 0 ? 100 : d === 1 ? 55 : 15;
  const arrangement = prefs.mode === 'Any' || prefs.mode === job.mode ? 100 : 35;
  const score = Math.round(skillScore * 0.6 + seniority * 0.25 + arrangement * 0.15);
  return { strong, partial, gaps, skillScore, seniority, arrangement, score };
}

export const fitOf = (score: number): { label: string; tone: FitTone } =>
  score >= 80
    ? { label: 'Strong Fit', tone: 's' }
    : score >= 60
      ? { label: 'Potential Fit', tone: 'p' }
      : { label: 'Not a Fit', tone: 'n' };

export function whyText(job: Job, m: Match): string {
  if (m.recruiterRationale) {
    return m.recruiterRationale;
  }
  return (
    (m.strong.length ? `Strong on ${m.strong.slice(0, 3).join(', ')}. ` : 'No confirmed skill matches yet. ') +
    (m.gaps.length ? `Gap: ${m.gaps.slice(0, 2).join(', ')}. ` : '') +
    (m.arrangement < 100 ? 'Work arrangement differs from your preference.' : `${job.mode} in ${job.location}.`)
  );
}

export interface ScoredJob {
  job: Job;
  match: Match;
}

export interface AiJobScoreEntry {
  score: number;
  rationale?: string;
  fit?: string;
  experienceFitAnalysis?: string;
  preferenceFitAnalysis?: string;
}

const COUNTRY_KEYWORD_MAP: Record<string, string[]> = {
  US: ['united states', 'usa', 'u.s.', ', us', ' ca', ' ny', ' tx', ' wa', ' ma', ' il', ' oh', ' fl', ' nc', ' ga', ' va', ' co', ' ut', 'seattle', 'new york', 'san francisco', 'austin', 'boston', 'chicago', 'los angeles', 'silicon valley', 'mountain view', 'salt lake city', 'dayton'],
  GB: ['united kingdom', 'uk', 'u.k.', 'england', 'scotland', 'wales', 'london', 'manchester', 'birmingham', 'edinburgh', 'glasgow', 'cardiff'],
  AE: ['united arab emirates', 'uae', 'u.a.e.', 'dubai', 'abu dhabi', 'sharjah'],
  SA: ['saudi arabia', 'ksa', 'k.s.a.', 'riyadh', 'jeddah', 'dammam', 'khobar'],
  EG: ['egypt', 'cairo', 'giza', 'alexandria', 'maadi', 'heliopolis', 'nasr city'],
  DE: ['germany', 'deutschland', 'berlin', 'munich', 'münchen', 'frankfurt', 'hamburg', 'bavaria', 'cologne', 'köln', 'stuttgart'],
  CA: ['canada', 'toronto', 'vancouver', 'montreal', 'ottawa', 'calgary', 'ontario', 'quebec', 'british columbia'],
  FR: ['france', 'paris', 'lyon', 'marseille', 'toulouse'],
  NL: ['netherlands', 'holland', 'amsterdam', 'rotterdam', 'utrecht', 'the hague'],
  IE: ['ireland', 'dublin', 'cork', 'galway'],
  SG: ['singapore'],
  IN: ['india', 'bangalore', 'bengaluru', 'hyderabad', 'pune', 'mumbai', 'delhi', 'noida', 'gurgaon', 'gurugram', 'chennai'],
  AU: ['australia', 'sydney', 'melbourne', 'brisbane', 'perth'],
};

export function locationMatchesSelected(jobLocation: string, selectedCodes: string[], locationString: string): boolean {
  if (!jobLocation) return true;
  const lower = jobLocation.toLowerCase();
  if (lower === 'remote' || lower === 'worldwide' || lower === 'anywhere') return true;

  const targetTokens: string[] = [];
  for (const code of selectedCodes) {
    const cUpper = code.toUpperCase();
    const cName = getCountryName(cUpper).toLowerCase();
    targetTokens.push(cName);
    const extra = COUNTRY_KEYWORD_MAP[cUpper];
    if (extra) {
      targetTokens.push(...extra);
    }
  }

  if (locationString) {
    const parts = locationString.split(',').map((p) => p.trim().toLowerCase()).filter((p) => p && p !== 'any' && p !== 'worldwide' && p !== 'all');
    targetTokens.push(...parts);
  }

  if (targetTokens.length === 0) return true;
  return targetTokens.some((token) => lower.includes(token));
}

export function filterJobs(
  state: Pick<AppState, 'profile' | 'prefs' | 'dismissed'> & {
    customJobs?: Job[];
    aiScores?: Record<string, AiJobScoreEntry>;
  },
  filters: JobFilters,
): { items: ScoredJob[]; hidden: number } {
  const { profile, prefs, dismissed, customJobs, aiScores } = state;
  if (!profile) return { items: [], hidden: 0 };
  let hidden = 0;
  const q = filters.q.toLowerCase();
  const catalog = customJobs && customJobs.length > 0 ? customJobs : JOBS;
  const items = catalog
    .filter((j) => !dismissed[j.id])
    .map((job) => {
      const baseMatch = matchJob(job, profile, prefs);
      const aiData = aiScores ? aiScores[String(job.id)] : undefined;
      if (aiData) {
        return {
          job,
          match: {
            ...baseMatch,
            score: aiData.score,
            recruiterRationale: aiData.rationale,
            experienceFitAnalysis: aiData.experienceFitAnalysis,
            preferenceFitAnalysis: aiData.preferenceFitAnalysis,
            isAiEvaluated: true,
          },
        };
      }
      const hasAiRun = aiScores && Object.keys(aiScores).length > 0;
      const unrankedScore = hasAiRun ? Math.min(baseMatch.score, 40) : baseMatch.score;
      return { job, match: { ...baseMatch, score: unrankedScore, isAiEvaluated: false } };
    })
    .filter(({ job, match }) => {
      if (prefs.requireMode && prefs.mode !== 'Any' && job.mode !== prefs.mode) {
        hidden++;
        return false;
      }

      // Target country / location matching
      const hasTargetLocs = (prefs.countries && prefs.countries.length > 0) || Boolean(prefs.location);
      if (hasTargetLocs) {
        const matchesCountry = locationMatchesSelected(job.location, prefs.countries || [], prefs.location || '');
        if (!matchesCountry) {
          hidden++;
          return false;
        }
      }
      if (q && !`${job.title} ${job.company} ${job.requirements.join(' ')}`.toLowerCase().includes(q)) return false;
      if (filters.mode && job.mode !== filters.mode) return false;
      if (filters.type && job.type !== filters.type) return false;
      if (filters.level && job.level !== filters.level) return false;
      if (filters.timePosted && filters.timePosted !== 'anyTime') {
        if (filters.timePosted === 'past24Hours' && job.daysAgo > 1) return false;
        if (filters.timePosted === 'pastWeek' && job.daysAgo > 7) return false;
        if (filters.timePosted === 'pastMonth' && job.daysAgo > 30) return false;
      }
      return match.score >= filters.min;
    });
  items.sort((a, b) => (filters.sort === 'recent' ? a.job.daysAgo - b.job.daysAgo : b.match.score - a.match.score));
  return { items, hidden };
}

// ---- Tailoring -------------------------------------------------------------

export interface Proposal {
  related: string[];
  original: Draft;
  proposed: Draft;
}

/** Reorders and rewords only what already exists in the profile. Never adds skills. */
export function genProposal(job: Job, profile: Profile, variant: number): Proposal {
  const skills = splitList(profile.skills);
  const seenSkills = new Set<string>();
  const uniqueSkills: string[] = [];
  for (const s of skills) {
    const low = s.toLowerCase();
    if (!seenSkills.has(low)) {
      seenSkills.add(low);
      uniqueSkills.push(s);
    }
  }

  const related = uniqueSkills.filter((k) => job.requirements.some((r) => r.toLowerCase() === k.toLowerCase()));
  const others = uniqueSkills.filter((k) => !related.some((r) => r.toLowerCase() === k.toLowerCase()));
  const proposedSkills = [...related, ...others].join(', ');

  const proposedSummary = profile.summary
    ? profile.summary + (related.length ? ` Strengths for this role: ${related.slice(0, 4).join(', ')}.` : '')
    : '';

  // Preserve structured job blocks intact
  const jobBlocks = profile.experience
    ? profile.experience.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean)
    : [];

  let proposedExp = profile.experience;
  if (variant % 2 === 0 && jobBlocks.length > 1) {
    const scoreBlock = (block: string) => {
      const low = block.toLowerCase();
      return related.filter((k) => low.includes(k.toLowerCase())).length;
    };
    const sortedBlocks = jobBlocks.slice().sort((a, b) => scoreBlock(b) - scoreBlock(a));
    proposedExp = sortedBlocks.join('\n\n');
  }

  return {
    related,
    original: {
      summary: profile.summary,
      skills: uniqueSkills.join(', '),
      experience: profile.experience,
      leadership: profile.leadership,
    },
    proposed: {
      summary: proposedSummary,
      skills: proposedSkills,
      experience: proposedExp,
      leadership: profile.leadership,
    },
  };
}

export function buildLetter(job: Job, related: string[], profile: Profile): string {
  const b = splitSentences(profile.experience);
  return (
    `Dear Hiring Team at ${job.company},\n\n` +
    `I am applying for the ${job.title} position. ` +
    (related.length ? `My hands-on experience with ${related.slice(0, 3).join(', ')} maps directly to what the role asks for. ` : '') +
    `${b[0] ?? ''}${b[1] ? ' ' + b[1] : ''}\n\n` +
    `I would welcome the chance to discuss how I can contribute to ${job.company}. Thank you for your time and consideration.\n\n` +
    `Sincerely,\n${profile.name}`
  );
}

/** Truth check: every skill on the resume must exist in the profile skills. */
export function auditSkills(draftSkills: string, profile: Profile): { verified: number; flagged: string[] } {
  const allowed = splitList(profile.skills).map((s) => s.toLowerCase());
  const used = splitList(draftSkills);
  const flagged = used.filter((s) => !allowed.includes(s.toLowerCase()));
  return { verified: used.length - flagged.length, flagged };
}

export const latexEscape = (s: string): string => s.replace(/[&%$#_{}]/g, '\\$&');

export function formatLatexHeader(header: string): string {
  const mdRegex = /\[([^\]]+)\]\(([^)]*)\)/g;
  let lastIdx = 0;
  let match;
  let result = '';

  while ((match = mdRegex.exec(header)) !== null) {
    const before = header.slice(lastIdx, match.index);
    result += latexEscape(before);
    const label = latexEscape(match[1]!.trim());
    const url = match[2]!.trim();
    if (url) {
      result += `\\href{${latexEscape(url)}}{\\color{AccentBlue}{${label}}}`;
    } else {
      result += label;
    }
    lastIdx = mdRegex.lastIndex;
  }
  result += latexEscape(header.slice(lastIdx));
  return result;
}

function formatLatexEntries(text: string): string[] {
  const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean);
  const lines: string[] = [];
  const t = latexEscape;

  for (const block of blocks) {
    const rawLines = block.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
    if (!rawLines.length) continue;
    const header = rawLines[0] || '';
    const bullets = rawLines.slice(1).map((b) => b.replace(/^[-•*▪·–—\d.)\s]+/, '').trim()).filter(Boolean);

    lines.push(`\\noindent\\textbf{${formatLatexHeader(header)}}\\\\[-2pt]`);
    if (bullets.length > 0) {
      lines.push('\\begin{itemize}[leftmargin=*,itemsep=1.5pt,topsep=2pt,partopsep=0pt]');
      for (const b of bullets) {
        lines.push(`  \\item ${t(b)}`);
      }
      lines.push('\\end{itemize}');
    }
    lines.push('\\vspace{4pt}');
  }
  return lines;
}

export function toLatex(profile: Profile, draft: Draft): string {
  const t = latexEscape;
  const row1 = [profile.location, profile.phone, profile.email].filter(Boolean).map(t).join(' \\textbar\\ ');
  const row2Parts: string[] = [];
  if (profile.link) {
    const liUrl = profile.link.startsWith('http') ? profile.link : `https://${profile.link}`;
    row2Parts.push(`\\href{${latexEscape(liUrl)}}{\\color{AccentBlue}{LinkedIn}}`);
  }
  if (profile.github) {
    const ghUrl = profile.github.startsWith('http') ? profile.github : `https://${profile.github}`;
    row2Parts.push(`\\href{${latexEscape(ghUrl)}}{\\color{AccentBlue}{GitHub}}`);
  }
  const row2 = row2Parts.join(' \\textbar\\ ');

  const headerCenter = row2
    ? `\\begin{center}{\\LARGE\\bfseries\\color{AccentBlue} ${t(profile.name)}}\\\\[3pt] ${row1}\\\\[2pt] ${row2}\\end{center}`
    : `\\begin{center}{\\LARGE\\bfseries\\color{AccentBlue} ${t(profile.name)}}\\\\[3pt] ${row1}\\end{center}`;

  const sections: string[] = [
    '\\documentclass[10pt,a4paper]{article}',
    '\\usepackage[margin=0.7in]{geometry}',
    '\\usepackage{xcolor,enumitem,titlesec,hyperref}',
    '\\definecolor{AccentBlue}{HTML}{163A5F}',
    '\\titleformat{\\section}{\\color{AccentBlue}\\large\\bfseries}{}{0em}{}[\\titlerule]',
    '\\pagestyle{empty}',
    '\\begin{document}',
    headerCenter,
  ];

  if (draft.summary) {
    sections.push('\\section*{Summary}', t(draft.summary));
  }

  if (draft.skills) {
    sections.push('\\section*{Skills}', t(draft.skills));
  }

  if (draft.experience) {
    sections.push('\\section*{Experience}', ...formatLatexEntries(draft.experience));
  }

  const leadText = draft.leadership || profile.leadership;
  if (leadText) {
    sections.push('\\section*{Leadership \\& Community}', ...formatLatexEntries(leadText));
  }

  if (profile.education) {
    sections.push('\\section*{Education}', ...formatLatexEntries(profile.education));
  }

  if (profile.projects) {
    sections.push('\\section*{Projects}', ...formatLatexEntries(profile.projects));
  }

  if (profile.certs) {
    const certBullets = profile.certs
      .split('\n')
      .map((c) => c.replace(/^[-•*▪·–—\d.)\s]+/, '').replace(/\s*-\s*Certification Authority/gi, '').trim())
      .filter((c) => c && !/^https?:\/\//i.test(c) && !/^links:?$/i.test(c));
    if (certBullets.length > 0) {
      sections.push('\\section*{Certifications}', '\\begin{itemize}[leftmargin=*,itemsep=1.5pt,topsep=2pt,partopsep=0pt]');
      for (const cb of certBullets) {
        sections.push(`  \\item ${formatLatexHeader(cb)}`);
      }
      sections.push('\\end{itemize}', '\\vspace{4pt}');
    }
  }

  sections.push('\\end{document}');
  return sections.join('\n');
}
