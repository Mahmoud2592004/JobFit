import { createContext, useContext, useEffect, useMemo, useReducer, type ReactNode } from 'react';
import { jobById } from '../data/jobs';
import { matchJob, today } from '../lib/match';
import { sessionManager } from '../api';
import type { AppState, Application, Prefs, Profile, Stage, TemplateId, TailoredResume, User } from '../types';

const KEY = 'jobfit:v1';
const USER_KEY_PREFIX = 'jobfit:v1:user:';

export const getUserStorageKey = (email?: string | null): string | null =>
  email ? `${USER_KEY_PREFIX}${email.trim().toLowerCase()}` : null;

export const DEFAULT_PREFS: Prefs = {
  titles: 'Machine Learning Engineer, NLP Engineer',
  location: 'Cairo',
  mode: 'Any',
  type: 'Any',
  level: 'Entry-level',
  requireMode: false,
  requireLocation: false,
};

const initial: AppState = {
  user: null,
  prefs: DEFAULT_PREFS,
  profile: null,
  saved: {},
  dismissed: {},
  applications: [],
  resumes: [],
  nextId: 1,
  alertsSeen: false,
  template: 'navy',
};

function load(): AppState {
  // Purge any stale un-namespaced global mock data
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }

  try {
    const session = sessionManager.get();
    if (session?.email) {
      const uKey = getUserStorageKey(session.email);
      const raw = uKey ? localStorage.getItem(uKey) : null;
      if (raw) {
        return {
          ...initial,
          ...(JSON.parse(raw) as Partial<AppState>),
          user: {
            name: session.name || session.email.split('@')[0],
            email: session.email,
          },
        };
      }
      return {
        ...initial,
        user: {
          name: session.name || session.email.split('@')[0],
          email: session.email,
        },
      };
    }
  } catch {
    /* storage unavailable: start fresh */
  }
  return initial;
}

export interface ApplicationPatch {
  stage?: Stage;
  appliedDate?: string;
  milestone?: string;
  salary?: string;
  resumeId?: number | null;
  notes?: string;
}

export interface ResumePayload {
  resumeId: number | null;
  jobId: number;
  template: TemplateId;
  summary: string;
  skills: string;
  experience: string;
  coverLetter: string;
}

type Action =
  | { type: 'login'; user: User }
  | { type: 'logout' }
  | { type: 'profile'; profile: Profile | null }
  | { type: 'prefs'; prefs: Prefs }
  | { type: 'save'; jobId: number }
  | { type: 'dismiss'; jobId: number }
  | { type: 'alertsSeen' }
  | { type: 'move'; id: number; stage: Stage }
  | { type: 'updateApplication'; id: number; patch: ApplicationPatch }
  | { type: 'saveResume'; payload: ResumePayload }
  | { type: 'deleteResume'; id: number }
  | { type: 'deleteAllResumes' }
  | { type: 'template'; template: TemplateId }
  | { type: 'deleteAccount' };

function ensureApplication(state: AppState, jobId: number, stage: Stage): { state: AppState; app: Application } {
  const found = state.applications.find((a) => a.jobId === jobId);
  if (found) return { state, app: found };
  const job = jobById(jobId);
  const score = job && state.profile ? matchJob(job, state.profile, state.prefs).score : 0;
  const app: Application = {
    id: state.nextId,
    jobId,
    stage,
    score,
    appliedDate: '',
    milestone: '',
    salary: '',
    notes: '',
    resumeId: null,
    history: [`${today()}: ${stage}`],
  };
  return { state: { ...state, nextId: state.nextId + 1, applications: [...state.applications, app] }, app };
}

function changeStage(app: Application, stage: Stage): Application {
  if (app.stage === stage) return app;
  return {
    ...app,
    stage,
    history: [...app.history, `${today()}: ${stage}`],
    appliedDate: stage === 'Applied' && !app.appliedDate ? today() : app.appliedDate,
  };
}

