import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { Logo } from '../components/Logo';
import { PrefsForm } from '../components/PrefsForm';
import { SAMPLE_RESUME } from '../data/jobs';
import { today } from '../lib/match';
import { formatBackendProfileToState, parseResumeSections, type ParsedResume } from '../lib/resumeParser';
import { useApp } from '../store/AppContext';
import { api } from '../api';
import type { Profile as ProfileT } from '../types';

export default function Onboarding() {
  const { state, actions } = useApp();
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [text, setText] = useState('');
  const [fileObj, setFileObj] = useState<File | null>(null);
  const [prefs, setPrefs] = useState(state.prefs);
  const [loading, setLoading] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [error, setError] = useState('');

  // Draft profile parsed from resume
  const [parsed, setParsed] = useState<ParsedResume | null>(null);

  if (!state.user) return <Navigate to="/login" replace />;
  const user = state.user;

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileObj(file);
      setError('');
      // If text file, preview text automatically
      if (file.name.endsWith('.txt')) {
        const reader = new FileReader();
        reader.onload = () => setText(String(reader.result || ''));
        reader.readAsText(file);
      }
    }
  };

  const processResume = async () => {
    setError('');
    setStatusMsg('');

    // Case 1: Binary File Upload (PDF / DOCX)
    if (fileObj) {
      setLoading(true);
      setStatusMsg(`Uploading and parsing ${fileObj.name}...`);
      try {
        const uploadRes = await api.resumes.upload(fileObj);
        if (uploadRes.data && uploadRes.data.resume_version_id) {
          setStatusMsg('Resume parsed by backend. Fetching structured profile...');
          // Fetch backend profile with structured sections
          const profRes = await api.profile.getProfile();
          if (profRes.data) {
            const formatted = formatBackendProfileToState(profRes.data, user.name, user.email);
            setParsed(formatted);
            setStep(2);
            setLoading(false);
            return;
          }
        }
      } catch (err: any) {
        // Fall back gracefully if backend storage or token has issues during preview
        setStatusMsg('Backend processing busy. Parsing locally...');
      }
    }

    // Case 2: Pasted text (or fallback from file)
    const raw = text.trim();
    if (raw.length < 30) {
      setLoading(false);
      return setError('Please paste your resume text (at least a few sentences) or upload a PDF/DOCX file.');
    }

    setLoading(true);
    setStatusMsg('Extracting resume sections (skills, work history, education, projects)...');

    try {
      // 1. Try sending to backend paste endpoint for persistence
      api.resumes.paste(raw).catch(() => {
        /* non-blocking background sync */
      });

      // 2. Client-side deterministic section splitter guarantees no data loss
      const structured = parseResumeSections(raw);
      setParsed(structured);
      setStep(2);
    } catch {
      setError('Could not parse resume text.');
    } finally {
      setLoading(false);
      setStatusMsg('');
    }
  };

  const build = () => {
    if (!parsed) return;
    actions.savePrefs(prefs);

    const fullProfile: ProfileT = {
      name: parsed.name || user.name,
      email: parsed.email || user.email,
      phone: parsed.phone || '',
      location: parsed.location || '',
      link: parsed.link || '',
      summary: parsed.summary || '',
      skills: parsed.skills || '',
      experience: parsed.experience || '',
      education: parsed.education || '',
      projects: parsed.projects || '',
      certs: parsed.certs || '',
      confirmed: {
        summary: !!parsed.summary,
        skills: !!parsed.skills,
        experience: !!parsed.experience,
        education: !!parsed.education,
        projects: !!parsed.projects,
        certs: !!parsed.certs,
      },
      created: today(),
    };

    actions.saveProfile(fullProfile);

    // Sync to backend profile if active
    api.profile.updateProfile({
      display_name: fullProfile.name,
      phone: fullProfile.phone,
      location: fullProfile.location,
      linkedin: fullProfile.link,
    }).catch(() => {
      /* non-blocking */
    });

    navigate('/prof');
  };

  return (
    <div className="au" style={{ maxWidth: 740 }}>
      <Logo />
      <div className="meta">Step {step} of 2</div>
      <div className="bar"><i style={{ width: `${step * 50}%` }} /></div>
      <div className="card">
        {step === 1 ? (
          <>
            <h3>Add your resume</h3>
            <p className="meta" style={{ margin: '6px 0 12px' }}>
              Upload your PDF/DOCX resume or paste the text. Sections like work experience, education, projects, and skills will be parsed into their proper categories.
            </p>

            <label>
              Upload resume file (PDF or DOCX)
              <input
                className="i"
                type="file"
                accept=".pdf,.docx,.txt"
                onChange={handleFileChange}
              />
            </label>
            {fileObj && (
              <p className="meta" style={{ marginTop: 4, color: 'var(--blue)' }}>
                Selected: {fileObj.name} ({(fileObj.size / 1024).toFixed(1)} KB)
              </p>
            )}

            <label style={{ marginTop: 14 }}>
              Or paste resume text
              <textarea
                className="i"
                style={{ minHeight: 180 }}
                placeholder="Paste your full resume here including Summary, Work Experience, Education, Projects, and Skills..."
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
            </label>

            {statusMsg && <div className="meta" style={{ marginTop: 8, color: 'var(--blue)' }}>{statusMsg}</div>}
            {error && <div className="msg e" role="status">{error}</div>}

            <div className="row" style={{ marginTop: 14, justifyContent: 'space-between', alignItems: 'center' }}>
              <button
                type="button"
                className="btn g xs"
                onClick={() => {
                  setText(SAMPLE_RESUME);
                  setFileObj(null);
                }}
              >
                Use sample resume
              </button>
              <button
                type="button"
                className="btn"
                disabled={loading}
                onClick={processResume}
              >
                {loading ? 'Parsing resume...' : 'Continue'}
              </button>
            </div>
          </>
        ) : (
          <>
            <h3>Review parsed sections & career preferences</h3>
            <p className="meta" style={{ margin: '4px 0 14px' }}>
              Verify how your resume was parsed across individual sections before creating your profile.
            </p>

            {parsed && (
              <div className="stack" style={{ gap: 10, marginBottom: 16 }}>
                <div className="row" style={{ gap: 10 }}>
                  <label style={{ flex: 1 }}>
                    Name
                    <input className="i" value={parsed.name || ''} onChange={(e) => setParsed({ ...parsed, name: e.target.value })} />
                  </label>
                  <label style={{ flex: 1 }}>
                    Email
                    <input className="i" value={parsed.email || ''} onChange={(e) => setParsed({ ...parsed, email: e.target.value })} />
                  </label>
                </div>

                <label>
                  Skills (comma separated)
                  <input
                    className="i"
                    value={parsed.skills}
                    placeholder="e.g. Python, SQL, Docker, Machine Learning"
                    onChange={(e) => setParsed({ ...parsed, skills: e.target.value })}
                  />
                </label>

                <label>
                  Work Experience ({parsed.experience ? `${parsed.experience.split('\n').length} lines` : 'Empty'})
                  <textarea
                    className="i"
                    style={{ minHeight: 110 }}
                    placeholder="Work history, roles, and achievements"
                    value={parsed.experience}
                    onChange={(e) => setParsed({ ...parsed, experience: e.target.value })}
                  />
                </label>

                <div className="row" style={{ gap: 10 }}>
                  <label style={{ flex: 1 }}>
                    Education ({parsed.education ? 'Extracted' : 'Empty'})
                    <textarea
                      className="i"
                      style={{ minHeight: 80 }}
                      placeholder="Degrees, universities, dates"
                      value={parsed.education}
                      onChange={(e) => setParsed({ ...parsed, education: e.target.value })}
                    />
                  </label>
                  <label style={{ flex: 1 }}>
                    Projects ({parsed.projects ? 'Extracted' : 'Empty'})
                    <textarea
                      className="i"
                      style={{ minHeight: 80 }}
                      placeholder="Projects, tools used, descriptions"
                      value={parsed.projects}
                      onChange={(e) => setParsed({ ...parsed, projects: e.target.value })}
                    />
                  </label>
                </div>

                {parsed.summary && (
                  <label>
                    Professional Summary
                    <textarea
                      className="i"
                      style={{ minHeight: 60 }}
                      value={parsed.summary}
                      onChange={(e) => setParsed({ ...parsed, summary: e.target.value })}
                    />
                  </label>
                )}
              </div>
            )}

            <h4 style={{ margin: '14px 0 8px', fontSize: '1.05rem' }}>Your search preferences</h4>
            <PrefsForm value={prefs} onChange={setPrefs} />

            <div className="row" style={{ marginTop: 16, justifyContent: 'space-between' }}>
              <button className="btn g" onClick={() => setStep(1)}>Back to upload</button>
              <button className="btn" onClick={build}>Build my profile</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
