// The Bubbles body map for the Android app: the same model file as the website (body.glb, quantized, no decoder), three.js served from the app itself.
// Nothing here loads from the internet. The app (Kotlin) owns the data and the words: this page only draws, colours by status, and reports a tap.
// Native -> page: bodyApi.setOrgans([{id,status}]), bodyApi.select(id|null), bodyApi.setView("front"|"side"|"back"), bodyApi.setAnatomy("female"|...)
// Page -> native: Bubbles.onReady(), Bubbles.onPick(organId), Bubbles.onError(message)
import * as THREE from "three";
import { GLTFLoader } from "./loaders/GLTFLoader.js";
import { OrbitControls } from "./controls/OrbitControls.js";

const native = window.Bubbles || { onReady() {}, onPick() {}, onError() {} };

// Drawn part -> organ (kept the same as app/lib/organ-map.ts on the website).
const ORGAN_PARTS = {
  heart: ["heart"], lungs: ["lungs"], brain: ["brain"], eyes: ["eye_left", "eye_right"],
  stomach_intestines: ["stomach", "intestines"], liver_pancreas: ["liver", "pancreas"], kidneys_bladder: ["kidneys", "bladder"],
  thyroid: ["thyroid"], uterus_ovaries: ["uterus", "ovaries"], skeleton_muscles: ["skeleton"], skin: ["skin"],
};
const SHELLS = new Set(["skin", "skeleton"]);
const PAINTED = new Set(["eye_left", "eye_right"]); // coloured inside the model itself
const SHELL_OPACITY = { skin: 0.17, skeleton: 0.28 };
// "Talk to a doctor" is a deep red-brown, never a bright red: serious and steady, not alarming.
const STATUS_COLOR = { talk_to_doctor: "#9A3A12", worth_watching: "#FFC83D", steady: "#22C39A", no_data: "#B9AFCB" };
const BASE = {
  brain: "#EEE8FF", heart: "#FFC2D9", lungs: "#CBE6FF", liver: "#FFD6C2", pancreas: "#FFE9A8", stomach: "#FFE0B8", intestines: "#FFD0BC",
  kidneys: "#E2D8FF", bladder: "#D6ECFF", thyroid: "#CFF3E6", uterus: "#FFC9DD", ovaries: "#FFD9E8",
};
const HOME_TARGET = new THREE.Vector3(0, 1.25, 0);
const VIEWS = { front: [0, 0.06, 1], side: [1, 0.06, 0], back: [0, 0.06, -1] };
const SELECTED_SCALE = 1.06;

const canvas = document.getElementById("c");
// A phone draws ~400k triangles: no antialiasing and a capped pixel ratio keep it smooth. (Unmeasured on a real mid-range phone: the app lets the person hide 3D.)
const coarse = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
const renderer = new THREE.WebGLRenderer({ canvas, antialias: !coarse, alpha: true, powerPreference: "default" });
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, coarse ? 1.5 : 2));
renderer.toneMapping = THREE.NeutralToneMapping;
const scene = new THREE.Scene();
scene.add(new THREE.HemisphereLight(0xffffff, 0xf3e6ff, 1.25));
const key = new THREE.DirectionalLight(0xffffff, 1.6);
key.position.set(1.5, 3, 2.5);
scene.add(key);
const camera = new THREE.PerspectiveCamera(32, 1, 0.05, 20);
const controls = new OrbitControls(camera, canvas);
controls.target.copy(HOME_TARGET);
controls.enableDamping = true;
controls.enablePan = false;
controls.minDistance = 0.9;
controls.maxDistance = 4;

let dirty = true;
const request = () => { dirty = true; };
controls.addEventListener("change", request);

