import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';

const cl = (x: number) => Math.max(0, Math.min(1, x));
const ez = (t: number) => t * t * (3 - 2 * t);
const lp = (a: number, b: number, t: number) => a + (b - a) * t;

const STEPS: [string, string][] = [
  ['Fetch', 'We search job sources for roles matching your titles, locations and work setup. Expired or unverifiable listings are flagged, not hidden.'],
  ['Compare', 'Each job is read against your confirmed profile. Strong matches rise, weak fits fall back, and every score comes with reasons and gaps.'],
  ['Tailor', 'Pick a job and your resume is rewritten around it, using only facts from your profile. You review every change before downloading.'],
];

interface CardD { gx: number; gy: number; sy: number; s: number }
interface Card { m: THREE.Mesh; mt: THREE.MeshStandardMaterial; d: CardD }

function mk(w: number, h: number) {
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

function jobTex() {
  const c = mk(256, 170), x = c.getContext('2d')!;
  x.fillStyle = '#f3f1ea'; x.fillRect(0, 0, 256, 170);
  x.fillStyle = '#0e3034'; x.fillRect(20, 18, 150, 16);
  x.fillStyle = '#cfcabd'; x.fillRect(20, 52, 200, 9); x.fillRect(20, 76, 160, 9); x.fillRect(20, 100, 120, 9);
  x.fillStyle = '#7fe0c9'; x.fillRect(20, 130, 64, 18);
  return new THREE.CanvasTexture(c);
}

function resTex() {
  const c = mk(256, 340), x = c.getContext('2d')!;
  x.fillStyle = '#f3f1ea'; x.fillRect(0, 0, 256, 340);
  x.fillStyle = '#0e3034'; x.fillRect(20, 22, 96, 14);
  x.fillStyle = '#cfcabd'; x.fillRect(20, 44, 60, 7);
  for (let k = 0; k < 10; k++) x.fillRect(20, 76 + k * 24, (k % 4 === 3 ? 110 : 200) - ((k * 17) % 50), 8);
  return new THREE.CanvasTexture(c);
}

export default function ProcessShow() {
  const showRef = useRef<HTMLElement>(null);
  const cvRef = useRef<HTMLCanvasElement>(null);
  const statRef = useRef<HTMLDivElement>(null);
  const pbarRef = useRef<HTMLElement>(null);
  const [idx, setIdx] = useState(0);
  const [noGL, setNoGL] = useState(false);

  useEffect(() => {
    const show = showRef.current!, cv = cvRef.current!, stat = statRef.current!, pbar = pbarRef.current!;
    let raf = 0;
    const cleanups: (() => void)[] = [];
    try {
      const R = new THREE.WebGLRenderer({ canvas: cv, antialias: true, alpha: true });
      R.setPixelRatio(Math.min(devicePixelRatio, 2));
      const S = new THREE.Scene(), C = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
      S.add(new THREE.AmbientLight(0xffffff, 0.95));
      const dl = new THREE.DirectionalLight(0xffffff, 0.55);
      dl.position.set(3, 5, 7); S.add(dl);

      const jt = jobTex(), rt = resTex(), M = 30, best = 14, strong = [8, 14, 21];
      const cards: Card[] = [];
      const jg = new THREE.BoxGeometry(0.9, 0.6, 0.03);
      for (let i = 0; i < M; i++) {
        const mt = new THREE.MeshStandardMaterial({ map: jt, roughness: 0.6, transparent: true, emissive: 0xffb800, emissiveIntensity: 0 });
        const m = new THREE.Mesh(jg, mt);
        const col = i % 6, row = Math.floor(i / 6);
        const d: CardD = { gx: col - 2.5 + 1.2, gy: (2 - row) * 0.78, sy: (((i * 37) % 7) - 3) * 0.5, s: strong.includes(i) ? 1 : 0.1 + ((i * 29) % 50) / 100 };
        S.add(m); cards.push({ m, mt, d });
      }
      const resumeMat = new THREE.MeshStandardMaterial({ map: rt, transparent: true });
      const resume = new THREE.Mesh(new THREE.BoxGeometry(1.4, 1.85, 0.04), resumeMat);
      S.add(resume);
      const scan = new THREE.Mesh(new THREE.PlaneGeometry(0.05, 4.1), new THREE.MeshBasicMaterial({ color: 0xffd23f, transparent: true, opacity: 0.85 }));
      scan.position.z = 0.5; S.add(scan);
      const lines = strong.map(() => {
        const l = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]), new THREE.LineBasicMaterial({ color: 0xffd23f }));
        S.add(l); return l;
      });
      const sheetG = new THREE.Group();
      sheetG.add(new THREE.Mesh(new THREE.BoxGeometry(1.6, 2.12, 0.04), new THREE.MeshStandardMaterial({ map: rt })));
      S.add(sheetG);
      const bars = ([[0.41, 0.95], [0.112, 0.8], [-0.186, 0.95], [-0.636, 0.9]] as [number, number][]).map((d) => {
        const b = new THREE.Mesh(new THREE.PlaneGeometry(d[1], 0.13), new THREE.MeshBasicMaterial({ color: 0xffd23f, transparent: true, opacity: 0.7, depthWrite: false }));
        b.position.set(-0.675, d[0], 0.04); sheetG.add(b);
        return { b, w: d[1] };
      });

      let camZ = 10;
      const size = () => {
        const w = cv.clientWidth, h = cv.clientHeight;
        if (!w || !h) return;
        R.setSize(w, h, false); C.aspect = w / h; C.updateProjectionMatrix();
        camZ = w / h < 1.1 ? 11.5 : 10;
      };
      size();
      addEventListener('resize', size);
      cleanups.push(() => removeEventListener('resize', size));

      let mx = 0, vis = true, cp = 0, last = -1;
      const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
      const onMove = (e: PointerEvent) => { mx = e.clientX / innerWidth - 0.5; };
      addEventListener('pointermove', onMove);
      cleanups.push(() => removeEventListener('pointermove', onMove));
      const io = new IntersectionObserver((e) => { vis = e[0].isIntersecting; });
      io.observe(show);
      cleanups.push(() => io.disconnect());

      const tick = (t: number) => {
        raf = requestAnimationFrame(tick);
        if (!vis) return;
        const r = show.getBoundingClientRect();
        const p0 = cl(-r.top / (r.height - innerHeight));
        cp += (p0 - cp) * 0.12;
        const p = cp;
        const f = cl(p / 0.33), g = cl((p - 0.33) / 0.33), h = cl((p - 0.66) / 0.34);
        const a = ez(cl(h / 0.4)), b = ez(cl((h - 0.4) / 0.3)), c = cl((h - 0.7) / 0.3);
        const sx = lp(-1.9, 4.4, cl(g / 0.9)), idle = reduce ? 0 : Math.sin(t * 0.001);

        resume.scale.setScalar(Math.max(0.001, ez(cl(p * 12)) * (1 - b * 0.95)));
        resumeMat.opacity = 1 - b; resume.visible = b < 1;
        resume.position.set(lp(lp(-3.6, -1.8, a), 0, b), 0, 0);
        resume.rotation.y = idle * 0.12;

        cards.forEach(({ m, mt, d }, i) => {
          const ti = cl((f - (i / M) * 0.55) / 0.45), e = ez(ti), pe = ez(cl((sx - d.gx) / 0.5)), st = d.s >= 1;
          let sc = 1, z = 0;
          let x = lp(d.gx + 8 + (i % 5) * 0.6, d.gx, e), y = lp(d.gy + d.sy, d.gy, e);
          const zz = lp(-5, 0, e);
          if (st) { z = pe * 0.8; sc = 1 + 0.25 * pe; mt.emissiveIntensity = 0.5 * pe; mt.color.setScalar(1); }
          else { z = -0.3 * pe; sc = 1 - 0.15 * pe; mt.emissiveIntensity = 0; mt.color.setScalar(1 - 0.55 * pe * (1 - d.s)); }
          let op = 1;
          if (i === best) {
            x = lp(lp(x, 1.8, a), 0, b); y = lp(y, 0, a); z = lp(z, 0.3, a);
            sc = lp(sc, 2, a) * (1 - b * 0.95); op = 1 - b;
          } else {
            const fa = ez(cl(h * 2.5)); op = 1 - fa; y -= fa * 2.5;
          }
          m.position.set(x, y, zz + z);
          m.rotation.y = lp(1.2, 0, e) + idle * 0.05;
          m.scale.setScalar(Math.max(0.001, sc));
          mt.opacity = op; m.visible = ti > 0 && op > 0.02;
        });

        scan.visible = g > 0 && g < 1 && h === 0; scan.position.x = sx;
        lines.forEach((l, k) => {
          const q = cards[strong[k]].m.position;
          const pa = l.geometry.attributes.position as THREE.BufferAttribute;
          pa.setXYZ(0, resume.position.x + 0.7, 0, 0); pa.setXYZ(1, q.x, q.y, q.z); pa.needsUpdate = true;
          l.visible = g > 0.75 && h === 0;
        });
        sheetG.scale.setScalar(Math.max(0.001, b)); sheetG.visible = b > 0;
        bars.forEach(({ b: br, w }, k) => {
          const pr = Math.max(0.001, ez(cl(c * 4 - k)));
          br.scale.x = pr; br.position.x = -0.675 + (w * pr) / 2;
        });
        C.position.set(mx * 0.7, 0, camZ); C.lookAt(0.3, 0, 0); R.render(S, C);

        const i2 = p < 0.33 ? 0 : p < 0.66 ? 1 : 2;
        let txt: string;
        if (p < 0.33) txt = 'Fetching jobs… ' + Math.round(248 * f) + ' found';
        else if (p < 0.66) txt = g < 0.95 ? 'Comparing with your profile… ' + Math.round(248 * cl(g / 0.9)) + ' of 248' : 'Compared 248 jobs · 3 strong matches';
        else txt = h < 0.4 ? 'Selected: Machine Learning Engineer' : h < 0.7 ? 'Combining your confirmed profile with the job' : 'Tailored resume ready to review · 0 invented claims';
        if (i2 !== last) { last = i2; setIdx(i2); }
        if (stat.textContent !== txt) stat.textContent = txt;
        pbar.style.width = p * 100 + '%';
      };
      raf = requestAnimationFrame(tick);
      cleanups.push(() => { cancelAnimationFrame(raf); R.dispose(); });
    } catch {
      setNoGL(true);
    }
    return () => cleanups.forEach((f) => f());
  }, []);

  return (
    <section id="process" className="show" ref={showRef}>
      <div className="stick"><div className="wrap sg">
        <div className="txt">
          <h2>Watch one search happen, start to finish</h2>
          {STEPS.map(([h, p], i) => (
            <div key={h} className={'st' + (i === idx ? ' on' : '')}><h3>{h}</h3><p>{p}</p></div>
          ))}
          <div className="pb"><i ref={pbarRef} /></div>
        </div>
        <div className="stage">
          <canvas ref={cvRef} id="c3d" role="img" style={noGL ? { display: 'none' } : undefined}
            aria-label="Animation: job listings stream in, get compared to your resume, and one is turned into a tailored resume" />
          <div id="stat" role="status" ref={statRef}>Scroll to start</div>
        </div>
      </div></div>
    </section>
  );
}
