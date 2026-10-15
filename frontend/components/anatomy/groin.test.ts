import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { GROIN, abdomenFront, protrudes } from "./groin";

describe("the female groin rule", () => {
  it("marks the hanging strip and the root that sticks out, and nothing else", () => {
    expect(protrudes(0, 0.81, 0.105)).toBe(true);       // the front of the structure
    expect(protrudes(0, 0.78, 0.02)).toBe(true);        // its middle
    expect(protrudes(0, 0.72, 0.0)).toBe(true);         // the lower end
    expect(protrudes(0, 0.855, 0.085)).toBe(true);      // the root, past the abdomen line
    expect(protrudes(0, 0.855, 0.07)).toBe(false);      // the abdomen itself
    expect(protrudes(0, 0.81, -0.03)).toBe(false);      // behind: buttock and underside of the pelvis
    expect(protrudes(0.07, 0.81, 0.06)).toBe(false);    // a thigh
    expect(protrudes(0, 0.6, 0.1)).toBe(false);         // below the box
    expect(protrudes(0, 0.9, 0.09)).toBe(false);        // above it
  });

  it("the abdomen line rises with height and starts at the pelvis front", () => {
    expect(abdomenFront(0.8)).toBe(0.062);
    expect(abdomenFront(0.865)).toBeGreaterThan(abdomenFront(0.85));
    expect(abdomenFront(0.865)).toBeLessThan(0.09);
  });
});

// Decode the skin mesh of the real model (quantized int16, one node transform) and prove the rule does what it says on it.
function skinVertices(): Float64Array {
  const buffer = readFileSync(resolve(__dirname, "../../public/models/body.glb"));
  let offset = 12;
  let json: { nodes: { name?: string; mesh?: number; translation?: number[]; scale?: number[] }[]; meshes: { primitives: { attributes: { POSITION: number } }[] }[]; accessors: { bufferView: number; byteOffset?: number; count: number; normalized?: boolean }[]; bufferViews: { byteOffset?: number; byteStride?: number }[] } | null = null;
  let bin: Buffer | null = null;
  while (offset < buffer.length) {
    const length = buffer.readUInt32LE(offset);
    const type = buffer.readUInt32LE(offset + 4);
    const chunk = buffer.subarray(offset + 8, offset + 8 + length);
    if (type === 0x4e4f534a) json = JSON.parse(chunk.toString("utf8"));
    else if (type === 0x004e4942) bin = chunk;
    offset += 8 + length;
  }
  const node = json!.nodes.find((n) => n.name === "skin")!;
  const accessor = json!.accessors[json!.meshes[node.mesh!].primitives[0].attributes.POSITION];
  const view = json!.bufferViews[accessor.bufferView];
  const stride = view.byteStride ?? 6;
  const start = (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0);
  const [tx, ty, tz] = node.translation ?? [0, 0, 0];
  const s = (node.scale ?? [1, 1, 1])[0];
  const out = new Float64Array(accessor.count * 3);
  for (let i = 0; i < accessor.count; i += 1) {
    const at = start + i * stride;
    out[i * 3] = Math.max(bin!.readInt16LE(at) / 32767, -1) * s + tx;
    out[i * 3 + 1] = Math.max(bin!.readInt16LE(at + 2) / 32767, -1) * s + ty;
    out[i * 3 + 2] = Math.max(bin!.readInt16LE(at + 4) / 32767, -1) * s + tz;
  }
  return out;
}

describe("on the real body model", () => {
  const v = skinVertices();
  const n = v.length / 3;

  it("has a protrusion in the groin box, and it is a small patch of the skin", () => {
    let marked = 0;
    let outsideBox = 0;
    for (let i = 0; i < n; i += 1) {
      const [x, y, z] = [v[i * 3], v[i * 3 + 1], v[i * 3 + 2]];
      if (!protrudes(x, y, z)) continue;
      marked += 1;
      if (Math.abs(x) > GROIN.xMax || y < GROIN.yMin || y > GROIN.yMax) outsideBox += 1;
    }
    expect(n).toBeGreaterThan(20000);
    expect(marked).toBeLessThan(n * 0.06);       // and it is a small patch, not the body
    expect(outsideBox).toBe(0);
    expect(marked).toBeGreaterThan(400);         // the whole structure, front and underside, not just its tip
  });

  it("the protruding patch is centred on the body, below the navel and above the thighs", () => {
    let sx = 0, sy = 0, count = 0;
    for (let i = 0; i < n; i += 1) {
      if (protrudes(v[i * 3], v[i * 3 + 1], v[i * 3 + 2])) { sx += v[i * 3]; sy += v[i * 3 + 1]; count += 1; }
    }
    expect(Math.abs(sx / count)).toBeLessThan(0.02);
    expect(sy / count).toBeGreaterThan(0.74);
    expect(sy / count).toBeLessThan(0.88);
  });
});
