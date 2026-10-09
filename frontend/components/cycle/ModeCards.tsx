// Pregnancy and postpartum cards. PregnancyInfo.week is COMPLETED weeks and `day` is 0-6 extra days.

import { fmtDay, pregnancyProgress } from "../../app/lib/cycle-format";
import type { PostpartumInfo, PregnancyInfo } from "../../app/lib/cycle-types";
import { Card } from "./shared";

export function PregnancyCard({ info }: { info: PregnancyInfo }) {
  return (
    <Card labelledBy="cycle-preg-title">
      <h3 id="cycle-preg-title" className="m-0 font-display text-h3 text-ink">Your pregnancy, week by week</h3>
      <p className="m-0 mt-2 font-display text-metric text-bubbles-grape-deep">{pregnancyProgress(info)}</p>
      <p className="m-0 mt-1 text-body-sm font-bold text-muted">
        Trimester {info.trimester} · estimated due date {fmtDay(info.due_date, { day: "numeric", month: "long", year: "numeric" })}
        {info.days_to_go > 0 ? ` · about ${info.days_to_go} days to go` : ""}
      </p>
      <p className="m-0 mt-3 text-body text-ink">{info.note}</p>
      <p className="m-0 mt-3 rounded-2xl bg-tint-grape px-4 py-3 text-body font-bold text-bubbles-grape-deep">Next step: {info.next_step}</p>
      <p className="m-0 mt-3 text-body-sm text-muted">Dates are estimates. Your midwife or doctor confirms your due date.</p>
    </Card>
  );
}

export function PostpartumCard({ info }: { info: PostpartumInfo }) {
  return (
    <Card labelledBy="cycle-pp-title">
      <h3 id="cycle-pp-title" className="m-0 font-display text-h3 text-ink">After the birth</h3>
      <p className="m-0 mt-2 font-display text-metric text-bubbles-grape-deep">
        {info.weeks_since} {info.weeks_since === 1 ? "week" : "weeks"}
        <span className="text-body font-bold text-muted"> · {info.days_since} days since {fmtDay(info.delivery_date, { day: "numeric", month: "long" })}</span>
      </p>
      <p className="m-0 mt-3 text-body text-ink">{info.note}</p>
      {info.lochia_expected && <p className="m-0 mt-2 text-body-sm text-muted">Some bleeding (lochia) is expected in the first weeks. If it soaks a pad every hour, call your clinician.</p>}
      <p className="m-0 mt-3 text-body-sm text-muted">Cycles can take a while to settle, so period predictions stay low-confidence for now.</p>
    </Card>
  );
}
