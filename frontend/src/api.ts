/**
 * JobFit Backend API Client.
 * Connects frontend React components to FastAPI backend endpoints.
 */

const API_BASE = '/api/v1';

export interface TokenSession {
  access_token: string;
  user_id: string;
  email: string;
  name?: string;
  refresh_token?: string;
}

const TOKEN_KEY = 'jobfit_token_session';

export const sessionManager = {
  get(): TokenSession | null {
    try {
      const raw = localStorage.getItem(TOKEN_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },
  set(session: TokenSession) {
    try {
      localStorage.setItem(TOKEN_KEY, JSON.stringify(session));
    } catch {
      /* ignore */
    }
  },
  clear() {
    try {
      localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ignore */
    }
  },
  getToken(): string | null {
    return this.get()?.access_token || null;
  },
  getRefreshToken(): string | null {
    return this.get()?.refresh_token || null;
  },
};

function formatFriendlyError(body: any, status: number): string {
  if (body?.error?.message && typeof body.error.message === 'string') {
    return body.error.message;
  }
  if (body?.message && typeof body.message === 'string') {
    return body.message;
  }
  if (typeof body?.detail === 'string') {
    return body.detail;
  }
  if (body?.detail?.message && typeof body.detail.message === 'string') {
    return body.detail.message;
  }
  if (Array.isArray(body?.detail) && body.detail.length > 0) {
    const first = body.detail[0];
    const field = Array.isArray(first.loc) ? first.loc[first.loc.length - 1] : '';
    return `${field ? `${field}: ` : ''}${first.msg || 'Please check your inputs.'}`;
  }

  switch (status) {
    case 400:
      return 'The provided information could not be processed. Please check your inputs.';
    case 401:
      return 'Invalid email or password. Please verify your credentials.';
    case 403:
      return 'Access not permitted. Please sign in again.';
    case 404:
      return 'The requested record or resource was not found.';
    case 409:
      return 'An account with this email already exists. Please log in instead.';
    case 422:
      return 'Please make sure all fields are filled out correctly.';
    case 429:
      return 'Please wait a moment before trying again.';
    case 500:
    case 502:
    case 503:
      return 'The service is temporarily unavailable. Please try again shortly.';
    default:
      return 'Unable to complete request. Please verify your internet connection.';
  }
}

let isRefreshing = false;
let refreshSubscribers: ((token: string | null) => void)[] = [];

function onTokenRefreshed(token: string | null) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retry = true,
): Promise<{ data: T | null; error: string | null; status: number }> {
  const token = sessionManager.getToken();
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      ...options,
      headers,
      credentials: 'include',
    });

    if (res.status === 401 && retry && !endpoint.startsWith('/auth/')) {
      if (!isRefreshing) {
        isRefreshing = true;
        const refreshRes = await api.auth.refresh();
        isRefreshing = false;
        if (refreshRes.data) {
          onTokenRefreshed(refreshRes.data.access_token);
          return request<T>(endpoint, options, false);
        } else {
          onTokenRefreshed(null);
          sessionManager.clear();
          if (typeof window !== 'undefined') {
            window.dispatchEvent(new CustomEvent('jobfit:auth-expired'));
          }
        }
      } else {
        return new Promise((resolve) => {
          refreshSubscribers.push((newToken) => {
            if (newToken) {
              resolve(request<T>(endpoint, options, false));
            } else {
              resolve({ data: null, error: 'Session expired. Please log in again.', status: 401 });
            }
          });
        });
      }
    }

    const isJson = res.headers.get('content-type')?.includes('application/json');
    const body = isJson ? await res.json() : null;

    if (!res.ok) {
      const errorMsg = formatFriendlyError(body, res.status);
      return { data: null, error: errorMsg, status: res.status };
    }

    return { data: body as T, error: null, status: res.status };
  } catch (err: unknown) {
    const errorMsg = err instanceof Error ? err.message : 'Network error or backend unreachable';
    return { data: null, error: errorMsg, status: 0 };
  }
}

