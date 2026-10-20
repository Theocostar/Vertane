// Modèle 3D d'un drone FPV 5 pouces, construit en géométrie procédurale (unités : millimètres).
// Avant du drone vers -Z, haut vers +Y.
import * as THREE from 'three';
import { RoundedBoxGeometry } from './vendor/RoundedBoxGeometry.js';

// ------------------------------------------------------------------ textures procédurales
function canvasTex(w, h, draw, repeat) {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  draw(c.getContext('2d'), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  if (repeat) t.repeat.set(repeat[0], repeat[1]);
  t.anisotropy = 4;
  return t;
}

// sergé de carbone 2x2 : chaque mèche a un léger dégradé, ce qui donne le reflet changeant
const carbonTex = canvasTex(256, 256, (g, w, h) => {
  const n = 16, s = w / n;
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    const horiz = ((x + y) >> 1) % 2 === 0;
    const gr = horiz ? g.createLinearGradient(x * s, y * s, x * s, y * s + s) : g.createLinearGradient(x * s, y * s, x * s + s, y * s);
    gr.addColorStop(0, '#0f1112'); gr.addColorStop(.5, horiz ? '#565b5e' : '#33373a'); gr.addColorStop(1, '#0f1112');
    g.fillStyle = gr; g.fillRect(x * s, y * s, s, s);
  }
}, [5, 5]);

const pcbTex = (base, accent) => canvasTex(256, 256, (g, w, h) => {
  g.fillStyle = base; g.fillRect(0, 0, w, h);
  g.strokeStyle = accent; g.globalAlpha = .35; g.lineWidth = 2;
  for (let i = 0; i < 40; i++) {           // pistes de cuivre sous le vernis
    let x = Math.random() * w, y = Math.random() * h; g.beginPath(); g.moveTo(x, y);
    for (let k = 0; k < 4; k++) { if (k % 2) x += (Math.random() - .5) * 120; else y += (Math.random() - .5) * 120; g.lineTo(x, y); }
    g.stroke();
  }
  g.globalAlpha = 1;
  g.fillStyle = 'rgba(255,255,255,.55)'; g.font = '600 14px Inter';
  g.fillText('F7  ·  30x30', 18, h - 18);
});

const labelTex = canvasTex(512, 256, (g, w, h) => {
  g.fillStyle = '#1b1d1e'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#2F7A55'; g.fillRect(0, 0, w, 40); g.fillRect(0, h - 14, w, 14);
  g.fillStyle = '#E9F3EC'; g.font = '700 92px Inter'; g.textAlign = 'center'; g.fillText('LiPo', w / 2, h / 2 + 32);
  g.fillStyle = '#8DB89A'; g.font = '600 26px Inter'; g.fillText('LITHIUM-POLYMÈRE', w / 2, 38);
});

// disque d'hélice floue (rotation rapide)
const blurTex = canvasTex(256, 256, (g, w, h) => {
  const gr = g.createRadialGradient(w / 2, h / 2, 10, w / 2, h / 2, w / 2);
  gr.addColorStop(0, 'rgba(183,217,193,0)'); gr.addColorStop(.12, 'rgba(183,217,193,.10)');
  gr.addColorStop(.75, 'rgba(183,217,193,.22)'); gr.addColorStop(.97, 'rgba(230,242,233,.32)'); gr.addColorStop(1, 'rgba(230,242,233,0)');
  g.fillStyle = gr; g.fillRect(0, 0, w, h);
});

