export type Mode = 'Remote' | 'Hybrid' | 'On-site';
export type JobType = 'Full-time' | 'Part-time' | 'Internship';
export type Level = 'Entry-level' | 'Mid' | 'Senior';
export type Stage =
  | 'Saved'
  | 'Applied'
  | 'Screening'
  | 'Technical'
  | 'Final Interview'
  | 'Offer'
  | 'Rejected';
export type TemplateId = 'navy' | 'black' | 'tech';
/** s = strong fit, p = potential fit, n = not a fit */
export type FitTone = 's' | 'p' | 'n';

export interface ItemLink {
  label: string;
  url: string;
}

export interface Job {
  id: number | string;
  title: string;
  company: string;
  location: string;
  mode: Mode;
  type: JobType;
  level: Level;
  daysAgo: number;
  requirements: string[];
  eligibility: string;
  source_url?: string;
  description?: string;
}

export interface Match {
  strong: string[];
  partial: string[];
  gaps: string[];
  skillScore: number;
  seniority: number;
  arrangement: number;
  score: number;
  recruiterRationale?: string;
  experienceFitAnalysis?: string;
  preferenceFitAnalysis?: string;
  isAiEvaluated?: boolean;
}

export type SectionKey = 'summary' | 'skills' | 'experience' | 'leadership' | 'education' | 'projects' | 'certs';

export interface Profile extends Record<SectionKey, string> {
  name: string;
  email: string;
  phone: string;
  location: string;
  link: string;
  github?: string;
  other_links?: string[];
  years_experience?: number;
  confirmed: Partial<Record<SectionKey, boolean>>;
  created: string;
}

export interface Prefs {
  titles: string;
  location: string;
  countries?: string[];
  mode: Mode | 'Any';
  type: JobType | 'Any';
  level: Level;
  requireMode: boolean;
  requireLocation: boolean;
  urls?: string[];
  geoId?: string;
  distance?: number;
  datePosted?: 'anyTime' | 'past24Hours' | 'pastWeek' | 'pastMonth';
  companyIds?: string[];
  under10Applicants?: boolean;
  autoConvertToAiSearch?: boolean;
  scrapeCompany?: boolean;
  limitPerSource?: number;
  splitByLocation?: boolean;
  splitCountry?: string;
}

export interface User {
  name: string;
  email: string;
}

export interface Application {
  id: number;
  jobId: number | string;
  stage: Stage;
  /** Fit score at the time the job was saved */
  score: number;
  appliedDate: string;
  milestone: string;
  salary: string;
  notes: string;
  resumeId: number | null;
  history: string[];
}

export interface TailoredResume {
  id: number;
  jobId: number | string;
  name: string;
  date: string;
  state: 'Approved';
  template: TemplateId;
  summary: string;
  skills: string;
  experience: string;
  leadership?: string;
  coverLetter: string;
}

export interface AppState {
  user: User | null;
  prefs: Prefs;
  profile: Profile | null;
  saved: Record<number | string, boolean>;
  dismissed: Record<number | string, boolean>;
  applications: Application[];
  resumes: TailoredResume[];
  nextId: number;
  alertsSeen: boolean;
  template: TemplateId;
  jobs?: Job[];
}

export interface Draft {
  summary: string;
  skills: string;
  experience: string;
  leadership?: string;
}

export interface JobFilters {
  q: string;
  mode: '' | Mode;
  type: '' | JobType;
  level?: '' | Level;
  timePosted?: 'anyTime' | 'past24Hours' | 'pastWeek' | 'pastMonth';
  min: number;
  sort: 'score' | 'recent';
}

export interface JobAIEvaluation {
  job_id: string;
  is_valid_match: boolean;
  fit_level: 'Strong Fit' | 'Potential Fit' | 'Not a Fit';
  ai_score: number;
  experience_fit_analysis: string;
  preference_fit_analysis: string;
  recruiter_rationale: string;
}

export interface JobAIFilteredItem {
  job: any;
  evaluation: JobAIEvaluation;
}

export interface JobAIFilterResponse {
  candidate_summary: {
    display_name: string;
    years_experience: number;
    seniority_level: string;
    target_roles: string[];
    top_skills: string[];
    preferred_work_arrangements: string[];
    preferred_locations: string[];
  };
  total_evaluated: number;
  valid_count: number;
  results: JobAIFilteredItem[];
  search_run_id?: string;
  query?: string;
}

