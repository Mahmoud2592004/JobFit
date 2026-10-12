import { useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { useApp } from '../store/AppContext';
import { api, sessionManager } from '../api';
import { formatBackendProfileToState } from '../lib/resumeParser';

export default function Auth({ mode }: { mode: 'login' | 'signup' }) {
  const signup = mode === 'signup';
  const { state, actions } = useApp();
  const navigate = useNavigate();
  const location = useLocation();
  const navState = location.state as { email?: string; msg?: string } | null;
  const prefill = navState?.email ?? '';
  const [name, setName] = useState('');
  const [email, setEmail] = useState(prefill);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [msg, setMsg] = useState<{ text: string; error: boolean } | null>(
    navState?.msg ? { text: navState.msg, error: true } : null,
  );

  if (state.user && sessionManager.getToken()) {
    return (
      <div className="au">
        <Logo />
        <div className="card">
          <h3>Already signed in</h3>
          <p className="meta" style={{ margin: '8px 0 16px' }}>
            You are currently signed in as <strong>{state.user.email}</strong>.
          </p>
          <div className="row" style={{ gap: 10, flexWrap: 'wrap' }}>
            <Link className="btn" to={state.profile ? '/dash' : '/onb'}>
              Continue to {state.profile ? 'Dashboard' : 'Resume upload'}
            </Link>
            <button
              type="button"
              className="btn o"
              onClick={() => {
                actions.logout();
                sessionManager.clear();
              }}
            >
              Sign out / Use another account
            </button>
          </div>
        </div>
      </div>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const em = email.trim();
    if (signup && !name.trim()) return setMsg({ text: 'Enter your name.', error: true });
    if (!/^\S+@\S+\.\S+$/.test(em)) return setMsg({ text: 'Enter a valid email address.', error: true });
    if (password.length < 6) return setMsg({ text: 'Use a password with at least 6 characters.', error: true });

    setLoading(true);
    setMsg(null);

    try {
      const res = signup
        ? await api.auth.signup(em, password, name.trim())
        : await api.auth.login(em, password);

      if (res.error) {
        setMsg({ text: res.error, error: true });
        setLoading(false);
        return;
      }

      const userName = res.data?.name || (signup ? name.trim() : em.split('@')[0]!);
      actions.login({ name: userName, email: em });

      // Check if user has an existing confirmed profile in backend
      let hasConfirmedProfile = false;
      try {
        const profRes = await api.profile.getProfile();
        if (profRes.data && (profRes.data.profile || profRes.data.active_version)) {
          const formatted = formatBackendProfileToState(profRes.data, userName, em);
          if (formatted.summary || formatted.skills || formatted.experience) {
            hasConfirmedProfile = true;
            actions.saveProfile({
              name: formatted.name || userName,
              email: formatted.email || em,
              phone: formatted.phone || '',
              location: formatted.location || '',
              link: formatted.link || '',
              summary: formatted.summary || '',
              skills: formatted.skills || '',
              experience: formatted.experience || '',
              leadership: formatted.leadership || '',
              education: formatted.education || '',
              projects: formatted.projects || '',
              certs: formatted.certs || '',
              github: formatted.github || '',
              other_links: formatted.other_links || [],
              confirmed: {
                summary: true,
                skills: true,
                experience: true,
                leadership: !!formatted.leadership,
                education: true,
                projects: true,
                certs: true,
              },
              created: new Date().toLocaleDateString(),
            });
          }
        }
      } catch {
        /* no profile in backend */
      }

      if (!hasConfirmedProfile) {
        actions.saveProfile(null);
      }

      navigate(hasConfirmedProfile ? '/dash' : '/onb');
    } catch (err: any) {
      setMsg({ text: err.message || 'Authentication failed. Please check your credentials.', error: true });
    } finally {
      setLoading(false);
    }
  };

  const forgot = () =>
    setMsg(
      /^\S+@\S+\.\S+$/.test(email.trim())
        ? { text: `If an account exists for ${email.trim()}, a reset link has been sent.`, error: false }
        : { text: 'Enter your email above first.', error: true },
    );

  return (
    <div className="au">
      <Logo />
      <form className="card stack" onSubmit={submit} noValidate autoComplete="off">
        <h1 style={{ fontSize: '1.8rem' }}>{signup ? 'Join JobFit, free' : 'Welcome back'}</h1>
        {signup && <label>Name<input className="i" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" /></label>}
        <label>Email<input className="i" type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="off" autoCapitalize="none" spellCheck="false" /></label>
        <label>Password<input className="i" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="new-password" /></label>
        <button className="btn" type="submit" disabled={loading}>{loading ? 'Please wait...' : signup ? 'Agree and join' : 'Log in'}</button>
        <div className={`msg${msg?.error ? ' e' : ''}`} role="status">{msg?.text}</div>
      </form>
      <p className="meta" style={{ textAlign: 'center' }}>
        {signup ? (
          <>Already on JobFit? <Link to="/login">Log in</Link></>
        ) : (
          <><button type="button" onClick={forgot} style={{ border: 0, background: 'none', color: 'var(--blue)', cursor: 'pointer', font: 'inherit', padding: 0 }}>Forgot password?</button> · New here? <Link to="/signup">Join now</Link></>
        )}
      </p>
    </div>
  );
}
