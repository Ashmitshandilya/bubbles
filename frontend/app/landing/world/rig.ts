import { lerp, range, smooth } from "../story/store";
import { feelAt, feelBand } from "../story/feel";

/**
 * Choreography. Each chapter is a function of its scroll progress `p` that says
 * where the camera is, where Bubbles stands, what Bubbles does and looks at, and what
 * shape the living spine takes. The world blends neighbouring chapters during
 * hand-overs, so every transition is a continuous morph.
 */

export type PoseName =
  | "idle" | "wave" | "pointA" | "pointB" | "pointUpB" | "present" | "think" | "sit" | "cheer" | "surprised" | "fly" | "lookBack";

export type LayoutName = "column" | "scatter" | "orbit" | "cycle" | "lattice" | "timeline" | "halo" | "wave";
export type Look = "pointer" | "camera" | "focus" | "nerve" | "left" | "right" | "up";

export type Rig = {
  cam: [number, number, number];
  target: [number, number, number];
  fov: number;
  bubbles: {
    /** "screen": x/y are normalised screen coords, z is distance from the camera.
     *  "ring": Bubbles sits on top of the cycle ring. */
    mode: "screen" | "ring";
    x: number;
    y: number;
    z: number;
    scale: number;
    pose: PoseName;
    turn: number;
    look: Look;
    show: number;
    /** 0..1: how tightly Bubbles tracks its anchor (1 = glued, for walking on a path) */
    stiff?: number;
  };
  spine: {
    layout: LayoutName;
    param: number;
    pos: [number, number, number];
    rot: [number, number, number];
    scale: number;
    /** 0..1 attach the spine group to Bubbles (orbit / halo) */
    follow: number;
    dim: number;
  };
  nerves: number;
  motes: number;
};

export type Env = { mobile: boolean; aspect: number; time: number; intro: number };

/* ── Travel paths ─────────────────────────────────────────────────────────── */

/** Carry hop (Track to Cycle): the arc's lift in world units, and in viewport fractions without WebGL. */
export const HOP_LIFT = { desktop: [0, 1.6, 0], mobile: [-1.0, 0.3, 0] } as const;
export const HOP_LIFT_PX = { desktop: [0, -0.3], mobile: [-0.34, -0.06] } as const;

/** Memory walk (desktop): four waymark stones and the three legs Bubbles walks between them. */
export const WALK_STOPS = [0, 1 / 3, 2 / 3, 1] as const;
export const WALK_LEGS = [
  [0.16, 0.27],
  [0.41, 0.52],
  [0.66, 0.77],
] as const;
export const walkU = (p: number) => WALK_LEGS.reduce((sum, [a, b]) => sum + smooth(range(p, a, b)) / 3, 0);
/** Pelvis position on the walk in NDC, with three soft hills between the stones. */
export const walkPoint = (u: number) => ({ x: lerp(-0.62, 0.3, u), y: -0.62 + 0.03 * Math.abs(Math.sin(3 * Math.PI * u)) });

const rig = (r: Rig) => r;

const enter = (p: number, e: Env): Rig => {
  const dive = smooth(range(p, 0.4, 1));
  return rig({
    cam: [0, lerp(0.55, 0.3, dive), lerp(10, 9, dive)],
    target: [0, 0.55, 0],
    fov: 35,
    bubbles: e.mobile
      ? { mode: "screen", x: 0.02, y: -0.06, z: 10.5, scale: 0.92, pose: dive > 0.25 ? "pointUpB" : "idle", turn: dive * -0.5, look: "pointer", show: 1 }
      : { mode: "screen", x: lerp(0.3, 0.22, dive), y: -0.36, z: 10, scale: 1.18, pose: dive > 0.2 ? "pointB" : "idle", turn: dive * -0.55, look: dive > 0.2 ? "left" : "pointer", show: 1 },
    spine: {
      layout: "column",
      param: 0,
      pos: e.mobile ? [lerp(1.7, 0, dive), lerp(1.9, 0.6, dive), lerp(-7, -3, dive)] : [lerp(4.9, 0.85, dive), lerp(0.3, 0.1, dive), lerp(-5, -2, dive)],
      rot: [0, e.time * 0.18, lerp(0.08, 0, dive)],
      scale: e.mobile ? 0.5 : lerp(0.82, 0.95, dive),
      follow: 0,
      dim: lerp(0.55, 1, dive),
    },
    nerves: 0,
    motes: lerp(0.35, 0.9, dive),
  });
};

