"use client";

export type SafetyLevel = "GREEN" | "AMBER" | "RED";

/** Backend safety level, always visible when not GREEN. RED is plain and urgent: no mascot, no playful styling. */
export function SafetyBanner({ level, reasons }: { level: SafetyLevel; reasons: string[] }) {
  if (level === "GREEN") return null;
  const noticed = reasons.length > 0 ? ` Bubbles noticed: ${reasons.join(", ")}.` : "";

  if (level === "RED") {
    return (
      <div role="alert" data-safety="urgent" className="bg-bubbles-urgent px-6 py-5 text-white">
        <p className="m-0 text-[1.125rem] font-semibold">Please get urgent help now if this may be an emergency.</p>
        <p className="m-0 mt-1 text-[0.9375rem]">Call your local emergency number or go to the nearest emergency department.{noticed}</p>
      </div>
    );
  }

  return (
    <div role="status" data-safety="caution" className="bg-bubbles-caution px-6 py-4 text-white">
      <p className="m-0 text-[1.125rem] font-semibold">This may deserve timely medical attention.</p>
      <p className="m-0 mt-1 text-[0.9375rem]">Consider contacting a clinician soon, and get urgent care if it gets worse.{noticed}</p>
    </div>
  );
}