const homeDistance = (aspect) => 2.3 * Math.max(1, 0.95 / aspect);
function setView(name) {
  const dir = new THREE.Vector3(...(VIEWS[name] || VIEWS.front)).normalize();
  camera.position.copy(dir.multiplyScalar(homeDistance(camera.aspect))).add(HOME_TARGET);
  controls.target.copy(HOME_TARGET);
  controls.update();
  request();
}
function resize() {
  const w = canvas.clientWidth || window.innerWidth, h = canvas.clientHeight || window.innerHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
  request();
}
window.addEventListener("resize", resize);

// ---- the model ------------------------------------------------------------------------------------------------------------------------
const meshes = new Map();   // part name -> mesh
const springs = new Map();  // part name -> { s, v } scale spring
let organs = [];            // [{id,status}]
let selected = null;
let anatomy = "neutral";
const pivots = new Map();   // organ part -> the pivot group that bumps

function owners() {
  const m = new Map();
  for (const o of organs) for (const part of ORGAN_PARTS[o.id] || [o.id]) if (!m.has(part)) m.set(part, o);
  return m;
}

function makeMaterial(name) {
  if (name === "skin") return new THREE.MeshStandardMaterial({ color: new THREE.Color("#FFF7FA").lerp(new THREE.Color("#FFE3EF"), 0.45), roughness: 0.4, transparent: true, opacity: SHELL_OPACITY.skin, depthWrite: false, side: THREE.FrontSide });
  if (name === "skeleton") return new THREE.MeshStandardMaterial({ color: "#FFF4D2", roughness: 0.55, transparent: true, opacity: SHELL_OPACITY.skeleton, depthWrite: false });
  if (PAINTED.has(name)) return new THREE.MeshStandardMaterial({ vertexColors: true, roughness: 0.28 });
  // Phones get plain satin: clearcoat and sheen are extra lighting passes over ~400k triangles.
  return new THREE.MeshStandardMaterial({ color: BASE[name] || "#F5EEFF", roughness: 0.5, emissive: new THREE.Color("#000000") });
}

function paint() {
  const own = owners();
  for (const [name, mesh] of meshes) {
    const organ = own.get(name);
    // An area the app does not offer (the uterus and ovaries for some profiles) is not drawn at all; the two shells always are.
    mesh.visible = SHELLS.has(name) ? true : Boolean(organ);
    const mat = mesh.material;
    if (!organ || SHELLS.has(name) || PAINTED.has(name)) continue;
    const isSel = organ.id === selected;
    const status = new THREE.Color(STATUS_COLOR[organ.status] || STATUS_COLOR.no_data);
    // Status shows as a glow on top of the organ's calm base tint, never as the organ's own colour.
    mat.emissive.copy(organ.status === "no_data" ? new THREE.Color("#000000") : status).multiplyScalar(isSel ? 0.55 : 0.3);
  }
  request();
}

function applyAnatomy() {
  const skin = meshes.get("skin");
  if (!skin) return;
  const orig = skin.userData.index;
  if (!orig) return;
  if (anatomy !== "female") { skin.geometry.setIndex(new THREE.BufferAttribute(orig, 1)); request(); return; }
  // The model's skin is male-based; a female profile leaves the protruding groin patch out of the faint shell (same rule as the website).
  const pos = skin.geometry.attributes.position;
  const drop = new Uint8Array(pos.count);
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) { v.fromBufferAttribute(pos, i); drop[i] = protrudes(v.x, v.y, v.z) ? 1 : 0; }
  const keep = [];
  for (let i = 0; i < orig.length; i += 3) if (!(drop[orig[i]] || drop[orig[i + 1]] || drop[orig[i + 2]])) keep.push(orig[i], orig[i + 1], orig[i + 2]);
  skin.geometry.setIndex(new THREE.BufferAttribute(orig.constructor === Uint32Array ? new Uint32Array(keep) : new Uint16Array(keep), 1));
  request();
}
const GROIN = { xMax: 0.04, yMin: 0.69, yMax: 0.865 }, ROOT_Y = 0.84, ROOT_Z = 0.062, ROOT_SLOPE = 0.6, BEHIND_Z = -0.012;
const abdomenFront = (y) => ROOT_Z + Math.max(0, y - ROOT_Y) * ROOT_SLOPE;
function protrudes(x, y, z) {
  if (Math.abs(x) > GROIN.xMax || y < GROIN.yMin || y > GROIN.yMax) return false;
  return y < ROOT_Y ? z >= BEHIND_Z : z > abdomenFront(y);
}