const body = (p: number, e: Env): Rig => {
  const dolly = smooth(range(p, 0, 0.75));
  return rig({
    cam: e.mobile ? [0, lerp(0.1, -0.2, dolly), lerp(16, 14.5, dolly)] : [lerp(0.2, 1.0, dolly), lerp(0.1, 0.45, dolly), lerp(12.2, 10.6, dolly)],
    target: [0, lerp(0.15, 0.4, dolly), 0],
    fov: 35,
    bubbles: e.mobile
      ? { mode: "screen", x: 0.6, y: 0.08, z: 9, scale: 0.34, pose: "pointB", turn: -0.4, look: "nerve", show: 1 }
      : { mode: "screen", x: -0.64, y: -0.6, z: 9.5, scale: 0.62, pose: "pointA", turn: 0.5, look: "nerve", show: 1 },
    spine: {
      layout: "column",
      param: 0,
      pos: e.mobile ? [-0.1, -1.25, 0] : [0.85, -0.42, 0],
      rot: [0, lerp(0.85, 0.3, p), 0],
      scale: e.mobile ? 0.52 : 1,
      follow: 0,
      dim: 1,
    },
    nerves: range(p, 0.08, 0.78),
    motes: 1,
  });
};

const noise = (p: number, e: Env): Rig =>
  rig({
    cam: [0, 0.3, lerp(9.5, 7.6, p)],
    target: [0, 0.3, 0],
    fov: lerp(35, 40, p),
    bubbles: { mode: "screen", x: 0, y: e.mobile ? -0.72 : -0.62, z: 9, scale: e.mobile ? 0.5 : 0.62, pose: p < 0.55 ? "surprised" : "think", turn: 0, look: p < 0.55 ? "pointer" : "up", show: 1 },
    spine: { layout: "scatter", param: p, pos: [0, 0.2, 0], rot: [0, p * 0.8, 0], scale: 1, follow: 0, dim: 1 },
    nerves: 0,
    motes: 1,
  });

const track = (p: number, e: Env): Rig =>
  rig({
    cam: [0, 0.4, 9],
    target: [0, 0.4, 0],
    fov: 35,
    bubbles: e.mobile
      ? { mode: "screen", x: 0.55, y: -0.82, z: 9, scale: 0.4, pose: p < 0.45 ? "idle" : p < 0.78 ? "present" : "cheer", turn: 0.45, look: "focus", show: 1 }
      : { mode: "screen", x: -0.64, y: -0.5, z: 9, scale: 0.86, pose: p < 0.45 ? "idle" : p < 0.78 ? "present" : "cheer", turn: 0.5, look: "focus", show: 1 },
    spine: { layout: "orbit", param: p, pos: [0, 0, 0], rot: [0.25, 0, -0.12], scale: e.mobile ? 0.55 : 0.85, follow: 1, dim: 1 },
    nerves: 0,
    motes: 0.8,
  });

const cycle = (p: number, e: Env): Rig => {
  const history = smooth(range(p, 0.64, 0.8));
  const day = range(p, 0.04, 0.62) * 27.999;
  const ringPos: [number, number, number] = e.mobile
    ? [lerp(0, -0.55, history), lerp(0.55, 1.55, history), 0]
    : [lerp(2.0, -3.4, history), lerp(-0.75, 0.6, history), lerp(0, -1.5, history)];
  const onRing = history < 0.35;
  return rig({
    cam: [0, 0.2, 10.5],
    target: [0, 0.05, 0],
    fov: 35,
    bubbles: onRing
      ? { mode: "ring", x: 0, y: 0, z: 0, scale: e.mobile ? 0.44 : 0.58, pose: "sit", turn: 0, look: feelBand(feelAt(day)) === "heavy" ? "focus" : "pointer", show: 1 }
      : e.mobile
        ? { mode: "screen", x: 0.5, y: 0.28, z: 10, scale: 0.4, pose: "pointB", turn: -0.35, look: "left", show: 1 }
        : { mode: "screen", x: 0.02, y: -0.42, z: 10, scale: 0.7, pose: "pointA", turn: 0.45, look: "right", show: 1 },
    spine: {
      layout: "cycle",
      param: day,
      pos: ringPos,
      rot: [-0.16, 0, 0],
      scale: (e.mobile ? 0.6 : 0.86) * lerp(1, 0.6, history),
      follow: 0,
      dim: 1,
    },
    nerves: 0,
    motes: 0.85,
  });
};