export const api = {
  auth: {
    async login(email: string, password: string, name?: string) {
      const res = await request<TokenSession>('/auth/session', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password, name }),
      });
      if (res.data) {
        sessionManager.set(res.data);
      }
      return res;
    },
    async signup(email: string, password: string, name?: string) {
      const res = await request<TokenSession>('/auth/signup', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim(), password, name }),
      });
      if (res.data) {
        sessionManager.set(res.data);
      }
      return res;
    },
    async refresh() {
      const refreshToken = sessionManager.getRefreshToken();
      const res = await request<TokenSession>(
        '/auth/refresh',
        {
          method: 'POST',
          body: JSON.stringify({ refresh_token: refreshToken }),
        },
        false,
      );
      if (res.data) {
        sessionManager.set(res.data);
      }
      return res;
    },
    async me() {
      return request<{ user_id: string; email?: string; name?: string }>('/auth/me');
    },
    async logout() {
      try {
        await request('/auth/logout', { method: 'POST' }, false);
      } catch {
        /* ignore */
      }
      sessionManager.clear();
    },
  },

  profile: {
    async getProfile() {
      return request<any>('/profile');
    },
    async updateProfile(payload: any) {
      return request<any>('/profile', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
    },
    async getPreferences() {
      return request<any>('/profile/preferences');
    },
    async updatePreferences(payload: any) {
      return request<any>('/profile/preferences', {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
    },
  },

  resumes: {
    async upload(file: File) {
      const formData = new FormData();
      formData.append('file', file);
      return request<{ resume_version_id: string; message: string; status: string }>('/resumes/upload', {
        method: 'POST',
        body: formData,
      });
    },
    async paste(text: string) {
      return request<{ resume_version_id: string; message: string; status: string }>('/resumes/paste', {
        method: 'POST',
        body: JSON.stringify({ text }),
      });
    },
    async createRaw(raw_text: string) {
      return this.paste(raw_text);
    },
    async extract(resumeVersionId: string) {
      return request<any>(`/resumes/${resumeVersionId}/extract`, {
        method: 'POST',
      });
    },
    async list() {
      return request<any[]>('/resumes');
    },
  },

  jobs: {
    async list(params?: { query?: string; location?: string; work_arrangement?: string; limit?: number }) {
      const q = new URLSearchParams();
      if (params?.query) q.set('query', params.query);
      if (params?.location) q.set('location', params.location);
      if (params?.work_arrangement) q.set('work_arrangement', params.work_arrangement);
      if (params?.limit) q.set('limit', String(params.limit));
      const str = q.toString();
      return request<any[]>(`/jobs${str ? '?' + str : ''}`);
    },
    async get(jobId: string) {
      return request<any>(`/jobs/${jobId}`);
    },
    async search(
      query?: string,
      location?: string,
      date_posted?: 'past24Hours' | 'pastWeek' | 'pastMonth' | 'anyTime',
      under_10_applicants?: boolean,
      extra?: {
        urls?: string[];
        geo_id?: string;
        distance?: number;
        locations?: string[];
        company_ids?: string[];
        auto_convert_to_ai_search?: boolean;
        scrape_company?: boolean;
        split_by_location?: boolean;
        split_country?: string;
        limit_per_provider?: number;
      },
    ) {
      return this.triggerDiscovery(query, location, date_posted, under_10_applicants, extra);
    },
    async triggerDiscovery(
      query?: string,
      location?: string,
      date_posted?: 'past24Hours' | 'pastWeek' | 'pastMonth' | 'anyTime',
      under_10_applicants?: boolean,
      extra?: {
        urls?: string[];
        geo_id?: string;
        distance?: number;
        locations?: string[];
        company_ids?: string[];
        auto_convert_to_ai_search?: boolean;
        scrape_company?: boolean;
        split_by_location?: boolean;
        split_country?: string;
        limit_per_provider?: number;
      },
    ) {
      return request<any>('/jobs/search', {
        method: 'POST',
        body: JSON.stringify({
          query: query || undefined,
          location: location || undefined,
          locations: extra?.locations && extra.locations.length > 0 ? extra.locations : undefined,
          date_posted: date_posted || undefined,
          under_10_applicants: under_10_applicants || undefined,
          urls: extra?.urls && extra.urls.length > 0 ? extra.urls : undefined,
          geo_id: extra?.geo_id || undefined,
          distance: extra?.distance !== undefined ? extra.distance : undefined,
          company_ids: extra?.company_ids || undefined,
          auto_convert_to_ai_search: extra?.auto_convert_to_ai_search ?? true,
          scrape_company: extra?.scrape_company ?? false,
          split_by_location: extra?.split_by_location ?? false,
          split_country: extra?.split_country || undefined,
          limit_per_provider: extra?.limit_per_provider || 35,
        }),
      });
    },
    async aiFilter(
      query?: string,
      min_fit: 'all' | 'valid_only' | 'strong_only' = 'all',
      limit = 30,
      filters?: {
        location?: string;
        work_arrangement?: string;
        date_posted?: 'anyTime' | 'past24Hours' | 'pastWeek' | 'pastMonth';
        experience_level?: string;
        employment_type?: string;
        candidate_profile?: any;
      },
    ) {
      return request<import('./types').JobAIFilterResponse>('/jobs/ai-filter', {
        method: 'POST',
        body: JSON.stringify({
          query: query || null,
          min_fit,
          limit,
          location: filters?.location || null,
          work_arrangement: filters?.work_arrangement || null,
          date_posted: filters?.date_posted || null,
          experience_level: filters?.experience_level || null,
          employment_type: filters?.employment_type || null,
          candidate_profile: filters?.candidate_profile || null,
        }),
      });
    },
  },

  matches: {
    async list(params?: { min_score?: number; limit?: number }) {
      const q = new URLSearchParams();
      if (params?.min_score) q.set('min_score', String(params.min_score));
      if (params?.limit) q.set('limit', String(params.limit));
      const str = q.toString();
      return request<any[]>(`/matches${str ? '?' + str : ''}`);
    },
    async evaluate(jobId: string) {
      return request<any>('/matches/evaluate', {
        method: 'POST',
        body: JSON.stringify({ job_id: jobId }),
      });
    },
    async save(matchId: string, is_saved: boolean) {
      return request<any>(`/matches/${matchId}/save`, {
        method: 'PATCH',
        body: JSON.stringify({ is_saved }),
      });
    },
    async batch(jobIds: string[]) {
      return request<{ evaluated_count: number; matches: any[] }>('/matches/batch', {
        method: 'POST',
        body: JSON.stringify({ job_ids: jobIds }),
      });
    },
  },

  tailor: {
    async generate(jobId: string, targetRoleNotes?: string) {
      return request<any>('/tailor', {
        method: 'POST',
        body: JSON.stringify({
          job_id: jobId,
          target_role_notes: targetRoleNotes,
        }),
      });
    },
    async listDocuments() {
      return request<any[]>('/tailored-documents');
    },
    async getDocument(id: string) {
      return request<any>(`/tailored-documents/${id}`);
    },
    async getDownloadUrl(id: string) {
      return request<{ download_url: string; filename?: string; expires_in_seconds: number }>(`/tailored-documents/${id}/download`);
    },
  },

  applications: {
    async list(status?: string) {
      const q = status ? `?status=${encodeURIComponent(status)}` : '';
      return request<any[]>(`/applications${q}`);
    },
    async create(jobId: string, status = 'saved', notes?: string, tailoredDocId?: string) {
      return request<any>('/applications', {
        method: 'POST',
        body: JSON.stringify({
          job_id: jobId,
          status,
          notes,
          tailored_document_id: tailoredDocId || null,
        }),
      });
    },
    async get(id: string) {
      return request<any>(`/applications/${id}`);
    },
    async update(id: string, updates: { status?: string; notes?: string; tailored_document_id?: string }) {
      return request<any>(`/applications/${id}`, {
        method: 'PATCH',
        body: JSON.stringify(updates),
      });
    },
    async addEvent(id: string, event_type: string, note?: string) {
      return request<any>(`/applications/${id}/events`, {
        method: 'POST',
        body: JSON.stringify({ event_type, note }),
      });
    },
    async listEvents(id: string) {
      return request<any[]>(`/applications/${id}/events`);
    },
  },

  tasks: {
    async get(id: string) {
      return request<any>(`/tasks/${id}`);
    },
  },

  searchRuns: {
    async list(limit = 20) {
      return request<any[]>(`/search-runs?limit=${limit}`);
    },
    async delete(runId: string) {
      return request<void>(`/search-runs/${runId}`, {
        method: 'DELETE',
      });
    },
  },
};

