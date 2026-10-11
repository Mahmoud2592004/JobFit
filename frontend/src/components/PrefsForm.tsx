import { LEVELS } from '../data/jobs';
import type { JobType, Level, Mode, Prefs } from '../types';

interface Props {
  value: Prefs;
  onChange: (next: Prefs) => void;
}

export function PrefsForm({ value, onChange }: Props) {
  const set = <K extends keyof Prefs>(key: K, v: Prefs[K]) => onChange({ ...value, [key]: v });
  return (
    <div className="stack">
      <label>Target roles<input className="i" value={value.titles} onChange={(e) => set('titles', e.target.value)} /></label>
      <label>Locations<input className="i" value={value.location} onChange={(e) => set('location', e.target.value)} /></label>
      <div className="row">
        <label style={{ flex: 1 }}>Work arrangement
          <select className="i" value={value.mode} onChange={(e) => set('mode', e.target.value as Mode | 'Any')}>
            {['Any', 'Remote', 'Hybrid', 'On-site'].map((o) => <option key={o}>{o}</option>)}
          </select>
        </label>
        <label style={{ flex: 1 }}>Employment type
          <select className="i" value={value.type} onChange={(e) => set('type', e.target.value as JobType | 'Any')}>
            {['Any', 'Full-time', 'Part-time', 'Internship'].map((o) => <option key={o}>{o}</option>)}
          </select>
        </label>
        <label style={{ flex: 1 }}>Level
          <select className="i" value={value.level} onChange={(e) => set('level', e.target.value as Level)}>
            {LEVELS.map((o) => <option key={o}>{o}</option>)}
          </select>
        </label>
      </div>
      <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <input type="checkbox" checked={value.requireMode} onChange={(e) => set('requireMode', e.target.checked)} />
        Work arrangement is a requirement, not just a preference
      </label>
      <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <input type="checkbox" checked={value.requireLocation} onChange={(e) => set('requireLocation', e.target.checked)} />
        Location is a requirement (remote jobs still shown)
      </label>
    </div>
  );
}
