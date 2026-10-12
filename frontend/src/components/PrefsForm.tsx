import { useState, useMemo } from 'react';
import { LEVELS } from '../data/jobs';
import { SUPPORTED_COUNTRIES, getCountryName, type CountryOption } from '../data/countries';
import type { JobType, Level, Mode, Prefs } from '../types';

interface Props {
  value: Prefs;
  onChange: (next: Prefs) => void;
}

export function PrefsForm({ value, onChange }: Props) {
  const [countryQuery, setCountryQuery] = useState('');
  const [showCountryDropdown, setShowCountryDropdown] = useState(false);
  const [showAdvancedLinkedIn, setShowAdvancedLinkedIn] = useState(false);

  const selectedCountryCodes = value.countries || [];

  const set = <K extends keyof Prefs>(key: K, v: Prefs[K]) => onChange({ ...value, [key]: v });

  // Filter country options based on search query
  const filteredCountries = useMemo(() => {
    const q = countryQuery.trim().toLowerCase();
    if (!q) return SUPPORTED_COUNTRIES.slice(0, 15);
    return SUPPORTED_COUNTRIES.filter(
      (c) =>
        c.name.toLowerCase().includes(q) ||
        c.code.toLowerCase().includes(q)
    ).slice(0, 20);
  }, [countryQuery]);

  const addCountry = (country: CountryOption) => {
    if (!selectedCountryCodes.includes(country.code)) {
      const nextCodes = [...selectedCountryCodes, country.code];
      const nextLocationNames = nextCodes.map((code) => getCountryName(code)).join(', ');
      onChange({
        ...value,
        countries: nextCodes,
        location: value.location ? `${value.location}, ${country.name}` : nextLocationNames,
      });
    }
    setCountryQuery('');
    setShowCountryDropdown(false);
  };

  const removeCountry = (code: string) => {
    const nextCodes = selectedCountryCodes.filter((c) => c !== code);
    const countryName = getCountryName(code);
    const updatedLocation = value.location
      .split(',')
      .map((s) => s.trim())
      .filter((s) => s.toLowerCase() !== countryName.toLowerCase())
      .join(', ');
    onChange({
      ...value,
      countries: nextCodes,
      location: updatedLocation,
    });
  };

  return (
    <div className="stack" style={{ gap: 16 }}>
      <label>
        Target roles
        <input
          className="i"
          placeholder="e.g. Machine Learning Engineer, NLP Engineer"
          value={value.titles}
          onChange={(e) => set('titles', e.target.value)}
        />
      </label>

      {/* Supported Countries Selection */}
      <div style={{ position: 'relative' }}>
        <label style={{ display: 'block', marginBottom: 6 }}>
          Target Countries (Select one or more from supported LinkedIn list)
        </label>
        
        {/* Selected Country Chips */}
        {selectedCountryCodes.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
            {selectedCountryCodes.map((code) => (
              <span
                key={code}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 10px',
                  background: '#e0f2fe',
                  color: '#0369a1',
                  borderRadius: 16,
                  fontSize: '0.86rem',
                  fontWeight: 600,
                  border: '1px solid #bae6fd',
                }}
              >
                {getCountryName(code)} ({code})
                <button
                  type="button"
                  onClick={() => removeCountry(code)}
                  style={{
                    border: 'none',
                    background: 'none',
                    color: '#0284c7',
                    cursor: 'pointer',
                    fontSize: '1rem',
                    lineHeight: 1,
                    padding: 0,
                  }}
                  title="Remove country"
                >
                  ✕
                </button>
              </span>
            ))}
          </div>
        )}

        {/* Search input for countries */}
        <div style={{ position: 'relative' }}>
          <input
            className="i"
            placeholder="Type to search countries (e.g. United States, Egypt, Germany, United Kingdom)..."
            value={countryQuery}
            onChange={(e) => {
              setCountryQuery(e.target.value);
              setShowCountryDropdown(true);
            }}
            onFocus={() => setShowCountryDropdown(true)}
          />

          {showCountryDropdown && filteredCountries.length > 0 && (
            <div
              style={{
                position: 'absolute',
                top: '100%',
                left: 0,
                right: 0,
                zIndex: 40,
                background: '#ffffff',
                border: '1px solid #cbd5e1',
                borderRadius: 8,
                marginTop: 4,
                maxHeight: 220,
                overflowY: 'auto',
                boxShadow: '0 8px 24px rgba(0,0,0,0.12)',
              }}
            >
              {filteredCountries.map((country) => {
                const isSelected = selectedCountryCodes.includes(country.code);
                return (
                  <div
                    key={country.code}
                    onClick={() => {
                      if (!isSelected) addCountry(country);
                    }}
                    style={{
                      padding: '8px 14px',
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      cursor: isSelected ? 'default' : 'pointer',
                      background: isSelected ? '#f1f5f9' : 'transparent',
                      color: isSelected ? '#94a3b8' : '#1e293b',
                      borderBottom: '1px solid #f8fafc',
                    }}
                  >
                    <span style={{ fontWeight: 500 }}>{country.name}</span>
                    <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
                      {country.code} {isSelected ? '✓' : ''}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <label>
        Additional location or cities (e.g. "Cairo, London, Remote")
        <input
          className="i"
          placeholder="e.g. Cairo, Alexandria, London, Remote"
          value={value.location}
          onChange={(e) => set('location', e.target.value)}
        />
      </label>

      <div className="row" style={{ gap: 12 }}>
        <label style={{ flex: 1 }}>
          Work arrangement
          <select className="i" value={value.mode} onChange={(e) => set('mode', e.target.value as Mode | 'Any')}>
            {['Any', 'Remote', 'Hybrid', 'On-site'].map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </label>
        <label style={{ flex: 1 }}>
          Employment type
          <select className="i" value={value.type} onChange={(e) => set('type', e.target.value as JobType | 'Any')}>
            {['Any', 'Full-time', 'Part-time', 'Internship'].map((o) => (
              <option key={o}>{o}</option>
            ))}
          </select>
        </label>
        <label style={{ flex: 1 }}>
          Level
          <select className="i" value={value.level} onChange={(e) => set('level', e.target.value as Level)}>
            {LEVELS.map((o) => (
              <option key={o}>{o}</option>
            ))}
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

      {/* Advanced LinkedIn Search Section */}
      <div style={{ marginTop: 8, paddingTop: 12, borderTop: '1px solid #e2e8f0' }}>
        <button
          type="button"
          onClick={() => setShowAdvancedLinkedIn(!showAdvancedLinkedIn)}
          style={{
            background: 'none',
            border: 'none',
            color: 'var(--blue)',
            fontWeight: 600,
            cursor: 'pointer',
            padding: 0,
            fontSize: '0.94rem',
            display: 'flex',
            alignItems: 'center',
            gap: 6,
          }}
        >
          <span>{showAdvancedLinkedIn ? '▼' : '►'}</span>
          Advanced LinkedIn Job Search & Scraping Parameters
        </button>

        {showAdvancedLinkedIn && (
          <div className="card" style={{ marginTop: 12, padding: 16, background: '#f8fafc', border: '1px solid #e2e8f0' }}>
            <div className="stack" style={{ gap: 14 }}>
              <div>
                <label style={{ fontWeight: 600 }}>LinkedIn Search URLs (one per line)</label>
                <p className="meta" style={{ margin: '4px 0 8px', fontSize: '0.84rem' }}>
                  Go to <a href="https://www.linkedin.com/jobs/search/" target="_blank" rel="noreferrer" style={{ textDecoration: 'underline' }}>public linkedin jobs search page</a> on an incognito window, search with required filters, and copy the full URL from the address bar here. You can pass multiple search URLs. When URLs are provided, manual AI search filters are bypassed.
                </p>
                <textarea
                  className="i"
                  style={{ minHeight: 70, fontFamily: 'monospace', fontSize: '0.85rem' }}
                  placeholder="https://www.linkedin.com/jobs/search/?keywords=machine%20learning&location=Egypt&#10;https://www.linkedin.com/jobs/search/?keywords=python%20remote"
                  value={(value.urls || []).join('\n')}
                  onChange={(e) => {
                    const lines = e.target.value.split('\n').map((l) => l.trim()).filter(Boolean);
                    set('urls', lines);
                  }}
                />
              </div>

              <div className="row" style={{ gap: 12 }}>
                <label style={{ flex: 1 }}>
                  Geo ID (Optional)
                  <input
                    className="i"
                    placeholder="e.g. 106155005 (found as geoId= in search URL)"
                    value={value.geoId || ''}
                    onChange={(e) => set('geoId', e.target.value)}
                  />
                </label>
                <label style={{ flex: 1 }}>
                  Distance (miles)
                  <input
                    className="i"
                    type="number"
                    min={0}
                    placeholder="Search radius in miles"
                    value={value.distance ?? ''}
                    onChange={(e) => set('distance', e.target.value ? Number(e.target.value) : undefined)}
                  />
                </label>
                <label style={{ flex: 1 }}>
                  Date posted
                  <select
                    className="i"
                    value={value.datePosted || 'anyTime'}
                    onChange={(e) => set('datePosted', e.target.value as any)}
                  >
                    <option value="anyTime">Any time</option>
                    <option value="past24Hours">Past 24 hours</option>
                    <option value="pastWeek">Past week</option>
                    <option value="pastMonth">Past month</option>
                  </select>
                </label>
              </div>

              <div className="row" style={{ gap: 12 }}>
                <label style={{ flex: 2 }}>
                  Company IDs (comma-separated numbers)
                  <input
                    className="i"
                    placeholder="e.g. 1441 (Google), 1035 (Microsoft)"
                    value={(value.companyIds || []).join(', ')}
                    onChange={(e) => {
                      const ids = e.target.value.split(',').map((s) => s.trim()).filter(Boolean);
                      set('companyIds', ids);
                    }}
                  />
                </label>
                <label style={{ flex: 1 }}>
                  Max jobs to scrape
                  <input
                    className="i"
                    type="number"
                    min={1}
                    max={100}
                    value={value.limitPerSource || 35}
                    onChange={(e) => set('limitPerSource', Math.min(100, Math.max(1, Number(e.target.value) || 35)))}
                  />
                </label>
              </div>

              <div className="row" style={{ gap: 16, flexWrap: 'wrap' }}>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={value.under10Applicants ?? false}
                    onChange={(e) => set('under10Applicants', e.target.checked)}
                  />
                  <span>Under 10 applicants only</span>
                </label>

                <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={value.autoConvertToAiSearch ?? true}
                    onChange={(e) => set('autoConvertToAiSearch', e.target.checked)}
                  />
                  <span>Auto convert old search URLs to AI search</span>
                </label>

                <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={value.scrapeCompany ?? true}
                    onChange={(e) => set('scrapeCompany', e.target.checked)}
                  />
                  <span>Scrape company details</span>
                </label>
              </div>

              <div style={{ paddingTop: 8, borderTop: '1px dashed #cbd5e1' }}>
                <label style={{ display: 'flex', gap: 8, alignItems: 'center', cursor: 'pointer', marginBottom: 8 }}>
                  <input
                    type="checkbox"
                    checked={value.splitByLocation ?? false}
                    onChange={(e) => set('splitByLocation', e.target.checked)}
                  />
                  <span style={{ fontWeight: 600 }}>Split search by city locations (bypasses 1000 limit)</span>
                </label>

                {value.splitByLocation && (
                  <label style={{ display: 'block' }}>
                    Country to split by:
                    <select
                      className="i"
                      value={value.splitCountry || (selectedCountryCodes[0] || 'US')}
                      onChange={(e) => set('splitCountry', e.target.value)}
                    >
                      {SUPPORTED_COUNTRIES.map((c) => (
                        <option key={c.code} value={c.code}>
                          {c.name} ({c.code})
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

