"use client";

import { useState } from "react";
import { Gap, InlineNote, Lede, LivingBubbles, Page, Quote, Row, Rows, Section, Sheet, Thread } from "../../../components/pearl";
import type { BubbleSignal } from "../../lib/bubbles-layout";

const SIGNALS: BubbleSignal[] = [
  { id: "sleep", label: "Sleep", domain: "sleep", amount: 0.4, trend: -0.7 },
  { id: "mood", label: "Mood", domain: "mood", amount: 0.7, trend: 0.5 },
  { id: "water", label: "Water", domain: "food", amount: null, trend: null },
  { id: "move", label: "Move", domain: "move", amount: 0.9, trend: 0 },
];

export default function PearlGallery() {
  const [open, setOpen] = useState(false);
  return (
    <div style={{ padding: "0 16px" }}><Page eyebrow="Thursday, 23 October" title="Good evening." lede="Your sleep has been shorter three nights running, and your mood logs dipped with it.">
      <Section label="Living bubbles"><LivingBubbles signals={SIGNALS} onOpen={() => setOpen(true)} /></Section>
      <Section label="Rows">
        <Rows><Row label="Coming up" value="Period may start in 3 to 6 days" href="#" /><Row label="Orbit" value="Today's question is waiting" href="#" /></Rows>
      </Section>
      <Section label="Thread"><Thread from="Sleep" to="Mood" sentence="On days you slept under 6 hours, your mood logs were lower." sure="Fairly sure, from 23 days." onOpen={() => setOpen(true)} /></Section>
      <Section label="Quote"><Quote tone="Gentle" why="Names the feeling first.">I felt worried when you went quiet. Can we talk tonight?</Quote></Section>
      <Section label="Inline note and gap"><InlineNote>Noted: slept 6h</InlineNote><Gap>No entries yet.</Gap><Lede>One honest sentence.</Lede></Section>
      <Sheet open={open} onClose={() => setOpen(false)} title="Sleep">Details rise from the bottom.</Sheet>
    </Page></div>
  );
}
