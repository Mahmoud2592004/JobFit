import { useState } from 'react';
import { Link, Navigate, useParams } from 'react-router-dom';
import { STAGES, jobById } from '../data/jobs';
import { useApp } from '../store/AppContext';
import type { Application, Stage } from '../types';

export default function ApplicationDetail() {
  const { id } = useParams();
  const { state } = useApp();
  const app = state.applications.find((a) => a.id === Number(id));
  if (!app) return <Navigate to="/track" replace />;
  return <Form key={app.id} app={app} />;
}

function Form({ app }: { app: Application }) {
  const { state, actions } = useApp();
  const job = jobById(app.jobId)!;
  const resumes = state.resumes.filter((r) => r.jobId === app.jobId);
  const [stage, setStage] = useState<Stage>(app.stage);
  const [date, setDate] = useState(app.appliedDate);
  const [milestone, setMilestone] = useState(app.milestone);
  const [salary, setSalary] = useState(app.salary);
  const [resumeId, setResumeId] = useState<number | null>(app.resumeId);
  const [notes, setNotes] = useState(app.notes);
  const [saved, setSaved] = useState(false);

  const save = () => {
    actions.updateApplication(app.id, { stage, appliedDate: date, milestone, salary, resumeId, notes });
    setSaved(true);
  };

  return (
    <>
      <Link className="bk" style={{ display: 'block' }} to="/track">&larr; Board</Link>
      <div className="g3" style={{ gridTemplateColumns: 'minmax(0,1fr) 300px' }}>
        <div className="card stack">
          <h2 style={{ fontSize: '1.4rem' }}>{job.title}</h2>
          <p className="meta">{job.company} · fit at save: {app.score} · <a target="_blank" rel="noopener noreferrer" href={`https://example.com/jobs/${job.id}`}>Original listing</a></p>
          <label>Stage<select className="i" value={stage} onChange={(e) => setStage(e.target.value as Stage)}>{STAGES.map((s) => <option key={s}>{s}</option>)}</select></label>
          <label>Date applied<input className="i" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></label>
          <label>Next milestone<input className="i" value={milestone} onChange={(e) => setMilestone(e.target.value)} /></label>
          <label>Salary offered (if any)<input className="i" value={salary} onChange={(e) => setSalary(e.target.value)} /></label>
          <label>Resume used
            <select className="i" value={resumeId ?? ''} onChange={(e) => setResumeId(e.target.value ? Number(e.target.value) : null)}>
              <option value="">None attached</option>
              {resumes.map((r) => <option key={r.id} value={r.id}>{r.name} ({r.date})</option>)}
            </select>
          </label>
          <label>Notes<textarea className="i" value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          <button className="btn" onClick={save}>Save changes</button>
          <div className="msg" role="status">{saved ? 'Saved.' : ''}</div>
        </div>
        <div className="card">
          <h3>History</h3>
          <ul className="tl">{app.history.map((h, i) => <li key={i}>{h}</li>)}</ul>
          <p className="meta" style={{ marginTop: 12 }}>Stages change only when you change them.</p>
        </div>
      </div>
    </>
  );
}
