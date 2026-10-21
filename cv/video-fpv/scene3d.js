// Mise en scène 3D de la vidéo FPV (three.js). Appelée à chaque image par render(t) via window.R3.frame(t).
// Utilise les outils globaux de la page : T, C(), p(), lerp(), E, sceneAlpha(), fbm(), noiseHash().
import * as THREE from 'three';
import { RoomEnvironment } from './vendor/RoomEnvironment.js';
import { buildDrone, spinProps, highlight } from './drone3d.js';

const W = 1920, H = 1080;
const canvas = document.getElementById('gl');
const R = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, preserveDrawingBuffer: true });
R.setSize(W, H, false); R.setPixelRatio(1);
R.toneMapping = THREE.ACESFilmicToneMapping; R.toneMappingExposure = 1.05;
R.outputColorSpace = THREE.SRGBColorSpace;
R.shadowMap.enabled = true; R.shadowMap.type = THREE.PCFSoftShadowMap;
const clamp = THREE.MathUtils.clamp, D2R = Math.PI / 180;

// =================================================================== studio (drone)
const studio = new THREE.Scene();
const pm = new THREE.PMREMGenerator(R);
studio.environment = pm.fromScene(new RoomEnvironment(), .04).texture;
studio.environmentIntensity = .42;
const key = new THREE.DirectionalLight(0xfff4e6, 3.0); key.position.set(-250, 420, 180); key.castShadow = true;
key.shadow.mapSize.set(2048, 2048); Object.assign(key.shadow.camera, { left: -300, right: 300, top: 300, bottom: -300, near: 10, far: 1600 });
key.shadow.bias = -.0004; key.shadow.radius = 4; studio.add(key);
const rim = new THREE.DirectionalLight(0x8DB89A, 2.2); rim.position.set(300, 160, -380); studio.add(rim);
studio.add(new THREE.HemisphereLight(0xcfe8d6, 0x0b1f15, .35));
const ground = new THREE.Mesh(new THREE.PlaneGeometry(5000, 5000), new THREE.ShadowMaterial({ opacity: .38 }));
ground.rotation.x = -Math.PI / 2; ground.position.y = -20; ground.receiveShadow = true; studio.add(ground);
const solderLight = new THREE.PointLight(0xff9a3c, 0, 120, 2); studio.add(solderLight);
const cam = new THREE.PerspectiveCamera(30, W / H, 5, 8000);

const { root, parts } = buildDrone(); studio.add(root);
const rest = new Map();
studio.traverse(o => { if (o.parent === root) rest.set(o, { p: o.position.clone(), r: o.rotation.clone() }); });
const wires = parts.wires.userData.list;

