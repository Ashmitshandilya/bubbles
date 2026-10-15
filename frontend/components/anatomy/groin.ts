// The body model is one male-based skin shell. For a female profile Bubbles leaves the protruding groin patch out of that shell in the
// browser (no new model file): every skin triangle that uses a vertex in the groin box sticking out past a smooth pelvis-front line is dropped.
// (Pulling the vertices back instead keeps the outline from the front, so the triangles themselves have to go.) The shell is a faint
// veil, so the opening is barely noticeable, and nothing hangs in any view.
// World units are metres, y up, the body faces +z, the model is 1.72 m tall. The numbers were read from public/models/body.glb
// (groin.test.ts checks them against the real model, so a re-exported model that moves the geometry fails the test).

export const GROIN = { xMax: 0.04, yMin: 0.69, yMax: 0.865 } as const;

/** Above this height the strip joins the lower abdomen, so only what sticks out past the abdomen's own front line is dropped. */
const ROOT_Y = 0.84;
const ROOT_Z = 0.062;
const ROOT_SLOPE = 0.6;
/** Below it, anything this far forward or further (the whole hanging structure, front and underside) is dropped; further back is thigh and buttock. */
const BEHIND_Z = -0.012;

/** The abdomen's front surface at a height in the root zone, in metres. */
export function abdomenFront(y: number): number {
  return ROOT_Z + Math.max(0, y - ROOT_Y) * ROOT_SLOPE;
}

/** True for a skin vertex that belongs to the male groin structure. A female profile drops every skin triangle that uses one. */
export function protrudes(x: number, y: number, z: number): boolean {
  if (Math.abs(x) > GROIN.xMax || y < GROIN.yMin || y > GROIN.yMax) return false;
  return y < ROOT_Y ? z >= BEHIND_Z : z > abdomenFront(y);
}
