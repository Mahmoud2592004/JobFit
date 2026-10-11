const FAQ: [string, string][] = [
  ['How does job matching work?', 'JobFit compares each job with your confirmed profile on skills, seniority and work arrangement, then shows the reasons.'],
  ['How should I read a fit score?', 'It helps you prioritize. It does not predict interviews or offers.'],
  ['How does the truth check work?', 'Every skill on a tailored resume is compared with your profile skills. Unsupported ones are flagged and block approval.'],
  ['Can you guarantee interviews?', 'No. We help you apply with a clearer, accurate resume. Employers decide.'],
  ['A detail was extracted wrongly.', 'Open Profile, correct the section and tick "This is accurate".'],
  ['A listing looks expired or wrong.', 'Open the original listing to check it. Reporting is coming soon.'],
  ['How do I delete my data?', 'Go to Settings to delete your resumes or your whole account.'],
];

export default function Help() {
  return (
    <div className="card" style={{ maxWidth: 760, margin: '0 auto' }}>
      <h2 style={{ fontSize: '1.4rem', marginBottom: 8 }}>Help and guidance</h2>
      {FAQ.map(([q, a]) => (
        <details className="q" key={q}>
          <summary>{q}</summary>
          <p>{a}</p>
        </details>
      ))}
    </div>
  );
}
