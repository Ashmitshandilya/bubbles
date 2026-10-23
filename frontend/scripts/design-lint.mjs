// Anti-slop guard (renovation plan 10.2). Run by `npm run lint`. Fails when a file under app/ or components/:
//   - uses CARD twice on one line (a box inside a box)
//   - lays out mapped children in grid-cols-3 / grid-cols-4 (a tile grid)
//   - writes "score" next to a percent in visible copy
//   - puts an emoji in visible copy
// Justified exceptions go in scripts/design-lint.allow, one per line: `path/relative/to/frontend  rule  reason`.
import { readFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(fileURLToPath(import.meta.url), "..", "..");

export const RULES = {
  "nested-card": (src) => src.split(/\r?\n/).some((line) => (line.match(/\bCARD\b/g) ?? []).length > 1),
  "tile-grid": (src) => /grid-cols-[34]\b/.test(src) && /\.map\(/.test(src),
  "score-percent": (src) => /score[^\n"'`]{0,24}\d+\s?%|\d+\s?%[^\n"'`]{0,12}score/i.test(src),
  emoji: (src) => /[\u{1F300}-\u{1FAFF}\u{2600}-\u{26FF}\u{2705}\u{2728}\u{274C}\u{2764}\u{FE0F}]/u.test(src.replace(/\/\/.*$|\/\*[\s\S]*?\*\//gm, "")),
};

export function lintSource(src) {
  return Object.entries(RULES).filter(([, test]) => test(src)).map(([name]) => name);
}

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.tsx$/.test(name) && !/\.test\.tsx$/.test(name)) yield full;
  }
}

function allowed() {
  const file = join(ROOT, "scripts", "design-lint.allow");
  if (!existsSync(file)) return new Set();
  const lines = readFileSync(file, "utf8").split(/\r?\n/).filter((l) => l.trim() && !l.startsWith("#"));
  return new Set(lines.map((l) => l.trim().split(/\s+/).slice(0, 2).join(" ")));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const allow = allowed();
  const problems = [];
  for (const area of ["app", "components"]) {
    for (const file of walk(join(ROOT, area))) {
      const rel = relative(ROOT, file).split(sep).join("/");
      for (const rule of lintSource(readFileSync(file, "utf8"))) if (!allow.has(`${rel} ${rule}`)) problems.push(`${rel}: ${rule}`);
    }
  }
  if (problems.length) {
    console.error(`design-lint: ${problems.length} problem(s)\n` + problems.join("\n"));
    process.exit(1);
  }
  console.log("design-lint: clean");
}