// ------------------------------------------------------------------ matériaux
export const MAT = {
  carbon: new THREE.MeshPhysicalMaterial({ map: carbonTex, roughness: .28, metalness: .25, clearcoat: .7, clearcoatRoughness: .1, specularIntensity: .8 }),
  alu: new THREE.MeshStandardMaterial({ color: 0x9aa3a0, metalness: 1, roughness: .28 }),
  aluDark: new THREE.MeshStandardMaterial({ color: 0x2b2f2d, metalness: .9, roughness: .38 }),
  anod: new THREE.MeshStandardMaterial({ color: 0x2F7A55, metalness: .85, roughness: .26 }),
  copper: new THREE.MeshStandardMaterial({ color: 0xb8733a, metalness: 1, roughness: .32 }),
  steel: new THREE.MeshStandardMaterial({ color: 0xd8dcdb, metalness: 1, roughness: .18 }),
  gold: new THREE.MeshStandardMaterial({ color: 0xd9a84e, metalness: 1, roughness: .22 }),
  chip: new THREE.MeshStandardMaterial({ color: 0x16181a, metalness: .2, roughness: .55 }),
  pcbEsc: new THREE.MeshStandardMaterial({ map: pcbTex('#123323', '#3f9a6c'), roughness: .42, metalness: .1 }),
  pcbFc: new THREE.MeshStandardMaterial({ map: pcbTex('#15181a', '#6b8c79'), roughness: .4, metalness: .1 }),
  rubber: new THREE.MeshStandardMaterial({ color: 0x1a1c1d, roughness: .85, metalness: 0 }),
  tpu: new THREE.MeshStandardMaterial({ color: 0x8DB89A, roughness: .7, metalness: 0 }),
  grommet: new THREE.MeshStandardMaterial({ color: 0x4b8a6a, roughness: .8 }),
  prop: new THREE.MeshPhysicalMaterial({ color: 0x4f6b5d, roughness: .14, metalness: 0, transparent: true, opacity: .72, clearcoat: 1, clearcoatRoughness: .05, side: THREE.DoubleSide }),
  glass: new THREE.MeshPhysicalMaterial({ color: 0x0c1410, roughness: .04, metalness: .3, clearcoat: 1, clearcoatRoughness: .02 }),
  wrap: new THREE.MeshPhysicalMaterial({ color: 0x1b1d1e, roughness: .42, clearcoat: .35, clearcoatRoughness: .3 }),
  label: new THREE.MeshPhysicalMaterial({ map: labelTex, roughness: .35, clearcoat: .6 }),
  xt60: new THREE.MeshStandardMaterial({ color: 0xe8c547, roughness: .45 }),
  wireR: new THREE.MeshStandardMaterial({ color: 0xc8373b, roughness: .45 }),
  wireB: new THREE.MeshStandardMaterial({ color: 0x1d1f20, roughness: .45 }),
  wireY: new THREE.MeshStandardMaterial({ color: 0xd9b44a, roughness: .45 }),
  cap: new THREE.MeshStandardMaterial({ color: 0x1e2a24, roughness: .4, metalness: .2 }),
  led: new THREE.MeshStandardMaterial({ color: 0x64ffa0, emissive: 0x35ff86, emissiveIntensity: 2 }),
  solder: new THREE.MeshStandardMaterial({ color: 0xcfd3d2, metalness: 1, roughness: .2, emissive: 0xff8a2a, emissiveIntensity: 0 }),
  blur: new THREE.MeshBasicMaterial({ map: blurTex, transparent: true, depthWrite: false, side: THREE.DoubleSide }),
};

// ------------------------------------------------------------------ primitives
const mesh = (geo, mat, x = 0, y = 0, z = 0) => { const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); m.castShadow = true; m.receiveShadow = true; return m; };
const rbox = (w, h, d, r, mat, x, y, z) => mesh(new RoundedBoxGeometry(w, h, d, 3, r), mat, x, y, z);
const cyl = (r, h, mat, x, y, z, seg = 40, rt) => mesh(new THREE.CylinderGeometry(rt ?? r, r, h, seg), mat, x, y, z);

function plateShape(w, l, r) {
  const s = new THREE.Shape(), x = -w / 2, y = -l / 2;
  s.moveTo(x + r, y); s.lineTo(x + w - r, y); s.quadraticCurveTo(x + w, y, x + w, y + r);
  s.lineTo(x + w, y + l - r); s.quadraticCurveTo(x + w, y + l, x + w - r, y + l);
  s.lineTo(x + r, y + l); s.quadraticCurveTo(x, y + l, x, y + l - r);
  s.lineTo(x, y + r); s.quadraticCurveTo(x, y, x + r, y);
  return s;
}
function extrudePlate(shape, thick, mat, holes = []) {
  holes.forEach(([hx, hy, hr]) => { const p = new THREE.Path(); p.absarc(hx, hy, hr, 0, Math.PI * 2, true); shape.holes.push(p); });
  const g = new THREE.ExtrudeGeometry(shape, { depth: thick, bevelEnabled: true, bevelThickness: .5, bevelSize: .5, bevelSegments: 2, curveSegments: 18 });
  g.rotateX(-Math.PI / 2);
  // UV en coordonnées planes pour que le tressage suive la plaque
  const pos = g.attributes.position, uv = g.attributes.uv;
  for (let i = 0; i < pos.count; i++) uv.setXY(i, pos.getX(i) / 60, pos.getZ(i) / 60);
  return mesh(g, mat);
}

