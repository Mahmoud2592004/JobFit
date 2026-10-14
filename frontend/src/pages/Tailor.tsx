import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { EditableText } from '../components/Editable';
import { jobById } from '../data/jobs';
import { auditSkills, buildLetter, genProposal, matchJob, toLatex } from '../lib/match';
import {
  extractItemLinks,
  parseEducationToCards,
  parseExperienceToCards,
  parseLeadershipToCards,
  parseProjectsToCards,
  serializeCardsToExperience,
  serializeCardsToProjects,
} from '../lib/resumeParser';
import { useApp } from '../store/AppContext';
import { api } from '../api';
import type { Draft, Job, Profile, TailoredResume, TemplateId } from '../types';

type Tab = 'resume' | 'letter';
type Decision = 'a' | 'k';

const TEMPLATES: { id: TemplateId; label: string }[] = [
  { id: 'navy', label: 'Navy (ATS LaTeX)' },
  { id: 'black', label: 'Classic black' },
  { id: 'tech', label: 'Tech minimal' },
];

const REVIEW: { key: keyof Draft; label: string; badge?: string }[] = [
  { key: 'summary', label: 'Professional Summary', badge: 'Tailored' },
  { key: 'skills', label: 'Prioritized Skills', badge: 'Keywords' },
  { key: 'experience', label: 'Experience & Bullet Points', badge: 'Action bullets' },
  { key: 'projects', label: 'Tailored Projects', badge: 'Targeted' },
];

export default function Tailor() {
  const { jobId, resumeId } = useParams();
  const { state } = useApp();
  const job = jobById(jobId);
  const existing = state.resumes.find((r) => r.id === Number(resumeId));
  if (!job || !state.profile) return <Navigate to="/jobs" replace />;
  return <TailorEditor key={`${job.id}-${existing?.id ?? 'new'}`} job={job} profile={state.profile} existing={existing} />;
}

interface EditorProps {
  job: Job;
  profile: Profile;
  existing: TailoredResume | undefined;
}

