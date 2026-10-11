import { Link } from 'react-router-dom';
import { useApp } from '../store/AppContext';
import { fitOf, whyText, type ScoredJob } from '../lib/match';

export function JobListItem({ item, selected }: { item: ScoredJob; selected: boolean }) {
  const { job, match } = item;
  const f = fitOf(match.score);
  return (
    <Link className={`ji${selected ? ' on' : ''}`} to={`/jobs/${job.id}`}>
      <div>
        <h3>{job.title}</h3>
        <div className="meta">{job.company} · {job.location} · {job.mode}</div>
        <div className="meta">{job.type} · {job.level} · {job.daysAgo}d ago</div>
      </div>
      <div className="fs">
        <span className={`sc ${f.tone}`}>{match.score}</span>
        <span className={`badge ${f.tone}`}>{f.label}</span>
      </div>
    </Link>
  );
}

export function JobCard({ item }: { item: ScoredJob }) {
  const { job, match } = item;
  const f = fitOf(match.score);
  return (
    <div className="card">
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'start' }}>
        <div>
          <h3><Link to={`/jobs/${job.id}`} style={{ textDecoration: 'none' }}>{job.title}</Link></h3>
          <p className="meta">{job.company} · {job.location} · {job.mode}</p>
        </div>
        <span className={`sc ${f.tone}`}>{match.score}</span>
      </div>
      <p style={{ margin: '8px 0', fontSize: '.93rem' }}>{whyText(job, match)}</p>
      <div className="row">
        <span className={`badge ${f.tone}`}>{f.label}</span>
        <Link className="btn xs" to={`/tailor/${job.id}`}>Tailor resume</Link>
        <Link className="btn o xs" to={`/jobs/${job.id}`}>Why this fit</Link>
      </div>
    </div>
  );
}

export function buildLinkedInSearchUrl(job: ScoredJob['job']): string {
  if (job.source_url) {
    return job.source_url;
  }

  const params = new URLSearchParams();

  // If company is one of the mock catalog names, omit it so LinkedIn finds real open listings for this job title.
  // If it's a real company (like Fawry), include it.
  const isMockCompany = /^(?:Nilecore|Lexica|Orbit|Delta|Sahara|Pyramid|Nile Retail)/i.test(job.company);
  const cleanCompany = isMockCompany ? '' : job.company.replace(/\s+(?:Works|AI|Labs|Cloud)$/i, '').trim();

  const queryTerms = [job.title, cleanCompany].filter(Boolean).join(' ');
  params.set('keywords', queryTerms);

  // Set location filter on LinkedIn so it doesn't default to the user's personal profile country
  if (job.mode === 'Remote' || (job.location && job.location.toLowerCase() === 'remote')) {
    params.set('f_WT', '2'); // LinkedIn remote filter
  } else if (job.location) {
    const loc = job.location.toLowerCase().includes('egypt')
      ? job.location
      : `${job.location}, Egypt`;
    params.set('location', loc);
  }

  return `https://www.linkedin.com/jobs/search/?${params.toString()}`;
}

export function JobDetail({ item }: { item: ScoredJob }) {
  const { state, actions } = useApp();
  const { job, match: m } = item;
  const f = fitOf(m.score);
  const dims: [string, number][] = [
    ['Technical skill overlap', m.skillScore],
    ['Seniority and role', m.seniority],
    ['Work arrangement', m.arrangement],
  ];
  return (
    <div className="card">
      <Link className="bk" to="/jobs">&larr; All jobs</Link>
      <h2>{job.title}</h2>
      <p className="meta">
        {job.company} · {job.location} · {job.mode} · {job.type} · {job.level}.
        {job.source_url && !job.source_url.includes('/jobs/search')
          ? ' Direct listing link verified.'
          : ' Sample catalog listing (searches LinkedIn).'}
      </p>
      <div className="row" style={{ margin: '14px 0' }}>
        <Link className="btn" to={`/tailor/${job.id}`}>Tailor resume</Link>
        <button className="btn o" onClick={() => actions.saveJob(job.id)}>{state.saved[job.id] ? 'Saved ✓' : 'Save'}</button>
        <a
          className="btn g"
          target="_blank"
          rel="noopener noreferrer"
          href={buildLinkedInSearchUrl(job)}
          title={job.source_url && !job.source_url.includes('/jobs/search') ? 'Open exact direct job post' : 'Search matching open positions on LinkedIn'}
        >
          {job.source_url && !job.source_url.includes('/jobs/search')
            ? (job.source_url.includes('linkedin.com') ? 'Apply on LinkedIn (Direct Post)' : 'Apply Directly')
            : 'Search on LinkedIn'}
        </a>
        <button className="btn g" onClick={() => actions.dismissJob(job.id)}>Not interested</button>
      </div>
      <div className={`fitbox ${f.tone}`}>
        <div className={`sc ${f.tone} big`}>{m.score}</div>
        <div>
          <b>{f.label}</b>
          <p>{m.recruiterRationale || whyText(job, m)}</p>
          <p className="meta">{m.recruiterRationale ? 'Evaluated by Gemini AI based on verified experience.' : 'A decision aid, not a hiring probability.'}</p>
        </div>
      </div>
      <h3 style={{ margin: '18px 0 6px' }}>How the score is built</h3>
      {dims.map(([label, value]) => (
        <div className="dim" key={label}>
          <span>{label}</span>
          <div className="bar"><i style={{ width: `${value}%` }} /></div>
          <b>{value}%</b>
        </div>
      ))}
      <div className="dim" style={{ gridTemplateColumns: '170px 1fr' }}>
        <span>Years of experience</span>
        <span className="meta">Not in your profile yet. <Link to="/prof">Add it</Link> for a better read.</span>
      </div>
      <ul className="pts">
        <li><b>Strong matches</b>{m.strong.join(', ') || 'None confirmed yet'}</li>
        <li className="p"><b>Partial matches</b>{m.partial.length ? `${m.partial.join(', ')} appear in your experience text but not your skills list.` : 'None'}</li>
        <li className="g"><b>Possible gaps</b>{m.gaps.length ? `${m.gaps.join(', ')}. Missing from your profile, which is not proof you lack them. Add them if true.` : 'None'}</li>
        <li className="e"><b>Eligibility to verify</b>{job.eligibility}</li>
      </ul>
    </div>
  );
}
