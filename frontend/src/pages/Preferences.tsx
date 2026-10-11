import { useState } from 'react';
import { PrefsForm } from '../components/PrefsForm';
import { useApp } from '../store/AppContext';

export default function Preferences() {
  const { state, actions } = useApp();
  const [prefs, setPrefs] = useState(state.prefs);
  const [saved, setSaved] = useState(false);
  return (
    <div className="card" style={{ maxWidth: 720, margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.4rem' }}>Job-search preferences</h2>
      <p className="meta" style={{ margin: '4px 0 14px' }}>Required items hide jobs. Everything else only changes ranking.</p>
      <PrefsForm value={prefs} onChange={(p) => { setPrefs(p); setSaved(false); }} />
      <div className="row" style={{ marginTop: 16, alignItems: 'center' }}>
        <button className="btn" onClick={() => { actions.savePrefs(prefs); setSaved(true); }}>Save preferences</button>
        <span className="msg" role="status">{saved ? 'Saved.' : ''}</span>
      </div>
    </div>
  );
}
