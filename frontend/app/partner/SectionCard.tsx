import { formatRange } from "../lib/cycle-format";
import type { PartnerSection } from "../lib/partner-sharing";

/** One shared summary, as the partner sees it. Used on the public link page and in the signed-in "Shared with you" view. */
export function SectionCard({ section, idPrefix }: { section: PartnerSection; idPrefix: string }) {
  const id = `${idPrefix}-${section.key}`;
  return (
    <section aria-labelledby={id} className="mt-4 rounded-3xl bg-tint-pink p-5 text-left text-bubbles-pink-deep">
      <h3 id={id} className="m-0 text-body-sm font-extrabold uppercase tracking-wide">{section.title}</h3>
      {section.range && (
        <p className="m-0 mt-1 font-display text-h3">Between {formatRange(section.range.earliest, section.range.latest).replace(" to ", " and ")}</p>
      )}
      {section.text && <p className="m-0 mt-1 whitespace-pre-line text-body font-bold">{section.text}</p>}
      {section.detail && <p className="m-0 mt-2 text-body-sm font-semibold">{section.detail}</p>}
      {section.tips && section.tips.length > 0 && (
        <div className="mt-3 rounded-2xl bg-surface/70 p-3 text-ink">
          <p className="m-0 text-body-sm font-extrabold">Ways to help</p>
          <ul className="m-0 mt-1 list-disc space-y-1 pl-5 text-body-sm">
            {section.tips.map((tip) => <li key={tip}>{tip}</li>)}
          </ul>
          {section.tips_caveat && <p className="m-0 mt-2 text-body-sm font-semibold">{section.tips_caveat}</p>}
        </div>
      )}
      {section.caveat && <p className="m-0 mt-2 text-body-sm">{section.caveat}</p>}
    </section>
  );
}
