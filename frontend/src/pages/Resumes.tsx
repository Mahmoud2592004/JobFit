import { Link } from 'react-router-dom';
import { jobById } from '../data/jobs';
import { useApp } from '../store/AppContext';

export default function Resumes() {
  const { state, actions } = useApp();
  return (
    <div className="card">
      <h2 style={{ fontSize: '1.4rem', marginBottom: 12 }}>Resume library</h2>
      <table>
        <thead>
          <tr><th>Resume</th><th>Company</th><th>Created</th><th>State</th><th /></tr>
        </thead>
        <tbody>
          <tr>
            <td>Original (from your profile)</td><td>All</td><td>{state.profile?.created}</td>
            <td><span className="badge">Source</span></td>
            <td><Link to="/prof">Open</Link></td>
          </tr>
          {state.resumes.map((r) => {
            const j = jobById(r.jobId)!;
            return (
              <tr key={r.id}>
                <td>{j.title}{r.coverLetter ? ' + letter' : ''}</td>
                <td>{j.company}</td>
                <td>{r.date}</td>
                <td><span className="badge s">{r.state}</span></td>
                <td>
                  <Link to={`/tailor/${r.jobId}/${r.id}`}>Open</Link> ·{' '}
                  <button type="button" onClick={() => actions.deleteResume(r.id)} style={{ border: 0, background: 'none', color: 'var(--blue)', cursor: 'pointer', font: 'inherit', padding: 0 }}>Delete</button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {state.resumes.length === 0 && <div className="empty" style={{ marginTop: 14 }}>No tailored resumes yet. Open a job and choose Tailor resume.</div>}
    </div>
  );
}
