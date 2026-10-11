import { useEffect, useRef, useState } from 'react';
import { createProcessScene } from '../three/processScene';

const STEPS = [
  { title: 'Fetch', text: 'JobFit pulls fresh listings that match your titles, locations and work setup. Unverifiable listings are flagged, not hidden.' },
  { title: 'Compare', text: 'Each job is scored on skills, seniority and work arrangement. Strong matches rise, weak fits fall back.' },
  { title: 'Tailor', text: 'Your resume is reordered and reworded around one job, using only facts from your profile. You review every change.' },
];

export function ProcessSection() {
  const section = useRef<HTMLElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const stat = useRef<HTMLDivElement>(null);
  const bar = useRef<HTMLElement>(null);
  const [stage, setStage] = useState(0);

  useEffect(() => {
    if (!section.current || !canvas.current || !stat.current || !bar.current) return;
    return createProcessScene({ section: section.current, canvas: canvas.current, stat: stat.current, bar: bar.current, onStage: setStage });
  }, []);

  return (
    <section id="process" className="show" ref={section}>
      <div className="stick">
        <div className="w sg">
          <div className="txt">
            <h2>See one search happen, start to finish</h2>
            {STEPS.map((s, i) => (
              <div className={`st${i === stage ? ' on' : ''}`} key={s.title}>
                <h3>{s.title}</h3>
                <p>{s.text}</p>
              </div>
            ))}
            <div className="pb"><i ref={bar} /></div>
          </div>
          <div className="stage">
            <canvas ref={canvas} id="c3d" role="img" aria-label="Animation: job listings stream in, get compared to your resume, and one becomes a tailored resume" />
            <div id="stat" ref={stat} role="status">Scroll to start</div>
          </div>
        </div>
      </div>
    </section>
  );
}
