"use client";

// Android 2.0, top of Today: the body map as a hero tile, then one tile per section the person uses (app/lib/app-home.ts).
// Only rendered in the app build (DashboardClient checks isNativeApp); styles live in globals.css under html[data-native] .ah-*.

import Link from "next/link";
import { NavIcon } from "./Navigation";
import { useExperience } from "./Providers";
import { appTiles, bodyMapShown } from "../app/lib/app-home";

export function AppHome() {
  const { experience } = useExperience();
  const tiles = appTiles(experience);
  return (
    <section aria-label="Explore Bubbles" className="ah">
      {bodyMapShown(experience) && (
        <Link href="/body" className="ah-hero">
          <span className="ah-hero-copy">
            <span className="ah-kicker">Body map</span>
            <span className="ah-hero-title">See your body, organ by organ</span>
            <span className="ah-hero-sub">Tap an organ for what you logged and what to watch.</span>
          </span>
          <span className="ah-hero-figure" aria-hidden="true">
            <NavIcon id="body" size={64} />
          </span>
        </Link>
      )}
      <ul className="ah-grid">
        {tiles.map((tile) => (
          <li key={tile.id}>
            <Link href={tile.href} className="ah-tile" data-tone={tile.tone}>
              <span className="ah-icon"><NavIcon id={tile.icon} size={22} /></span>
              <span className="ah-label">{tile.label}</span>
              <span className="ah-blurb">{tile.blurb}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