// étincelles de soudure
const SPK = 40, spkGeo = new THREE.BufferGeometry();
spkGeo.setAttribute('position', new THREE.Float32BufferAttribute(new Float32Array(SPK * 3), 3));
const sparks = new THREE.Points(spkGeo, new THREE.PointsMaterial({ color: 0xffc070, size: 2.2, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
root.add(sparks);

function place(o, t, t0, off, dur = 1.1, spin = 0) {
  const r0 = rest.get(o); if (!r0) return;
  if (t < t0) { o.visible = false; return; }
  o.visible = true;
  const k = E.expo(p(t, t0, t0 + dur)), b = 1 - k;
  o.position.set(r0.p.x + off[0] * b, r0.p.y + off[1] * b, r0.p.z + off[2] * b);
  o.rotation.set(r0.r.x, r0.r.y + spin * b, r0.r.z);
}
function orbit(az, el, dist, target, shiftX) {
  const a = az * D2R, e = el * D2R;
  cam.position.set(target.x + Math.sin(a) * Math.cos(e) * dist, target.y + Math.sin(e) * dist, target.z + Math.cos(a) * Math.cos(e) * dist);
  cam.lookAt(target);
  cam.setViewOffset(W, H, -shiftX, 0, W, H);
}
function allVisible() { root.traverse(o => { o.visible = true; }); }
function resetRest() { rest.forEach((v, o) => { o.position.copy(v.p); o.rotation.copy(v.r); o.visible = true; }); root.position.set(0, 0, 0); root.rotation.set(0, 0, 0); }

// =================================================================== vol en immersion
const flyS = new THREE.Scene();
const SKY_H = new THREE.Color(0xe9d7b0), SKY_T = new THREE.Color(0x6f98a8);
flyS.fog = new THREE.Fog(SKY_H, 60, 900);
{ // ciel dégradé
  const g = new THREE.SphereGeometry(3000, 32, 16), col = [];
  const pos = g.attributes.position;
  for (let i = 0; i < pos.count; i++) { const y = pos.getY(i) / 3000, c = SKY_H.clone().lerp(SKY_T, clamp(y * 2.2, 0, 1)); col.push(c.r, c.g, c.b); }
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  flyS.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide, fog: false })));
}
const sun = new THREE.DirectionalLight(0xffd9a0, 3.0); sun.position.set(-500, 160, -700); flyS.add(sun);
flyS.add(new THREE.HemisphereLight(0xcfe2ea, 0x3c4a2a, 1.1));
const terrH = (x, z) => (fbm(x * .0035 + 11, z * .0035 + 7) - .5) * 46 + (fbm(x * .02 + 3, z * .02 + 9) - .5) * 3;
{ // terrain : prairie avec plaques plus sèches
  const g = new THREE.PlaneGeometry(2400, 2400, 220, 220); g.rotateX(-Math.PI / 2);
  const pos = g.attributes.position, col = [];
  const grassA = new THREE.Color(0x3f6b39), grassB = new THREE.Color(0x6d8a45), dry = new THREE.Color(0x9c8f5a);
  for (let i = 0; i < pos.count; i++) {
    const x = pos.getX(i), z = pos.getZ(i), y = terrH(x, z); pos.setY(i, y);
    const n = fbm(x * .012 + 5, z * .012 + 2), d = fbm(x * .004 + 1, z * .004 + 8);
    const c = grassA.clone().lerp(grassB, n).lerp(dry, clamp((d - .55) * 3, 0, .7)); col.push(c.r, c.g, c.b);
  }
  g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3)); g.computeVertexNormals();
  const uv = g.attributes.uv; for (let i = 0; i < uv.count; i++) uv.setXY(i, pos.getX(i) / 6, pos.getZ(i) / 6);
  const gc = document.createElement('canvas'); gc.width = gc.height = 256; const gx = gc.getContext('2d');
  gx.fillStyle = '#808080'; gx.fillRect(0, 0, 256, 256);
  for (let k = 0; k < 9000; k++) { const v = 90 + Math.floor(noiseHash(k * 1.7) * 110); gx.fillStyle = 'rgb(' + v + ',' + (v + 12) + ',' + (v - 10) + ')'; gx.fillRect(noiseHash(k * 3.1) * 256, noiseHash(k * 5.3) * 256, 1 + noiseHash(k) * 2, 2 + noiseHash(k * 9) * 4); }
  const gt = new THREE.CanvasTexture(gc); gt.wrapS = gt.wrapT = THREE.RepeatWrapping; gt.colorSpace = THREE.SRGBColorSpace; gt.anisotropy = 8;
  flyS.add(new THREE.Mesh(g, new THREE.MeshStandardMaterial({ vertexColors: true, map: gt, roughness: 1 })));
  // collines au loin
  const hg = new THREE.CylinderGeometry(1500, 1500, 1, 160, 1, true), hp = hg.attributes.position;
  for (let i = 0; i < hp.count; i++) { const a = Math.atan2(hp.getZ(i), hp.getX(i)); if (hp.getY(i) > 0) hp.setY(i, 40 + 90 * fbm(a * 3 + 4, 1.3) + 40 * fbm(a * 9, 5)); else hp.setY(i, -20); }
  hg.computeVertexNormals();
  flyS.add(new THREE.Mesh(hg, new THREE.MeshStandardMaterial({ color: 0x4d6e52, roughness: 1, side: THREE.BackSide })));
}
{ // arbres (instanciés)
  const N = 2600, trunk = new THREE.CylinderGeometry(.25, .35, 2.4, 8), crown = (() => { const a = new THREE.ConeGeometry(2.4, 5, 12); a.translate(0, -1.2, 0); const b = new THREE.ConeGeometry(1.7, 4.4, 12); b.translate(0, 1.6, 0); const pa = a.toNonIndexed(), pb = b.toNonIndexed(); const m = new THREE.BufferGeometry(); const arr = new Float32Array(pa.attributes.position.array.length + pb.attributes.position.array.length); arr.set(pa.attributes.position.array); arr.set(pb.attributes.position.array, pa.attributes.position.array.length); m.setAttribute('position', new THREE.BufferAttribute(arr, 3)); m.computeVertexNormals(); return m; })();
  const it = new THREE.InstancedMesh(trunk, new THREE.MeshStandardMaterial({ color: 0x4a3a2a, roughness: 1 }), N);
  const ic = new THREE.InstancedMesh(crown, new THREE.MeshStandardMaterial({ color: 0x2d4f2c, roughness: .95 }), N);
  const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3();
  for (let i = 0; i < N; i++) {
    let z = (noiseHash(i * 7 + 2) - .5) * 2200, x = i < 1300 ? pathX(z) + (noiseHash(i * 3 + 1) - .5) * 160 : (noiseHash(i * 3 + 1) - .5) * 2200;
    if (Math.abs(x - pathX(z)) < 9) x += 14 * Math.sign(x - pathX(z) || 1);          // couloir de vol dégagé
    const y = terrH(x, z), sc = .7 + noiseHash(i * 11) * .9;
    s.set(sc, sc, sc); m.compose(new THREE.Vector3(x, y + 1.2 * sc, z), q, s); it.setMatrixAt(i, m);
    m.compose(new THREE.Vector3(x, y + 5.4 * sc, z), q, s); ic.setMatrixAt(i, m);
  }
  flyS.add(it, ic);
}
function pathX(z) { return 26 * Math.sin(z / 95) + 10 * Math.sin(z / 37); }
const gates = [];
{ // portes de course
  const white = new THREE.MeshStandardMaterial({ color: 0xf2f4f0, roughness: .6 }), green = new THREE.MeshStandardMaterial({ color: 0x2F7A55, roughness: .6 });
  for (let k = 0; k < 9; k++) {
    const z = -70 - k * 48, x = pathX(z), y = terrH(x, z), g = new THREE.Group();
    const bar = (w, h, d, px, py, mat) => { const b = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); b.position.set(px, py, 0); g.add(b); };
    bar(.35, 2.6, .35, -1.6, 1.3, k % 2 ? white : green); bar(.35, 2.6, .35, 1.6, 1.3, k % 2 ? white : green);
    bar(3.55, .35, .35, 0, 2.6, white); bar(3.55, .25, .3, 0, .9, green);
    g.position.set(x, y, z); g.rotation.y = Math.atan(26 / 95 * Math.cos(z / 95) + 10 / 37 * Math.cos(z / 37)) * -1;
    flyS.add(g); gates.push(g);
  }
}
const fcam = new THREE.PerspectiveCamera(98, W / H, .2, 4000);

