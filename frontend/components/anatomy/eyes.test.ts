import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { partsOf } from "../../app/lib/organ-map";

interface Accessor { componentType: number; count: number; min?: number[]; max?: number[]; normalized?: boolean }
interface Gltf {
  nodes: { name?: string; mesh?: number; extras?: { center?: number[] }; translation?: number[]; scale?: number[] }[];
  meshes: { primitives: { attributes: Record<string, number>; indices?: number }[] }[];
  accessors: Accessor[];
}

function readGltf(): Gltf {
  const buffer = readFileSync(resolve(__dirname, "../../public/models/body.glb"));
  const length = buffer.readUInt32LE(12);
  return JSON.parse(buffer.subarray(20, 20 + length).toString("utf8"));
}

describe("the eyes in the body model", () => {
  const gltf = readGltf();
  const eye = (name: string) => gltf.nodes.find((n) => n.name === name)!;

  it("are two painted parts the body map draws for the eyes organ", () => {
    expect(partsOf("eyes")).toEqual(["eye_left", "eye_right"]);
    for (const name of partsOf("eyes")) {
      const node = eye(name);
      expect(node?.mesh).toBeDefined();
      const attributes = gltf.meshes[node.mesh!].primitives[0].attributes;
      expect(attributes.COLOR_0).toBeDefined();   // white of the eye, iris, pupil and nerve are painted in
      expect(attributes.NORMAL).toBeDefined();
      expect(gltf.accessors[attributes.POSITION].componentType).toBe(5126);   // plain floats: placed in metres at the scene root
      expect(node.translation).toBeUndefined();
      expect(node.scale).toBeUndefined();
    }
  });

  it("sit in the face: a pupil distance apart, at eye level, behind the skin and in front of the brain", () => {
    for (const [name, side] of [["eye_left", 1], ["eye_right", -1]] as const) {
      const node = eye(name);
      const box = gltf.accessors[gltf.meshes[node.mesh!].primitives[0].attributes.POSITION];
      const [minX, minY, minZ] = box.min!;
      const [maxX, maxY, maxZ] = box.max!;
      expect(side * (minX + maxX)).toBeGreaterThan(0);          // the left eye is on the body's left (+X)
      expect(Math.abs(maxX - minX)).toBeLessThan(0.05);
      expect(minY).toBeGreaterThan(1.58);
      expect(maxY).toBeLessThan(1.63);
      expect(maxZ).toBeLessThan(0.065);                           // the cornea stays behind the skin of the face
      expect(minZ).toBeLessThan(0.01);                            // the optic nerve runs back to the chiasm
      const [cx, cy, cz] = node.extras!.center!;
      expect(Math.abs(cx)).toBeCloseTo(0.031, 3);
      expect(cy).toBeCloseTo(1.605, 3);
      expect(cz).toBeCloseTo(0.046, 3);
    }
  });
});
