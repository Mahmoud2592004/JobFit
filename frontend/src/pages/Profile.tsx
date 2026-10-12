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
  parseEducationToCards,
  serializeCardsToEducation,
  DEFAULT_EDUCATION_CARDS,
  type EducationCardItem,
  parseLeadershipToCards,
  serializeCardsToLeadership,
  type LeadershipCardItem,
  parseProjectsToCards,
  serializeCardsToProjects,
  DEFAULT_PROJECT_CARDS,
  type ProjectCardItem,
  parseCertsToCards,
  serializeCardsToCerts,
  type CertCardItem,
} from '../lib/resumeParser';
import { useApp } from '../store/AppContext';
import { api } from '../api';
import type { Profile as ProfileT, SectionKey, ItemLink } from '../types';

const CONTACT: { key: 'name' | 'email' | 'phone' | 'location' | 'link'; label: string }[] = [
  { key: 'name', label: 'Name' },
  { key: 'email', label: 'Email' },
  { key: 'phone', label: 'Phone' },
  { key: 'location', label: 'Location' },
  { key: 'link', label: 'LinkedIn or portfolio' },
];

function ItemLinksEditor({
  links,
  onChange,
}: {
  links: ItemLink[];
  onChange: (links: ItemLink[]) => void;
}) {
  const addLink = () => {
    onChange([...links, { label: '', url: '' }]);
  };

  const updateLink = (idx: number, patch: Partial<ItemLink>) => {
    const updated = links.map((l, i) => (i === idx ? { ...l, ...patch } : l));
    onChange(updated);
  };

  const removeLink = (idx: number) => {
    onChange(links.filter((_, i) => i !== idx));
  };

  return (
    <div style={{ marginBottom: 12, padding: '10px 12px', background: '#f8fafc', borderRadius: 8, border: '1px solid #e2e8f0' }}>
      <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#334155' }}>
          Attached Links (e.g. Google Play, App Store, GitHub, Demo, Verify)
        </span>
        <button
          type="button"
          className="btn o xs"
          style={{ fontSize: '0.78rem', padding: '2px 8px' }}
          onClick={addLink}
        >
          + Add link
        </button>
      </div>
      {links.length === 0 ? (
        <p className="meta" style={{ fontSize: '0.82rem', margin: 0 }}>
          No attached links. Click "+ Add link" to attach links with custom display text (e.g. "Google Play", "App Store").
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {links.map((link, idx) => (
            <div key={idx} className="row" style={{ gap: 8, alignItems: 'center' }}>
              <input
                className="i"
                style={{ flex: '1 1 140px', padding: '6px 10px', fontSize: '0.85rem' }}
                placeholder="Display text (e.g. Google Play)"
                value={link.label}
                onChange={(e) => updateLink(idx, { label: e.target.value })}
              />
              <input
                className="i"
                style={{ flex: '2 1 220px', padding: '6px 10px', fontSize: '0.85rem' }}
                placeholder="URL (e.g. https://play.google.com/...)"
                value={link.url}
                onChange={(e) => updateLink(idx, { url: e.target.value })}
              />
              <button
                type="button"
                style={{
                  border: 'none',
                  background: 'none',
                  color: '#94a3b8',
                  cursor: 'pointer',
                  padding: '4px 6px',
                  fontSize: '0.95rem',
                }}
                onClick={() => removeLink(idx)}
                title="Remove link"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ItemLinksBadgeView({ links }: { links?: ItemLink[] }) {
  if (!links || links.length === 0) return null;
  return (
    <span style={{ fontWeight: 600, fontSize: '0.88rem', color: 'var(--navy)' }}>
      {' ('}
      {links.map((link, idx) => (
        <span key={idx}>
          {idx > 0 && ' | '}
          <a
            href={link.url.startsWith('http') ? link.url : `https://${link.url}`}
            target="_blank"
            rel="noreferrer"
            style={{ color: 'var(--navy)', textDecoration: 'none', fontWeight: 600 }}
            onMouseEnter={(e) => ((e.target as HTMLElement).style.textDecoration = 'underline')}
            onMouseLeave={(e) => ((e.target as HTMLElement).style.textDecoration = 'none')}
          >
            {link.label || 'Link'}
          </a>
        </span>
      ))}
      {')'}
    </span>
  );
}

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
    leadership: '',
    education: '',
    projects: '',
    certs: '',
    years_experience: undefined,
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
    links: [],
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
                prev.certs.includes('Certification Authority') ||
                prev.experience.includes('(Feb 2024 - Present) (Feb 2024 - Present)');
              if (hasMissing || hasCorrupted) {
                const merged: ProfileT = {
                  ...prev,
                  name: formatted.name || prev.name,
                  email: formatted.email || prev.email,
                  phone: formatted.phone || prev.phone,
                  location: formatted.location || prev.location,
                  link: formatted.link || prev.link,
                  github: formatted.github || prev.github,
                  other_links: formatted.other_links?.length ? formatted.other_links : prev.other_links,
                  summary: formatted.summary || prev.summary,
                  skills: formatted.skills || prev.skills,
                  experience: formatted.experience || prev.experience,
                  leadership: formatted.leadership || prev.leadership || '',
                  education: formatted.education || prev.education,
                  projects: formatted.projects || prev.projects,
                  certs: formatted.certs || prev.certs,
                  years_experience: prev.years_experience !== undefined ? prev.years_experience : formatted.years_experience,
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
      links: card.links || [],
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
      links: [],
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
              links: expForm.links?.length ? expForm.links : undefined,
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
        links: expForm.links?.length ? expForm.links : undefined,
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

  // Structured Education Cards State
  const [eduCards, setEduCards] = useState<EducationCardItem[]>(() => {
    const list = parseEducationToCards(stored.education || draft.education);
    return list.length > 0 ? list : DEFAULT_EDUCATION_CARDS;
  });
  const [editingEduId, setEditingEduId] = useState<string | null>(null);
  const [isAddingEdu, setIsAddingEdu] = useState(false);
  const [showRawEdu, setShowRawEdu] = useState(false);
  const [eduForm, setEduForm] = useState<Omit<EducationCardItem, 'id'>>({
    degree: '',
    institution: '',
    location: '',
    startDate: '',
    endDate: 'Present',
    isCurrent: false,
    gpa: '',
    bullets: [],
    links: [],
  });
  const [eduBulletsInput, setEduBulletsInput] = useState('');

  useEffect(() => {
    setEduCards(parseEducationToCards(draft.education));
  }, [draft.education]);

  const startEditEduCard = (card: EducationCardItem) => {
    setIsAddingEdu(false);
    setEditingEduId(card.id);
    setEduForm({
      degree: card.degree,
      institution: card.institution,
      location: card.location || '',
      startDate: card.startDate || '',
      endDate: card.endDate || '',
      isCurrent: !!card.isCurrent,
      gpa: card.gpa || '',
      bullets: card.bullets,
      links: card.links || [],
    });
    setEduBulletsInput(card.bullets.map((b) => `- ${b}`).join('\n'));
  };

  const startAddEduCard = () => {
    setEditingEduId(null);
    setIsAddingEdu(true);
    setEduForm({
      degree: '',
      institution: '',
      location: draft.location || '',
      startDate: '',
      endDate: '',
      isCurrent: false,
      gpa: '',
      bullets: [],
      links: [],
    });
    setEduBulletsInput('');
  };

  const handleSaveEduCard = (idToSave?: string) => {
    const bullets = eduBulletsInput
      .split(/\r?\n/)
      .map((l) => l.replace(/^[–-—*•▪·\d.)\s]+/, '').trim())
      .filter(Boolean);

    let updated: EducationCardItem[];
    if (idToSave) {
      updated = eduCards.map((c) =>
        c.id === idToSave
          ? {
              ...c,
              ...eduForm,
              endDate: eduForm.isCurrent ? 'Present' : eduForm.endDate,
              bullets,
              links: eduForm.links?.length ? eduForm.links : undefined,
            }
          : c
      );
      setEditingEduId(null);
    } else {
      updated = [
        ...eduCards,
        {
          id: `edu-${Date.now()}`,
          ...eduForm,
          endDate: eduForm.isCurrent ? 'Present' : eduForm.endDate,
          bullets,
          links: eduForm.links?.length ? eduForm.links : undefined,
        },
      ];
      setIsAddingEdu(false);
    }
    setEduCards(updated);
    const serialized = serializeCardsToEducation(updated);
    setDraft((d) => ({
      ...d,
      education: serialized,
      confirmed: { ...d.confirmed, education: true },
    }));
    setSaved(false);
  };

  const handleDeleteEduCard = (idToDelete: string) => {
    const updated = eduCards.filter((c) => c.id !== idToDelete);
    setEduCards(updated);
    const serialized = serializeCardsToEducation(updated);
    setDraft((d) => ({ ...d, education: serialized }));
    setSaved(false);
  };

  // Structured Leadership & Volunteering Cards State
  const [leadCards, setLeadCards] = useState<LeadershipCardItem[]>(() => {
    return parseLeadershipToCards(stored.leadership || draft.leadership);
  });
  const [editingLeadId, setEditingLeadId] = useState<string | null>(null);
  const [isAddingLead, setIsAddingLead] = useState(false);
  const [showRawLead, setShowRawLead] = useState(false);
  const [leadForm, setLeadForm] = useState<Omit<LeadershipCardItem, 'id'>>({
    title: '',
    organization: '',
    location: '',
    startDate: '',
    endDate: 'Present',
    isCurrent: true,
    bullets: [],
    links: [],
  });
  const [leadBulletsInput, setLeadBulletsInput] = useState('');

  useEffect(() => {
    setLeadCards(parseLeadershipToCards(draft.leadership));
  }, [draft.leadership]);

  const startEditLeadCard = (card: LeadershipCardItem) => {
    setIsAddingLead(false);
    setEditingLeadId(card.id);
    setLeadForm({
      title: card.title,
      organization: card.organization,
      location: card.location || '',
      startDate: card.startDate || '',
      endDate: card.endDate || '',
      isCurrent: !!card.isCurrent,
      bullets: card.bullets,
      links: card.links || [],
    });
    setLeadBulletsInput(card.bullets.map((b) => `- ${b}`).join('\n'));
  };

  const startAddLeadCard = () => {
    setEditingLeadId(null);
    setIsAddingLead(true);
    setLeadForm({
      title: '',
      organization: '',
      location: draft.location || '',
      startDate: '',
      endDate: 'Present',
      isCurrent: true,
      bullets: [],
      links: [],
    });
    setLeadBulletsInput('');
  };

  const handleSaveLeadCard = (idToSave?: string) => {
    const bullets = leadBulletsInput
      .split(/\r?\n/)
      .map((l) => l.replace(/^[–-—*•▪·\d.)\s]+/, '').trim())
      .filter(Boolean);

    let updated: LeadershipCardItem[];
    if (idToSave) {
      updated = leadCards.map((c) =>
        c.id === idToSave
          ? {
              ...c,
              ...leadForm,
              endDate: leadForm.isCurrent ? 'Present' : leadForm.endDate,
              bullets,
              links: leadForm.links?.length ? leadForm.links : undefined,
            }
          : c
      );
      setEditingLeadId(null);
    } else {
      updated = [
        ...leadCards,
        {
          id: `lead-${Date.now()}`,
          ...leadForm,
          endDate: leadForm.isCurrent ? 'Present' : leadForm.endDate,
          bullets,
          links: leadForm.links?.length ? leadForm.links : undefined,
        },
      ];
      setIsAddingLead(false);
    }
    setLeadCards(updated);
    const serialized = serializeCardsToLeadership(updated);
    setDraft((d) => ({
      ...d,
      leadership: serialized,
      confirmed: { ...d.confirmed, leadership: true },
    }));
    setSaved(false);
  };

  const handleDeleteLeadCard = (idToDelete: string) => {
    const updated = leadCards.filter((c) => c.id !== idToDelete);
    setLeadCards(updated);
    const serialized = serializeCardsToLeadership(updated);
    setDraft((d) => ({ ...d, leadership: serialized }));
    setSaved(false);
  };

  // Structured Certification Cards State
  const [certCards, setCertCards] = useState<CertCardItem[]>(() => {
    return parseCertsToCards(stored.certs || draft.certs);
  });
  const [editingCertId, setEditingCertId] = useState<string | null>(null);
  const [isAddingCert, setIsAddingCert] = useState(false);
  const [showRawCert, setShowRawCert] = useState(false);
  const [certForm, setCertForm] = useState<Omit<CertCardItem, 'id'>>({
    name: '',
    authority: '',
    links: [],
  });

  useEffect(() => {
    setCertCards(parseCertsToCards(draft.certs));
  }, [draft.certs]);

  const startEditCertCard = (card: CertCardItem) => {
    setIsAddingCert(false);
    setEditingCertId(card.id);
    setCertForm({
      name: card.name,
      authority: card.authority || '',
      links: card.links || [],
    });
  };

  const startAddCertCard = () => {
    setEditingCertId(null);
    setIsAddingCert(true);
    setCertForm({
      name: '',
      authority: '',
      links: [],
    });
  };

  const handleSaveCertCard = (idToSave?: string) => {
    let updated: CertCardItem[];
    if (idToSave) {
      updated = certCards.map((c) =>
        c.id === idToSave
          ? {
              ...c,
              ...certForm,
              links: certForm.links?.length ? certForm.links : undefined,
            }
          : c
      );
      setEditingCertId(null);
    } else {
      updated = [
        ...certCards,
        {
          id: `cert-${Date.now()}`,
          ...certForm,
          links: certForm.links?.length ? certForm.links : undefined,
        },
      ];
      setIsAddingCert(false);
    }
    setCertCards(updated);
    const serialized = serializeCardsToCerts(updated);
    setDraft((d) => ({
      ...d,
      certs: serialized,
      confirmed: { ...d.confirmed, certs: true },
    }));
    setSaved(false);
  };

  const handleDeleteCertCard = (idToDelete: string) => {
    const updated = certCards.filter((c) => c.id !== idToDelete);
    setCertCards(updated);
    const serialized = serializeCardsToCerts(updated);
    setDraft((d) => ({ ...d, certs: serialized }));
    setSaved(false);
  };

  // Structured Project Cards State
  const [projCards, setProjCards] = useState<ProjectCardItem[]>(() => {
    const list = parseProjectsToCards(stored.projects || draft.projects);
    return list.length > 0 ? list : DEFAULT_PROJECT_CARDS;
  });
  const [editingProjId, setEditingProjId] = useState<string | null>(null);
  const [isAddingProj, setIsAddingProj] = useState(false);
  const [showRawProj, setShowRawProj] = useState(false);
  const [projForm, setProjForm] = useState<Omit<ProjectCardItem, 'id'>>({
    title: '',
    roleOrSubtitle: '',
    technologies: '',
    link: '',
    date: '',
    bullets: [],
    links: [],
  });
  const [projBulletsInput, setProjBulletsInput] = useState('');

  useEffect(() => {
    setProjCards(parseProjectsToCards(draft.projects));
  }, [draft.projects]);

  const startEditProjCard = (card: ProjectCardItem) => {
    setIsAddingProj(false);
    setEditingProjId(card.id);
    setProjForm({
      title: card.title,
      roleOrSubtitle: card.roleOrSubtitle || '',
      technologies: card.technologies || '',
      link: card.link || '',
      date: card.date || '',
      bullets: card.bullets,
      links: card.links || [],
    });
    setProjBulletsInput(card.bullets.map((b) => `- ${b}`).join('\n'));
  };

  const startAddProjCard = () => {
    setEditingProjId(null);
    setIsAddingProj(true);
    setProjForm({
      title: '',
      roleOrSubtitle: '',
      technologies: '',
      link: '',
      date: '',
      bullets: [],
      links: [],
    });
    setProjBulletsInput('');
  };

  const handleSaveProjCard = (idToSave?: string) => {
    const bullets = projBulletsInput
      .split(/\r?\n/)
      .map((l) => l.replace(/^[–-—*•▪·\d.)\s]+/, '').trim())
      .filter(Boolean);

    let updated: ProjectCardItem[];
    if (idToSave) {
      updated = projCards.map((c) =>
        c.id === idToSave
          ? {
              ...c,
              ...projForm,
              bullets,
              links: projForm.links?.length ? projForm.links : undefined,
            }
          : c
      );
      setEditingProjId(null);
    } else {
      updated = [
        ...projCards,
        {
          id: `proj-${Date.now()}`,
          ...projForm,
          bullets,
          links: projForm.links?.length ? projForm.links : undefined,
        },
      ];
      setIsAddingProj(false);
    }
    setProjCards(updated);
    const serialized = serializeCardsToProjects(updated);
    setDraft((d) => ({
      ...d,
      projects: serialized,
      confirmed: { ...d.confirmed, projects: true },
    }));
    setSaved(false);
  };

  const handleDeleteProjCard = (idToDelete: string) => {
    const updated = projCards.filter((c) => c.id !== idToDelete);
    setProjCards(updated);
    const serialized = serializeCardsToProjects(updated);
    setDraft((d) => ({ ...d, projects: serialized }));
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
          github: parsed.github || draft.github,
          other_links: parsed.other_links?.length ? parsed.other_links : draft.other_links,
          summary: parsed.summary || draft.summary,
          skills: parsed.skills || draft.skills,
          experience: parsed.experience || draft.experience,
          leadership: parsed.leadership || draft.leadership || '',
          education: parsed.education || draft.education,
          projects: parsed.projects || draft.projects,
          certs: parsed.certs || draft.certs,
          confirmed: {
            summary: !!(parsed.summary || draft.summary),
            skills: !!(parsed.skills || draft.skills),
            experience: !!(parsed.experience || draft.experience),
            leadership: !!(parsed.leadership || draft.leadership),
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
      contact_phone: full.phone,
      phone: full.phone,
      location: full.location,
      linkedin_url: full.link,
      linkedin: full.link,
      years_experience: full.years_experience !== undefined && full.years_experience !== null ? Number(full.years_experience) : null,
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
        <h3 style={{ marginBottom: 10 }}>Contact & Professional Background</h3>
        <div className="row">
          {CONTACT.slice(0, 2).map((c) => <label key={c.key} style={{ flex: 1 }}>{c.label}<input className="i" value={draft[c.key]} onChange={(e) => setField(c.key, e.target.value)} /></label>)}
        </div>
        <div className="row" style={{ marginTop: 10 }}>
          {CONTACT.slice(2, 4).map((c) => <label key={c.key} style={{ flex: 1 }}>{c.label}<input className="i" value={draft[c.key]} onChange={(e) => setField(c.key, e.target.value)} /></label>)}
        </div>
        <div className="row" style={{ marginTop: 10, gap: 12 }}>
          <label style={{ flex: 1 }}>
            LinkedIn URL
            <input className="i" placeholder="https://linkedin.com/in/username" value={draft.link} onChange={(e) => setField('link', e.target.value)} />
          </label>
          <label style={{ flex: 1 }}>
            GitHub URL
            <input
              className="i"
              placeholder="https://github.com/username"
              value={draft.github || ''}
              onChange={(e) => {
                setDraft((d) => ({ ...d, github: e.target.value }));
                setSaved(false);
              }}
            />
          </label>
          <label style={{ flex: 1 }}>
            Years of Experience
            <input
              className="i"
              type="number"
              step="0.5"
              min="0"
              max="50"
              placeholder="e.g. 1.5"
              value={draft.years_experience !== undefined && draft.years_experience !== null ? draft.years_experience : ''}
              onChange={(e) => {
                const val = e.target.value === '' ? undefined : Number(e.target.value);
                setDraft((d) => ({ ...d, years_experience: val }));
                setSaved(false);
              }}
            />
          </label>
        </div>
        {/* Additional Links */}
        <div style={{ marginTop: 12 }}>
          <label>
            Additional Links (Portfolio, App Store, Project Repositories)
            <input
              className="i"
              placeholder="Comma-separated URLs"
              value={Array.isArray(draft.other_links) ? draft.other_links.join(', ') : (draft.other_links || '')}
              onChange={(e) => {
                const linksArr = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                setDraft((d) => ({ ...d, other_links: linksArr }));
                setSaved(false);
              }}
            />
          </label>
          {Array.isArray(draft.other_links) && draft.other_links.length > 0 && (
            <div className="row" style={{ gap: 8, marginTop: 8, flexWrap: 'wrap' }}>
              {draft.other_links.map((link, idx) => (
                <a
                  key={idx}
                  href={link.startsWith('http') ? link : `https://${link}`}
                  target="_blank"
                  rel="noreferrer"
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    fontSize: '0.82rem',
                    background: '#f1f5f9',
                    padding: '3px 8px',
                    borderRadius: 6,
                    color: 'var(--blue)',
                    textDecoration: 'none',
                    border: '1px solid #cbd5e1',
                  }}
                >
                  🔗 {link.length > 45 ? link.slice(0, 42) + '...' : link}
                </a>
              ))}
            </div>
          )}
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

                      <ItemLinksEditor
                        links={expForm.links || []}
                        onChange={(links) => setExpForm({ ...expForm, links })}
                      />

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

                            <ItemLinksEditor
                              links={expForm.links || []}
                              onChange={(links) => setExpForm({ ...expForm, links })}
                            />

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
                                  <span>{item.company}</span>
                                  <ItemLinksBadgeView links={item.links} />
                                  {[item.location, item.mode].filter(Boolean).length > 0 && (
                                    <span> · {[item.location, item.mode].filter(Boolean).join(' · ')}</span>
                                  )}
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

        if (s.key === 'education') {
          return (
            <div className="card stack" key={s.key} style={{ gap: 14 }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>{s.label}</h3>
                  <button
                    type="button"
                    className="btn g xs"
                    style={{ fontSize: '0.8rem', padding: '3px 8px' }}
                    onClick={() => setShowRawEdu(!showRawEdu)}
                  >
                    {showRawEdu ? 'View cards' : 'Edit raw text'}
                  </button>
                </div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  {!isAddingEdu && !showRawEdu && (
                    <button type="button" className="btn xs" onClick={startAddEduCard}>
                      + Add education
                    </button>
                  )}
                  {!stored[s.key] ? (
                    <span className="badge n">Empty</span>
                  ) : stored.confirmed[s.key] ? (
                    <span className="badge s">Confirmed</span>
                  ) : (
                    <span className="badge p">Needs confirmation</span>
                  )}
                </div>
              </div>

              {showRawEdu ? (
                <textarea
                  className="i"
                  style={{ minHeight: 140 }}
                  aria-label={s.label}
                  value={draft.education}
                  onChange={(e) => setField('education', e.target.value)}
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {isAddingEdu && (
                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 10, padding: 16 }}>
                      <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>
                        Add education
                      </h4>
                      <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                        <label style={{ flex: 1 }}>
                          Degree / Qualification *
                          <input
                            className="i"
                            placeholder="e.g. Bachelor of Science in Computer Science"
                            value={eduForm.degree}
                            onChange={(e) => setEduForm({ ...eduForm, degree: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          School / University *
                          <input
                            className="i"
                            placeholder="e.g. Cairo University, Faculty of Computers"
                            value={eduForm.institution}
                            onChange={(e) => setEduForm({ ...eduForm, institution: e.target.value })}
                          />
                        </label>
                      </div>

                      <div className="row" style={{ gap: 10, marginBottom: 10, alignItems: 'flex-end' }}>
                        <label style={{ flex: 1 }}>
                          Start date
                          <input
                            className="i"
                            placeholder="e.g. 2020"
                            value={eduForm.startDate}
                            onChange={(e) => setEduForm({ ...eduForm, startDate: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          End date
                          <input
                            className="i"
                            placeholder="e.g. 2024 or Present"
                            disabled={eduForm.isCurrent}
                            value={eduForm.isCurrent ? 'Present' : eduForm.endDate}
                            onChange={(e) => setEduForm({ ...eduForm, endDate: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          GPA / Grade
                          <input
                            className="i"
                            placeholder="e.g. 3.8 / 4.0 or Excellent"
                            value={eduForm.gpa}
                            onChange={(e) => setEduForm({ ...eduForm, gpa: e.target.value })}
                          />
                        </label>
                      </div>

                      <label style={{ marginBottom: 12 }}>
                        Highlights & Achievements (one per line)
                        <textarea
                          className="i"
                          style={{ minHeight: 80 }}
                          placeholder="- Graduation Project: AI Healthcare System (Grade: Excellent)&#10;- Coursework: Machine Learning, NLP, Distributed Systems"
                          value={eduBulletsInput}
                          onChange={(e) => setEduBulletsInput(e.target.value)}
                        />
                      </label>

                      <ItemLinksEditor
                        links={eduForm.links || []}
                        onChange={(links) => setEduForm({ ...eduForm, links })}
                      />

                      <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                        <button type="button" className="btn g xs" onClick={() => setIsAddingEdu(false)}>
                          Cancel
                        </button>
                        <button
                          type="button"
                          className="btn xs"
                          disabled={!eduForm.degree.trim() || !eduForm.institution.trim()}
                          onClick={() => handleSaveEduCard()}
                        >
                          Save education
                        </button>
                      </div>
                    </div>
                  )}

                  {eduCards.length === 0 && !isAddingEdu ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1' }}>
                      <p className="meta" style={{ margin: '0 0 10px' }}>No education entries recorded yet.</p>
                      <button type="button" className="btn xs" onClick={startAddEduCard}>
                        + Add education
                      </button>
                    </div>
                  ) : (
                    eduCards.map((item) => (
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
                        {editingEduId === item.id ? (
                          <div>
                            <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>Edit education</h4>
                            <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                              <label style={{ flex: 1 }}>
                                Degree *
                                <input
                                  className="i"
                                  value={eduForm.degree}
                                  onChange={(e) => setEduForm({ ...eduForm, degree: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                School / University *
                                <input
                                  className="i"
                                  value={eduForm.institution}
                                  onChange={(e) => setEduForm({ ...eduForm, institution: e.target.value })}
                                />
                              </label>
                            </div>

                            <div className="row" style={{ gap: 10, marginBottom: 10, alignItems: 'flex-end' }}>
                              <label style={{ flex: 1 }}>
                                Start date
                                <input
                                  className="i"
                                  value={eduForm.startDate}
                                  onChange={(e) => setEduForm({ ...eduForm, startDate: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                End date
                                <input
                                  className="i"
                                  disabled={eduForm.isCurrent}
                                  value={eduForm.isCurrent ? 'Present' : eduForm.endDate}
                                  onChange={(e) => setEduForm({ ...eduForm, endDate: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                GPA / Grade
                                <input
                                  className="i"
                                  value={eduForm.gpa}
                                  onChange={(e) => setEduForm({ ...eduForm, gpa: e.target.value })}
                                />
                              </label>
                            </div>

                            <label style={{ marginBottom: 12 }}>
                              Highlights & Achievements (one per line)
                              <textarea
                                className="i"
                                style={{ minHeight: 80 }}
                                value={eduBulletsInput}
                                onChange={(e) => setEduBulletsInput(e.target.value)}
                              />
                            </label>

                            <ItemLinksEditor
                              links={eduForm.links || []}
                              onChange={(links) => setEduForm({ ...eduForm, links })}
                            />

                            <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                              <button type="button" className="btn g xs" onClick={() => setEditingEduId(null)}>Cancel</button>
                              <button
                                type="button"
                                className="btn xs"
                                disabled={!eduForm.degree.trim()}
                                onClick={() => handleSaveEduCard(item.id)}
                              >
                                Save changes
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <div>
                                <h4 style={{ margin: 0, fontSize: '1.14rem', fontWeight: 700, color: '#0f172a' }}>
                                  {item.degree}
                                </h4>
                                <div style={{ marginTop: 4, fontSize: '0.94rem', color: '#334155', fontWeight: 500 }}>
                                  <span>{item.institution}</span>
                                  <ItemLinksBadgeView links={item.links} />
                                </div>
                                <div style={{ marginTop: 3, fontSize: '0.84rem', color: '#64748b' }}>
                                  {[
                                    [item.startDate, item.endDate || (item.isCurrent ? 'Present' : '')].filter(Boolean).join(' - '),
                                    item.gpa ? `GPA: ${item.gpa}` : '',
                                    item.location,
                                  ].filter(Boolean).join(' · ')}
                                </div>
                              </div>
                              <div className="row" style={{ gap: 8 }}>
                                <button
                                  type="button"
                                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#64748b' }}
                                  onClick={() => startEditEduCard(item)}
                                  title="Edit education"
                                >
                                  ✎
                                </button>
                                <button
                                  type="button"
                                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#94a3b8' }}
                                  onClick={() => handleDeleteEduCard(item.id)}
                                  title="Delete education"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                            {item.bullets.length > 0 && (
                              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #f1f5f9' }}>
                                {item.bullets.map((b, bi) => (
                                  <p key={bi} style={{ margin: '0 0 6px', color: '#334155', fontSize: '0.92rem', lineHeight: '1.55' }}>
                                    - {b.replace(/^[-•*▪·\s]+/, '').trim()}
                                  </p>
                                ))}
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
                  checked={!!draft.confirmed.education}
                  onChange={(e) => setConfirmed('education', e.target.checked)}
                />
                This is accurate
              </label>
            </div>
          );
        }

        if (s.key === 'leadership') {
          return (
            <div className="card stack" key={s.key} style={{ gap: 14 }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>{s.label}</h3>
                  <button
                    type="button"
                    className="btn g xs"
                    style={{ fontSize: '0.8rem', padding: '3px 8px' }}
                    onClick={() => setShowRawLead(!showRawLead)}
                  >
                    {showRawLead ? 'View cards' : 'Edit raw text'}
                  </button>
                </div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  {!isAddingLead && !showRawLead && (
                    <button type="button" className="btn xs" onClick={startAddLeadCard}>
                      + Add leadership role
                    </button>
                  )}
                  {!stored[s.key] ? (
                    <span className="badge n">Empty</span>
                  ) : stored.confirmed[s.key] ? (
                    <span className="badge s">Confirmed</span>
                  ) : (
                    <span className="badge p">Needs confirmation</span>
                  )}
                </div>
              </div>

              {showRawLead ? (
                <textarea
                  className="i"
                  style={{ minHeight: 140 }}
                  aria-label={s.label}
                  value={draft.leadership}
                  onChange={(e) => setField('leadership', e.target.value)}
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {isAddingLead && (
                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 10, padding: 16 }}>
                      <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>
                        Add leadership / community role
                      </h4>
                      <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                        <label style={{ flex: 1 }}>
                          Role Title *
                          <input
                            className="i"
                            placeholder="e.g. Head of AI and ML Community"
                            value={leadForm.title}
                            onChange={(e) => setLeadForm({ ...leadForm, title: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          Organization *
                          <input
                            className="i"
                            placeholder="e.g. IEEE Computer Society - EJUST"
                            value={leadForm.organization}
                            onChange={(e) => setLeadForm({ ...leadForm, organization: e.target.value })}
                          />
                        </label>
                      </div>

                      <div className="row" style={{ gap: 10, marginBottom: 10, alignItems: 'flex-end' }}>
                        <label style={{ flex: 1 }}>
                          Location
                          <input
                            className="i"
                            placeholder="e.g. Alexandria, Egypt"
                            value={leadForm.location}
                            onChange={(e) => setLeadForm({ ...leadForm, location: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          Start date / Year
                          <input
                            className="i"
                            placeholder="e.g. 2024"
                            value={leadForm.startDate}
                            onChange={(e) => setLeadForm({ ...leadForm, startDate: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          End date / Year
                          <input
                            className="i"
                            placeholder="e.g. 2025 or Present"
                            disabled={leadForm.isCurrent}
                            value={leadForm.isCurrent ? 'Present' : leadForm.endDate}
                            onChange={(e) => setLeadForm({ ...leadForm, endDate: e.target.value })}
                          />
                        </label>
                        <label style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8, cursor: 'pointer' }}>
                          <input
                            type="checkbox"
                            checked={leadForm.isCurrent}
                            onChange={(e) => setLeadForm({ ...leadForm, isCurrent: e.target.checked, endDate: e.target.checked ? 'Present' : '' })}
                          />
                          <span style={{ fontSize: '0.85rem' }}>Current role</span>
                        </label>
                      </div>

                      <label style={{ marginBottom: 12 }}>
                        Key Achievements & Responsibilities (one per line)
                        <textarea
                          className="i"
                          style={{ minHeight: 80 }}
                          placeholder="- Spearheaded a 10-member team mentoring 100+ students in AI/ML...&#10;- Organized 6+ hands-on technical workshops..."
                          value={leadBulletsInput}
                          onChange={(e) => setLeadBulletsInput(e.target.value)}
                        />
                      </label>

                      <ItemLinksEditor
                        links={leadForm.links || []}
                        onChange={(links) => setLeadForm({ ...leadForm, links })}
                      />

                      <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                        <button type="button" className="btn g xs" onClick={() => setIsAddingLead(false)}>
                          Cancel
                        </button>
                        <button
                          type="button"
                          className="btn xs"
                          disabled={!leadForm.title.trim()}
                          onClick={() => handleSaveLeadCard()}
                        >
                          Save role
                        </button>
                      </div>
                    </div>
                  )}

                  {leadCards.length === 0 && !isAddingLead ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1' }}>
                      <p className="meta" style={{ margin: '0 0 10px' }}>No leadership or volunteering roles recorded yet.</p>
                      <button type="button" className="btn xs" onClick={startAddLeadCard}>
                        + Add leadership role
                      </button>
                    </div>
                  ) : (
                    leadCards.map((item) => (
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
                        {editingLeadId === item.id ? (
                          <div>
                            <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>Edit leadership role</h4>
                            <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                              <label style={{ flex: 1 }}>
                                Title *
                                <input
                                  className="i"
                                  value={leadForm.title}
                                  onChange={(e) => setLeadForm({ ...leadForm, title: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                Organization *
                                <input
                                  className="i"
                                  value={leadForm.organization}
                                  onChange={(e) => setLeadForm({ ...leadForm, organization: e.target.value })}
                                />
                              </label>
                            </div>

                            <div className="row" style={{ gap: 10, marginBottom: 10, alignItems: 'flex-end' }}>
                              <label style={{ flex: 1 }}>
                                Location
                                <input
                                  className="i"
                                  value={leadForm.location}
                                  onChange={(e) => setLeadForm({ ...leadForm, location: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                Start date
                                <input
                                  className="i"
                                  value={leadForm.startDate}
                                  onChange={(e) => setLeadForm({ ...leadForm, startDate: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                End date
                                <input
                                  className="i"
                                  disabled={leadForm.isCurrent}
                                  value={leadForm.isCurrent ? 'Present' : leadForm.endDate}
                                  onChange={(e) => setLeadForm({ ...leadForm, endDate: e.target.value })}
                                />
                              </label>
                              <label style={{ display: 'flex', gap: 6, alignItems: 'center', marginBottom: 8, cursor: 'pointer' }}>
                                <input
                                  type="checkbox"
                                  checked={leadForm.isCurrent}
                                  onChange={(e) => setLeadForm({ ...leadForm, isCurrent: e.target.checked, endDate: e.target.checked ? 'Present' : '' })}
                                />
                                <span style={{ fontSize: '0.85rem' }}>Current role</span>
                              </label>
                            </div>

                            <label style={{ marginBottom: 12 }}>
                              Achievements & Responsibilities (one per line)
                              <textarea
                                className="i"
                                style={{ minHeight: 80 }}
                                value={leadBulletsInput}
                                onChange={(e) => setLeadBulletsInput(e.target.value)}
                              />
                            </label>

                            <ItemLinksEditor
                              links={leadForm.links || []}
                              onChange={(links) => setLeadForm({ ...leadForm, links })}
                            />

                            <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                              <button type="button" className="btn g xs" onClick={() => setEditingLeadId(null)}>Cancel</button>
                              <button
                                type="button"
                                className="btn xs"
                                disabled={!leadForm.title.trim()}
                                onClick={() => handleSaveLeadCard(item.id)}
                              >
                                Save changes
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <div>
                                <h4 style={{ margin: 0, fontSize: '1.14rem', fontWeight: 700, color: '#0f172a' }}>
                                  {item.title}
                                </h4>
                                <div style={{ marginTop: 4, fontSize: '0.94rem', color: '#334155', fontWeight: 500 }}>
                                  <span>{item.organization}</span>
                                  <ItemLinksBadgeView links={item.links} />
                                </div>
                                <div style={{ marginTop: 3, fontSize: '0.84rem', color: '#64748b' }}>
                                  {[
                                    [item.startDate, item.endDate || (item.isCurrent ? 'Present' : '')].filter(Boolean).join(' - '),
                                    item.location,
                                  ].filter(Boolean).join(' · ')}
                                </div>
                              </div>
                              <div className="row" style={{ gap: 8 }}>
                                <button
                                  type="button"
                                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#64748b' }}
                                  onClick={() => startEditLeadCard(item)}
                                  title="Edit role"
                                >
                                  ✎
                                </button>
                                <button
                                  type="button"
                                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#94a3b8' }}
                                  onClick={() => handleDeleteLeadCard(item.id)}
                                  title="Delete role"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                            {item.bullets.length > 0 && (
                              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #f1f5f9' }}>
                                {item.bullets.map((b, bi) => (
                                  <p key={bi} style={{ margin: '0 0 6px', color: '#334155', fontSize: '0.92rem', lineHeight: '1.55' }}>
                                    - {b.replace(/^[-•*▪·\s]+/, '').trim()}
                                  </p>
                                ))}
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
                  checked={!!draft.confirmed.leadership}
                  onChange={(e) => setConfirmed('leadership', e.target.checked)}
                />
                This is accurate
              </label>
            </div>
          );
        }

        if (s.key === 'projects') {
          return (
            <div className="card stack" key={s.key} style={{ gap: 14 }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>{s.label}</h3>
                  <button
                    type="button"
                    className="btn g xs"
                    style={{ fontSize: '0.8rem', padding: '3px 8px' }}
                    onClick={() => setShowRawProj(!showRawProj)}
                  >
                    {showRawProj ? 'View cards' : 'Edit raw text'}
                  </button>
                </div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  {!isAddingProj && !showRawProj && (
                    <button type="button" className="btn xs" onClick={startAddProjCard}>
                      + Add project
                    </button>
                  )}
                  {!stored[s.key] ? (
                    <span className="badge n">Empty</span>
                  ) : stored.confirmed[s.key] ? (
                    <span className="badge s">Confirmed</span>
                  ) : (
                    <span className="badge p">Needs confirmation</span>
                  )}
                </div>
              </div>

              {showRawProj ? (
                <textarea
                  className="i"
                  style={{ minHeight: 140 }}
                  aria-label={s.label}
                  value={draft.projects}
                  onChange={(e) => setField('projects', e.target.value)}
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {isAddingProj && (
                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 10, padding: 16 }}>
                      <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>
                        Add project
                      </h4>
                      <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                        <label style={{ flex: 1 }}>
                          Project Title *
                          <input
                            className="i"
                            placeholder="e.g. MedDigi-Verse Assistant, JobFit Autonomous Agent"
                            value={projForm.title}
                            onChange={(e) => setProjForm({ ...projForm, title: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          Role or Subtitle
                          <input
                            className="i"
                            placeholder="e.g. Lead AI Engineer, Open-source Creator"
                            value={projForm.roleOrSubtitle}
                            onChange={(e) => setProjForm({ ...projForm, roleOrSubtitle: e.target.value })}
                          />
                        </label>
                      </div>

                      <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                        <label style={{ flex: 2 }}>
                          Technologies & Frameworks
                          <input
                            className="i"
                            placeholder="e.g. React, TypeScript, FastAPI, Gemini LLM, Supabase"
                            value={projForm.technologies}
                            onChange={(e) => setProjForm({ ...projForm, technologies: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          Date / Period
                          <input
                            className="i"
                            placeholder="e.g. 2024 - Present"
                            value={projForm.date}
                            onChange={(e) => setProjForm({ ...projForm, date: e.target.value })}
                          />
                        </label>
                      </div>

                      <label style={{ marginBottom: 10 }}>
                        Link / URL (Optional)
                        <input
                          className="i"
                          placeholder="e.g. github.com/Mahmoud2592004/JobFit or demo app link"
                          value={projForm.link}
                          onChange={(e) => setProjForm({ ...projForm, link: e.target.value })}
                        />
                      </label>

                      <label style={{ marginBottom: 12 }}>
                        Key Highlights & Responsibilities (one per line)
                        <textarea
                          className="i"
                          style={{ minHeight: 80 }}
                          placeholder="- Architected multi-role simulation system with FastAPI and Supabase...&#10;- Integrated Gemini LLM reasoning for automated ATS candidate evaluation..."
                          value={projBulletsInput}
                          onChange={(e) => setProjBulletsInput(e.target.value)}
                        />
                      </label>

                      <ItemLinksEditor
                        links={projForm.links || []}
                        onChange={(links) => setProjForm({ ...projForm, links })}
                      />

                      <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                        <button type="button" className="btn g xs" onClick={() => setIsAddingProj(false)}>
                          Cancel
                        </button>
                        <button
                          type="button"
                          className="btn xs"
                          disabled={!projForm.title.trim()}
                          onClick={() => handleSaveProjCard()}
                        >
                          Save project
                        </button>
                      </div>
                    </div>
                  )}

                  {projCards.length === 0 && !isAddingProj ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1' }}>
                      <p className="meta" style={{ margin: '0 0 10px' }}>No project entries recorded yet.</p>
                      <button type="button" className="btn xs" onClick={startAddProjCard}>
                        + Add project
                      </button>
                    </div>
                  ) : (
                    projCards.map((item) => (
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
                        {editingProjId === item.id ? (
                          <div>
                            <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>Edit project</h4>
                            <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                              <label style={{ flex: 1 }}>
                                Title *
                                <input
                                  className="i"
                                  value={projForm.title}
                                  onChange={(e) => setProjForm({ ...projForm, title: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                Role or Subtitle
                                <input
                                  className="i"
                                  value={projForm.roleOrSubtitle}
                                  onChange={(e) => setProjForm({ ...projForm, roleOrSubtitle: e.target.value })}
                                />
                              </label>
                            </div>

                            <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                              <label style={{ flex: 2 }}>
                                Technologies
                                <input
                                  className="i"
                                  value={projForm.technologies}
                                  onChange={(e) => setProjForm({ ...projForm, technologies: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                Date / Period
                                <input
                                  className="i"
                                  value={projForm.date}
                                  onChange={(e) => setProjForm({ ...projForm, date: e.target.value })}
                                />
                              </label>
                            </div>

                            <label style={{ marginBottom: 10 }}>
                              Link / URL
                              <input
                                className="i"
                                value={projForm.link}
                                onChange={(e) => setProjForm({ ...projForm, link: e.target.value })}
                              />
                            </label>

                            <label style={{ marginBottom: 12 }}>
                              Key Highlights & Responsibilities (one per line)
                              <textarea
                                className="i"
                                style={{ minHeight: 80 }}
                                value={projBulletsInput}
                                onChange={(e) => setProjBulletsInput(e.target.value)}
                              />
                            </label>

                            <ItemLinksEditor
                              links={projForm.links || []}
                              onChange={(links) => setProjForm({ ...projForm, links })}
                            />

                            <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                              <button type="button" className="btn g xs" onClick={() => setEditingProjId(null)}>Cancel</button>
                              <button
                                type="button"
                                className="btn xs"
                                disabled={!projForm.title.trim()}
                                onClick={() => handleSaveProjCard(item.id)}
                              >
                                Save changes
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <div>
                                <h4 style={{ margin: 0, fontSize: '1.14rem', fontWeight: 700, color: '#0f172a' }}>
                                  <span>{item.title}</span>
                                  <ItemLinksBadgeView links={item.links} />
                                </h4>
                                <div style={{ marginTop: 4, fontSize: '0.94rem', color: '#334155', fontWeight: 500 }}>
                                  {[item.roleOrSubtitle, item.technologies ? `[${item.technologies}]` : ''].filter(Boolean).join(' · ')}
                                </div>
                                <div style={{ marginTop: 3, fontSize: '0.84rem', color: '#64748b' }}>
                                  {[
                                    item.date,
                                    item.link && (!item.links || item.links.length === 0) ? (
                                      <a
                                        key="link"
                                        href={item.link.startsWith('http') ? item.link : `https://${item.link}`}
                                        target="_blank"
                                        rel="noreferrer"
                                        style={{ color: 'var(--blue)', textDecoration: 'underline' }}
                                      >
                                        {item.link}
                                      </a>
                                    ) : null,
                                  ].filter(Boolean).map((el, i) => (
                                    <span key={i}>{i > 0 ? ' · ' : ''}{el}</span>
                                  ))}
                                </div>
                              </div>
                              <div className="row" style={{ gap: 8 }}>
                                <button
                                  type="button"
                                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#64748b' }}
                                  onClick={() => startEditProjCard(item)}
                                  title="Edit project"
                                >
                                  ✎
                                </button>
                                <button
                                  type="button"
                                  style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#94a3b8' }}
                                  onClick={() => handleDeleteProjCard(item.id)}
                                  title="Delete project"
                                >
                                  ✕
                                </button>
                              </div>
                            </div>
                            {item.bullets.length > 0 && (
                              <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px solid #f1f5f9' }}>
                                {item.bullets.map((b, bi) => (
                                  <p key={bi} style={{ margin: '0 0 6px', color: '#334155', fontSize: '0.92rem', lineHeight: '1.55' }}>
                                    - {b.replace(/^[-•*▪·\s]+/, '').trim()}
                                  </p>
                                ))}
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
                  checked={!!draft.confirmed.projects}
                  onChange={(e) => setConfirmed('projects', e.target.checked)}
                />
                This is accurate
              </label>
            </div>
          );
        }

        if (s.key === 'certs') {
          return (
            <div className="card stack" key={s.key} style={{ gap: 14 }}>
              <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                <div className="row" style={{ gap: 10, alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>{s.label}</h3>
                  <button
                    type="button"
                    className="btn g xs"
                    style={{ fontSize: '0.8rem', padding: '3px 8px' }}
                    onClick={() => setShowRawCert(!showRawCert)}
                  >
                    {showRawCert ? 'View list' : 'Edit raw text'}
                  </button>
                </div>
                <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                  {!isAddingCert && !showRawCert && (
                    <button type="button" className="btn xs" onClick={startAddCertCard}>
                      + Add certification
                    </button>
                  )}
                  {!stored[s.key] ? (
                    <span className="badge n">Empty</span>
                  ) : stored.confirmed[s.key] ? (
                    <span className="badge s">Confirmed</span>
                  ) : (
                    <span className="badge p">Needs confirmation</span>
                  )}
                </div>
              </div>

              {showRawCert ? (
                <textarea
                  className="i"
                  style={{ minHeight: 140 }}
                  aria-label={s.label}
                  value={draft.certs}
                  onChange={(e) => setField('certs', e.target.value)}
                />
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
                  {isAddingCert && (
                    <div style={{ background: '#f8fafc', border: '1px solid #cbd5e1', borderRadius: 10, padding: 16 }}>
                      <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>
                        Add certification / achievement
                      </h4>
                      <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                        <label style={{ flex: 1 }}>
                          Certification Name *
                          <input
                            className="i"
                            placeholder="e.g. Machine Learning Specialization"
                            value={certForm.name}
                            onChange={(e) => setCertForm({ ...certForm, name: e.target.value })}
                          />
                        </label>
                        <label style={{ flex: 1 }}>
                          Issuing Organization (Optional)
                          <input
                            className="i"
                            placeholder="e.g. DeepLearning.AI & Harvard University"
                            value={certForm.authority}
                            onChange={(e) => setCertForm({ ...certForm, authority: e.target.value })}
                          />
                        </label>
                      </div>

                      <ItemLinksEditor
                        links={certForm.links || []}
                        onChange={(links) => setCertForm({ ...certForm, links })}
                      />

                      <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                        <button type="button" className="btn g xs" onClick={() => setIsAddingCert(false)}>
                          Cancel
                        </button>
                        <button
                          type="button"
                          className="btn xs"
                          disabled={!certForm.name.trim()}
                          onClick={() => handleSaveCertCard()}
                        >
                          Save certification
                        </button>
                      </div>
                    </div>
                  )}

                  {certCards.length === 0 && !isAddingCert ? (
                    <div style={{ padding: '24px 16px', textAlign: 'center', background: '#f8fafc', borderRadius: 8, border: '1px dashed #cbd5e1' }}>
                      <p className="meta" style={{ margin: '0 0 10px' }}>No certifications recorded yet.</p>
                      <button type="button" className="btn xs" onClick={startAddCertCard}>
                        + Add certification
                      </button>
                    </div>
                  ) : (
                    certCards.map((item) => (
                      <div
                        key={item.id}
                        style={{
                          background: '#ffffff',
                          border: '1px solid #e2e8f0',
                          borderRadius: 10,
                          padding: '14px 18px',
                          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
                        }}
                      >
                        {editingCertId === item.id ? (
                          <div>
                            <h4 style={{ margin: '0 0 12px', fontSize: '1rem', color: 'var(--blueD)' }}>Edit certification</h4>
                            <div className="row" style={{ gap: 10, marginBottom: 10 }}>
                              <label style={{ flex: 1 }}>
                                Certification Name *
                                <input
                                  className="i"
                                  value={certForm.name}
                                  onChange={(e) => setCertForm({ ...certForm, name: e.target.value })}
                                />
                              </label>
                              <label style={{ flex: 1 }}>
                                Issuing Organization
                                <input
                                  className="i"
                                  value={certForm.authority}
                                  onChange={(e) => setCertForm({ ...certForm, authority: e.target.value })}
                                />
                              </label>
                            </div>

                            <ItemLinksEditor
                              links={certForm.links || []}
                              onChange={(links) => setCertForm({ ...certForm, links })}
                            />

                            <div className="row" style={{ justifyContent: 'flex-end', gap: 8 }}>
                              <button type="button" className="btn g xs" onClick={() => setEditingCertId(null)}>Cancel</button>
                              <button
                                type="button"
                                className="btn xs"
                                disabled={!certForm.name.trim()}
                                onClick={() => handleSaveCertCard(item.id)}
                              >
                                Save changes
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                              <div style={{ fontSize: '1.02rem', fontWeight: 600, color: '#0f172a' }}>
                                <span>{item.name}</span>
                                {item.authority && <span style={{ color: '#475569' }}> - {item.authority}</span>}
                                <ItemLinksBadgeView links={item.links} />
                              </div>
                            </div>
                            <div className="row" style={{ gap: 8 }}>
                              <button
                                type="button"
                                style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#64748b' }}
                                onClick={() => startEditCertCard(item)}
                                title="Edit certification"
                              >
                                ✎
                              </button>
                              <button
                                type="button"
                                style={{ border: 'none', background: 'none', cursor: 'pointer', padding: '4px 6px', fontSize: '1rem', color: '#94a3b8' }}
                                onClick={() => handleDeleteCertCard(item.id)}
                                title="Delete certification"
                              >
                                ✕
                              </button>
                            </div>
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
                  checked={!!draft.confirmed.certs}
                  onChange={(e) => setConfirmed('certs', e.target.checked)}
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
