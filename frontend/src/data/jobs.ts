import type { Job, Level, SectionKey, Stage } from '../types';

/** Dynamic jobs catalog loaded from backend database and live scrapers (zero hardcoded jobs). */
export const JOBS: Job[] = [];

let dynamicJobs: Job[] = [];

export function setDynamicJobs(jobs: Job[]) {
  dynamicJobs = jobs;
}

export function getDynamicJobs(): Job[] {
  return dynamicJobs;
}

export function registerJobs(jobs: Job[]) {
  const map = new Map(dynamicJobs.map((j) => [String(j.id), j]));
  jobs.forEach((j) => map.set(String(j.id), j));
  dynamicJobs = Array.from(map.values());
}

export const STAGES: Stage[] = ['Saved', 'Applied', 'Screening', 'Technical', 'Final Interview', 'Offer', 'Rejected'];
export const LEVELS: Level[] = ['Entry-level', 'Mid', 'Senior'];

export const SKILL_KEYWORDS = ['Python', 'SQL', 'NLP', 'PyTorch', 'LangChain', 'Docker', 'AWS', 'React', 'Excel', 'Tableau', 'Git', 'Hugging Face', 'FastAPI', 'Node.js', 'Kubernetes', 'Statistics', 'Fine-tuning', 'APIs', 'Research', 'Evaluation'];

export const SAMPLE_RESUME =
  'Machine learning engineer with experience in NLP. Built a retrieval search tool using Python, LangChain and APIs. Fine-tuned a Hugging Face model for text classification. Used SQL and Git daily. Mentored students in an AI community.';

export const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: 'summary', label: 'Professional summary' },
  { key: 'skills', label: 'Skills (comma separated)' },
  { key: 'experience', label: 'Work experience' },
  { key: 'leadership', label: 'Leadership & Community' },
  { key: 'education', label: 'Education' },
  { key: 'projects', label: 'Projects' },
  { key: 'certs', label: 'Certifications and achievements' },
];

export const jobById = (id: number | string | undefined): Job | undefined => {
  if (id === undefined || id === null) return undefined;
  const strId = String(id);
  return dynamicJobs.find((j) => String(j.id) === strId) || JOBS.find((j) => String(j.id) === strId);
};

