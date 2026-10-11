import { JOBS, LEVELS, SKILL_KEYWORDS } from '../data/jobs';
import type { AppState, Draft, FitTone, Job, JobFilters, Match, Prefs, Profile } from '../types';

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
  score >= 70
    ? { label: 'Strong Fit', tone: 's' }
    : score >= 45
      ? { label: 'Potential Fit', tone: 'p' }
      : { label: 'Not a Fit', tone: 'n' };

export function whyText(job: Job, m: Match): string {
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

export function filterJobs(
  state: Pick<AppState, 'profile' | 'prefs' | 'dismissed'>,
  filters: JobFilters,
): { items: ScoredJob[]; hidden: number } {
  const { profile, prefs, dismissed } = state;
  if (!profile) return { items: [], hidden: 0 };
  let hidden = 0;
  const q = filters.q.toLowerCase();
  const items = JOBS.filter((j) => !dismissed[j.id])
    .map((job) => ({ job, match: matchJob(job, profile, prefs) }))
    .filter(({ job, match }) => {
      if (prefs.requireMode && prefs.mode !== 'Any' && job.mode !== prefs.mode) {
        hidden++;
        return false;
      }
      if (prefs.requireLocation && job.mode !== 'Remote' && !prefs.location.toLowerCase().includes(job.location.toLowerCase())) {
        hidden++;
        return false;
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
  const related = skills.filter((k) => job.requirements.some((r) => r.toLowerCase() === k.toLowerCase()));
  const others = skills.filter((k) => !related.includes(k));
  const sentences = splitSentences(profile.experience);
  const sorted = sentences.slice();
  if (variant % 2 === 0) {
    const rel = (s: string) => related.filter((k) => s.toLowerCase().includes(k.toLowerCase())).length;
    sorted.sort((a, b) => rel(b) - rel(a));
  }
  return {
    related,
    original: { summary: profile.summary, skills: profile.skills, experience: sentences.join('\n') },
    proposed: {
      summary: profile.summary
        ? profile.summary + (related.length ? ` Strengths for this role: ${related.slice(0, 4).join(', ')}.` : '')
        : '',
      skills: related.concat(others).join(', '),
      experience: sorted.join('\n'),
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

export function toLatex(profile: Profile, draft: Draft): string {
  const t = latexEscape;
  const contact = [profile.location, profile.phone, profile.email, profile.link].filter(Boolean).map(t).join(' | ');
  const bullets = draft.experience
    .split('\n')
    .filter(Boolean)
    .map((x) => `\\item ${t(x)}`);
  return [
    '\\documentclass[11pt]{article}',
    '\\usepackage[margin=0.8in]{geometry}',
    '\\usepackage{xcolor,enumitem,titlesec}',
    '\\definecolor{AccentBlue}{HTML}{163A5F}',
    '\\titleformat{\\section}{\\color{AccentBlue}\\large\\bfseries}{}{0em}{}[\\titlerule]',
    '\\pagestyle{empty}',
    '\\begin{document}',
    `\\begin{center}{\\Large\\bfseries\\color{AccentBlue} ${t(profile.name)}}\\\\ ${contact}\\end{center}`,
    '\\section*{Summary}',
    t(draft.summary),
    '\\section*{Skills}',
    t(draft.skills),
    '\\section*{Experience}',
    '\\begin{itemize}[leftmargin=*,itemsep=2pt]',
    ...bullets,
    '\\end{itemize}',
    '\\end{document}',
  ].join('\n');
}
