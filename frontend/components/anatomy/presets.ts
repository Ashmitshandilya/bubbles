// The 3D body as plain data: no React, no three.js, so every rule here is unit-tested (presets.test.ts).
// Coordinates: y is up, the figure is about 2.4 units tall and faces +z (towards the camera), so the person's left is +x.
// Sphere parts take [radius]; capsule parts take [radius, length]. A sphere with a non-uniform scale is an ellipsoid.

export type Anatomy = "female" | "male" | "neutral";
export type Vec3 = [number, number, number];
export type Geometry = "sphere" | "capsule";

export interface Part {
  geometry: Geometry;
  args: number[];
  position: Vec3;
  scale?: Vec3;
  rotation?: Vec3;
}

export interface BodyPart extends Part {
  id: string;
}

export interface OrganSpec {
  id: string;
  label: string;
  /** Centre of the organ: the camera eases here and the halo sits here. */
  focus: Vec3;
  /** Parts in absolute figure coordinates (the renderer subtracts `focus`). */
  parts: Part[];
  /** Radius of the invisible tap target, so tiny organs (eyes, thyroid) are easy to hit. */
  hit: number;
}

interface Shape {
  shoulder: number;
  waist: number;
  hip: number;
}

const SHAPES: Record<Anatomy, Shape> = {
  female: { shoulder: 0.3, waist: 0.19, hip: 0.29 },
  male: { shoulder: 0.37, waist: 0.22, hip: 0.23 },
  neutral: { shoulder: 0.33, waist: 0.205, hip: 0.25 },
};

export const ANATOMIES: readonly Anatomy[] = ["female", "male", "neutral"];

export function isAnatomy(value: unknown): value is Anatomy {
  return typeof value === "string" && (ANATOMIES as readonly string[]).includes(value);
}

const mirrorX = (v: Vec3): Vec3 => [-v[0], v[1], v[2]];

/** The same part on both sides of the body (x mirrored; z rotation mirrored too). */
function pair(part: Part): Part[] {
  const left: Part = { ...part, position: mirrorX(part.position) };
  if (part.rotation) left.rotation = [part.rotation[0], part.rotation[1], -part.rotation[2]];
  return [part, left];
}

/** The silhouette: head, neck, chest, waist, pelvis, two arms with hands, two legs with feet. */
export function figure(anatomy: Anatomy): BodyPart[] {
  const { shoulder, waist, hip } = SHAPES[anatomy];
  const body: BodyPart[] = [
    { id: "head", geometry: "sphere", args: [0.17], position: [0, 0.95, 0], scale: [0.9, 1.12, 0.95] },
    { id: "neck", geometry: "capsule", args: [0.06, 0.1], position: [0, 0.77, 0] },
    { id: "chest", geometry: "sphere", args: [1], position: [0, 0.52, 0], scale: [shoulder * 0.95, 0.27, 0.2] },
    { id: "abdomen", geometry: "sphere", args: [1], position: [0, 0.18, 0], scale: [waist, 0.27, 0.17] },
    { id: "pelvis", geometry: "sphere", args: [1], position: [0, -0.12, 0], scale: [hip, 0.17, 0.18] },
  ];
  const sided: Array<[string, Part]> = [
    ["upper-arm", { geometry: "capsule", args: [0.06, 0.28], position: [shoulder + 0.04, 0.4, 0], rotation: [0, 0, 0.08] }],
    ["forearm", { geometry: "capsule", args: [0.05, 0.3], position: [shoulder + 0.09, 0.07, 0], rotation: [0, 0, 0.05] }],
    ["hand", { geometry: "sphere", args: [0.055], position: [shoulder + 0.11, -0.15, 0], scale: [0.85, 1.25, 0.6] }],
    ["thigh", { geometry: "capsule", args: [0.1, 0.45], position: [hip * 0.52, -0.58, 0] }],
    ["shin", { geometry: "capsule", args: [0.075, 0.45], position: [hip * 0.5, -1.06, 0] }],
    ["foot", { geometry: "sphere", args: [0.07], position: [hip * 0.5, -1.36, 0.06], scale: [1, 0.55, 1.7] }],
  ];
  for (const [id, part] of sided) {
    pair(part).forEach((p, i) => body.push({ id: `${id}-${i === 0 ? "l" : "r"}`, ...p }));
  }
  return body;
}

function organ(id: string, label: string, focus: Vec3, parts: Part[], hit = 0.1): OrganSpec {
  return { id, label, focus, parts, hit };
}

const sphere = (r: number, position: Vec3, scale?: Vec3): Part => ({ geometry: "sphere", args: [r], position, scale });
const capsule = (r: number, length: number, position: Vec3, rotation?: Vec3): Part => ({
  geometry: "capsule", args: [r, length], position, rotation,
});

/** Names shown for the reproductive system, by anatomy. Neutral stays general. */
export const REPRODUCTIVE_LABEL: Record<Anatomy, string> = {
  female: "Uterus and ovaries",
  male: "Prostate and testes",
  neutral: "Reproductive",
};