function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'login': {
      const isSameUser = state.user?.email && state.user.email.toLowerCase() === action.user.email.toLowerCase();
      if (isSameUser) {
        return { ...state, user: action.user };
      }
      const uKey = getUserStorageKey(action.user.email);
      let userCached: Partial<AppState> = {};
      if (uKey) {
        try {
          const raw = localStorage.getItem(uKey);
          if (raw) userCached = JSON.parse(raw);
        } catch {
          /* ignore */
        }
      }
      return {
        ...initial,
        ...userCached,
        user: action.user,
      };
    }
    case 'logout': {
      sessionManager.clear();
      return {
        ...initial,
        user: null,
      };
    }
    case 'profile':
      return { ...state, profile: action.profile };
    case 'prefs':
      return { ...state, prefs: action.prefs };
    case 'save': {
      if (state.saved[action.jobId]) return state;
      const { state: next } = ensureApplication(state, action.jobId, 'Saved');
      return { ...next, saved: { ...next.saved, [action.jobId]: true } };
    }
    case 'dismiss':
      return { ...state, dismissed: { ...state.dismissed, [action.jobId]: true } };
    case 'alertsSeen':
      return { ...state, alertsSeen: true };
    case 'move':
      return { ...state, applications: state.applications.map((a) => (a.id === action.id ? changeStage(a, action.stage) : a)) };
    case 'updateApplication':
      return {
        ...state,
        applications: state.applications.map((a) => {
          if (a.id !== action.id) return a;
          const { stage, ...rest } = action.patch;
          const staged = stage ? changeStage(a, stage) : a;
          return { ...staged, ...rest, appliedDate: rest.appliedDate ?? staged.appliedDate };
        }),
      };
    case 'saveResume': {
      const p = action.payload;
      const job = jobById(p.jobId);
      if (!job) return state;
      const fields = {
        jobId: p.jobId,
        name: `${job.title} · ${job.company}`,
        date: today(),
        state: 'Approved' as const,
        template: p.template,
        summary: p.summary,
        skills: p.skills,
        experience: p.experience,
        coverLetter: p.coverLetter,
      };
      let resumes: TailoredResume[];
      let resumeId = p.resumeId;
      let nextState = state;
      if (resumeId !== null && state.resumes.some((r) => r.id === resumeId)) {
        const id = resumeId;
        resumes = state.resumes.map((r) => (r.id === id ? { ...r, ...fields } : r));
      } else {
        resumeId = state.nextId;
        resumes = [...state.resumes, { id: resumeId, ...fields }];
        nextState = { ...state, nextId: state.nextId + 1 };
      }
      const withApp = ensureApplication({ ...nextState, resumes }, p.jobId, 'Saved');
      const rid = resumeId;
      return {
        ...withApp.state,
        template: p.template,
        applications: withApp.state.applications.map((a) => (a.id === withApp.app.id ? { ...a, resumeId: rid } : a)),
      };
    }
    case 'deleteResume':
      return {
        ...state,
        resumes: state.resumes.filter((r) => r.id !== action.id),
        applications: state.applications.map((a) => (a.resumeId === action.id ? { ...a, resumeId: null } : a)),
      };
    case 'deleteAllResumes':
      return { ...state, resumes: [], applications: state.applications.map((a) => ({ ...a, resumeId: null })) };
    case 'template':
      return { ...state, template: action.template };
    case 'deleteAccount': {
      if (state.user?.email) {
        const uKey = getUserStorageKey(state.user.email);
        if (uKey) {
          try {
            localStorage.removeItem(uKey);
          } catch {
            /* ignore */
          }
        }
      }
      sessionManager.clear();
      return { ...initial, user: null };
    }
  }
}

interface Actions {
  login: (user: User) => void;
  logout: () => void;
  saveProfile: (profile: Profile | null) => void;
  savePrefs: (prefs: Prefs) => void;
  saveJob: (jobId: number) => void;
  dismissJob: (jobId: number) => void;
  markAlertsSeen: () => void;
  moveApplication: (id: number, stage: Stage) => void;
  updateApplication: (id: number, patch: ApplicationPatch) => void;
  saveResume: (payload: ResumePayload) => void;
  deleteResume: (id: number) => void;
  deleteAllResumes: () => void;
  deleteAccount: () => void;
}

interface Ctx {
  state: AppState;
  actions: Actions;
}

const AppContext = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, undefined, load);

  useEffect(() => {
    if (state.user?.email) {
      const uKey = getUserStorageKey(state.user.email);
      if (uKey) {
        try {
          localStorage.setItem(uKey, JSON.stringify(state));
        } catch {
          /* ignore */
        }
      }
    }
    try {
      localStorage.removeItem(KEY);
    } catch {
      /* ignore */
    }
  }, [state]);

  const actions = useMemo<Actions>(
    () => ({
      login: (user) => dispatch({ type: 'login', user }),
      logout: () => dispatch({ type: 'logout' }),
      saveProfile: (profile) => dispatch({ type: 'profile', profile }),
      savePrefs: (prefs) => dispatch({ type: 'prefs', prefs }),
      saveJob: (jobId) => dispatch({ type: 'save', jobId }),
      dismissJob: (jobId) => dispatch({ type: 'dismiss', jobId }),
      markAlertsSeen: () => dispatch({ type: 'alertsSeen' }),
      moveApplication: (id, stage) => dispatch({ type: 'move', id, stage }),
      updateApplication: (id, patch) => dispatch({ type: 'updateApplication', id, patch }),
      saveResume: (payload) => dispatch({ type: 'saveResume', payload }),
      deleteResume: (id) => dispatch({ type: 'deleteResume', id }),
      deleteAllResumes: () => dispatch({ type: 'deleteAllResumes' }),
      deleteAccount: () => dispatch({ type: 'deleteAccount' }),
    }),
    [],
  );

  const value = useMemo(() => ({ state, actions }), [state, actions]);
  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): Ctx {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error('useApp must be used inside <AppProvider>');
  return ctx;
}