// ------------------------------------------------------------------ pièces
export const MOTORS = [[-80, -80], [80, -80], [-80, 80], [80, 80]];   // AV-G, AV-D, AR-G, AR-D

function buildFrame() {
  const g = new THREE.Group(); g.name = 'frame';
  // plaque inférieure : corps + 4 bras d'un seul tenant (bras de 6 mm)
  const body = extrudePlate(plateShape(46, 108, 10), 5, MAT.carbon, [[0, 0, 4]]); g.add(body);
  MOTORS.forEach(([x, z]) => {
    const len = Math.hypot(x, z) + 16, a = Math.atan2(x, z);
    const arm = extrudePlate(plateShape(15, len, 7.5), 6, MAT.carbon, [[0, len / 2 - 8, 2.6]]);
    arm.geometry.translate(0, 0, -len / 2 + 0);  // le bras part du centre
    arm.rotation.y = a + Math.PI; arm.position.y = 0;
    g.add(arm);
  });
  // entretoises aluminium anodisé
  [[-16, -36], [16, -36], [-16, 36], [16, 36]].forEach(([x, z]) => g.add(cyl(2.6, 25, MAT.anod, x, 6 + 12.5, z, 24)));
  // visserie sous la plaque + support d'antenne TPU à l'arrière
  [[-12, -12], [12, -12], [-12, 12], [12, 12]].forEach(([x, z]) => g.add(cyl(2.1, 1.4, MAT.steel, x, 6.2, z, 6)));
  g.add(rbox(18, 10, 8, 2, MAT.tpu, 0, 30, 48));
  return g;
}

// plaque supérieure (posée en dernier, avant la batterie)
function buildTop() {
  const g = new THREE.Group(); g.name = 'top';
  const top = extrudePlate(plateShape(40, 92, 9), 2.5, MAT.carbon); top.position.y = 31; g.add(top);
  [[-16, -36], [16, -36], [-16, 36], [16, 36]].forEach(([x, z]) => g.add(cyl(2.1, 1.4, MAT.steel, x, 34.4, z, 6)));
  g.add(rbox(30, 1, 70, .5, MAT.rubber, 0, 34.2, 0));   // pad antidérapant
  return g;
}

function buildMotor() {
  const m = new THREE.Group(); m.name = 'motor';
  m.add(cyl(13.5, 4, MAT.aluDark, 0, 8, 0));                         // base
  m.add(cyl(11.6, 9.5, MAT.copper, 0, 15, 0));                       // bobinages
  // cloche : 6 segments séparés par des fentes qui laissent voir le cuivre
  for (let k = 0; k < 6; k++) {
    const seg = new THREE.Mesh(new THREE.CylinderGeometry(14, 14, 11, 10, 1, true, k * Math.PI / 3, Math.PI / 3 - .22), MAT.anod);
    seg.position.y = 15.5; seg.castShadow = true; m.add(seg);
  }
  m.add(cyl(14, 2.6, MAT.anod, 0, 22.3, 0));                         // dessus de cloche
  m.add(cyl(6, 1, MAT.aluDark, 0, 23.9, 0));
  m.add(cyl(2.5, 9, MAT.steel, 0, 27.5, 0, 16));                     // axe
  const nut = cyl(4.4, 5, MAT.steel, 0, 31, 0, 6); m.add(nut);       // écrou hexagonal
  return m;
}