function TailorEditor({ job, profile, existing }: EditorProps) {
  const { state, actions } = useApp();
  const navigate = useNavigate();
  const [variant, setVariant] = useState(0);
  const [proposal, setProposal] = useState(() => genProposal(job, profile, 0));
  const [cur, setCur] = useState<Draft>(() =>
    existing
      ? { summary: existing.summary, skills: existing.skills, experience: existing.experience, projects: existing.projects }
      : { ...proposal.original },
  );
  const [letter, setLetter] = useState(() => existing?.coverLetter ?? buildLetter(job, proposal.related, profile));
  const [decisions, setDecisions] = useState<Partial<Record<keyof Draft, Decision>>>(
    existing ? { summary: 'a', skills: 'a', experience: 'a', projects: 'a' } : {},
  );
  /** Bumped whenever the editable fields must be re-seeded from state (approve, keep, regenerate, tab switch). */
  const [seed, setSeed] = useState({ draft: cur, letter, version: 0 });
  const [tab, setTab] = useState<Tab>('resume');
  const [template, setTemplate] = useState<TemplateId>(existing?.template ?? state.template);
  const [showTex, setShowTex] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [isEditingExp, setIsEditingExp] = useState(false);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiSuccess, setAiSuccess] = useState(false);
  const [letterLoading, setLetterLoading] = useState(false);
  const [letterSuccess, setLetterSuccess] = useState(false);
  const [letterCompanySummary, setLetterCompanySummary] = useState<string | null>(null);
  const [copiedLetter, setCopiedLetter] = useState(false);
  const timer = useRef<number>();

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const touch = useCallback(() => {
    setSaving(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setSaving(false), 800);
  }, []);

  const onSummary = useCallback((t: string) => { setCur((c) => ({ ...c, summary: t })); touch(); }, [touch]);
  const onSkills = useCallback((t: string) => { setCur((c) => ({ ...c, skills: t })); touch(); }, [touch]);
  const onExperience = useCallback((t: string) => { setCur((c) => ({ ...c, experience: t })); touch(); }, [touch]);
  const onLetter = useCallback((t: string) => { setLetter(t); touch(); }, [touch]);

  const reseed = (draft: Draft, l: string) => setSeed((s) => ({ draft, letter: l, version: s.version + 1 }));

  const decide = (key: keyof Draft, d: Decision) => {
    const next = { ...cur, [key]: d === 'a' ? proposal.proposed[key] : proposal.original[key] };
    setCur(next);
    setDecisions((x) => ({ ...x, [key]: d }));
    reseed(next, letter);
  };

  const fetchGeminiTailoring = useCallback(async () => {
    setAiLoading(true);
    setError('');
    try {
      const expCards = parseExperienceToCards(profile.experience || '');
      const projCards = parseProjectsToCards(profile.projects || '');
      const eduCards = parseEducationToCards(profile.education || '');

      const candidateProfilePayload = {
        name: profile.name,
        summary: profile.summary,
        skills: profile.skills ? profile.skills.split(',').map((s) => s.trim()).filter(Boolean) : [],
        employment_history: expCards.map((c) => ({
          company: c.company,
          title: c.title,
          start_date: c.startDate,
          end_date: c.endDate,
          location: c.location,
          achievements: c.bullets,
        })),
        projects: projCards.map((p) => ({
          name: p.title,
          description: p.roleOrSubtitle,
          technologies: p.technologies ? p.technologies.split(',').map((t) => t.trim()).filter(Boolean) : [],
          achievements: p.bullets,
        })),
        education: eduCards.map((e) => ({
          institution: e.institution,
          degree: e.degree,
          start_date: e.startDate,
          end_date: e.endDate,
          gpa: e.gpa,
        })),
      };

      const jobPayload = {
        title: job.title,
        employer: job.company,
        company: job.company,
        description: job.description || (job.requirements ? job.requirements.join('\n') : ''),
        requirements: job.requirements || [],
      };

      const res = await api.tailor.preview(jobPayload, candidateProfilePayload);
      const tailored = res.data;
      if (tailored) {
        // Map tailored experience entries
        const tailoredExpCards = (tailored.experience && tailored.experience.length > 0)
          ? tailored.experience.map((e: any, idx: number) => {
              const orig = expCards[idx] || expCards.find((c) => c.company.toLowerCase() === (e.company || '').toLowerCase());
              return {
                id: `ai-exp-${idx}`,
                title: e.title || orig?.title || '',
                company: e.company || orig?.company || '',
                startDate: e.start_date || orig?.startDate || '',
                endDate: e.end_date || orig?.endDate || '',
                location: e.location || orig?.location || '',
                mode: orig?.mode || '',
                isCurrent: /present/i.test(e.end_date || orig?.endDate || ''),
                bullets: (e.bullet_points && e.bullet_points.length > 0) ? e.bullet_points : (orig?.bullets || []),
                links: orig?.links,
              };
            })
          : expCards;
        const tailoredExpText = serializeCardsToExperience(tailoredExpCards);

        // Map tailored projects entries
        const tailoredProjCards = (tailored.projects && tailored.projects.length > 0)
          ? tailored.projects.map((p: any, idx: number) => {
              const orig = projCards[idx] || projCards.find((c) => c.title.toLowerCase() === (p.name || '').toLowerCase());
              return {
                id: `ai-proj-${idx}`,
                title: p.name || orig?.title || '',
                roleOrSubtitle: p.description || orig?.roleOrSubtitle || '',
                technologies: Array.isArray(p.technologies) ? p.technologies.join(', ') : (orig?.technologies || ''),
                bullets: (p.bullet_points && p.bullet_points.length > 0) ? p.bullet_points : (orig?.bullets || []),
                links: orig?.links,
              };
            })
          : projCards;
        const tailoredProjText = serializeCardsToProjects(tailoredProjCards);

        const proposedSkills = Array.isArray(tailored.skills) ? tailored.skills.join(', ') : (tailored.skills || profile.skills);
        const proposedSummary = tailored.summary || profile.summary;

        setProposal({
          related: Array.isArray(tailored.skills) ? tailored.skills : [],
          original: {
            summary: profile.summary,
            skills: profile.skills,
            experience: profile.experience,
            projects: profile.projects,
            leadership: profile.leadership,
          },
          proposed: {
            summary: proposedSummary,
            skills: proposedSkills,
            experience: tailoredExpText,
            projects: tailoredProjText,
            leadership: profile.leadership,
          },
        });

        setDecisions({});
        setAiSuccess(true);
      } else if (res.error) {
        setError(res.error);
      }
    } catch (err: any) {
      console.error('Gemini tailoring failed, using offline fallback:', err);
      setError(err?.message || 'Gemini tailoring request failed. Showing offline suggestions.');
    } finally {
      setAiLoading(false);
    }
  }, [job, profile]);

  const fetchGeminiCoverLetter = useCallback(async () => {
    setLetterLoading(true);
    setError('');
    try {
      const expCards = parseExperienceToCards(profile.experience || '');
      const projCards = parseProjectsToCards(profile.projects || '');
      const eduCards = parseEducationToCards(profile.education || '');

      const candidateProfilePayload = {
        name: profile.name,
        summary: profile.summary,
        skills: profile.skills ? profile.skills.split(',').map((s) => s.trim()).filter(Boolean) : [],
        employment_history: expCards.map((c) => ({
          company: c.company,
          title: c.title,
          start_date: c.startDate,
          end_date: c.endDate,
          location: c.location,
          achievements: c.bullets,
        })),
        projects: projCards.map((p) => ({
          name: p.title,
          description: p.roleOrSubtitle,
          technologies: p.technologies ? p.technologies.split(',').map((t) => t.trim()).filter(Boolean) : [],
          achievements: p.bullets,
        })),
        education: eduCards.map((e) => ({
          institution: e.institution,
          degree: e.degree,
          start_date: e.startDate,
          end_date: e.endDate,
          gpa: e.gpa,
        })),
      };

      const jobPayload = {
        title: job.title,
        employer: job.company,
        company: job.company,
        description: job.description || (job.requirements ? job.requirements.join('\n') : ''),
        requirements: job.requirements || [],
      };

      const res = await api.tailor.previewCoverLetter(jobPayload, candidateProfilePayload);
      if (res.data && res.data.full_text) {
        setLetter(res.data.full_text);
        if (res.data.company_research_summary) {
          setLetterCompanySummary(res.data.company_research_summary);
        }
        setSeed((s) => ({ ...s, letter: res.data.full_text, version: s.version + 1 }));
        setLetterSuccess(true);
      } else if (res.error) {
        setError(res.error);
      }
    } catch (err: any) {
      console.error('Gemini cover letter generation failed:', err);
      setError(err?.message || 'Gemini cover letter generation failed. Showing offline draft.');
    } finally {
      setLetterLoading(false);
    }
  }, [job, profile]);

  useEffect(() => {
    if (!existing) {
      fetchGeminiTailoring();
    }
  }, [existing, fetchGeminiTailoring]);

  const switchTab = (t: Tab) => {
    setTab(t);
    reseed(cur, letter);
    if (t === 'letter' && !letterSuccess && !existing?.coverLetter) {
      fetchGeminiCoverLetter();
    }
  };

  const audit = auditSkills(cur.skills, profile);
  const gaps = matchJob(job, profile, state.prefs).gaps;

  const approve = () => {
    if (audit.flagged.length) return setError('Resolve the flagged skills before approving.');
    actions.saveResume({
      resumeId: existing?.id ?? null,
      jobId: job.id,
      template,
      ...cur,
      projects: cur.projects || profile.projects,
      coverLetter: letter,
    });
    navigate('/res');
  };

  const pickTemplate = (t: TemplateId) => setTemplate(t);

  const dedupeSkills = (str: string) => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const s of (str || '').split(',')) {
      const t = s.trim();
      if (!t) continue;
      const low = t.toLowerCase();
      if (!seen.has(low)) {
        seen.add(low);
        out.push(t);
      }
    }
    return out.join(', ');
  };

  const contactRow1: React.ReactNode[] = [];
  if (profile.location) contactRow1.push(<span key="loc">{profile.location}</span>);
  if (profile.phone) contactRow1.push(<span key="ph">{profile.phone}</span>);
  if (profile.email) contactRow1.push(<a key="em" href={`mailto:${profile.email}`}>{profile.email}</a>);

  const contactRow2: React.ReactNode[] = [];
  if (profile.link) {
    const liHref = profile.link.startsWith('http') ? profile.link : `https://${profile.link}`;
    contactRow2.push(
      <a key="li" href={liHref} target="_blank" rel="noreferrer" className="ct-link">
        LinkedIn
      </a>
    );
  }
  if (profile.github) {
    const ghHref = profile.github.startsWith('http') ? profile.github : `https://${profile.github}`;
    contactRow2.push(
      <a key="gh" href={ghHref} target="_blank" rel="noreferrer" className="ct-link">
        GitHub
      </a>
    );
  }

  const ellipsis = (s?: string) => (s || '').replace(/\n/g, ' / ').slice(0, 110);
  const leadershipText = cur.leadership || profile.leadership || '';
  const projectsText = cur.projects || profile.projects || '';

  return (
    <>
      <Link className="bk" style={{ display: 'block' }} to={`/jobs/${job.id}`}>&larr; Back to job</Link>
      <div className="card" style={{ margin: '8px 0 14px' }}>
        <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <h2 style={{ fontSize: '1.35rem' }}>Tailor for {job.title}</h2>
            <p className="meta">{job.company} · needs {job.requirements.join(', ')}</p>
          </div>
          <div className="row" style={{ alignItems: 'center', gap: 8 }}>
            <span className="meta" role="status">{saving ? 'Saving…' : 'Saved ✓'}</span>
            <button className="btn o xs" onClick={() => setShowTex((s) => !s)}>{showTex ? 'Hide' : 'View'} .tex</button>
            <button className="btn o xs" onClick={() => window.print()}>Download PDF</button>
            <button className="btn xs" onClick={approve}>Approve and save</button>
          </div>
        </div>
        <div className="tabs">
          <button className={tab === 'resume' ? 'on' : ''} onClick={() => switchTab('resume')}>Resume</button>
          <button className={tab === 'letter' ? 'on' : ''} onClick={() => switchTab('letter')}>Cover letter</button>
          <select className="i tsel" aria-label="Template" value={template} onChange={(e) => pickTemplate(e.target.value as TemplateId)}>
            {TEMPLATES.map((t) => <option key={t.id} value={t.id}>{t.label}</option>)}
          </select>
        </div>
      </div>

      <div className="tg">
        <div className="stack">
          {tab === 'resume' ? (
            <>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
                <div>
                  <h3 style={{ margin: 0 }}>Review suggested changes</h3>
                  {aiSuccess && <span className="meta" style={{ color: '#16a34a', fontSize: '0.8rem' }}>✨ Powered by Gemini AI</span>}
                </div>
                <button
                  className="btn xs"
                  onClick={fetchGeminiTailoring}
                  disabled={aiLoading}
                  style={{
                    background: 'linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 600,
                  }}
                >
                  {aiLoading ? 'Tailoring…' : '✨ Regenerate with Gemini'}
                </button>
              </div>

              {aiLoading && (
                <div className="card" style={{ background: 'rgba(37,99,235,0.06)', border: '1px solid rgba(37,99,235,0.25)', padding: '12px 14px' }}>
                  <div className="row" style={{ alignItems: 'center', gap: 10 }}>
                    <span className="spinner" style={{ width: 16, height: 16 }} />
                    <div>
                      <strong style={{ fontSize: '0.9rem', color: '#1e40af' }}>Gemini is rewriting bullet points...</strong>
                      <p className="meta" style={{ margin: 0, fontSize: '0.8rem' }}>
                        Transforming achievements into action-verb bullets tailored for {job.title}.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {REVIEW.map(({ key, label, badge }) => {
                const o = proposal.original[key];
                const p = proposal.proposed[key];
                const d = decisions[key];
                if (!p && !o) return null;
                if (o === p) {
                  return (
                    <div className="card rc" key={key}>
                      <div className="row" style={{ justifyContent: 'space-between' }}>
                        <h3>{label}</h3>
                        <span className="badge s">Aligned</span>
                      </div>
                      <p className="meta" style={{ margin: '4px 0' }}>Current content matches target qualifications.</p>
                    </div>
                  );
                }
                return (
                  <div className="card rc" key={key} style={{ borderLeft: d === 'a' ? '3px solid #10b981' : '3px solid #2563eb' }}>
                    <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                      <div>
                        <h3 style={{ margin: 0 }}>{label}</h3>
                        {badge && <span className="meta" style={{ fontSize: '0.75rem' }}>{badge}</span>}
                      </div>
                      {d ? (
                        <span className={`badge ${d === 'a' ? 's' : ''}`}>{d === 'a' ? 'Applied ✓' : 'Kept original'}</span>
                      ) : (
                        <span className="badge p">AI Suggested</span>
                      )}
                    </div>

                    <div style={{ margin: '10px 0', fontSize: '0.86rem' }}>
                      {key === 'experience' && p ? (
                        <div style={{ maxHeight: '280px', overflowY: 'auto', paddingRight: '4px' }}>
                          {parseExperienceToCards(p).map((item, idx) => (
                            <div key={idx} style={{ marginBottom: 10, padding: '8px', background: 'rgba(37,99,235,0.04)', borderRadius: 6 }}>
                              <strong style={{ display: 'block', color: '#163a5f', fontSize: '0.88rem' }}>
                                {item.title} · {item.company}
                              </strong>
                              <ul style={{ margin: '6px 0 0 16px', padding: 0 }}>
                                {item.bullets.map((b, bi) => (
                                  <li key={bi} style={{ marginBottom: 4, lineHeight: 1.35 }}>
                                    {b.replace(/^[-•*▪·–—\d.)\s]+/, '').trim()}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ))}
                        </div>
                      ) : key === 'projects' && p ? (
                        <div style={{ maxHeight: '280px', overflowY: 'auto', paddingRight: '4px' }}>
                          {parseProjectsToCards(p).map((item, idx) => (
                            <div key={idx} style={{ marginBottom: 10, padding: '8px', background: 'rgba(37,99,235,0.04)', borderRadius: 6 }}>
                              <strong style={{ display: 'block', color: '#163a5f', fontSize: '0.88rem' }}>
                                {item.title} {item.roleOrSubtitle && `(${item.roleOrSubtitle})`}
                              </strong>
                              <ul style={{ margin: '6px 0 0 16px', padding: 0 }}>
                                {item.bullets.map((b, bi) => (
                                  <li key={bi} style={{ marginBottom: 4, lineHeight: 1.35 }}>
                                    {b.replace(/^[-•*▪·–—\d.)\s]+/, '').trim()}
                                  </li>
                                ))}
                              </ul>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <>
                          <p className="meta" style={{ margin: '4px 0' }}><s>{ellipsis(o) || '(empty)'}</s></p>
                          <p style={{ margin: '4px 0', color: '#111827', fontWeight: 500, lineHeight: 1.35 }}>{p}</p>
                        </>
                      )}
                    </div>

                    <div className="row" style={{ marginTop: 10, gap: 8 }}>
                      <button className="btn xs" onClick={() => decide(key, 'a')}>✓ Approve and apply</button>
                      <button className="btn g xs" onClick={() => decide(key, 'k')}>Keep original</button>
                    </div>
                  </div>
                );
              })}
            </>
          ) : (
            <div className="stack" style={{ gap: 12 }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 2 }}>
                <div>
                  <h3 style={{ margin: 0 }}>Cover letter</h3>
                  {letterSuccess && (
                    <span className="meta" style={{ color: '#16a34a', fontSize: '0.8rem' }}>
                      ✨ Powered by Gemini (Researched {job.company})
                    </span>
                  )}
                </div>
                <button
                  className="btn xs"
                  onClick={fetchGeminiCoverLetter}
                  disabled={letterLoading}
                  style={{
                    background: 'linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%)',
                    color: '#fff',
                    border: 'none',
                    fontWeight: 600,
                  }}
                >
                  {letterLoading ? 'Researching & Writing…' : '✨ Regenerate with Gemini'}
                </button>
              </div>

              {letterLoading && (
                <div className="card" style={{ background: 'rgba(37,99,235,0.06)', border: '1px solid rgba(37,99,235,0.25)', padding: '12px 14px' }}>
                  <div className="row" style={{ alignItems: 'center', gap: 10 }}>
                    <span className="spinner" style={{ width: 16, height: 16 }} />
                    <div>
                      <strong style={{ fontSize: '0.9rem', color: '#1e40af' }}>Gemini is researching {job.company}...</strong>
                      <p className="meta" style={{ margin: 0, fontSize: '0.8rem' }}>
                        Searching company mission, products, and culture to write a natural, deeply personalized cover letter.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {letterCompanySummary && (
                <div className="card" style={{ borderLeft: '3px solid #2563eb', padding: '12px 14px' }}>
                  <h4 style={{ margin: '0 0 4px', fontSize: '0.86rem', color: '#163a5f' }}>🔍 Company Intelligence Discovered</h4>
                  <p style={{ margin: 0, fontSize: '0.82rem', color: '#374151', whiteSpace: 'pre-line', lineHeight: 1.45 }}>
                    {letterCompanySummary}
                  </p>
                </div>
              )}

              <div className="card">
                <h4 style={{ margin: '0 0 6px', fontSize: '0.88rem' }}>Tailoring Strategy</h4>
                <ul style={{ margin: 0, paddingLeft: 18, fontSize: '0.82rem', color: '#4b5563', lineHeight: 1.45 }}>
                  <li><strong>Researched First:</strong> Prompt directs Gemini to search and analyze {job.company}'s mission and products.</li>
                  <li><strong>Natural & Human Voice:</strong> Eliminates robotic corporate clichés and boilerplate.</li>
                  <li><strong>Factual Grounding:</strong> Strictly anchored in verified accomplishments from your profile.</li>
                </ul>
                <div className="row" style={{ marginTop: 12, gap: 8 }}>
                  <button
                    className="btn g xs"
                    onClick={() => {
                      navigator.clipboard.writeText(letter);
                      setCopiedLetter(true);
                      setTimeout(() => setCopiedLetter(false), 2000);
                    }}
                  >
                    {copiedLetter ? 'Copied ✓' : '📋 Copy Cover Letter'}
                  </button>
                </div>
              </div>
            </div>
          )}
          <div className="card">
            <h3>Truth check</h3>
            <p className="meta" style={{ margin: '4px 0 8px' }}>Every skill is compared with your profile as you edit.</p>
            {audit.flagged.length ? (
              <>
                <span className="badge n">{audit.flagged.length} flagged</span>
                <ul className="tl">
                  {audit.flagged.map((x) => <li key={x}><b>{x}</b> is not in your profile skills. Remove it, or add it to your profile if it is true.</li>)}
                </ul>
              </>
            ) : (
              <span className="badge s">{audit.verified} of {audit.verified} skills verified</span>
            )}
            {gaps.length > 0 && <p className="meta" style={{ marginTop: 10 }}>The job asks for {gaps.join(', ')}. Not in your profile, so not claimed.</p>}
          </div>
          <div className={`msg${error ? ' e' : ''}`} role="status">{error}</div>
        </div>

        <div>
          <div className={`paper t-${template}`} id="rdoc">
            <h2>{profile.name}</h2>
            <div className="ct">
              {contactRow1.length > 0 && (
                <div className="ct-row">
                  {contactRow1.map((item, idx) => (
                    <span key={idx}>
                      {idx > 0 && '  |  '}
                      {item}
                    </span>
                  ))}
                </div>
              )}
              {contactRow2.length > 0 && (
                <div className="ct-row ct-links-row">
                  {contactRow2.map((item, idx) => (
                    <span key={idx}>
                      {idx > 0 && '  |  '}
                      {item}
                    </span>
                  ))}
                </div>
              )}
            </div>
            {tab === 'letter' ? (
              <EditableText key={seed.version} label="Cover letter" initial={seed.letter} resetKey={seed.version} onText={onLetter} style={{ marginTop: 22 }} />
            ) : (
              <>
                {seed.draft.summary && (
                  <div className="resume-section">
                    <div className="resume-section-header">
                      <h4>Summary</h4>
                    </div>
                    <div className="summary-content">
                      <EditableText label="Summary" initial={seed.draft.summary} resetKey={seed.version} onText={onSummary} />
                    </div>
                  </div>
                )}

                {seed.draft.skills && (
                  <div className="resume-section">
                    <div className="resume-section-header">
                      <h4>Skills</h4>
                    </div>
                    <div className="skills-content">
                      <EditableText label="Skills" initial={dedupeSkills(seed.draft.skills)} resetKey={seed.version} onText={onSkills} />
                    </div>
                  </div>
                )}

                {seed.draft.experience && (
                  <div className="resume-section">
                    <div className="resume-section-header">
                      <h4>Experience</h4>
                      <button
                        type="button"
                        className="section-edit-btn no-print"
                        onClick={() => setIsEditingExp(!isEditingExp)}
                      >
                        {isEditingExp ? '✓ Preview' : '✎ Edit text'}
                      </button>
                    </div>
                    {isEditingExp ? (
                      <EditableText label="Experience" initial={seed.draft.experience} resetKey={seed.version} onText={onExperience} />
                    ) : (
                      parseExperienceToCards(seed.draft.experience).map((item, idx) => (
                        <div className="resume-entry" key={idx}>
                          <div className="entry-header">
                            <div className="entry-left">
                              <span className="entry-title">{item.title}</span>
                              {item.company && (
                                <span className="entry-company">
                                  {' · '}{item.company}
                                  {item.links && item.links.length > 0 && (
                                    <span className="entry-item-links">
                                      {' ('}
                                      {item.links.map((link, lidx) => (
                                        <span key={lidx}>
                                          {lidx > 0 && ' | '}
                                          <a href={link.url.startsWith('http') ? link.url : `https://${link.url}`} target="_blank" rel="noreferrer">
                                            {link.label}
                                          </a>
                                        </span>
                                      ))}
                                      {')'}
                                    </span>
                                  )}
                                </span>
                              )}
                            </div>
                            {[item.startDate, item.endDate].filter(Boolean).length > 0 && (
                              <span className="entry-date">{[item.startDate, item.endDate].filter(Boolean).join(' – ')}</span>
                            )}
                          </div>
                          {(item.location || item.mode) && (
                            <div className="entry-sub">
                              <span>{[item.location, item.mode].filter(Boolean).join(' · ')}</span>
                            </div>
                          )}
                          {item.bullets.length > 0 && (
                            <ul className="entry-bullets">
                              {item.bullets.map((b, bi) => (
                                <li key={bi}>{b.replace(/^[-•*▪·–—\d.)\s]+/, '').trim()}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                )}

                {leadershipText && (
                  <div className="resume-section">
                    <div className="resume-section-header">
                      <h4>Leadership & Community</h4>
                    </div>
                    {parseLeadershipToCards(leadershipText).map((item, idx) => (
                      <div className="resume-entry" key={idx}>
                        <div className="entry-header">
                          <div className="entry-left">
                            <span className="entry-title">{item.title}</span>
                            {item.organization && (
                              <span className="entry-company">
                                {' · '}{item.organization}
                                {item.links && item.links.length > 0 && (
                                  <span className="entry-item-links">
                                    {' ('}
                                    {item.links.map((link, lidx) => (
                                      <span key={lidx}>
                                        {lidx > 0 && ' | '}
                                        <a href={link.url.startsWith('http') ? link.url : `https://${link.url}`} target="_blank" rel="noreferrer">
                                          {link.label}
                                        </a>
                                      </span>
                                    ))}
                                    {')'}
                                  </span>
                                )}
                              </span>
                            )}
                          </div>
                          {[item.startDate, item.endDate].filter(Boolean).length > 0 && (
                            <span className="entry-date">{[item.startDate, item.endDate].filter(Boolean).join(' – ')}</span>
                          )}
                        </div>
                        {item.location && (
                          <div className="entry-sub">
                            <span>{item.location}</span>
                          </div>
                        )}
                        {item.bullets.length > 0 && (
                          <ul className="entry-bullets">
                            {item.bullets.map((b, bi) => (
                              <li key={bi}>{b.replace(/^[-•*▪·–—\d.)\s]+/, '').trim()}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {profile.education && (
                  <div className="resume-section">
                    <div className="resume-section-header">
                      <h4>Education</h4>
                    </div>
                    {parseEducationToCards(profile.education).map((item, idx) => (
                      <div className="resume-entry" key={idx}>
                        <div className="entry-header">
                          <div className="entry-left">
                            <span className="entry-title">{item.degree}</span>
                            {item.institution && (
                              <span className="entry-company">
                                {' · '}{item.institution}
                                {item.links && item.links.length > 0 && (
                                  <span className="entry-item-links">
                                    {' ('}
                                    {item.links.map((link, lidx) => (
                                      <span key={lidx}>
                                        {lidx > 0 && ' | '}
                                        <a href={link.url.startsWith('http') ? link.url : `https://${link.url}`} target="_blank" rel="noreferrer">
                                          {link.label}
                                        </a>
                                      </span>
                                    ))}
                                    {')'}
                                  </span>
                                )}
                              </span>
                            )}
                          </div>
                          {[item.startDate, item.endDate].filter(Boolean).length > 0 && (
                            <span className="entry-date">{[item.startDate, item.endDate].filter(Boolean).join(' – ')}</span>
                          )}
                        </div>
                        {(item.location || item.gpa) && (
                          <div className="entry-sub">
                            <span>{[item.location, item.gpa ? `GPA: ${item.gpa}` : ''].filter(Boolean).join(' · ')}</span>
                          </div>
                        )}
                        {item.bullets.length > 0 && (
                          <ul className="entry-bullets">
                            {item.bullets.map((b, bi) => (
                              <li key={bi}>{b.replace(/^[-•*▪·–—\d.)\s]+/, '').trim()}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {projectsText && (
                  <div className="resume-section">
                    <div className="resume-section-header">
                      <h4>Projects</h4>
                    </div>
                    {parseProjectsToCards(projectsText).map((item, idx) => (
                      <div className="resume-entry" key={idx}>
                        <div className="entry-header">
                          <div className="entry-left">
                            <span className="entry-title">{item.title}</span>
                            {item.links && item.links.length > 0 ? (
                              <span className="entry-item-links">
                                {' ('}
                                {item.links.map((link, lidx) => (
                                  <span key={lidx}>
                                    {lidx > 0 && ' | '}
                                    <a href={link.url.startsWith('http') ? link.url : `https://${link.url}`} target="_blank" rel="noreferrer">
                                      {link.label}
                                    </a>
                                  </span>
                                ))}
                                {')'}
                              </span>
                            ) : item.link ? (
                              <span className="entry-link"> · {item.link}</span>
                            ) : null}
                            {item.technologies && <span className="entry-tech"> [{item.technologies}]</span>}
                          </div>
                          {item.date && <span className="entry-date">{item.date}</span>}
                        </div>
                        {item.roleOrSubtitle && (
                          <div className="entry-sub">
                            <span>{item.roleOrSubtitle}</span>
                          </div>
                        )}
                        {item.bullets.length > 0 && (
                          <ul className="entry-bullets">
                            {item.bullets.map((b, bi) => (
                              <li key={bi}>{b.replace(/^[-•*▪·–—\d.)\s]+/, '').trim()}</li>
                            ))}
                          </ul>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {profile.certs && (
                  <div className="resume-section">
                    <div className="resume-section-header">
                      <h4>Certifications</h4>
                    </div>
                    <ul className="entry-bullets">
                      {profile.certs
                        .split('\n')
                        .map((c) => c.replace(/^[-•*▪·–—\d.)\s]+/, '').replace(/\s*-\s*Certification Authority/gi, '').trim())
                        .filter((c) => c && !/^https?:\/\//i.test(c) && !/^links:?$/i.test(c))
                        .map((c, idx) => {
                          const { cleanText, links } = extractItemLinks(c);
                          return (
                            <li key={idx}>
                              <span>{cleanText}</span>
                              {links.length > 0 && (
                                <span className="entry-item-links">
                                  {' ('}
                                  {links.map((link, lidx) => (
                                    <span key={lidx}>
                                      {lidx > 0 && ' | '}
                                      <a href={link.url.startsWith('http') ? link.url : `https://${link.url}`} target="_blank" rel="noreferrer">
                                        {link.label}
                                      </a>
                                    </span>
                                  ))}
                                  {')'}
                                </span>
                              )}
                            </li>
                          );
                        })}
                    </ul>
                  </div>
                )}
              </>
            )}
          </div>
          {showTex && (
            <div className="card" style={{ marginTop: 14 }}>
              <h3>LaTeX source</h3>
              <p className="meta" style={{ margin: '4px 0 8px' }}>Copy into a blank Overleaf project (main.tex).</p>
              <textarea className="i" readOnly style={{ minHeight: 200, font: '.8rem monospace' }} value={toLatex(profile, cur)} />
            </div>
          )}
        </div>
      </div>
    </>
  );
}
