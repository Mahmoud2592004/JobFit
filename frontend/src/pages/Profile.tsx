import { useEffect, useState } from 'react';
import { Avatar } from '../components/Avatar';
import { SECTIONS } from '../data/jobs';
import {
  formatBackendProfileToState,
  parseResumeSections,
  parseExperienceToCards,
  serializeCardsToExperience,
  DEFAULT_EXPERIENCE_CARDS,
  type ExperienceCardItem,
} from '../lib/resumeParser';
import { useApp } from '../store/AppContext';
import { api } from '../api';
import type { Profile as ProfileT, SectionKey } from '../types';

const CONTACT: { key: 'name' | 'email' | 'phone' | 'location' | 'link'; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'location', label: 'Location' },
  { key: 'link', label: 'LinkedIn or portfolio' },
];

export default function Profile() {
  const { state, actions } = useApp();
  const stored: ProfileT = state.profile || {
    name: state.user?.name || 'Candidate',
    email: state.user?.email || '',
    phone: '',
    location: '',
    link: '',
    summary: '',
    skills: '',
    experience: serializeCardsToExperience(DEFAULT_EXPERIENCE_CARDS),
    education: '',
    projects: '',
    certs: '',
    confirmed: {},
    created: new Date().toLocaleDateString(),
  };

  const [draft, setDraft] = useState<ProfileT>(() => {
    if (!stored.experience) {
      return { ...stored, experience: serializeCardsToExperience(DEFAULT_EXPERIENCE_CARDS) };
    }
    return stored;
  });
  const [saved, setSaved] = useState(false);
  const [showUploader, setShowUploader] = useState(false);
  const [resumeText, setResumeText] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadLoading, setUploadLoading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState('');

  // Structured Experience Cards State (LinkedIn Style)
  const [expCards, setExpCards] = useState<ExperienceCardItem[]>(() => {
    const list = parseExperienceToCards(stored.experience || draft.experience);
    return list.length > 0 ? list : DEFAULT_EXPERIENCE_CARDS;
  });
  const [editingExpId, setEditingExpId] = useState<string | null>(null);
  const [isAddingExp, setIsAddingExp] = useState(false);
  const [showRawExp, setShowRawExp] = useState(false);
  const [expForm, setExpForm] = useState<Omit<ExperienceCardItem, 'id'>>({
    title: '',
    company: '',
    location: '',
    mode: 'Hybrid',
    startDate: '',
    endDate: 'Present',
    isCurrent: true,
    bullets: [],
  });
  const [bulletsInput, setBulletsInput] = useState('');

  useEffect(() => {
    // If current profile is missing fields or contains legacy corrupted formatting, fetch clean parsed data from backend
    api.profile
      .getProfile()
      .then((res) => {
        if (res.data?.active_version || res.data?.profile) {
          const formatted = formatBackendProfileToState(
            res.data,
            state.user?.name || draft.name,
            state.user?.email || draft.email,
          );
          if (formatted.experience || formatted.education || formatted.phone || formatted.link) {
            setDraft((prev) => {
              const hasMissing = !prev.experience || !prev.education || !prev.phone;
              const hasCorrupted =
                prev.experience.includes('at Company') ||
                prev.experience.includes('()') ||
                prev.education.includes('()') ||
                prev.education.includes('Degree,') ||
                prev.experience.includes('(Feb 2024 - Present) (Feb 2024 - Present)');
              if (hasMissing || hasCorrupted) {
                const merged: ProfileT = {
                  ...prev,
                  name: formatted.name || prev.name,
                  email: formatted.email || prev.email,
                  phone: formatted.phone || prev.phone,
                  location: formatted.location || prev.location,
                  link: formatted.link || prev.link,
                  summary: formatted.summary || prev.summary,
                  skills: formatted.skills || prev.skills,
                  experience: formatted.experience || prev.experience,
                  education: formatted.education || prev.education,
                  projects: formatted.projects || prev.projects,
                  certs: formatted.certs || prev.certs,
                  confirmed: {
                    ...prev.confirmed,
                    ...formatted.confirmed,
                  },
                };
                actions.saveProfile(merged);
                return merged;
              }
              return prev;
            });
          }
        }
      })
      .catch(() => {});
  }, []);

  const attention = SECTIONS.filter((s) => !stored[s.key] || !stored.confirmed[s.key]).length;
  const setField = (k: keyof ProfileT, v: string) => { setDraft((d) => ({ ...d, [k]: v })); setSaved(false); };
  const setConfirmed = (k: SectionKey, v: boolean) => { setDraft((d) => ({ ...d, confirmed: { ...d.confirmed, [k]: v } })); setSaved(false); };

  // Synchronize structured experience cards when draft.experience changes externally
  useEffect(() => {
    setExpCards(parseExperienceToCards(draft.experience));
  }, [draft.experience]);

  const startEditCard = (card: ExperienceCardItem) => {
    setIsAddingExp(false);
    setEditingExpId(card.id);
    setExpForm({
      title: card.title,
      company: card.company,
      location: card.location || '',
      mode: card.mode || 'Hybrid',
      startDate: card.startDate || '',
      endDate: card.endDate || '',
      isCurrent: !!card.isCurrent,
      bullets: card.bullets,
    });
    setBulletsInput(card.bullets.map((b) => `- ${b}`).join('\n'));
  };

  const startAddCard = () => {
    setEditingExpId(null);
    setIsAddingExp(true);
    setExpForm({
      title: '',
      company: '',
      location: draft.location || '',
      mode: 'Hybrid',
      startDate: '',
      endDate: 'Present',
      isCurrent: true,
      bullets: [],
    });
    setBulletsInput('');
  };

  const handleSaveExpCard = (idToSave?: string) => {
    const bullets = bulletsInput
      .split(/\r?\n/)
      .map((l) => l.replace(/^[–-—*•▪·\d.)\s]+/, '').trim())
      .filter(Boolean);

    let updatedCards: ExperienceCardItem[];
    if (idToSave) {
      updatedCards = expCards.map((c) =>
        c.id === idToSave
          ? {
              ...c,
              ...expForm,
              endDate: expForm.isCurrent ? 'Present' : expForm.endDate,
              bullets,
            }
          : c
      );
      setEditingExpId(null);
    } else {
      const newCard: ExperienceCardItem = {
        id: `exp-${Date.now()}`,
        ...expForm,
        endDate: expForm.isCurrent ? 'Present' : expForm.endDate,
        bullets,
      };
      updatedCards = [...expCards, newCard];
      setIsAddingExp(false);
    }

    setExpCards(updatedCards);
    const serialized = serializeCardsToExperience(updatedCards);
    setDraft((d) => ({
      ...d,
      experience: serialized,
      confirmed: { ...d.confirmed, experience: true },
    }));
    setSaved(false);
  };

  const handleDeleteExpCard = (idToDelete: string) => {
    const updatedCards = expCards.filter((c) => c.id !== idToDelete);
    setExpCards(updatedCards);
    const serialized = serializeCardsToExperience(updatedCards);
    setDraft((d) => ({
      ...d,
      experience: serialized,
    }));
    setSaved(false);
  };

  // Check if work experience appears to contain lumped sections (e.g. Education, Projects, Skills)
  const experienceHasLumpedSections =
    draft.experience.length > 80 &&
    /(?:education|academic|degrees?|university|projects?|technical skills|certifications?)/i.test(draft.experience);

  const autoSplitExperience = () => {
    const res = parseResumeSections(draft.experience);
    const updated: ProfileT = {
      ...draft,
      experience: res.experience || draft.experience,
      education: draft.education ? `${draft.education}\n\n${res.education}`.trim() : res.education,
      projects: draft.projects ? `${draft.projects}\n\n${res.projects}`.trim() : res.projects,
      certs: draft.certs ? `${draft.certs}\n\n${res.certs}`.trim() : res.certs,
      skills: draft.skills
        ? Array.from(new Set([...draft.skills.split(','), ...res.skills.split(',')].map((s) => s.trim()).filter(Boolean))).join(', ')
        : res.skills,
      summary: draft.summary || res.summary,
      phone: draft.phone || res.phone || '',
      location: draft.location || res.location || '',
      link: draft.link || res.link || '',
      confirmed: {
        ...draft.confirmed,
        experience: true,
        education: !!(draft.education || res.education),
        projects: !!(draft.projects || res.projects),
        skills: true,
      },
    };
    setDraft(updated);
    actions.saveProfile(updated);
    setSaved(true);
  };

  const handleResumeFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setUploadFile(file);
      if (file.name.endsWith('.txt')) {
        const reader = new FileReader();
        reader.onload = () => setResumeText(String(reader.result || ''));
        reader.readAsText(file);
      }
    }
  };

  const executeReParse = async () => {
    setUploadLoading(true);
    setUploadMsg('Parsing resume...');
    try {
      if (uploadFile) {
        setUploadMsg(`Uploading ${uploadFile.name} to extraction engine...`);
        try {
          const upRes = await api.resumes.upload(uploadFile);
          if (upRes.data && upRes.data.resume_version_id) {
            const profRes = await api.profile.getProfile();
            if (profRes.data) {
              const formatted = formatBackendProfileToState(profRes.data, draft.name, draft.email);
              setDraft(formatted);
              actions.saveProfile(formatted);
              setShowUploader(false);
              setSaved(true);
              setUploadLoading(false);
              return;
            }
          }
        } catch {
          // Fall back to client parser
        }
      }

      if (resumeText.trim().length > 20) {
        const parsed = parseResumeSections(resumeText);
        const updated: ProfileT = {
          ...draft,
          name: parsed.name || draft.name,
          email: parsed.email || draft.email,
          phone: parsed.phone || draft.phone,
          location: parsed.location || draft.location,
          link: parsed.link || draft.link,
          summary: parsed.summary || draft.summary,
          skills: parsed.skills || draft.skills,
          experience: parsed.experience || draft.experience,
          education: parsed.education || draft.education,
          projects: parsed.projects || draft.projects,
          certs: parsed.certs || draft.certs,
          confirmed: {
            summary: !!(parsed.summary || draft.summary),
            skills: !!(parsed.skills || draft.skills),
            experience: !!(parsed.experience || draft.experience),
            education: !!(parsed.education || draft.education),
            projects: !!(parsed.projects || draft.projects),
            certs: !!(parsed.certs || draft.certs),
          },
        };
        setDraft(updated);
        actions.saveProfile(updated);
        setShowUploader(false);
        setSaved(true);
      }
    } finally {
      setUploadLoading(false);
      setUploadMsg('');
    }
  };

  const save = () => {
    const trimmed = { ...draft };
    for (const s of SECTIONS) trimmed[s.key] = draft[s.key].trim();
    const confirmed: ProfileT['confirmed'] = {};
    for (const s of SECTIONS) confirmed[s.key] = !!draft.confirmed[s.key] && !!trimmed[s.key];
    const full = { ...trimmed, confirmed };
    actions.saveProfile(full);
    setDraft(full);
    setSaved(true);

    // Sync to backend if reachable
    api.profile.updateProfile({
      display_name: full.name,
      phone: full.phone,
      location: full.location,
      linkedin: full.link,
    }).catch(() => {
      /* non-blocking */
    });
  };

  return (
    <div className="stack" style={{ maxWidth: 820, margin: '0 auto' }}>
      <div className="card pc">
        <div className="cv" style={{ height: 80 }} />
        <Avatar name={stored.name} size={84} />
        <h2>{stored.name}</h2>
        <p className="meta">{state.prefs.titles.split(',')[0]} · {attention ? `${attention} section(s) need attention` : 'Everything confirmed'}</p>
        <div className="row" style={{ justifyContent: 'center', marginTop: 12, gap: 10 }}>
          <button className="btn o xs" onClick={() => setShowUploader(!showUploader)}>
            {showUploader ? 'Close resume parser' : 'Re-upload / Paste Resume'}
          </button>
          <button
            className="btn g xs"
            onClick={async () => {
              setUploadLoading(true);
              setUploadMsg('Fetching clean parsed profile...');
              try {
                const res = await api.profile.getProfile();
                if (res.data?.active_version || res.data?.profile) {
                  const formatted = formatBackendProfileToState(
                    res.data,
                    state.user?.name || draft.name,
                    state.user?.email || draft.email,
                  );
                  setDraft(formatted);
                  actions.saveProfile(formatted);
                  setSaved(true);
                }
              } catch {
                /* ignore */
              } finally {
                setUploadLoading(false);
                setUploadMsg('');
              }
            }}
            disabled={uploadLoading}
          >
            Sync from parsed resume
          </button>
        </div>
      </div>

      {showUploader && (
        <div className="card stack" style={{ border: '2px solid var(--blue)', background: 'var(--blueL)' }}>
          <h3 style={{ margin: 0, color: 'var(--navy)' }}>Upload or Paste Resume to Parse Into Sections</h3>
          <p className="meta">
            Upload your PDF/DOCX or paste resume text. Our parser will categorize your summary, skills, experience, education, and projects into distinct sections.
          </p>

          <label>
            Upload Resume File (.pdf, .docx, .txt)
            <input className="i" type="file" accept=".pdf,.docx,.txt" onChange={handleResumeFileSelect} />
          </label>
          {uploadFile && <p className="meta">Selected: {uploadFile.name}</p>}

          <label>
            Or Paste Resume Text
            <textarea
              className="i"
              style={{ minHeight: 140 }}
              placeholder="Paste complete resume text..."
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
            />
          </label>

          {uploadMsg && <div className="meta" style={{ color: 'var(--blue)' }}>{uploadMsg}</div>}

          <div className="row" style={{ justifyContent: 'flex-end', gap: 10 }}>
            <button className="btn g xs" onClick={() => setShowUploader(false)}>Cancel</button>
            <button className="btn xs" disabled={uploadLoading} onClick={executeReParse}>
              {uploadLoading ? 'Parsing...' : 'Parse & Apply to Profile'}
            </button>
          </div>
        </div>
      )}

      <div className="card">
        <h3 style={{ marginBottom: 10 }}>Contact (shown on your resume)</h3>
        <div className="row">
          {CONTACT.slice(0, 2).map((c) => <label key={c.key} style={{ flex: 1 }}>{c.label}<input className="i" value={draft[c.key]} onChange={(e) => setField(c.key, e.target.value)} /></label>)}
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          {CONTACT.slice(2).map((c) => <label key={c.key} style={{ flex: 1 }}>{c.label}<input className="i" value={draft[c.key]} onChange={(e) => setField(c.key, e.target.value)} /></label>)}
        </div>
      </div>

      {SECTIONS.map((s) => {
        if (s.key === 'experience') {
          return (
            <div className="card stack" key="experience">
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="row" style={{ alignItems: 'center', gap: 10 }}>
                  <h3 style={{ margin: 0 }}>Work experience</h3>
                  <button
                    type="button"
                    className="btn o xs"
                    style={{ fontSize: '0.78rem', padding: '3px 10px' }}
                    onClick={() => setShowRawExp(!showRawExp)}
                  >
                    {showRawExp ? 'Switch to card view' : 'Edit raw text'}
                  </button>
                  <button
                    type="button"
                    className="btn g xs"
                    style={{ fontSize: '0.78rem', padding: '3px 10px' }}
                    onClick={() => {
                      setExpCards(DEFAULT_EXPERIENCE_CARDS);
                      setField('experience', serializeCardsToExperience(DEFAULT_EXPERIENCE_CARDS));
                    }}
                    title="Load sample positions matching the reference design"
                  >
                    Load sample positions
                  </button>
                  {experienceHasLumpedSections && (
                    <button
                      type="button"
                      className="btn xs"
                      style={{ background: 'var(--warn)', borderColor: 'var(--warn)', fontSize: '0.78rem', padding: '3px 10px' }}
                      onClick={autoSplitExperience}
                      title="Detect and move Education, Projects, and Skills into their dedicated sections"
                    >
                      Auto-split sections
                    </button>
                  )}
                </div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  {!stored.experience ? (
                    <span className="badge n">Empty</span>
                  ) : stored.confirmed.experience ? (
                    <span className="badge s">Confirmed</span>
                  ) : (
                    <span className="badge p">Needs confirmation</span>
                  )}
                  {!showRawExp && !isAddingExp && (
                    <button
                      type="button"
                      className="btn xs"
                      style={{ padding: '3px 12px', fontSize: '0.8rem' }}
                      onClick={startAddCard}
                    >
                      + Add position
                    </button>
                  )}
                </div>
              </div>

              {showRawExp ? (
                <>
                  <textarea
                    className="i"
                    aria-label="Work experience"
                    value={draft.experience}
                    onChange={(e) => setField('experience', e.target.value)}
                    rows={8}
                  />
                  <p className="meta" style={{ margin: 0 }}>
                    Changes in raw text update cards automatically when you return to card view.
                  </p>
                </>
              ) : (
                <div className="stack" style={{ gap: 12 }}>
                  {/* Position Add Form */}
                  {isAddingExp && (
                    <div
                      style={{
                        background: '#f8fafc',
                        border: '1.5px solid var(--blue)',
                        borderRadius: 10,
                        padding: 16,
                      }}
                    >
                      <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>
                        Add new work experience
                      </h4>
                      <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                        <label style={{ flex: 1 }}>
                          Title *
                          <input
                            className="i"
                            placeholder="e.g. Co-Founder and AI Engineer"
                            value={expForm.title}
                            onChange={(e) => setExpForm({ ...expForm, title: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          Company name *
                          <input
                            className="i"
                            placeholder="e.g. MedDigi-Verse"
                            value={expForm.company}
                            onChange={(e) => setExpForm({ ...expForm, company: e.target.value })}
                          />
                        </label>
                      </div>

                      <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                        <label style={{ flex: 1 }}>
                          Location
                          <input
                            className="i"
                            placeholder="e.g. Alexandria, Egypt"
                            value={expForm.location}
                            onChange={(e) => setExpForm({ ...expForm, location: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          Workplace type
                          <select
                            className="i"
                            value={expForm.mode}
                            onChange={(e) => setExpForm({ ...expForm, mode: e.target.value })}
                          >
                            <option value="Remote">Remote</option>
                            <option value="Hybrid">Hybrid</option>
                            <option value="On-site">On-site</option>
                          </select>
                        </label>
                      </div>

                      <div className="row" style={{ gap: 10, marginBottom: 10, alignItems: 'flex-end' }}>
                        <label style={{ flex: 1 }}>
                          Start date
                          <input
                            className="i"
                            placeholder="e.g. Jan 2024"
                            value={expForm.startDate}
                            onChange={(e) => setExpForm({ ...expForm, startDate: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          End date
                          <input
                            className="i"
                            placeholder="e.g. Present"
                            disabled={expForm.isCurrent}
                            value={expForm.isCurrent ? 'Present' : expForm.endDate}
                            onChange={(e) => setExpForm({ ...expForm, endDate: e.target.value })}
                          />
                        </label>
                        <label style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8, cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={expForm.isCurrent}
                            onChange={(e) => setExpForm({ ...expForm, isCurrent: e.target.checked, endDate: e.target.checked ? 'Present' : '' })}
                          />
                          <span style={{ fontSize: '0.85rem' }}>Current role</span>
                        </label>
                      </div>

                      <label style={{ marginBottom: 12 }}>
                        Responsibilities & Achievements (one per line)
                        <textarea
                          className="i"
                          style={{ minHeight: 90 }}
                          placeholder="- Shipped AI-powered assistant with OCR...&#10;- Orchestrated cross-functional collaboration across startup team..."
                          value={bulletsInput}
                          onChange={(e) => setBulletsInput(e.target.value)}
                        />
                      </label>

                      <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                        <button type="button" className="btn g xs" onClick={() => setIsAddingExp(false)}>
                          Cancel
                        </button>
                        <button
                          type="button"
                          className="btn xs"
                          disabled={!expForm.title.trim()}
                          onClick={() => handleSaveExpCard()}
                        >
                          Save position
                        </button>
                      </div>
                    </div>
                  )}

                  {/* Render Existing Cards */}
                  {expCards.length === 0 && !isAddingExp ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1' }}>
                      <p className="meta" style={{ margin: '0 0 10px' }}>
                        No work experience positions recorded yet.
                      </p>
                      <button type="button" className="btn xs" onClick={startAddCard}>
                        + Add position
                      </button>
                    </div>
                  ) : (
                    expCards.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: 10,
                          padding: '16px 20px',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
                        }}
                      >
                        {editingExpId === item.id ? (
                          /* Inline Edit Form */
                          <div>
                            <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>
                              Edit position
                            </h4>
                            <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                              <label style={{ flex: 1 }}>
                                Title *
                                <input
                                  className="i"
                                  value={expForm.title}
                                  onChange={(e) => setExpForm({ ...expForm, title: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                Company name
                                <input
                                  className="i"
                                  value={expForm.company}
                                  onChange={(e) => setExpForm({ ...expForm, company: e.target.value })}
                                />
                              </label>
                            </div>

                            <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                              <label style={{ flex: 1 }}>
                                Location
                                <input
                                  className="i"
                                  value={expForm.location}
                                  onChange={(e) => setExpForm({ ...expForm, location: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                Workplace type
                                <select
                                  className="i"
                                  value={expForm.mode}
                                  onChange={(e) => setExpForm({ ...expForm, mode: e.target.value })}
                                >
                                  <option value="Remote">Remote</option>
                                  <option value="Hybrid">Hybrid</option>
                                  <option value="On-site">On-site</option>
                                </select>
                              </label>
                            </div>

                            <div className="row" style={{ gap: 10, marginBottom: 10, alignItems: 'flex-end' }}>
                              <label style={{ flex: 1 }}>
                                Start date
                                <input
                                  className="i"
                                  value={expForm.startDate}
                                  onChange={(e) => setExpForm({ ...expForm, startDate: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                End date
                                <input
                                  className="i"
                                  disabled={expForm.isCurrent}
                                  value={expForm.isCurrent ? 'Present' : expForm.endDate}
                                  onChange={(e) => setExpForm({ ...expForm, endDate: e.target.value })}
                                />
                              </label>
                              <label style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8, cursor: 'pointer' }}>
                                <input
                                  type="checkbox"
                                  checked={expForm.isCurrent}
                                  onChange={(e) => setExpForm({ ...expForm, isCurrent: e.target.checked, endDate: e.target.checked ? 'Present' : '' })}
                                />
                                <span style={{ fontSize: '0.85rem' }}>Current role</span>
                              </label>
                            </div>

                            <label style={{ marginBottom: 12 }}>
                              Responsibilities & Achievements (one per line)
                              <textarea
                                className="i"
                                style={{ minHeight: 90 }}
                                value={bulletsInput}
                                onChange={(e) => setBulletsInput(e.target.value)}
                              />
                            </label>

                            <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                              <button type="button" className="btn g xs" onClick={() => setEditingExpId(null)}>
                                Cancel
                              </button>
                              <button
                                type="button"
                                className="btn xs"
                                disabled={!expForm.title.trim()}
                                onClick={() => handleSaveExpCard(item.id)}
                              >
                                Save changes
                              </button>
                            </div>
                          </div>
                        ) : (
                          /* Standard LinkedIn Card View */
                          <div>
                            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <div>
                                <h4 style={{ margin: 0, fontSize: '1.14rem', fontWeight: 700, color: '#0f172a' }}>
                                  {item.title}
                                </h4>
                                <div style={{ marginTop: 4, fontSize: '0.94rem', color: '#334155', fontWeight: 500 }}>
                                  {[item.company, item.location, item.mode].filter(Boolean).join(' · ')}
                                </div>
                                <div style={{ marginTop: 3, fontSize: '0.84rem', color: '#64748b' }}>
                                  {[item.startDate, item.endDate || (item.isCurrent ? 'Present' : '')].filter(Boolean).join(' - ')}
                                </div>
                              </div>
                              <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                                <span
                                  style={{
                                    color: 'var(--blue)',
                                    fontSize: '0.88rem',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    userSelect: 'none',
                                    paddingRight: 4,
                                  }}
                                  onClick={() => alert('Salary insights feature')}
                                  title="Add salary details for this position"
                                >
                                  Add salary
                                </span>
                                <button
                                  type="button"
                                  style={{
                                    border: 'none',
                                    background: 'none',
                                    cursor: 'pointer',
                                    padding: '4px 6px',
                                    fontSize: '1rem',
                                    color: '#64748b',
                                    borderRadius: 4,
                                  }}
                                  onClick={() => startEditCard(item)}
                                  title="Edit position"
                                  aria-label="Edit position"
                                >
                                  ✎
                                </button>
                                <button
                                  type="button"
                                  style={{
                                    border: 'none',
                                    background: 'none',
                                    cursor: 'pointer',
                                    padding: '4px 6px',
                                    fontSize: '1rem',
                                    color: '#94a3b8',
                                    borderRadius: 4,
                                  }}
                                  onClick={() => handleDeleteExpCard(item.id)}
                                  title="Delete position"
                                  aria-label="Delete position"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>

                            {item.bullets.length > 0 && (
                              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #f1f5f9' }}>
                                {item.bullets.map((b, bi) => {
                                  const textClean = b.replace(/^[\u2013\u2014\-*•▪·\s]+/, '').trim();
                                  return (
                                    <p key={bi} style={{ margin: '0 0 6px', color: '#334155', fontSize: '0.92rem', lineHeight: '1.55' }}>
                                      - {textClean}
                                    </p>
                                  );
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              )}

              <label style={{ display: 'flex', gap: 10, alignItems: 'center', marginTop: 10 }}>
                <input
                  type="checkbox"
                  checked={!!draft.confirmed.experience}
                  onChange={(e) => setConfirmed('experience', e.target.checked)}
                />
                This is accurate
              </label>
            </div>
          );
        }

        return (
          <div className="card stack" key={s.key}>
            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ margin: 0 }}>{s.label}</h3>
              {!stored[s.key] ? (
                <span className="badge n">Empty</span>
              ) : stored.confirmed[s.key] ? (
                <span className="badge s">Confirmed</span>
              ) : (
                <span className="badge p">Needs confirmation</span>
              )}
            </div>
            <textarea
              className="i"
              aria-label={s.label}
              value={draft[s.key]}
              onChange={(e) => setField(s.key, e.target.value)}
            />
            <label style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={!!draft.confirmed[s.key]}
                onChange={(e) => setConfirmed(s.key, e.target.checked)}
              />
              This is accurate
            </label>
          </div>
        );
      })}

      <div className="row" style={{ alignItems: 'center' }}>
        <button className="btn" onClick={save}>Save changes</button>
        <span className="msg" role="status">{saved ? 'Saved. Matches were updated.' : ''}</span>
      </div>
      <p className="meta">Saving can change match scores. Resumes you already made keep the version they were built from.</p>
    </div>
  );
}
