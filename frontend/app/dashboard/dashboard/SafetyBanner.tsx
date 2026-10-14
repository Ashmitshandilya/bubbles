"use client";

export type SafetyLevel = "GREEN" | "AMBER" | "RED";

/** Backend safety level, always visible when not GREEN. RED is plain and urgent: no mascot, no playful styling. */
export function SafetyBanner({ level, reasons }: { level: SafetyLevel; reasons: string[] }) {
  if (level === "GREEN") return null;
  const noticed = reasons.length > 0 ? ` Bubbles noticed: ${reasons.join(", ")}.` : "";

  if (level === "RED") {
    return (
      <div role="alert" className="rounded-[18px] bg-bubbles-urgent px-5 py-4 text-white">
        <p className="m-0 text-base font-extrabold">Please get urgent help now if this may be an emergency.</p>
        <p className="m-0 mt-1 text-[0.9375rem]">Call your local emergency number or go to the nearest emergency department.{noticed}</p>
      </div>
    );
  }

  return (
    <div role="status" className="rounded-[18px] border-2 border-line-sun bg-tint-sun px-5 py-4 text-bubbles-sun-deep">
      <p className="m-0 text-[0.9375rem] font-extrabold">This may deserve timely medical attention.</p>
      <p className="m-0 mt-1 text-[0.9375rem]">Consider contacting a clinician soon, and get urgent care if it gets worse.{noticed}</p>
    </div>
  );
}
