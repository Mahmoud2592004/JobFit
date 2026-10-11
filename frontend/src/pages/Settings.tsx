import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useApp } from '../store/AppContext';

export default function Settings() {
  const { state, actions } = useApp();
  const navigate = useNavigate();
  const [confirm, setConfirm] = useState('');
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(null);
  const user = state.user!;

  const deleteAccount = () => {
    if (confirm !== 'DELETE') return setMsg({ text: 'Type DELETE to confirm.', error: true });
    actions.deleteAccount();
    navigate('/signup');
  };

  return (
    <div className="stack" style={{ maxWidth: 720, margin: '0 auto' }}>
      <div className="card stack">
        <h2 style={{ fontSize: '1.4rem' }}>Account and privacy</h2>
        <p className="meta">{user.name} · {user.email}</p>
        <div className="row">
          <Link className="btn o xs" to="/prof">Manage profile</Link>
          <Link className="btn o xs" to="/prefs">Manage preferences</Link>
          <button className="btn g xs" onClick={() => { actions.logout(); navigate('/login'); }}>Log out</button>
        </div>
      </div>
      <div className="card stack">
        <h3>Your data</h3>
        <p className="meta">Your documents are only visible to you, and are used only to build your profile, matches and tailored versions.</p>
        <div><button className="btn g xs" onClick={() => { actions.deleteAllResumes(); setMsg({ text: 'All tailored resumes were deleted.', error: false }); }}>Delete all my resumes</button></div>
      </div>
      <div className="card stack" style={{ borderColor: 'var(--bad)' }}>
        <h3 style={{ color: 'var(--bad)' }}>Delete account</h3>
        <p className="meta">Permanently removes your profile, preferences, resumes and application history. This cannot be undone.</p>
        <label>Type DELETE to confirm<input className="i" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></label>
        <div><button className="btn d xs" onClick={deleteAccount}>Delete my account</button></div>
        <div className={`msg${msg?.error ? ' e' : ''}`} role="status">{msg?.text}</div>
      </div>
    </div>
  );
}
