import { useState } from 'react';
import { Link } from 'react-router-dom';
import { STAGES, jobById } from '../data/jobs';
import { fitOf } from '../lib/match';
import { useApp } from '../store/AppContext';
import type { Stage } from '../types';

export default function Tracker() {
  const { state, actions } = useApp();
  const [q, setQ] = useState('');
  const [over, setOver] = useState<Stage | null>(null);
  const needle = q.toLowerCase();

  return (
    <>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
        <div>
          <h2 style={{ fontSize: '1.4rem' }}>Application board</h2>
          <p className="meta">Drag cards or use the menu. Nothing moves to Applied until you do it.</p>
        </div>
        <input className="i" placeholder="Search board" aria-label="Search board" style={{ maxWidth: 240 }} value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {state.applications.length === 0 ? (
        <div className="empty">No applications yet. Save a job from <Link to="/jobs">Jobs</Link> to start your board.</div>
      ) : (
        <div className="kb">
          {STAGES.map((stage) => {
            const cards = state.applications.filter((a) => {
              const j = jobById(a.jobId)!;
              return a.stage === stage && `${j.title} ${j.company}`.toLowerCase().includes(needle);
            });
            return (
              <div
                key={stage}
                className="kc"
                style={over === stage ? { outline: '2px solid var(--blue)' } : undefined}
                onDragOver={(e) => { e.preventDefault(); setOver(stage); }}
                onDragLeave={() => setOver((o) => (o === stage ? null : o))}
                onDrop={(e) => {
                  e.preventDefault();
                  setOver(null);
                  const id = Number(e.dataTransfer.getData('text/plain'));
                  if (id) actions.moveApplication(id, stage);
                }}
              >
                <h3>{stage} <span className="badge">{cards.length}</span></h3>
                {cards.map((a) => {
                  const j = jobById(a.jobId)!;
                  const f = fitOf(a.score);
                  const r = state.resumes.find((x) => x.id === a.resumeId);
                  return (
                    <div className="kd" key={a.id} draggable onDragStart={(e) => e.dataTransfer.setData('text/plain', String(a.id))}>
                      <Link to={`/track/${a.id}`}><b>{j.title}</b></Link>
                      <div className="meta">{j.company}</div>
                      <div className="row" style={{ gap: 6, margin: '4px 0' }}>
                        <span className={`badge ${f.tone}`}>{a.score} {f.label}</span>
                        {r && <span className="badge">Resume</span>}
                        {r?.coverLetter && <span className="badge">Letter</span>}
                      </div>
                      <select className="i" aria-label="Move to stage" value={a.stage} onChange={(e) => actions.moveApplication(a.id, e.target.value as Stage)}>
                        {STAGES.map((s) => <option key={s}>{s}</option>)}
                      </select>
                    </div>
                  );
                })}
                {cards.length === 0 && <div className="empty" style={{ padding: 12, fontSize: '.85rem' }}>Drop here</div>}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