const connect = (p: number, e: Env): Rig =>
  rig({
    cam: [0, 0, 10],
    target: [0, 0, 0],
    fov: 35,
    bubbles: { mode: "screen", x: 0, y: e.mobile ? -0.12 : -0.2, z: 10, scale: e.mobile ? 0.42 : 0.6, pose: "idle", turn: 0, look: "focus", show: 1 },
    spine: { layout: "lattice", param: p, pos: [0, 0, -4], rot: [0.2, p * 0.9, 0], scale: 1, follow: 0, dim: 0.8 },
    nerves: 0,
    motes: 0.7,
  });

const remember = (p: number, e: Env): Rig => {
  const travel = smooth(range(p, 0.05, 0.9));
  // Desktop: Bubbles walks the memory road in three legs, pausing on a stone while each zoom level reads.
  const wp = walkPoint(walkU(p));
  const walking = WALK_LEGS.some(([a, b]) => p > a && p < b);
  return rig({
    cam: [0, 0.3, 10],
    target: [0, 0.3, 0],
    fov: 35,
    bubbles: {
      mode: "screen",
      x: e.mobile ? lerp(0.45, 0.6, travel) : wp.x,
      y: e.mobile ? 0.6 : wp.y,
      z: 10,
      scale: e.mobile ? 0.34 : 0.6,
      pose: p > 0.86 ? "lookBack" : "idle",
      turn: p > 0.86 ? -0.7 : 0.7,
      look: p > 0.86 ? "left" : e.mobile || walking ? "right" : "up",
      show: 1,
      stiff: e.mobile ? 0 : 1,
    },
    spine: { layout: "timeline", param: p, pos: [0, e.mobile ? -3.1 : -2.75, -0.5], rot: [0.12, 0, 0], scale: e.mobile ? 0.7 : 1, follow: 0, dim: 0.9 },
    nerves: 0,
    motes: 0.7,
  });
};

const companion = (p: number, e: Env): Rig =>
  rig({
    cam: [0, 0.3, 9],
    target: [0, 0.3, 0],
    fov: 35,
    bubbles: e.mobile
      ? { mode: "screen", x: 0.66, y: 0.6, z: 9, scale: 0.34, pose: p < 0.16 ? "idle" : p < 0.6 ? "think" : "present", turn: -0.35, look: "focus", show: 1 }
      : { mode: "screen", x: 0.4, y: -0.4, z: 9, scale: 1.0, pose: p < 0.16 ? "idle" : p < 0.6 ? "think" : "present", turn: -0.3, look: p < 0.6 ? "focus" : "camera", show: 1 },
    spine: { layout: "halo", param: p, pos: [0, 1.25, 0], rot: [0.18, 0, 0.06], scale: e.mobile ? 0.45 : 0.62, follow: 1, dim: 1 },
    nerves: 0,
    motes: 0.6,
  });

const care = (p: number, e: Env): Rig => {
  const walk = range(p, 0.02, 0.95);
  return rig({
    cam: [0, 0.3, 10],
    target: [0, 0.3, 0],
    fov: 35,
    bubbles: {
      mode: "screen",
      x: lerp(0.66, -0.66, walk) * (e.mobile ? 0.75 : 1),
      y: e.mobile ? -0.8 : -0.6,
      z: 10,
      scale: e.mobile ? 0.42 : 0.62,
      pose: "present",
      turn: -0.55,
      look: "up",
      show: 1,
    },
    spine: { layout: "wave", param: p, pos: [0, e.mobile ? -3 : -2.5, -1.2], rot: [0, 0, 0], scale: 1, follow: 0, dim: 0.75 },
    nerves: 0,
    motes: 0.35,
  });
};

const bubbles = (p: number, e: Env): Rig =>
  rig({
    cam: [0, 0.55, 9],
    target: [0, 0.75, 0],
    fov: 35,
    bubbles: { mode: "screen", x: 0, y: e.mobile ? -0.32 : -0.46, z: 9, scale: e.mobile ? 0.72 : 0.92, pose: p < 0.45 ? "wave" : "idle", turn: 0, look: "pointer", show: 1 },
    spine: { layout: "halo", param: p, pos: [0, 0.6, 0], rot: [0.28, 0, -0.1], scale: e.mobile ? 1.0 : 1.35, follow: 1, dim: 1 },
    nerves: 0,
    motes: 0.4,
  });

export const RIGS: Array<(p: number, e: Env) => Rig> = [enter, body, noise, track, cycle, connect, remember, companion, care, bubbles];