function bladeGeometry() {
  const s = new THREE.Shape();
  s.moveTo(5, -4); s.bezierCurveTo(22, -9.5, 45, -8.5, 61, -4.5); s.quadraticCurveTo(64.5, 0, 61, 3);
  s.bezierCurveTo(45, 6.5, 22, 7.5, 5, 4); s.lineTo(5, -4);
  const g = new THREE.ExtrudeGeometry(s, { depth: 1.1, bevelEnabled: true, bevelThickness: .35, bevelSize: .35, bevelSegments: 1, curveSegments: 16 });
  g.rotateX(-Math.PI / 2);
  // vrillage : le calage diminue vers le bout de pale
  const pos = g.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    const r = pos.getX(i), z = pos.getZ(i), y = pos.getY(i);
    const ang = THREE.MathUtils.degToRad(18 - 10 * (r / 64));
    pos.setY(i, y * Math.cos(ang) - z * Math.sin(ang)); pos.setZ(i, y * Math.sin(ang) + z * Math.cos(ang));
  }
  g.computeVertexNormals();
  return g;
}
const BLADE = bladeGeometry();
function buildProp(dir) {
  const p = new THREE.Group(); p.name = 'prop';
  const blades = new THREE.Group();
  for (let k = 0; k < 3; k++) { const b = new THREE.Mesh(BLADE, MAT.prop); b.rotation.y = k * 2 * Math.PI / 3; b.scale.z = dir; b.castShadow = true; blades.add(b); }
  blades.add(cyl(6.5, 6.5, MAT.prop, 0, 0, 0, 24));
  p.add(blades); p.userData.blades = blades;
  const disc = new THREE.Mesh(new THREE.CircleGeometry(64, 64), MAT.blur.clone()); disc.rotation.x = -Math.PI / 2; disc.material.opacity = 0;
  p.add(disc); p.userData.disc = disc;
  p.position.y = 25;
  return p;
}

function buildEsc() {
  const g = new THREE.Group(); g.name = 'esc';
  g.add(rbox(36, 1.6, 36, .4, MAT.pcbEsc, 0, 0, 0));
  for (let i = 0; i < 4; i++) for (let j = 0; j < 3; j++) {               // MOSFET par bras
    const a = i * Math.PI / 2 + Math.PI / 4, r = 9 + j * 3.6;
    g.add(rbox(3.2, 1, 3.6, .2, MAT.chip, Math.cos(a) * r, 1.2, Math.sin(a) * r));
  }
  g.add(rbox(5, .9, 5, .3, MAT.chip, 0, 1.2, 0));
  // pastilles moteur dorées aux 4 coins (3 phases)
  const pads = [];
  [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(([sx, sz]) => {
    for (let k = 0; k < 3; k++) { const pd = rbox(2.4, .3, 3.2, .1, MAT.gold, sx * 15.3, .9, sz * (8 + k * 3.6)); g.add(pd); pads.push(pd.position.clone()); }
  });
  g.userData.pads = pads;
  // pastilles batterie à l'arrière
  g.add(rbox(6, .3, 4, .1, MAT.gold, -5, .9, 15.5)); g.add(rbox(6, .3, 4, .1, MAT.gold, 5, .9, 15.5));
  return g;
}

function buildFc() {
  const g = new THREE.Group(); g.name = 'fc';
  g.add(rbox(36, 1.6, 36, .4, MAT.pcbFc, 0, 0, 0));
  g.add(rbox(8, 1.2, 8, .3, MAT.chip, 0, 1.3, 2));                       // microcontrôleur
  const gyro = rbox(3.2, 1, 3.2, .2, MAT.chip, 7, 1.2, -6); g.add(gyro); g.userData.gyro = gyro;
  g.add(rbox(9, 3.2, 7.5, 1.2, MAT.steel, 0, 2.2, 15.5));                // USB-C
  const led = cyl(.8, .6, MAT.led, -10, 1.2, -12, 12); g.add(led);
  for (let k = 0; k < 10; k++) {                                         // pastilles UART dorées
    const a = k / 10 * Math.PI * 2; g.add(cyl(.9, .3, MAT.gold, Math.cos(a) * 14, .9, Math.sin(a) * 14, 10));
  }
  // silentblocs
  [[-15.25, -15.25], [15.25, -15.25], [-15.25, 15.25], [15.25, 15.25]].forEach(([x, z]) => g.add(cyl(2.6, 2.6, MAT.grommet, x, 0, z, 16)));
  return g;
}

function buildRx() {
  const g = new THREE.Group(); g.name = 'rx';
  g.add(rbox(12, 1.2, 18, .3, MAT.pcbEsc, 0, 0, 0));
  g.add(rbox(5, .8, 5, .2, MAT.chip, 0, .9, -2));
  const ant = new THREE.MeshStandardMaterial({ color: 0x1a1c1d, roughness: .6 });
  [-1, 1].forEach(s => {
    const curve = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 0, 9), new THREE.Vector3(s * 10, 2, 40), new THREE.Vector3(s * 30, 6, 92)]);
    g.add(mesh(new THREE.TubeGeometry(curve, 24, .7, 8), ant));
    const tip = cyl(1.1, 14, MAT.tpu, 0, 0, 0, 12); tip.position.copy(curve.getPoint(1)); tip.lookAt(curve.getPoint(.85)); tip.rotateX(Math.PI / 2); g.add(tip);
  });
  return g;
}

