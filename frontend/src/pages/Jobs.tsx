import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { JobDetail, JobListItem } from '../components/Job';
import { filterJobs, extractSkills, inferSeniorityLevel } from '../lib/match';
import { useMediaQuery } from '../lib/hooks';
import { useApp } from '../store/AppContext';
import { api } from '../api';
import { getCountryName } from '../data/countries';
import type { Job, JobFilters, JobType, Level, Mode } from '../types';

export default function Jobs() {
  const { state } = useApp();
  const { id } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const desktop = useMediaQuery('(min-width: 821px)');
  const [filters, setFilters] = useState<JobFilters>({
    q: params.get('q') ?? '',
    mode: '',
    type: '',
    level: '',
    timePosted: 'anyTime',
    min: 0,
    sort: 'score',
  });

  const [aiLoading, setAiLoading] = useState(false);
  const [fetchPhase, setFetchPhase] = useState<'idle' | 'fetching' | 'ranking'>('idle');
  const [liveJobs, setLiveJobs] = useState<Job[] | null>(() => {
    try {
      const raw = sessionStorage.getItem('jobfit:cached_live_jobs');
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  });
  const [aiRationaleMap, setAiRationaleMap] = useState<Record<string, {
    score: number;
    rationale: string;
    fit: string;
    experienceFitAnalysis?: string;
    preferenceFitAnalysis?: string;
  }>>(() => {
    try {
      const raw = sessionStorage.getItem('jobfit:cached_ai_rationale');
      return raw ? JSON.parse(raw) : {};
    } catch {
      return {};
    }
  });
  const [statusMsg, setStatusMsg] = useState('');

  const calculateVerifiedYears = (): number | undefined => {
    if (
      state.profile?.years_experience !== undefined &&
      state.profile?.years_experience !== null &&
      !isNaN(Number(state.profile.years_experience))
    ) {
      return Number(state.profile.years_experience);
    }
    return undefined;
  };

  const runGeminiFilter = async (_catalogOverride?: Job[]) => {
    setAiLoading(true);
    setFetchPhase('ranking');
    setStatusMsg('Ranking listings with Gemini AI recruiter evaluation...');
    try {
      const verifiedYears = calculateVerifiedYears();
      const targetRoles = state.prefs.titles
        ? state.prefs.titles.split(',').map((t) => t.trim()).filter(Boolean)
        : ['Software Engineer'];
      const targetLocations = state.prefs.countries && state.prefs.countries.length > 0
        ? state.prefs.countries.map((c) => getCountryName(c))
        : (state.prefs.location ? state.prefs.location.split(',').map((l) => l.trim()).filter(Boolean) : []);
      const targetLocParam = targetLocations.length > 0 ? targetLocations.join(', ') : undefined;

      const candidateProfilePayload = state.profile
        ? {
            years_experience: verifiedYears,
            seniority_level: state.prefs.level || undefined,
            target_roles: targetRoles,
            skills: state.profile.skills ? state.profile.skills.split(',').map((s) => s.trim()).filter(Boolean) : [],
            preferred_work_arrangements: [state.prefs.mode || 'Remote'],
            preferred_locations: targetLocations,
            location: state.profile.location || 'Cairo, Egypt',
            summary: state.profile.summary,
            experience: state.profile.experience,
          }
        : undefined;

      const res = await api.jobs.aiFilter(filters.q || undefined, 'all', 60, {
        location: targetLocParam,
        work_arrangement: filters.mode || undefined,
        employment_type: filters.type || undefined,
        experience_level: filters.level || undefined,
        date_posted: filters.timePosted || undefined,
        candidate_profile: candidateProfilePayload,
      });

      if (res.data && res.data.results.length > 0) {
        const rationaleMap: Record<string, {
          score: number;
          rationale: string;
          fit: string;
          experienceFitAnalysis?: string;
          preferenceFitAnalysis?: string;
        }> = {};

        res.data.results.forEach((r) => {
          rationaleMap[String(r.job.id)] = {
            score: r.evaluation.ai_score,
            rationale: r.evaluation.recruiter_rationale,
            fit: r.evaluation.fit_level,
            experienceFitAnalysis: r.evaluation.experience_fit_analysis,
            preferenceFitAnalysis: r.evaluation.preference_fit_analysis,
          };
        });

        setAiRationaleMap(rationaleMap);
        try {
          sessionStorage.setItem('jobfit:cached_ai_rationale', JSON.stringify(rationaleMap));
        } catch {}
        setStatusMsg(`Gemini AI evaluated and ranked ${res.data.total_evaluated} listings.`);
      } else {
        setStatusMsg('Gemini evaluation completed.');
      }
    } catch {
      setStatusMsg('AI service busy: showing active catalog.');
    } finally {
      setAiLoading(false);
      setFetchPhase('idle');
    }
  };

  const loadPersistedJobs = () => {
    // If jobs are already cached in session/memory, do not refetch or re-rank automatically
    if (liveJobs && liveJobs.length > 0) {
      return;
    }

    const targetLocations = state.prefs.countries && state.prefs.countries.length > 0
      ? state.prefs.countries.map((c) => getCountryName(c))
      : (state.prefs.location ? state.prefs.location.split(',').map((l) => l.trim()).filter(Boolean) : []);
    const targetLocParam = targetLocations.length > 0 ? targetLocations.join(', ') : undefined;

    api.jobs
      .list({ limit: 50, location: targetLocParam })
      .then((res) => {
        if (res.data && res.data.length > 0) {
          const mapped: Job[] = res.data.map((b: any, idx: number) => ({
            id: b.id || 1000 + idx,
            title: b.title,
            company: b.employer,
            location: b.location || 'Remote',
            mode: (b.work_arrangement === 'remote' ? 'Remote' : b.work_arrangement === 'hybrid' ? 'Hybrid' : 'On-site') as Mode,
            type: (b.employment_type === 'internship' ? 'Internship' : b.employment_type === 'part_time' ? 'Part-time' : 'Full-time') as JobType,
            level: inferSeniorityLevel(b.seniority, b.title),
            daysAgo: Math.max(1, Math.round((Date.now() - new Date(b.published_at || b.retrieved_at).getTime()) / 86400000)),
            requirements: b.description ? extractSkills(b.description).split(', ').filter(Boolean) : ['Python', 'SQL'],
            eligibility: `${b.work_arrangement || 'Flexible'} in ${b.location || 'Anywhere'}. Verified via ${b.source_name}.`,
            source_url: b.canonical_url,
            description: b.description,
          }));
          setLiveJobs(mapped);
          try {
            sessionStorage.setItem('jobfit:cached_live_jobs', JSON.stringify(mapped));
          } catch {}
          // Note: we purposely do NOT trigger runGeminiFilter here to save API costs on page transitions.
        }
      })
      .catch(() => {});
  };

  useEffect(() => {
    loadPersistedJobs();
  }, []);

  const urlQuery = params.get('q');
  useEffect(() => {
    if (urlQuery !== null) setFilters((f) => ({ ...f, q: urlQuery }));
  }, [urlQuery]);

  // Merge live jobs and Gemini AI scores
  const effectiveState = {
    ...state,
    customJobs: liveJobs || undefined,
    aiScores: aiRationaleMap,
  };

  const { items, hidden } = filterJobs(effectiveState, filters);

  const selectedId = id ? String(id) : desktop ? (items[0]?.job.id ? String(items[0]?.job.id) : undefined) : undefined;
  const selected = items.find((x) => String(x.job.id) === selectedId);
  const set = <K extends keyof JobFilters>(k: K, v: JobFilters[K]) => setFilters((f) => ({ ...f, [k]: v }));

  const fetchAndRankJobs = async () => {
    setAiLoading(true);
    setFetchPhase('fetching');
    try {
      const targetQuery = filters.q || state.prefs.titles?.split(',')[0]?.trim() || 'Software Engineer';
      const targetLocationsList = state.prefs.countries && state.prefs.countries.length > 0
        ? state.prefs.countries.map((c) => getCountryName(c))
        : (state.prefs.location ? state.prefs.location.split(',').map((l) => l.trim()).filter(Boolean) : []);
      const targetLocation = targetLocationsList.length > 0 ? targetLocationsList.join(', ') : undefined;
      const splitCountryCode = targetLocationsList.length === 1
        ? (state.prefs.splitCountry || (state.prefs.countries && state.prefs.countries[0]))
        : undefined;

      setStatusMsg(
        targetLocationsList.length > 1
          ? `1/2 Fetching listings evenly across ${targetLocationsList.length} countries (${targetLocationsList.join(', ')})...`
          : `1/2 Fetching live listings for ${targetLocation || 'target location'}...`
      );

      // 1. Fetch live jobs based on user preferences
      const searchRes = await api.jobs.search(
        targetQuery,
        targetLocation,
        (state.prefs.datePosted as any) || (filters.timePosted as any) || 'anyTime',
        state.prefs.under10Applicants,
        {
          urls: state.prefs.urls && state.prefs.urls.length > 0 ? state.prefs.urls : undefined,
          geo_id: state.prefs.geoId || undefined,
          distance: state.prefs.distance,
          locations: targetLocationsList.length > 0 ? targetLocationsList : undefined,
          company_ids: state.prefs.companyIds,
          auto_convert_to_ai_search: state.prefs.autoConvertToAiSearch ?? true,
          scrape_company: state.prefs.scrapeCompany ?? true,
          split_by_location: state.prefs.splitByLocation ?? false,
          split_country: splitCountryCode,
          limit_per_provider: state.prefs.limitPerSource || 35,
        }
      );

      setFetchPhase('ranking');
      setStatusMsg(
        searchRes.data?.jobs_count
          ? `2/2 Discovered ${searchRes.data.jobs_count} live listings. Now evaluating fit with Gemini AI...`
          : '2/2 Catalog synchronized. Now evaluating fit with Gemini AI...'
      );

      // 2. Fetch fresh catalog listings
      const catalogRes = await api.jobs.list({ limit: 60, location: targetLocation });
      let mappedJobs: Job[] = [];
      if (catalogRes.data && catalogRes.data.length > 0) {
        mappedJobs = catalogRes.data.map((b: any, idx: number) => ({
          id: b.id || 1000 + idx,
          title: b.title,
          company: b.employer,
          location: b.location || 'Remote',
          mode: (b.work_arrangement === 'remote' ? 'Remote' : b.work_arrangement === 'hybrid' ? 'Hybrid' : 'On-site') as Mode,
          type: (b.employment_type === 'internship' ? 'Internship' : b.employment_type === 'part_time' ? 'Part-time' : 'Full-time') as JobType,
          level: inferSeniorityLevel(b.seniority, b.title),
          daysAgo: Math.max(1, Math.round((Date.now() - new Date(b.published_at || b.retrieved_at).getTime()) / 86400000)),
          requirements: b.description ? extractSkills(b.description).split(', ').filter(Boolean) : ['Python', 'SQL'],
          eligibility: `${b.work_arrangement || 'Flexible'} in ${b.location || 'Anywhere'}. Verified via ${b.source_name}.`,
          source_url: b.canonical_url,
          description: b.description,
        }));
      }

      // Merge newly discovered jobs from all countries
      const newlyDiscovered = searchRes.data?.jobs || [];
      if (newlyDiscovered.length > 0) {
        const seenIds = new Set(mappedJobs.map((j) => String(j.id)));
        const newMapped = newlyDiscovered
          .filter((b: any) => !seenIds.has(String(b.id)))
          .map((b: any, idx: number) => ({
            id: b.id || 2000 + idx,
            title: b.title,
            company: b.employer,
            location: b.location || 'Remote',
            mode: (b.work_arrangement === 'remote' ? 'Remote' : b.work_arrangement === 'hybrid' ? 'Hybrid' : 'On-site') as Mode,
            type: (b.employment_type === 'internship' ? 'Internship' : b.employment_type === 'part_time' ? 'Part-time' : 'Full-time') as JobType,
            level: inferSeniorityLevel(b.seniority, b.title),
            daysAgo: Math.max(1, Math.round((Date.now() - new Date(b.published_at || b.retrieved_at).getTime()) / 86400000)),
            requirements: b.description ? extractSkills(b.description).split(', ').filter(Boolean) : ['Python', 'SQL'],
            eligibility: `${b.work_arrangement || 'Flexible'} in ${b.location || 'Anywhere'}. Verified via ${b.source_name}.`,
            source_url: b.canonical_url,
            description: b.description,
          }));
        mappedJobs = [...newMapped, ...mappedJobs];
      }

      if (mappedJobs.length > 0) {
        setLiveJobs(mappedJobs);
        try {
          sessionStorage.setItem('jobfit:cached_live_jobs', JSON.stringify(mappedJobs));
        } catch {}
      }

      // 3. Rank with Gemini AI strictly incorporating candidate years of experience
      await runGeminiFilter(mappedJobs);
    } catch {
      setStatusMsg('Encountered an issue fetching live jobs. Ranking catalog with Gemini AI...');
      await runGeminiFilter();
    } finally {
      setAiLoading(false);
      setFetchPhase('idle');
    }
  };

  // A dismissed job disappears from the list: go back to the list instead of showing a stale detail pane.
  useEffect(() => {
    if (id && !items.some((x) => String(x.job.id) === String(id)) && desktop) navigate('/jobs', { replace: true });
  }, [id, items, desktop, navigate]);

  return (
    <>
      <div className="card fb stack" style={{ gap: 12 }}>
        <div className="row">
          <input className="i" placeholder="Title, company or skill" aria-label="Search" value={filters.q} onChange={(e) => set('q', e.target.value)} />
          <select className="i" aria-label="Work arrangement" value={filters.mode} onChange={(e) => set('mode', e.target.value as '' | Mode)}>
            <option value="">Any arrangement</option><option>Remote</option><option>Hybrid</option><option>On-site</option>
          </select>
          <select className="i" aria-label="Type" value={filters.type} onChange={(e) => set('type', e.target.value as '' | JobType)}>
            <option value="">Any type</option><option>Full-time</option><option>Part-time</option><option>Internship</option>
          </select>
          <select className="i" aria-label="Job level" value={filters.level} onChange={(e) => set('level', e.target.value as '' | Level)}>
            <option value="">All levels</option><option>Entry-level</option><option>Mid</option><option>Senior</option>
          </select>
          <select className="i" aria-label="Time posted" value={filters.timePosted} onChange={(e) => set('timePosted', e.target.value as any)}>
            <option value="anyTime">Any time</option><option value="past24Hours">Past 24 hours</option><option value="pastWeek">Past week</option><option value="pastMonth">Past month</option>
          </select>
          <select className="i" aria-label="Minimum score" value={filters.min} onChange={(e) => set('min', Number(e.target.value))}>
            <option value={0}>Any score</option><option value={45}>45+ Potential</option><option value={70}>70+ Strong Fit</option>
          </select>
          <select className="i" aria-label="Sort" value={filters.sort} onChange={(e) => set('sort', e.target.value as JobFilters['sort'])}>
            <option value="score">Best fit</option><option value="recent">Most recent</option>
          </select>
        </div>

        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--line)', paddingTop: 10 }}>
          <div className="row" style={{ gap: 10, alignItems: 'center' }}>
            <button
              className="btn"
              disabled={aiLoading}
              onClick={fetchAndRankJobs}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}
            >
              {aiLoading && (
                <svg className="spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" />
                </svg>
              )}
              {fetchPhase === 'fetching'
                ? '1/2 Fetching live jobs...'
                : fetchPhase === 'ranking'
                ? '2/2 Ranking fit with Gemini AI...'
                : 'Fetch & Rank Jobs based on Preferences'}
            </button>
            <button
              className="btn o xs"
              disabled={aiLoading}
              onClick={() => runGeminiFilter()}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}
            >
              {aiLoading && fetchPhase === 'ranking' && (
                <svg className="spin" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10" strokeOpacity="0.25" />
                  <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" />
                </svg>
              )}
              {aiLoading && fetchPhase === 'ranking' ? 'Re-ranking...' : 'Re-rank Current Catalog'}
            </button>
          </div>
          {statusMsg && (
            <span
              className="meta"
              style={{
                fontSize: '0.86rem',
                color: aiLoading ? '#0369a1' : 'var(--blue)',
                fontWeight: aiLoading ? 600 : 500,
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                background: aiLoading ? '#e0f2fe' : 'transparent',
                padding: aiLoading ? '5px 12px' : '0',
                borderRadius: 16,
                border: aiLoading ? '1px solid #bae6fd' : 'none',
              }}
            >
              {aiLoading && (
                <span
                  style={{
                    display: 'inline-block',
                    width: 7,
                    height: 7,
                    borderRadius: '50%',
                    background: '#0284c7',
                  }}
                />
              )}
              {statusMsg}
            </span>
          )}
        </div>
      </div>
      <div className={`mp${id ? ' sel' : ''}`}>
        <div className="lst card">
          {hidden > 0 && <p className="meta" style={{ padding: '10px 14px' }}>{hidden} hidden by your required preferences. <a href="/prefs" onClick={(e) => { e.preventDefault(); navigate('/prefs'); }}>Review</a></p>}
          {items.length ? items.map((x) => <JobListItem key={x.job.id} item={x} selected={x.job.id === selectedId} />) : (
            <div className="empty" style={{ margin: 14 }}>No jobs match. Lower the minimum score or clear filters. Nothing was changed for you.</div>
          )}
        </div>
        <div className="dt">
          {selected ? <JobDetail item={selected} /> : <div className="card empty">Select a job to see why it fits.</div>}
        </div>
      </div>
    </>
  );
}
