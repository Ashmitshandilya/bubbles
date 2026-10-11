import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { ImageResponse } from "next/og";

// The picture shown when a link to Bubbles is shared (chat apps, social posts, search results). Built once at deploy time.
export const alt = "Bubbles: your personal health companion that remembers your story";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const bubble = (left: number, top: number, d: number, tint: string) => (
  <div
    style={{
      position: "absolute",
      left,
      top,
      width: d,
      height: d,
      borderRadius: 9999,
      border: "3px solid rgba(255,255,255,0.85)",
      background: `radial-gradient(circle at 30% 28%, rgba(255,255,255,0.95), rgba(255,255,255,0.15) 38%, ${tint} 100%)`,
    }}
  />
);

export default async function OpenGraphImage() {
  const mascot = `data:image/png;base64,${(await readFile(join(process.cwd(), "app", "apple-icon.png"))).toString("base64")}`;
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          position: "relative",
          background: "linear-gradient(160deg, #E9D8FF 0%, #FFD3E8 48%, #FFE6CF 100%)",
          fontFamily: "sans-serif",
          color: "#2A1230",
        }}
      >
        {bubble(820, 40, 210, "rgba(190,170,255,0.35)")}
        {bubble(1010, 330, 130, "rgba(255,170,215,0.4)")}
        {bubble(930, 470, 70, "rgba(170,220,255,0.4)")}
        {bubble(760, 380, 56, "rgba(255,200,170,0.4)")}
        <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", padding: "0 80px", width: 900 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={mascot} width={96} height={96} alt="" style={{ borderRadius: 9999 }} />
            <div style={{ fontSize: 64, fontWeight: 800, letterSpacing: -2 }}>bubbles</div>
          </div>
          <div style={{ marginTop: 44, fontSize: 64, fontWeight: 800, lineHeight: 1.08, letterSpacing: -2, display: "flex", flexDirection: "column", whiteSpace: "nowrap" }}>
            <span>Your body keeps a story.</span>
            <span style={{ color: "#A5124D" }}>Bubbles remembers it.</span>
          </div>
          <div style={{ marginTop: 34, fontSize: 30, lineHeight: 1.35, color: "#5A3A63", display: "flex" }}>
            A health companion that listens and connects the dots over time. Not a diagnosis.
          </div>
        </div>
      </div>
    ),
    size,
  );
}