function renderFlight(t) {
  const s = 22 * t + 8, z = -s, x = pathX(z), y = terrH(x, z) + 2.2 + Math.sin(t * .8) * .5;
  const za = z - 16, xa = pathX(za), ya = terrH(xa, za) + 1.6;
  fcam.position.set(x, y, z); fcam.lookAt(xa, ya + 1.5, za);
  const dx = pathX(z - 2) - pathX(z + 2), bank = clamp(dx * 9, -32, 32) + Math.sin(t * 2.1) * 2.5;
  fcam.rotateZ(bank * D2R);
  R.shadowMap.enabled = false; R.toneMappingExposure = 1.3;
  R.render(flyS, fcam); R.toneMappingExposure = 1.05;
}

// =================================================================== images
function renderStudio() { R.shadowMap.enabled = true; R.render(studio, cam); }

window.R3 = {
  frame(t) {
    const c1 = T.c1, c2 = T.c2, c4 = T.c4;
    const flyEnd = C('c1end', 12.2), heroT = C('c1d', 18.8), PTs = ['p0', 'p1', 'p2', 'p3', 'p4', 'p5', 'p6'];
    let a = 0;
    // ---------------- C1 : vol puis plan studio
    if (t < flyEnd + .9) {
      a = sceneAlpha(t, c1) * (1 - p(t, flyEnd, flyEnd + .8));
      canvas.style.opacity = a; if (a > 0) renderFlight(t); return;
    }
    if (t >= heroT - .5 && t < c1[1]) {
      a = sceneAlpha(t, c1) * p(t, heroT - .5, heroT + .4);
      canvas.style.opacity = a; resetRest();
      root.position.y = 40 + Math.sin(t * 1.4) * 6; root.rotation.set(Math.sin(t * .9) * .05, (t - heroT) * .18 + .5, Math.sin(t * 1.1) * .06);
      spinProps(parts.props, t, 40); highlight(Object.values(parts).flat().filter(o => o.isObject3D), 0);
      orbit(30 + (t - heroT) * 4, 18, 640, new THREE.Vector3(0, 40, 0), 380);
      renderStudio(); return;
    }
    // ---------------- C2 : assemblage
    if (t >= c2[0] - .1 && t < c2[1]) {
      a = sceneAlpha(t, c2); canvas.style.opacity = a;
      if (a <= 0) return;
      resetRest();
      const PT = [C('p0', 26), C('p1', 30.5), C('p2', 35.5), C('p3', 40.5), C('p4', 47.5), C('p5', 50.5), C('p6', 55.5)], ASM = C('asm', 60.5);
      place(parts.frame, t, PT[0], [0, -70, 0], 1.6, .6);
      parts.motors.forEach((m, i) => place(m, t, PT[1] + i * .25, [0, 110, 0], 1.0, 2.5));
      parts.props.forEach((m, i) => place(m, t, ASM - 1.6 + i * .15, [0, 70, 0], .9, 3));
      place(parts.esc, t, PT[2], [0, 90, 0]); place(parts.cap, t, PT[2] + .4, [0, 0, 90]);
      place(parts.fc, t, PT[3], [0, 110, 0]);
      place(parts.rx, t, PT[4], [0, 40, -120]);
      place(parts.cam, t, PT[5], [0, 20, -140]); place(parts.vtx, t, PT[5] + .6, [0, 60, 140]);
      // batterie : posée, puis retirée pendant le câblage, puis remise
      const topOff = E.inOut(p(t, ASM - .2, ASM + .7)) * (1 - E.inOut(p(t, C('asmEnd', 69) - .3, C('asmEnd', 69) + .7)));
      place(parts.top, t, PT[6] - .9, [0, 90, 0], .9);
      if (t >= PT[6]) { parts.top.position.y = rest.get(parts.top).p.y + topOff * 120; parts.top.visible = topOff < .98; }
      const batOff = E.inOut(p(t, ASM, ASM + .9)) * (1 - E.inOut(p(t, C('asmEnd', 69), C('asmEnd', 69) + 1)));
      place(parts.bat, t, PT[6], [0, 150, 0], 1.1, .4);
      if (t >= PT[6] + 1.1) { parts.bat.position.y = rest.get(parts.bat).p.y + batOff * 160; parts.bat.visible = batOff < .98; }
      // surlignage de la pièce qui vient d'arriver
      const groups = [parts.frame, parts.motors, parts.esc, parts.fc, parts.rx, [parts.cam, parts.vtx], parts.bat];
      groups.forEach((g, i) => { const k = t >= PT[i] ? Math.max(0, 1 - Math.abs(t - PT[i] - 1.3) / 1.2) : 0; highlight(g, k * (.6 + .4 * Math.sin(t * 9))); });
      // gyroscope qui « pulse »
      const gy = parts.fc.userData.gyro; if (gy && gy.material.emissive) gy.material.emissive.setRGB(0, .9 * Math.max(0, Math.sin((t - PT[3]) * 6)) * p(t, PT[3] + 1, PT[3] + 1.4) * (1 - p(t, PT[4], PT[4] + .4)), .5 * Math.max(0, Math.sin((t - PT[3]) * 6)) * p(t, PT[3] + 1, PT[3] + 1.4) * (1 - p(t, PT[4], PT[4] + .4)));
      // câblage puis soudure
      let active = null;
      wires.forEach((w, i) => {
        const t0 = ASM + 1.1 + i * .38, f = E.inOut(p(t, t0, t0 + .9));
        w.mesh.visible = f > 0; w.mesh.geometry.setDrawRange(0, Math.floor(w.count * f / 3) * 3);
        const sd = parts.solder[i], ts = t0 + .95, heat = t >= ts ? Math.max(0, 1 - (t - ts) / 1.1) : 0;
        sd.visible = t >= ts; sd.scale.setScalar(t >= ts ? E.back(p(t, ts, ts + .3)) : 0); sd.scale.y *= .55;
        sd.material.emissiveIntensity = heat * 3.2;
        if (heat > .35) active = sd;
      });
      if (t < ASM) wires.forEach(w => { w.mesh.visible = false; });
      if (active) {
        solderLight.position.copy(active.position).add(new THREE.Vector3(0, 6, 0)); solderLight.intensity = 9000 * (.7 + .3 * Math.sin(t * 60));
        const arr = spkGeo.attributes.position.array;
        for (let k = 0; k < SPK; k++) { const ph = ((t * 3 + noiseHash(k)) % 1), ang = noiseHash(k * 3) * 6.283, v = 8 + noiseHash(k * 5) * 18;
          arr[k * 3] = active.position.x + Math.cos(ang) * v * ph; arr[k * 3 + 1] = active.position.y + 2 + (18 * ph - 30 * ph * ph); arr[k * 3 + 2] = active.position.z + Math.sin(ang) * v * ph; }
        spkGeo.attributes.position.needsUpdate = true; sparks.visible = true;
      } else { solderLight.intensity = 0; sparks.visible = false; }
      // hélices : essai moteurs à la fin
      const rpm = 40 * E.inOut(p(t, C('asmEnd', 69) + .6, C('asmEnd', 69) + 2));
      spinProps(parts.props, t, rpm); if (rpm > 0) root.position.y = Math.sin(t * 1.3) * 2 * rpm / 40;
      // caméra : tour lent, gros plan pendant le câblage, recul à la fin
      const close = E.inOut(p(t, ASM + .3, ASM + 1.6)) * (1 - E.inOut(p(t, C('asmEnd', 69), C('asmEnd', 69) + 1.6)));
      const az = 28 + (t - c2[0]) * 1.5, el = lerp(30, 52, close), dist = lerp(lerp(700, 600, p(t, c2[0], ASM)), 290, close);
      orbit(az, el, dist, new THREE.Vector3(0, lerp(26, 14, close), 0), lerp(360, 470, close));
      renderStudio(); return;
    }
    // ---------------- C4 : réaction aux manches
    if (t >= c4[0] && t < c4[1]) {
      const att = window.ATT || { roll: 0, pitch: 0, yaw: 0, z: 0 };
      a = (window.ATTA || 0); canvas.style.opacity = a; if (a <= 0) return;
      resetRest(); highlight(Object.values(parts).flat().filter(o => o.isObject3D), 0);
      root.rotation.order = 'YXZ'; root.rotation.set(-att.pitch * D2R, att.yaw * D2R, -att.roll * D2R);
      root.position.y = 70 + att.z * .55;
      spinProps(parts.props, t, 40);
      orbit(32, 14, 560, new THREE.Vector3(0, 92, 0), 360);
      ground.material.opacity = .16; renderStudio(); ground.material.opacity = .38; return;
    }
    canvas.style.opacity = 0;
  }
};
window.R3ready = true;
