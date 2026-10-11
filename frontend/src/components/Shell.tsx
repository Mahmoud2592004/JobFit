import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { Link, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { filterJobs } from '../lib/match';
import { useApp } from '../store/AppContext';
import { Avatar } from './Avatar';
import { Icon, type IconName } from './Icon';
import { Logo } from './Logo';

const NAV: { to: string; label: string; icon: IconName }[] = [
  { to: '/dash', label: 'Home', icon: 'dash' },
  { to: '/jobs', label: 'Jobs', icon: 'jobs' },
  { to: '/res', label: 'Resumes', icon: 'res' },
  { to: '/track', label: 'Tracker', icon: 'track' },
];

export function Shell({ children }: { children: ReactNode }) {
  const { state, actions } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const [menu, setMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const [query, setQuery] = useState('');

  useEffect(() => setMenu(false), [location.pathname]);
  useEffect(() => {
    if (!menu) return;
    const close = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenu(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, [menu]);

  const strongCount = filterJobs(state, { q: '', mode: '', type: '', min: 0, sort: 'score' }).items.filter((x) => x.match.score >= 70).length;
  const badge = state.alertsSeen ? 0 : strongCount;

  const onSearch = (e: FormEvent) => {
    e.preventDefault();
    navigate(`/jobs?q=${encodeURIComponent(query)}`);
  };
  const openAlerts = () => {
    actions.markAlertsSeen();
    navigate('/jobs');
  };
  const user = state.user!;

  return (
    <>
      <header className="tb">
        <Logo to="/dash" />
        <form onSubmit={onSearch} style={{ display: 'contents' }} role="search">
          <input className="i sr" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search jobs, companies or skills" aria-label="Search jobs" />
        </form>
        <nav className="nv">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={({ isActive }) => `nl hl${isActive ? ' on' : ''}`}>
              <Icon name={n.icon} />
              <span>{n.label}</span>
            </NavLink>
          ))}
          <button type="button" className="nl" style={{ position: 'relative', border: 0, background: 'none' }} onClick={openAlerts} aria-label="Alerts">
            <Icon name="bell" />
            {badge > 0 && <em className="bd">{badge}</em>}
            <span>Alerts</span>
          </button>
          <div className="dd" ref={menuRef}>
            <button type="button" className="nl" style={{ border: 0, background: 'none' }} onClick={() => setMenu((m) => !m)} aria-expanded={menu} aria-haspopup="menu">
              <Avatar name={user.name} size={26} />
              <span>Me &#9662;</span>
            </button>
            {menu && (
              <div className="dm" role="menu">
                <Link to="/prof">Profile</Link>
                <Link to="/prefs">Preferences</Link>
                <Link to="/set">Settings and privacy</Link>
                <Link to="/help">Help</Link>
                <Link
                  to="/login"
                  onClick={() => actions.logout()}
                >
                  Log out
                </Link>
              </div>
            )}
          </div>
        </nav>
      </header>
      <main className="pg">{children}</main>
      <nav className="bn" aria-label="Primary">
        {[...NAV, { to: '/prof', label: 'Me', icon: 'prof' as IconName }].map((n) => (
          <NavLink key={n.to} to={n.to} className={({ isActive }) => `nl${isActive ? ' on' : ''}`}>
            <Icon name={n.icon} />
            <span style={{ display: 'block' }}>{n.label}</span>
          </NavLink>
        ))}
      </nav>
    </>
  );
}
