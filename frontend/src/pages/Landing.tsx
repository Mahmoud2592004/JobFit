import { lazy, Suspense, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { useReveal } from '../lib/hooks';

// three.js is only needed on the landing page, so it is split into its own chunk.
const ProcessSection = lazy(() => import('../components/ProcessSection').then((m) => ({ default: m.ProcessSection })));

const FEATURES = [
  { icon: '%', title: 'Fit analysis', text: 'Strong Fit, Potential Fit or Not a Fit, with a short recruiter-style rationale for each job.' },
  { icon: '✓', title: 'Truth check', text: 'Live verification of skills against your profile while you edit. Approval is blocked until flags are cleared.' },
  { icon: '✎', title: 'Edit on the page', text: 'Click into a clean, ATS-friendly resume and change it. Changes save automatically.' },
  { icon: 'T', title: 'Resume templates', text: 'Navy, classic black or tech minimal. Download a PDF, or copy the LaTeX source for Overleaf.' },
  { icon: '@', title: 'Cover letters', text: 'A matching one-page letter written only from your real experience.' },
  { icon: '▦', title: 'Application board', text: 'Drag jobs from Saved to Applied, Screening, Technical, Final Interview, Offer. Each card keeps its resume.' },
];

const FAQ = [
  ['Is JobFit free?', 'Yes. Profile, job matching, tailored resumes and tracking are free to use.'],
  ['Will it make things up on my resume?', 'No. It only uses facts in your profile, and a truth check flags any skill that is not there.'],
  ['What does the fit score mean?', 'It helps you prioritize. It combines skills, seniority and work arrangement, and is not a hiring probability.'],
  ['Does JobFit apply for me?', "No. You apply on the employer's page, then move the card on your board yourself."],
  ['Where do the jobs come from?', 'Listings link back to their original source. Anything possibly outdated is labeled.'],
];

const Dim = ({ label, value }: { label: string; value: number }) => (
  <div className="dim">
    <span>{label}</span>
    <div className="bar"><i style={{ width: `${value}%` }} /></div>
    <b>{value}%</b>
  </div>
);

export default function Landing() {
  useReveal();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');

  return (
    <div id="site">
      <header className="ln">
        <div className="w">
          <Logo />
          <nav>
            <a href="#process">How it works</a>
            <a href="#features">Features</a>
            <a href="#faq">FAQ</a>
            <Link to="/login">Log in</Link>
            <Link className="btn" to="/signup">Join free</Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="w">
            <div>
              <h1>Find jobs that fit. Apply with a resume that <em>tells the truth.</em></h1>
              <p className="lead">JobFit finds relevant roles, explains how well you match, and tailors your resume for each one. Every claim is checked against your own profile before you can approve it.</p>
              <div className="row">
                <Link className="btn lg" to="/signup">Join JobFit, free</Link>
                <a className="btn o lg" href="#process">See how it works</a>
              </div>
              <p className="meta" style={{ marginTop: 14 }}>Free to use. You approve every change. Delete your data any time.</p>
            </div>
            <div className="card stack" style={{ padding: 22, boxShadow: '0 10px 34px rgba(22,58,95,.12)' }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'start' }}>
                <div>
                  <h3 style={{ fontSize: '1.2rem' }}>Machine Learning Engineer</h3>
                  <p className="meta">Nilecore AI · Cairo · Hybrid · 2 days ago</p>
                </div>
                <span className="badge s">Strong Fit</span>
              </div>
              <div className="fitbox">
                <div className="sc big">86</div>
                <div>
                  <b>Strong on Python, NLP, fine-tuning.</b>
                  <p className="meta">Gap: AWS certification. Hybrid matches your preference.</p>
                </div>
              </div>
              <div>
                <Dim label="Technical skill overlap" value={90} />
                <Dim label="Seniority and role" value={80} />
                <Dim label="Work arrangement" value={100} />
              </div>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="badge s">Truth check: 12 of 12 skills verified</span>
                <span className="btn xs">Tailor resume</span>
              </div>
            </div>
          </div>
        </section>

        <section className="sec" style={{ paddingTop: 20 }}>
          <div className="w trio">
            {[
              ['1', 'Every score has reasons', 'See strong matches, partial matches, gaps and eligibility checks. Never a mystery number.'],
              ['2', 'Nothing gets invented', 'Skills and employers on your resume are cross-checked against your profile. Anything unsupported is flagged.'],
              ['3', 'You stay in control', 'Approve or reject each suggested change. Edit anything. Download only what you trust.'],
            ].map(([n, t, p]) => (
              <div className="card rv" key={n}>
                <div className="ico">{n}</div>
                <h3>{t}</h3>
                <p>{p}</p>
              </div>
            ))}
          </div>
        </section>

        <Suspense fallback={<section id="process" style={{ minHeight: '60vh' }} />}>
          <ProcessSection />
        </Suspense>

        <section className="sec" id="features">
          <div className="w">
            <div className="head rv">
              <h2>Everything for your search in one workspace</h2>
              <p>Built to feel familiar, and to save you clicks.</p>
            </div>
            <div className="trio">
              {FEATURES.map((f) => (
                <div className="card rv" key={f.title}>
                  <div className="ico">{f.icon}</div>
                  <h3>{f.title}</h3>
                  <p>{f.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="sec" style={{ background: '#fff', borderBlock: '1px solid var(--line)' }}>
          <div className="w split">
            <div className="rv">
              <h2>Review every suggestion before it touches your resume</h2>
              <p className="meta" style={{ marginTop: 14, fontSize: '1.05rem' }}>JobFit proposes changes. You decide. Approve the ones you like, keep your original for the rest.</p>
            </div>
            <div className="card diff rv">
              <div className="row" style={{ justifyContent: 'space-between' }}>
                <h3>Summary</h3>
                <span className="badge p">Suggested</span>
              </div>
              <s>Engineer with experience in machine learning and software projects.</s>
              <div className="add">ML engineer with hands-on NLP and model fine-tuning experience, building retrieval systems in Python.</div>
              <div className="row">
                <span className="btn xs">&#10003; Approve and apply</span>
                <span className="btn g xs">Keep original</span>
              </div>
              <span className="badge s" style={{ justifySelf: 'start' }}>Truth check passed: 0 flagged claims</span>
            </div>
          </div>
        </section>

        <section className="sec">
          <div className="w">
            <div className="head rv"><h2>Built for every stage of a search</h2></div>
            <div className="chips rv">
              {['Students and graduates', 'Early-career professionals', 'Experienced professionals', 'Career changers', 'Anyone applying to many jobs'].map((c) => <span key={c}>{c}</span>)}
            </div>
          </div>
        </section>

        <section className="sec" style={{ paddingTop: 0 }}>
          <div className="w split">
            <div className="rv"><h2>Your career data stays yours</h2></div>
            <div className="card rv stack">
              {[
                ['Private by default.', 'Only you can open your documents.'],
                ['Time-limited download links.', 'Files are never publicly listed.'],
                ['Delete any time.', 'Remove a document or your whole account.'],
                ['No false promises.', 'We help you apply better. We cannot guarantee interviews or offers.'],
              ].map(([b, t]) => (
                <div key={b}><b>{b}</b> <span className="meta">{t}</span></div>
              ))}
            </div>
          </div>
        </section>

        <section className="sec" id="faq" style={{ paddingTop: 0 }}>
          <div className="w" style={{ maxWidth: 820 }}>
            <div className="head rv"><h2>Questions</h2></div>
            <div className="card rv">
              {FAQ.map(([q, a]) => (
                <details className="q" key={q}>
                  <summary>{q}</summary>
                  <p>{a}</p>
                </details>
              ))}
            </div>
          </div>
        </section>

        <section className="band" id="start">
          <div className="w rv">
            <h2>Stop rewriting the same resume</h2>
            <p>Create a free account and see your first matches in minutes.</p>
            <div className="signup">
              <input className="i" type="email" placeholder="you@example.com" aria-label="Email address" value={email} onChange={(e) => setEmail(e.target.value)} />
              <button className="btn lg" type="button" onClick={() => navigate('/signup', { state: { email } })}>Join JobFit</button>
            </div>
          </div>
        </section>
      </main>

      <footer>
        <div className="w">
          <span>&copy; 2026 JobFit</span>
          <span><a href="#top">Privacy policy</a><a href="#top">Terms of service</a><a href="#top">Contact</a></span>
        </div>
      </footer>
    </div>
  );
}
