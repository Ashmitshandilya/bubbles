// The first-run tour: which stops it makes and how it moves. Pure logic only (the component in FirstRunTour.tsx measures and draws).

export interface TourStep {
  id: string;
  /** Where the coach mark points. `closest` widens the target to its nearest ancestor that matches (the form around the Ask box). */
  selector: string;
  closest?: string;
  title: string;
  body: string;
}

export const TOUR_STEPS: readonly TourStep[] = [
  { id: "ask", selector: "#today-ask", closest: "form", title: "Ask anything", body: "Type a question here, or open Talk to chat. Bubbles keeps it short and kind." },
  { id: "log", selector: '[aria-labelledby="today-quick-log"]', title: "Log in a tap", body: "Water, mood, sleep and more. One tap each, no typing needed." },
  { id: "week", selector: '[aria-labelledby="today-signals"]', title: "Your week", body: "These tiles show how the last seven days went. Tap one to see more." },
  { id: "body", selector: 'main a[href="/body"]', title: "Your body map", body: "Tap a part of the body to see what you have logged about it." },
  { id: "me", selector: 'header a[href="/profile"]', title: "You, and your settings", body: "Your profile and privacy choices live here. You can replay this tour from Settings." },
];

/** The stops whose target is on the page right now, in order. */
export const usableSteps = (isPresent: (step: TourStep) => boolean, steps: readonly TourStep[] = TOUR_STEPS): TourStep[] => steps.filter(isPresent);

export interface TourState {
  open: boolean;
  index: number;
}

export type TourAction = { type: "next" } | { type: "back" } | { type: "close" };

/** Moves the tour. `total` is the number of usable stops; Next on the last stop closes it. */
export function reduceTour(state: TourState, action: TourAction, total: number): TourState {
  if (!state.open) return state;
  if (action.type === "close") return { open: false, index: state.index };
  if (action.type === "back") return { open: true, index: Math.max(0, state.index - 1) };
  return state.index + 1 >= total ? { open: false, index: state.index } : { open: true, index: state.index + 1 };
}

export interface TourView {
  position: string;
  isFirst: boolean;
  isLast: boolean;
}

export function tourView(index: number, total: number): TourView {
  return { position: `${index + 1} of ${total}`, isFirst: index === 0, isLast: index === total - 1 };
}

/** Whether the tour should start: never seen it, or asked to replay it from Settings. */
export const shouldStart = (seen: boolean | null, replay: boolean): boolean => replay || seen === false;

/** The body of PUT /onboarding/tour: finishing records seen, skipping records seen and skipped. */
export const outcomeBody = (skipped: boolean): string => JSON.stringify({ skipped });

export interface Box {
  top: number;
  left: number;
  width: number;
  height: number;
}

/** Where the coach card goes: under the target when it fits, else above, else pinned to the bottom of the screen. Always inside the screen. */
export function placeCard(target: Box, viewport: { width: number; height: number }, card: { width: number; height: number }, margin = 16, gap = 14): { top: number; left: number } {
  const width = Math.min(card.width, viewport.width - margin * 2);
  const centre = target.left + target.width / 2 - width / 2;
  const left = Math.min(Math.max(margin, centre), viewport.width - margin - width);
  const below = target.top + target.height + gap;
  if (below + card.height + margin <= viewport.height) return { top: Math.max(margin, below), left };
  const above = target.top - gap - card.height;
  if (above >= margin) return { top: above, left };
  return { top: Math.max(margin, viewport.height - card.height - margin), left };
}
