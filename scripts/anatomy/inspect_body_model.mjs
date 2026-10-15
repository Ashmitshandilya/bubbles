// Prints node names, triangle counts, bounds and file size of frontend/public/models/body.glb.
import { NodeIO } from '@gltf-transform/core';
import { ALL_EXTENSIONS } from '@gltf-transform/extensions';
import { statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const file = process.argv[2] ?? fileURLToPath(new URL('../../frontend/public/models/body.glb', import.meta.url));
const doc = await new NodeIO().registerExtensions(ALL_EXTENSIONS).read(file);
let total = 0;
for (const node of doc.getRoot().listNodes()) {
  const mesh = node.getMesh();
  const tris = mesh ? mesh.listPrimitives().reduce((s, p) => s + (p.getIndices()?.getCount() ?? 0) / 3, 0) : 0;
  total += tris;
  console.log(node.getName().padEnd(12), String(tris).padStart(8), 'tris');
}
console.log('total', total, 'tris;', (statSync(file).size / 1e6).toFixed(2), 'MB;', doc.getRoot().getAsset().copyright);
