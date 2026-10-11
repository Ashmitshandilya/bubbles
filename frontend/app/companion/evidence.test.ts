import { describe, expect, it } from "vitest";
import type { EvidenceItem } from "../lib/bubbles-events";
import { pickSources } from "./evidence";

const ev = (title: string, sourceUrl: string | null = null, chunkId: string | null = null): EvidenceItem => ({
  chunkId,
  title,
  sourceName: "Corpus",
  sourceUrl,
  publisher: null,
  evidenceLevel: null,
  fusedScore: null,
});

describe("pickSources", () => {
  it("caps the row at three and keeps the backend order", () => {
    const picked = pickSources([ev("A"), ev("B"), ev("C"), ev("D"), ev("E"), ev("F")]);
    expect(picked.map((s) => s.title)).toEqual(["A", "B", "C"]);
  });

  it("drops a repeat title ignoring case and outer spaces, keeping the first", () => {
    const picked = pickSources([
      ev("La Bomba dance exercise video", "https://a.example/1", "c1"),
      ev("  la bomba DANCE exercise video ", "https://a.example/2", "c2"),
      ev("Breathing exercises for stress"),
    ]);
    expect(picked.map((s) => s.chunkId ?? s.title)).toEqual(["c1", "Breathing exercises for stress"]);
  });

  it("drops a repeat link even when the title differs", () => {
    const picked = pickSources([ev("Colposcopy", "https://nhs.example/colposcopy"), ev("Colposcopy: causes", "https://nhs.example/colposcopy")]);
    expect(picked.map((s) => s.title)).toEqual(["Colposcopy"]);
  });

  it("does not treat two missing links as the same source", () => {
    expect(pickSources([ev("A"), ev("B")])).toHaveLength(2);
  });

  it("fills the three slots after skipping repeats (the reported six-chip reply)", () => {
    const picked = pickSources([
      ev("Colposcopy: causes, treatment", "https://x.example/c"),
      ev("La Bomba dance exercise video", "https://x.example/l"),
      ev("La Bomba dance exercise video", "https://x.example/l"),
      ev("Breathing exercises for stress", "https://x.example/b"),
      ev("Bowel cancer screening", "https://x.example/s"),
      ev("Allergic rhinitis", "https://x.example/r"),
    ]);
    expect(picked.map((s) => s.title)).toEqual([
      "Colposcopy: causes, treatment",
      "La Bomba dance exercise video",
      "Breathing exercises for stress",
    ]);
  });

  it("returns nothing for nothing", () => {
    expect(pickSources([])).toEqual([]);
  });
});
