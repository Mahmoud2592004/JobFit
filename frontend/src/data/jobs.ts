import type { Job, Level, SectionKey, Stage } from '../types';

/** Sample listings for the preview. Replace with your Apify/LinkedIn-backed API. */
export const JOBS: Job[] = [
  {
    id: 1,
    title: 'Machine Learning Engineer',
    company: 'Nilecore AI',
    location: 'Cairo',
    mode: 'Hybrid',
    type: 'Full-time',
    level: 'Mid',
    daysAgo: 2,
    requirements: ['Python', 'NLP', 'Fine-tuning', 'FastAPI', 'AWS'],
    eligibility: 'Hybrid in Cairo. Confirm you can commute.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=Machine%20Learning%20Engineer&location=Cairo%2C%20Egypt',
  },
  {
    id: 2,
    title: 'NLP Research Intern',
    company: 'Lexica Labs',
    location: 'Remote',
    mode: 'Remote',
    type: 'Internship',
    level: 'Entry-level',
    daysAgo: 5,
    requirements: ['Python', 'NLP', 'PyTorch', 'Research'],
    eligibility: 'Open to students and recent graduates.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=NLP%20Engineer&f_WT=2',
  },
  {
    id: 3,
    title: 'AI Application Developer',
    company: 'Orbit Commerce',
    location: 'Cairo',
    mode: 'On-site',
    type: 'Full-time',
    level: 'Entry-level',
    daysAgo: 1,
    requirements: ['Python', 'LangChain', 'APIs', 'React', 'Docker'],
    eligibility: 'On-site in Cairo.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=AI%20Developer&location=Cairo%2C%20Egypt',
  },
  {
    id: 4,
    title: 'Junior Data Scientist',
    company: 'Delta Analytics',
    location: 'Remote',
    mode: 'Remote',
    type: 'Full-time',
    level: 'Entry-level',
    daysAgo: 9,
    requirements: ['Python', 'SQL', 'Statistics', 'Tableau'],
    eligibility: 'Last checked 9 days ago. Confirm it is still open.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=Data%20Scientist&f_WT=2',
  },
  {
    id: 5,
    title: 'Backend Engineer',
    company: 'Fawry Works',
    location: 'Giza',
    mode: 'Hybrid',
    type: 'Full-time',
    level: 'Mid',
    daysAgo: 3,
    requirements: ['Node.js', 'SQL', 'Docker', 'AWS'],
    eligibility: 'Hybrid in Giza.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=Backend%20Engineer%20Fawry&location=Egypt',
  },
  {
    id: 6,
    title: 'LLM Evaluation Engineer',
    company: 'Sahara Intelligence',
    location: 'Remote',
    mode: 'Remote',
    type: 'Part-time',
    level: 'Mid',
    daysAgo: 4,
    requirements: ['Python', 'LangChain', 'NLP', 'Evaluation'],
    eligibility: 'Part-time, 20 hours a week.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=LLM%20Engineer&f_WT=2',
  },
  {
    id: 7,
    title: 'MLOps Engineer',
    company: 'Pyramid Cloud',
    location: 'Cairo',
    mode: 'Hybrid',
    type: 'Full-time',
    level: 'Senior',
    daysAgo: 6,
    requirements: ['Docker', 'Kubernetes', 'AWS', 'Python'],
    eligibility: 'Asks for 5+ years of experience. Verify before applying.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=MLOps%20Engineer&location=Cairo%2C%20Egypt',
  },
  {
    id: 8,
    title: 'Data Analyst Intern',
    company: 'Nile Retail',
    location: 'Alexandria',
    mode: 'On-site',
    type: 'Internship',
    level: 'Entry-level',
    daysAgo: 7,
    requirements: ['SQL', 'Excel', 'Tableau', 'Python'],
    eligibility: 'On-site in Alexandria.',
    source_url: 'https://www.linkedin.com/jobs/search/?keywords=Data%20Analyst&location=Alexandria%2C%20Egypt',
  },
];

export const STAGES: Stage[] = ['Saved', 'Applied', 'Screening', 'Technical', 'Final Interview', 'Offer', 'Rejected'];
export const LEVELS: Level[] = ['Entry-level', 'Mid', 'Senior'];

export const SKILL_KEYWORDS = ['Python', 'SQL', 'NLP', 'PyTorch', 'LangChain', 'Docker', 'AWS', 'React', 'Excel', 'Tableau', 'Git', 'Hugging Face', 'FastAPI', 'Node.js', 'Kubernetes', 'Statistics', 'Fine-tuning', 'APIs', 'Research', 'Evaluation'];

export const SAMPLE_RESUME =
  'Machine learning engineer with experience in NLP. Built a retrieval search tool using Python, LangChain and APIs. Fine-tuned a Hugging Face model for text classification. Used SQL and Git daily. Mentored students in an AI community.';

export const SECTIONS: { key: SectionKey; label: string }[] = [
  { key: 'summary', label: 'Professional summary' },
  { key: 'skills', label: 'Skills (comma separated)' },
  { key: 'experience', label: 'Work experience' },
  { key: 'education', label: 'Education' },
  { key: 'projects', label: 'Projects' },
  { key: 'certs', label: 'Certifications and achievements' },
];

export const jobById = (id: number | string | undefined): Job | undefined =>
  JOBS.find((j) => j.id === Number(id));
