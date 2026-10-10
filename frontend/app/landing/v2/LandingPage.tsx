import { Hero } from "./Hero";
import { Nav } from "./Nav";
import { Showcase } from "./Showcase";
import { SmoothScroll } from "./SmoothScroll";
import { Statement } from "./Statement";
import { Closing, Faq, Marquee, Safety } from "./Sections";
import "./landing.css";

/*
 * Bubbles landing v2. Seven sections, seven different layouts:
 * split hero, one marquee, a reading-driven statement, a pinned product showcase, an asymmetric safety trio, an accordion, a closing call.
 * The 3D Bubbles figure is intentionally not here: it waits for design approval and will replace the hero portrait.
 */
export function LandingPage() {
  return (
    <div className="lp">
      <SmoothScroll />
      <Nav />
      <main>
        <Hero />
        <Marquee />
        <Statement />
        <Showcase />
        <Safety />
        <Faq />
      </main>
      <Closing />
    </div>
  );
}
