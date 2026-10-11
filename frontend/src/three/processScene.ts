import * as THREE from 'three';

export interface SceneRefs {
  section: HTMLElement;
  canvas: HTMLCanvasElement;
  stat: HTMLElement;
  bar: HTMLElement;
  onStage: (index: number) => void;
}

const cl = (x: number) => Math.max(0, Math.min(1, x));
const ez = (t: number) => t * t * (3 - 2 * t);
const lp = (a: number, b: number, t: number) => a + (b - a) * t;

function canvasTexture(w: number, h: number, draw: (ctx: CanvasRenderingContext2D) => void): THREE.CanvasTexture {
  const c = document.createElement('canvas');
  c.width = w;
  c.height = h;
  const ctx = c.getContext('2d');
  if (ctx) draw(ctx);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

const jobTexture = () =>
  canvasTexture(256, 170, (x) => {
    x.fillStyle = '#f3f1ea';
    x.fillRect(0, 0, 256, 170);
    x.fillStyle = '#163a5f';
    x.fillRect(20, 18, 150, 16);
    x.fillStyle = '#cfcabd';
    x.fillRect(20, 52, 200, 9);
    x.fillRect(20, 76, 160, 9);
    x.fillRect(20, 100, 120, 9);
    x.fillStyle = '#1560bd';
    x.fillRect(20, 130, 64, 18);
  });

const resumeTexture = () =>
  canvasTexture(256, 340, (x) => {
    x.fillStyle = '#f3f1ea';
    x.fillRect(0, 0, 256, 340);
    x.fillStyle = '#163a5f';
    x.fillRect(20, 22, 96, 14);
    x.fillStyle = '#cfcabd';
    x.fillRect(20, 44, 60, 7);
    for (let k = 0; k < 10; k++) x.fillRect(20, 76 + k * 24, (k % 4 === 3 ? 110 : 200) - ((k * 17) % 50), 8);
  });

interface Card {
  mesh: THREE.Mesh<THREE.BoxGeometry, THREE.MeshStandardMaterial>;
  gx: number;
  gy: number;
  sy: number;
  score: number;
  strong: boolean;
}

/**
 * Scroll-driven scene: job cards stream in (fetch), a scan line scores them against the
 * resume (compare), then the best job and resume merge into a tailored resume (tailor).
 * Returns a dispose function.
 */
export function createProcessScene({ section, canvas, stat, bar, onStage }: SceneRefs): () => void {
  let renderer: THREE.WebGLRenderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch {
    canvas.style.display = 'none';
    stat.textContent = 'Your browser could not start the 3D preview.';
    return () => undefined;
  }
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(48, 1, 0.1, 100);
  scene.add(new THREE.AmbientLight(0xffffff, Math.PI * 0.95));
  const dir = new THREE.DirectionalLight(0xffffff, Math.PI * 0.55);
  dir.position.set(3, 5, 7);
  scene.add(dir);

  const jobTex = jobTexture();
  const resTex = resumeTexture();
  const disposables: { dispose: () => void }[] = [jobTex, resTex];

  const N = 30;
  const strongIdx = [8, 14, 21];
  const bestIdx = 14;
  const cardGeo = new THREE.BoxGeometry(0.9, 0.6, 0.03);
  disposables.push(cardGeo);
  const cards: Card[] = [];
  for (let i = 0; i < N; i++) {
    const mat = new THREE.MeshStandardMaterial({ map: jobTex, roughness: 0.6, transparent: true, emissive: 0xffb800, emissiveIntensity: 0 });
    disposables.push(mat);
    const mesh = new THREE.Mesh(cardGeo, mat);
    const col = i % 6;
    const row = Math.floor(i / 6);
    const strong = strongIdx.includes(i);
    cards.push({ mesh, gx: col - 2.5 + 1.2, gy: (2 - row) * 0.78, sy: ((i * 37) % 7 - 3) * 0.5, strong, score: strong ? 1 : 0.1 + ((i * 29) % 50) / 100 });
    scene.add(mesh);
  }

  const resumeGeo = new THREE.BoxGeometry(1.4, 1.85, 0.04);
  const resumeMat = new THREE.MeshStandardMaterial({ map: resTex, transparent: true });
  const resume = new THREE.Mesh(resumeGeo, resumeMat);
  scene.add(resume);
  disposables.push(resumeGeo, resumeMat);

  const scanGeo = new THREE.PlaneGeometry(0.05, 4.1);
  const scanMat = new THREE.MeshBasicMaterial({ color: 0xffd23f, transparent: true, opacity: 0.85 });
  const scan = new THREE.Mesh(scanGeo, scanMat);
  scan.position.z = 0.5;
  scene.add(scan);
  disposables.push(scanGeo, scanMat);

  const lineMat = new THREE.LineBasicMaterial({ color: 0xffd23f });
  disposables.push(lineMat);
  const lines = strongIdx.map(() => {
    const geo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]);
    disposables.push(geo);
    const line = new THREE.Line(geo, lineMat);
    scene.add(line);
    return line;
  });

  const sheetGroup = new THREE.Group();
  const sheetGeo = new THREE.BoxGeometry(1.6, 2.12, 0.04);
  const sheetMat = new THREE.MeshStandardMaterial({ map: resTex });
  sheetGroup.add(new THREE.Mesh(sheetGeo, sheetMat));
  disposables.push(sheetGeo, sheetMat);
  const barSpecs: [number, number][] = [[0.41, 0.95], [0.112, 0.8], [-0.186, 0.95], [-0.636, 0.9]];
  const bars = barSpecs.map(([y, w]) => {
    const geo = new THREE.PlaneGeometry(w, 0.13);
    const mat = new THREE.MeshBasicMaterial({ color: 0xffd23f, transparent: true, opacity: 0.7, depthWrite: false });
    disposables.push(geo, mat);
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(-0.675, y, 0.04);
    sheetGroup.add(mesh);
    return { mesh, w };
  });
  scene.add(sheetGroup);

  let camZ = 10;
  const size = () => {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    camZ = w / h < 1.1 ? 11.5 : 10;
  };
  size();
  window.addEventListener('resize', size);

  let mx = 0;
  const onPointer = (e: PointerEvent) => {
    mx = e.clientX / window.innerWidth - 0.5;
  };
  window.addEventListener('pointermove', onPointer);

  let visible = true;
  const io = new IntersectionObserver((entries) => {
    visible = entries[0]?.isIntersecting ?? true;
    if (visible) size();
  });
  io.observe(section);

  let smooth = 0;
  let lastStage = -1;
  let raf = 0;

  const frame = (t: number) => {
    raf = requestAnimationFrame(frame);
    if (!visible) return;
    const r = section.getBoundingClientRect();
    const target = cl(-r.top / (r.height - window.innerHeight));
    smooth += (target - smooth) * 0.12;
    const p = smooth;
    const f = cl(p / 0.33);
    const g = cl((p - 0.33) / 0.33);
    const h = cl((p - 0.66) / 0.34);
    const a = ez(cl(h / 0.4));
    const b = ez(cl((h - 0.4) / 0.3));
    const c = cl((h - 0.7) / 0.3);
    const sx = lp(-1.9, 4.4, cl(g / 0.9));
    const idle = reduceMotion ? 0 : Math.sin(t * 0.001);

    resume.scale.setScalar(Math.max(0.001, ez(cl(p * 12)) * (1 - b * 0.95)));
    resumeMat.opacity = 1 - b;
    resume.visible = b < 1;
    resume.position.set(lp(lp(-3.6, -1.8, a), 0, b), 0, 0);
    resume.rotation.y = idle * 0.12;

    cards.forEach((cd, i) => {
      const ti = cl((f - (i / N) * 0.55) / 0.45);
      const e = ez(ti);
      const pe = ez(cl((sx - cd.gx) / 0.5));
      let x = lp(cd.gx + 8 + (i % 5) * 0.6, cd.gx, e);
      let y = lp(cd.gy + cd.sy, cd.gy, e);
      const zz = lp(-5, 0, e);
      let z: number;
      let sc: number;
      const mat = cd.mesh.material;
      if (cd.strong) {
        z = pe * 0.8;
        sc = 1 + 0.25 * pe;
        mat.emissiveIntensity = 0.5 * pe;
        mat.color.setScalar(1);
      } else {
        z = -0.3 * pe;
        sc = 1 - 0.15 * pe;
        mat.emissiveIntensity = 0;
        mat.color.setScalar(1 - 0.55 * pe * (1 - cd.score));
      }
      let op = 1;
      if (i === bestIdx) {
        x = lp(lp(x, 1.8, a), 0, b);
        y = lp(y, 0, a);
        z = lp(z, 0.3, a);
        sc = lp(sc, 2, a) * (1 - b * 0.95);
        op = 1 - b;
      } else {
        const fa = ez(cl(h * 2.5));
        op = 1 - fa;
        y -= fa * 2.5;
      }
      cd.mesh.position.set(x, y, zz + z);
      cd.mesh.rotation.y = lp(1.2, 0, e) + idle * 0.05;
      cd.mesh.scale.setScalar(Math.max(0.001, sc));
      mat.opacity = op;
      cd.mesh.visible = ti > 0 && op > 0.02;
    });

    scan.visible = g > 0 && g < 1 && h === 0;
    scan.position.x = sx;
    lines.forEach((l, k) => {
      const q = cards[strongIdx[k]!]!.mesh.position;
      const pa = l.geometry.attributes.position as THREE.BufferAttribute;
      pa.setXYZ(0, resume.position.x + 0.7, 0, 0);
      pa.setXYZ(1, q.x, q.y, q.z);
      pa.needsUpdate = true;
      l.visible = g > 0.75 && h === 0;
    });
    sheetGroup.scale.setScalar(Math.max(0.001, b));
    sheetGroup.visible = b > 0;
    bars.forEach(({ mesh, w }, k) => {
      const pr = Math.max(0.001, ez(cl(c * 4 - k)));
      mesh.scale.x = pr;
      mesh.position.x = -0.675 + (w * pr) / 2;
    });

    camera.position.set(mx * 0.7, 0, camZ);
    camera.lookAt(0.3, 0, 0);
    renderer.render(scene, camera);

    const idx = p < 0.33 ? 0 : p < 0.66 ? 1 : 2;
    let text: string;
    if (p < 0.33) text = `Fetching jobs… ${Math.round(248 * f)} found`;
    else if (p < 0.66) text = g < 0.95 ? `Comparing with your profile… ${Math.round(248 * cl(g / 0.9))} of 248` : 'Compared 248 jobs · 3 strong matches';
    else text = h < 0.4 ? 'Selected: Machine Learning Engineer' : h < 0.7 ? 'Combining your confirmed profile with the job' : 'Tailored resume ready to review · 0 invented claims';
    if (idx !== lastStage) {
      lastStage = idx;
      onStage(idx);
    }
    if (stat.textContent !== text) stat.textContent = text;
    bar.style.width = `${p * 100}%`;
  };
  raf = requestAnimationFrame(frame);

  return () => {
    cancelAnimationFrame(raf);
    window.removeEventListener('resize', size);
    window.removeEventListener('pointermove', onPointer);
    io.disconnect();
    disposables.forEach((d) => d.dispose());
    renderer.dispose();
  };
}