new GLTFLoader().load(
  "./body.glb",
  (gltf) => {
    const root = gltf.scene;
    const box = new THREE.Box3();
    root.traverse((o) => {
      if (!o.isMesh) return;
      o.material = makeMaterial(o.name);
      if (SHELLS.has(o.name)) o.renderOrder = 1; // shells draw after the organs so the organs show through
      meshes.set(o.name, o);
      springs.set(o.name, { s: 1, v: 0 });
      if (o.name === "skin" && o.geometry.index) o.userData.index = o.geometry.index.array.slice();
    });
    scene.add(root);
    root.updateMatrixWorld(true);
    // A model made with mesh quantization keeps its real size in the node transforms, so a mesh is never scaled or moved directly:
    // each organ is re-parented (world transform kept) under a pivot at its own centre, and the pivot is what bumps.
    for (const [name, mesh] of meshes) {
      if (SHELLS.has(name)) continue;
      const pivot = new THREE.Group();
      pivot.position.copy(new THREE.Box3().setFromObject(mesh).getCenter(new THREE.Vector3()));
      scene.add(pivot);
      pivot.updateMatrixWorld(true);
      pivot.attach(mesh);
      pivots.set(name, pivot);
    }
    box.setFromObject(root);
    resize();
    setView("front");
    paint();
    applyAnatomy();
    native.onReady();
  },
  undefined,
  (e) => native.onError(String((e && e.message) || e)),
);

// ---- picking: a tap (not a drag) means the nearest organ under the finger, else the skeleton, else the skin ----------------------------
const ray = new THREE.Raycaster();
let down = null;
canvas.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; });
canvas.addEventListener("pointerup", (e) => {
  if (!down) return;
  const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y) > 8;
  down = null;
  if (moved) return;
  const r = canvas.getBoundingClientRect();
  ray.setFromCamera(new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
  const own = owners();
  const hits = ray.intersectObjects([...meshes.values()].filter((m) => m.visible), false).map((h) => h.object.name).filter((n) => own.has(n));
  const part = hits.find((n) => !SHELLS.has(n)) || hits.find((n) => n === "skeleton") || hits[0];
  if (part) native.onPick(own.get(part).id);
});

// ---- motion: the chosen organ bumps up with a short spring; nothing else animates, and the page draws only when something changed ----------
function step(dt) {
  let moving = false;
  const own = owners();
  for (const [name, mesh] of meshes) {
    const sp = springs.get(name);
    const organ = own.get(name);
    const target = organ && organ.id === selected && !SHELLS.has(name) ? SELECTED_SCALE : 1;
    const k = 180, c = 18;
    sp.v += ((target - sp.s) * k - sp.v * c) * dt;
    sp.s += sp.v * dt;
    if (Math.abs(target - sp.s) < 0.0005 && Math.abs(sp.v) < 0.005) { sp.s = target; sp.v = 0; } else moving = true;
    const pivot = pivots.get(name);
    if (pivot) pivot.scale.setScalar(sp.s);   // grows about its own centre, not the origin
  }
  return moving;
}

let last = performance.now();
renderer.setAnimationLoop((now) => {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  const moving = step(dt);
  const damping = controls.update();
  if (dirty || moving || damping) {
    dirty = false;
    renderer.render(scene, camera);
  }
});

window.bodyApi = {
  setOrgans(list) { organs = list || []; paint(); },
  select(id) { selected = id || null; paint(); },
  setView,
  setAnatomy(a) { anatomy = a || "neutral"; applyAnatomy(); },
};
