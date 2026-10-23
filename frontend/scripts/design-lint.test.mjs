import { describe, expect, it } from "vitest";
import { lintSource } from "./design-lint.mjs";

describe("design lint", () => {
  it("catches a seeded bad example for every rule", () => {
    const bad = `const a = \`\${CARD} \${CARD}\`;\n<div className="grid grid-cols-3">{xs.map((x) => <b>{x}</b>)}</div>\n<p>Health score 86%</p>\n<p>Well done 🎉</p>`;
    expect(lintSource(bad).sort()).toEqual(["emoji", "nested-card", "score-percent", "tile-grid"]);
  });
  it("passes clean Pearl code", () => {
    expect(lintSource(`<Rows><Row label="Sleep" value="6h" /></Rows>`)).toEqual([]);
  });
});
