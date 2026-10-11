import { Link } from 'react-router-dom';
import { Avatar } from '../components/Avatar';
import { JobCard } from '../components/Job';
import { SECTIONS, jobById } from '../data/jobs';
import { filterJobs } from '../lib/match';
import { useApp } from '../store/AppContext';

export default function Dashboard() {
  const { state, actions } = useApp();
  const profile = state.profile!;
  const items = filterJobs(state, { q: '', mode: '', type: '', min: 0, sort: 'score' }).items;
  const strong = items.filter((x) => x.match.score >= 70).length;
  const missing = SECTIONS.flatMap((s) => {
    const n = s.label.split(' (')[0]!;
    return !profile[s.key] ? [`${n} is empty`] : !profile.confirmed[s.key] ? [`${n} needs confirmation`] : [];
  });
  const pct = Math.round(((SECTIONS.length - missing.length) / SECTIONS.length) * 100);
  const inProgress = state.applications.filter((a) => ['Applied', 'Screening', 'Technical', 'Final Interview', 'Offer'].includes(a.stage));

  return (
    <div className="g3">
      <aside className="stack">
        <div className="card pc">
          <div className="cv" />
          <Avatar name={profile.name} size={64} />
          <h3>{profile.name}</h3>
          <p className="meta">{state.prefs.titles.split(',')[0]}</p>
          <div className="bar"><i style={{ width: `${pct}%` }} /></div>
          <p className="meta">Profile {pct}% complete</p>
          {missing.length > 0 && <Link to="/prof" className="btn o xs" style={{ marginTop: 8 }}>Finish profile</Link>}
        </div>
        <div className="card">
          <Link className="ql" to="/track">Applications <b>{state.applications.length}</b></Link>
          <Link className="ql" to="/res">Tailored resumes <b>{state.resumes.length}</b></Link>
          <Link className="ql" to="/jobs">Saved jobs <b>{Object.keys(state.saved).length}</b></Link>
        </div>
      </aside>

      <section className="stack">
        {strong > 0 && !state.alertsSeen && (
          <div className="card ban">
            <b>{strong} strong-fit job{strong > 1 ? 's' : ''}</b> match your profile.{' '}
            <Link to="/jobs" onClick={actions.markAlertsSeen}>View matches</Link>
          </div>
        )}
        <div className="card">
          <h3>Top picks for you</h3>
          <p className="meta">Ranked by fit with your confirmed profile.</p>
        </div>
        {items.slice(0, 4).map((x) => <JobCard key={x.job.id} item={x} />)}
        {items.length === 0 && <div className="empty">No matches yet. Adjust your <Link to="/prefs">preferences</Link>.</div>}
      </section>

      <aside className="stack">
        <div className="card">
          <h3>In progress</h3>
          {inProgress.length ? (
            <ul className="tl">
              {inProgress.map((a) => {
                const j = jobById(a.jobId)!;
                return <li key={a.id}><Link to={`/track/${a.id}`}>{j.title}, {j.company}</Link> · {a.stage}{a.milestone ? ` · ${a.milestone}` : ''}</li>;
              })}
            </ul>
          ) : (
            <p className="meta" style={{ marginTop: 6 }}>Nothing yet. Save a job and move it along your board.</p>
          )}
        </div>
        <div className="card">
          <h3>Recent resumes</h3>
          {state.resumes.length ? (
            <ul className="tl">
              {state.resumes.slice(-3).map((r) => <li key={r.id}><Link to={`/tailor/${r.jobId}/${r.id}`}>{r.name}</Link></li>)}
            </ul>
          ) : (
            <p className="meta" style={{ marginTop: 6 }}>Open a job and choose Tailor resume.</p>
          )}
        </div>
        {missing.length > 0 && (
          <div className="card">
            <h3>Improve your matches</h3>
            <ul className="tl">{missing.slice(0, 3).map((m) => <li key={m}>{m}</li>)}</ul>
          </div>
        )}
      </aside>
    </div>
  );
}