const BASE_LABELS: Record<string, string> = {
  brain: "Brain",
  eyes: "Eyes",
  ears: "Ears",
  mouth: "Mouth and teeth",
  thyroid: "Thyroid",
  heart: "Heart",
  lungs: "Lungs",
  breasts: "Breasts",
  liver: "Liver",
  pancreas: "Pancreas",
  kidneys: "Kidneys",
  digestive_system: "Digestion",
  bladder: "Bladder",
  reproductive_system: "Reproductive",
  musculoskeletal_system: "Muscles and bones",
  skin: "Skin",
};

/** Plain-language name of a body system. Unknown ids get a readable fallback instead of a raw key. */
export function organLabel(id: string, anatomy: Anatomy = "neutral"): string {
  if (id === "reproductive_system") return REPRODUCTIVE_LABEL[anatomy];
  return BASE_LABELS[id] ?? id.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase());
}

function reproductive(anatomy: Anatomy): Part[] {
  if (anatomy === "female") {
    return [sphere(0.055, [0, -0.1, 0.04], [1.2, 0.9, 0.9]), ...pair(sphere(0.03, [0.11, -0.07, 0.02]))];
  }
  if (anatomy === "male") {
    return [sphere(0.045, [0, -0.2, 0.05]), ...pair(sphere(0.04, [0.05, -0.32, 0.1], [1, 1.25, 1]))];
  }
  return [sphere(0.06, [0, -0.12, 0.04], [1.2, 0.9, 0.9])];
}

/** Every organ the map can draw for an anatomy. Which of them are shown is decided by the caller (see `organsFor`). */
function allOrgans(anatomy: Anatomy): OrganSpec[] {
  const list: OrganSpec[] = [
    organ("brain", organLabel("brain"), [0, 0.99, -0.01], [sphere(0.12, [0, 0.99, -0.01], [1, 0.85, 1.05])], 0.14),
    organ("eyes", organLabel("eyes"), [0, 0.97, 0.15], pair(sphere(0.03, [0.065, 0.97, 0.15])), 0.1),
    organ("ears", organLabel("ears"), [0, 0.94, 0], pair(sphere(0.028, [0.165, 0.94, 0], [0.6, 1.3, 0.9])), 0.1),
    organ("mouth", organLabel("mouth"), [0, 0.86, 0.15], [sphere(0.035, [0, 0.86, 0.15], [1.5, 0.6, 0.7])], 0.09),
    organ("thyroid", organLabel("thyroid"), [0, 0.73, 0.06], [sphere(0.03, [0, 0.73, 0.06], [2.1, 0.7, 0.8])], 0.1),
    organ("lungs", organLabel("lungs"), [0, 0.53, 0.03], pair(capsule(0.065, 0.2, [0.1, 0.53, 0.03])), 0.14),
    organ("heart", organLabel("heart"), [0.05, 0.46, 0.09], [sphere(0.07, [0.05, 0.46, 0.09], [0.95, 1.1, 0.85])], 0.1),
    organ("liver", organLabel("liver"), [-0.09, 0.28, 0.06], [sphere(0.07, [-0.09, 0.28, 0.06], [1.6, 0.8, 0.9])], 0.12),
    organ("pancreas", organLabel("pancreas"), [0.02, 0.2, 0.04], [sphere(0.035, [0.02, 0.2, 0.04], [2.6, 0.7, 0.8])], 0.1),
    organ("kidneys", organLabel("kidneys"), [0, 0.17, -0.05], pair(sphere(0.045, [0.12, 0.17, -0.05], [0.7, 1.4, 0.8])), 0.11),
    organ("digestive_system", organLabel("digestive_system"), [0, 0.02, 0.07], [sphere(0.1, [0, 0.02, 0.07], [1.2, 0.9, 0.75])], 0.13),
    organ("bladder", organLabel("bladder"), [0, -0.17, 0.08], [sphere(0.05, [0, -0.17, 0.08])], 0.09),
    organ("reproductive_system", REPRODUCTIVE_LABEL[anatomy], anatomy === "male" ? [0, -0.25, 0.07] : [0, -0.09, 0.03], reproductive(anatomy), 0.12),
    organ("musculoskeletal_system", organLabel("musculoskeletal_system"), [0, -0.83, 0.06], pair(sphere(0.06, [SHAPES[anatomy].hip * 0.5, -0.83, 0.06])), 0.12),
    organ("skin", organLabel("skin"), [SHAPES[anatomy].shoulder + 0.09, 0.07, 0.04], [sphere(0.045, [SHAPES[anatomy].shoulder + 0.09, 0.07, 0.04], [0.9, 2.2, 0.5])], 0.1),
  ];
  if (anatomy === "female") {
    list.push(organ("breasts", organLabel("breasts"), [0, 0.46, 0.18], pair(sphere(0.07, [0.1, 0.46, 0.18], [1, 0.95, 0.8])), 0.12));
  }
  return list;
}

/**
 * The organs to draw. With no `ids` (or none that the map knows) every organ for the anatomy is drawn; with `ids` only
 * those the backend reports, so a body system appears on the map the day the backend starts assessing it.
 */
export function organsFor(anatomy: Anatomy, ids?: readonly string[]): OrganSpec[] {
  const all = allOrgans(anatomy);
  if (!ids || ids.length === 0) return all;
  const wanted = new Set(ids);
  const chosen = all.filter((o) => wanted.has(o.id));
  return chosen.length > 0 ? chosen : all;
}