function buildCam() {
  const g = new THREE.Group(); g.name = 'cam';
  g.add(rbox(19, 19, 19, 2.2, MAT.chip, 0, 0, 0));
  const barrel = cyl(7.5, 9, MAT.aluDark, 0, 0, -12.5, 40); barrel.rotation.x = Math.PI / 2; g.add(barrel);
  const ring = cyl(8.2, 2, MAT.anod, 0, 0, -9, 40); ring.rotation.x = Math.PI / 2; g.add(ring);
  const lens = new THREE.Mesh(new THREE.SphereGeometry(6, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2.4), MAT.glass);
  lens.rotation.x = -Math.PI / 2; lens.position.z = -15.5; g.add(lens);
  // flancs de support carbone
  [-1, 1].forEach(s => { const pl = rbox(2, 24, 26, .6, MAT.carbon, s * 11, -2, 0); g.add(pl); });
  return g;
}

function buildVtx() {
  const g = new THREE.Group(); g.name = 'vtx';
  g.add(rbox(20, 1.4, 28, .3, MAT.pcbFc, 0, 0, 0));
  for (let k = 0; k < 7; k++) g.add(rbox(1.2, 5, 22, .2, MAT.alu, -7.2 + k * 2.4, 3.2, 0));   // radiateur
  const coax = new THREE.CatmullRomCurve3([new THREE.Vector3(0, 1, 14), new THREE.Vector3(0, 4, 24), new THREE.Vector3(0, 14, 36)]);
  g.add(mesh(new THREE.TubeGeometry(coax, 20, 1, 10), MAT.rubber));
  const mast = cyl(1.6, 26, MAT.rubber, 0, 27, 36, 16); g.add(mast);
  const lolli = new THREE.Mesh(new THREE.SphereGeometry(6, 32, 16), MAT.tpu); lolli.position.set(0, 44, 36); lolli.scale.set(1, 1.15, .55); lolli.castShadow = true; g.add(lolli);
  g.userData.antennaTip = new THREE.Vector3(0, 44, 36);
  return g;
}

function buildBattery() {
  const g = new THREE.Group(); g.name = 'bat';
  const body = rbox(34, 30, 76, 4, MAT.wrap, 0, 15, 0); g.add(body);
  const lab = new THREE.Mesh(new THREE.PlaneGeometry(70, 28), MAT.label); lab.rotation.set(-Math.PI / 2, 0, Math.PI / 2); lab.position.set(0, 30.15, 0); g.add(lab);
  const lab2 = new THREE.Mesh(new THREE.PlaneGeometry(70, 24), MAT.label); lab2.rotation.y = Math.PI / 2; lab2.position.set(17.15, 15, 0); g.add(lab2);
  // sangle
  g.add(rbox(36.5, 32, 12, 2, MAT.rubber, 0, 15, -26));
  g.add(rbox(14, 2, 9, .8, MAT.anod, 0, 31.4, -26));
  // câbles + XT60 à l'arrière
  [[-3, MAT.wireR], [3, MAT.wireB]].forEach(([x, m]) => {
    const c = new THREE.CatmullRomCurve3([new THREE.Vector3(x, 8, 38), new THREE.Vector3(x * 1.5, 4, 52), new THREE.Vector3(x * .6, -6, 62)]);
    g.add(mesh(new THREE.TubeGeometry(c, 20, 1.6, 10), m));
  });
  const xt = rbox(16, 8.5, 9, 1, MAT.xt60, 0, -9, 66); g.add(xt);
  return g;
}

function buildCap() {
  const g = new THREE.Group(); g.name = 'cap';
  const c = cyl(5, 16, MAT.cap, 0, 0, 0, 32); c.rotation.z = Math.PI / 2; g.add(c);
  const top = cyl(5.05, .8, MAT.alu, 8.2, 0, 0, 32); top.rotation.z = Math.PI / 2; g.add(top);
  return g;
}

