import { useEffect, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { JobDetail, JobListItem } from '../components/Job';
import { filterJobs } from '../lib/match';
import { useMediaQuery } from '../lib/hooks';
import { useApp } from '../store/AppContext';
import { api } from '../api';
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
  const [liveJobs, setLiveJobs] = useState<Job[] | null>(null);
  const [aiRationaleMap, setAiRationaleMap] = useState<Record<string, { rationale: string; score: number; fit: string }>>({});
  const [statusMsg, setStatusMsg] = useState('');

  const urlQuery = params.get('q');
  useEffect(() => {
    if (urlQuery !== null) setFilters((f) => ({ ...f, q: urlQuery }));
  }, [urlQuery]);

  // Merge live jobs if evaluated
  const effectiveState = liveJobs
    ? {
        ...state,
        // Override or supplement local JOBS if live jobs were returned
      }
    : state;

  const { items: baseItems, hidden } = filterJobs(effectiveState, filters);

  // Apply AI scores if available
  const items = baseItems.map((item) => {
    const aiData = aiRationaleMap[String(item.job.id)];
    if (aiData) {
      return {
        ...item,
        match: {
          ...item.match,
          score: aiData.score,
          recruiterRationale: aiData.rationale,
        },
      };
    }
    return item;
  });

  const selectedId = id ? Number(id) : desktop ? items[0]?.job.id : undefined;
  const selected = items.find((x) => x.job.id === selectedId);
  const set = <K extends keyof JobFilters>(k: K, v: JobFilters[K]) => setFilters((f) => ({ ...f, [k]: v }));

  const runGeminiFilter = async () => {
    setAiLoading(true);
    setStatusMsg('Evaluating catalog jobs with Gemini AI grounded in verified experience...');
    try {
      const res = await api.jobs.aiFilter(filters.q || undefined, 'valid_only', 20, {
        work_arrangement: filters.mode || undefined,
        employment_type: filters.type || undefined,
        experience_level: filters.level || undefined,
        date_posted: filters.timePosted || undefined,
      });
      if (res.data && res.data.results.length > 0) {
        const rationaleMap: Record<string, { rationale: string; score: number; fit: string }> = {};
        res.data.results.forEach((r) => {
          rationaleMap[String(r.job.id)] = {
            rationale: r.evaluation.recruiter_rationale,
            score: r.evaluation.ai_score,
            fit: r.evaluation.fit_level,
          };
        });
        setAiRationaleMap(rationaleMap);
        setStatusMsg(`Gemini AI evaluated ${res.data.total_evaluated} listings (${res.data.valid_count} valid matches).`);
      } else {
        setStatusMsg('AI filter completed with standard catalog listings.');
      }
    } catch {
      setStatusMsg('AI service offline: using local verified fit evaluation.');
    } finally {
      setAiLoading(false);
    }
  };

  const fetchLiveLinkedIn = async () => {
    setAiLoading(true);
    setStatusMsg('Fetching live LinkedIn jobs via Apify...');
    try {
      const res = await api.jobs.triggerDiscovery(filters.q || 'Software Engineer', undefined, filters.timePosted);
      if (res.data) {
        setStatusMsg(`Discovered ${res.data.jobs_count || 0} real LinkedIn listings.`);
      } else {
        setStatusMsg('Finished checking LinkedIn.');
      }
    } catch {
      setStatusMsg('Could not reach scraper: showing catalog listings.');
    } finally {
      setAiLoading(false);
    }
  };

  // A dismissed job disappears from the list: go back to the list instead of showing a stale detail pane.
  useEffect(() => {
    if (id && !items.some((x) => x.job.id === Number(id)) && desktop) navigate('/jobs', { replace: true });
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
          <div className="row" style={{ gap: 8 }}>
            <button className="btn xs" disabled={aiLoading} onClick={runGeminiFilter}>
              {aiLoading ? 'Evaluating with Gemini...' : 'Rank with Gemini AI'}
            </button>
            <button className="btn o xs" disabled={aiLoading} onClick={fetchLiveLinkedIn}>
              Fetch LinkedIn Jobs
            </button>
          </div>
          {statusMsg && <span className="meta" style={{ fontSize: '0.85rem', color: 'var(--blue)' }}>{statusMsg}</span>}
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