// fils moteur : 3 conducteurs le long du bras jusqu'aux pastilles de l'ESC
function buildWires(escY, padsWorld) {
  const g = new THREE.Group(); g.name = 'wires';
  const mats = [MAT.wireR, MAT.wireB, MAT.wireY];
  const list = [];
  MOTORS.forEach(([mx, mz], i) => {
    for (let k = 0; k < 3; k++) {
      const pad = padsWorld[i * 3 + k];
      const dir = new THREE.Vector2(mx, mz).normalize();
      const start = new THREE.Vector3(mx - dir.x * 12 + (k - 1) * 1.5 * -dir.y, 8, mz - dir.y * 12 + (k - 1) * 1.5 * dir.x);
      const mid = new THREE.Vector3(mx * .55 + (k - 1) * 1.6 * -dir.y, 7.4, mz * .55 + (k - 1) * 1.6 * dir.x);
      const end = new THREE.Vector3(pad.x, escY + 1.2, pad.z);
      const curve = new THREE.CatmullRomCurve3([start, mid, new THREE.Vector3(end.x * 1.15, escY + 3, end.z * 1.05), end]);
      const geo = new THREE.TubeGeometry(curve, 48, .8, 8);
      const m = mesh(geo, mats[k]); g.add(m);
      list.push({ mesh: m, count: geo.index.count, end });
    }
  });
  g.userData.list = list;
  return g;
}

export function buildDrone() {
  const root = new THREE.Group(); root.name = 'drone';
  const parts = {};
  parts.frame = buildFrame(); root.add(parts.frame);
  parts.top = buildTop(); root.add(parts.top);
  parts.motors = MOTORS.map(([x, z]) => { const m = buildMotor(); m.position.set(x, 0, z); root.add(m); return m; });
  parts.props = MOTORS.map(([x, z], i) => { const pr = buildProp(i === 0 || i === 3 ? 1 : -1); pr.position.set(x, 25, z); root.add(pr); return pr; });
  parts.esc = buildEsc(); parts.esc.position.set(0, 12, 0); root.add(parts.esc);
  parts.fc = buildFc(); parts.fc.position.set(0, 19.5, 0); root.add(parts.fc);
  parts.rx = buildRx(); parts.rx.position.set(0, 25.5, -26); root.add(parts.rx);
  parts.cam = buildCam(); parts.cam.position.set(0, 18, -50); parts.cam.rotation.x = .38; root.add(parts.cam);
  parts.vtx = buildVtx(); parts.vtx.position.set(0, 26, 36); root.add(parts.vtx);
  parts.bat = buildBattery(); parts.bat.position.set(0, 35, 0); root.add(parts.bat);
  parts.cap = buildCap(); parts.cap.position.set(0, 10, 50); root.add(parts.cap);
  const padsWorld = parts.esc.userData.pads.map(p => p.clone().add(parts.esc.position));
  parts.wires = buildWires(parts.esc.position.y, padsWorld); root.add(parts.wires);
  // points de soudure
  parts.solder = parts.wires.userData.list.map(w => { const s = new THREE.Mesh(new THREE.SphereGeometry(1.5, 16, 10), MAT.solder.clone()); s.position.copy(w.end); s.scale.y = .55; root.add(s); return s; });
  // copies de matériaux par pièce, pour pouvoir surligner une pièce sans toucher les autres
  Object.entries(parts).forEach(([k, v]) => {
    if (k === 'solder') return;
    (Array.isArray(v) ? v : [v]).forEach(obj => obj.traverse(o => { if (o.isMesh) o.material = o.material.clone(); }));
  });
  return { root, parts };
}

// surligne une pièce (émissif sauge) ; k de 0 à 1
const HL = new THREE.Color(.33, .55, .4);
export function highlight(obj, k) {
  (Array.isArray(obj) ? obj : [obj]).forEach(o => o.traverse(m => {
    if (!m.isMesh || !m.material || !('emissive' in m.material)) return;
    if (!m.userData.baseEm) m.userData.baseEm = m.material.emissive.clone();
    m.material.emissive.copy(m.userData.baseEm).lerp(HL, k * .55);
  }));
}

// hélices : rotation + flou progressif
export function spinProps(props, t, rpm) {
  props.forEach((p, i) => {
    const dir = i === 0 || i === 3 ? 1 : -1;
    p.userData.blades.rotation.y = dir * t * rpm * .9;
    const blur = THREE.MathUtils.clamp((rpm - 6) / 14, 0, 1);
    p.userData.blades.children.forEach(b => { b.material.opacity = .72 * (1 - blur * .85); });
    p.userData.disc.material.opacity = blur * .9;
  });
}
