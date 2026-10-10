"use client";

import Link from "next/link";
import { BubblesMascot } from "../../components/BubblesMascot";
import { useAuth } from "../../components/Providers";
import {
  BTN_SECONDARY,
  CARD,
  ErrorCard,
  HubPage,
  Icon,
  PILL,
  SignOutButton,
  Skeleton,
  TONE,
  humanize,
  toneFor,
  useBubblesQuery,
  type Tone,
} from "../../components/hub/HubKit";
import { formatWhen, parseWhen } from "../lib/dates";

interface Profile {
  display_name?: string | null;
  date_of_birth?: string | null;
  height_cm?: number | null;
  gender?: string | null;
  timezone?: string | null;
}

interface MemoryResponse {
  memory?: {
    L1?: number;
    L2?: number;
    L3?: number;
    recent?: Array<{ id?: string; event_type?: string; created_at?: string }>;
    errors?: string[];
  };
}

// memory_diagnostics reads at most 200 rows per level.
const count = (n: number | undefined) => (n == null ? "—" : n >= 200 ? "200+" : String(n));

function age(dob: string): number | null {
  const born = parseWhen(dob); // a date of birth is a calendar day: never shift it through UTC
  if (Number.isNaN(born.getTime())) return null;
  const now = new Date();
  const years = now.getFullYear() - born.getFullYear();
  return now < new Date(now.getFullYear(), born.getMonth(), born.getDate()) ? years - 1 : years;
}

export function ProfileClient() {
  return (
    <HubPage title="Me">
      <Me />
    </HubPage>
  );
}

function Me() {
  const { user } = useAuth();
  const [profileQuery, reloadProfile] = useBubblesQuery<{ profile?: Profile }>("/profile");
  const [memoryQuery, reloadMemory] = useBubblesQuery<MemoryResponse>("/memory/diagnostics");

  const profile = profileQuery.status === "ready" ? profileQuery.data.profile ?? {} : null;
  const memory = memoryQuery.status === "ready" ? memoryQuery.data.memory ?? {} : null;
  const name = profile?.display_name || user?.display_name;
  const years = profile?.date_of_birth ? age(profile.date_of_birth) : null;

  const details: Array<[string, string | null | undefined]> = profile
    ? [
        ["Name", profile.display_name],
        ["Date of birth", profile.date_of_birth && `${formatWhen(profile.date_of_birth, true)}${years != null ? ` · ${years} years` : ""}`],
        ["Height", profile.height_cm != null ? `${profile.height_cm} cm` : null],
        ["Gender", profile.gender && humanize(profile.gender)],
        ["Time zone", profile.timezone],
      ]
    : [];
  const coreSet = details.filter(([, value]) => value).length;

  const levels: Array<{ level: string; title: string; text: string; badge: string; tone: Tone }> = [
    { level: "L0", title: "This conversation", text: "What you're saying right now. Bubbles uses it in the moment and doesn't keep it as memory.", badge: "Not stored", tone: "plain" },
    { level: "L1", title: "Things you logged or mentioned", text: "Health details Bubbles noticed. They stay suggestions until you confirm them.", badge: `${count(memory?.L1)} noticed`, tone: "sky" },
    { level: "L2", title: "Lasting health facts", text: "Conditions, allergies and history you confirmed. Bubbles keeps these in mind.", badge: `${count(memory?.L2)} confirmed`, tone: "pink" },
    { level: "L3", title: "Everyday signals", text: "Confirmed sleep, mood, symptom and other signals that patterns are built from.", badge: `${count(memory?.L3)} confirmed`, tone: "grape" },
    { level: "L4", title: "Your core profile", text: "The basics from your account, shown above.", badge: profile ? `${coreSet} of ${details.length} details` : "—", tone: "mint" },
  ];

  return (
    <div className="space-y-8">
      <header className="bubbles-rise flex flex-wrap items-center gap-4">
        <div className="bubbles-breathe flex h-[72px] w-[72px] items-center justify-center rounded-[24px] bg-tint-pink">
          <BubblesMascot size={60} mood="happy" animated={false} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-h1 text-ink">{name ? `Hi, ${name}` : "Me"}</h1>
          <p className="mt-1 break-words text-body font-semibold text-muted">
            {user?.email}
            {user?.created_at ? ` · with Bubbles since ${formatWhen(user.created_at, true)}` : ""}
          </p>
        </div>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-2">
        <section aria-labelledby="details-title" className={`${CARD} p-5 sm:p-6`}>
          <h2 id="details-title" className="text-h3 text-ink">
            Your details
          </h2>
          {profileQuery.status === "loading" && <Skeleton className="mt-4 h-48" />}
          {profileQuery.status === "error" && (
            <div className="mt-4">
              <ErrorCard title="Your details didn't load" message={profileQuery.message} onRetry={reloadProfile} inset />
            </div>
          )}
          {profile && (
            <>
              <dl className="m-0 mt-4 divide-y-2 divide-line">
                {details.map(([label, value]) => (
                  <div key={label} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-3">
                    <dt className="text-body-sm font-extrabold text-ink-soft">{label}</dt>
                    <dd className={`m-0 text-body ${value ? "font-bold text-ink" : "text-muted"}`}>{value || "Not set"}</dd>
                  </div>
                ))}
              </dl>
              <p className="mt-3 text-body-sm text-muted">These come from your account. Editing them in the app isn&apos;t available yet.</p>
            </>
          )}
        </section>

        <section aria-labelledby="privacy-title" className="rounded-3xl bg-tint-mint p-5 sm:p-6">
          <div className="flex items-center gap-2 text-bubbles-mint-deep">
            <span className="shrink-0"><Icon id="shield" /></span>
            <h2 id="privacy-title" className="text-h3 text-bubbles-mint-deep">
              Nothing becomes memory without you
            </h2>
          </div>
          <ul className="m-0 mt-4 list-none space-y-3 p-0 text-body text-ink">
            <li>Bubbles may notice health details when you chat or log. They stay suggestions until you confirm them.</li>
            <li>Only what you confirm becomes lasting memory. If Bubbles gets something wrong, correct it — your word wins.</li>
            <li>If something sounds urgent, Bubbles&apos; built-in safety check answers first and points you to real help.</li>
            <li>Bubbles never diagnoses, and never treats missing data as &ldquo;all clear&rdquo;.</li>
          </ul>
        </section>
      </div>

      <section aria-labelledby="memory-title" className={`${CARD} p-5 sm:p-6`}>
        <h2 id="memory-title" className="text-h3 text-ink">
          What Bubbles remembers
        </h2>
        <p className="mt-1 text-body text-muted">Bubbles&apos; memory has five levels, from fleeting to lasting.</p>
        {memoryQuery.status === "error" && (
          <div className="mt-4">
            <ErrorCard title="Memory counts didn't load" message={memoryQuery.message} onRetry={reloadMemory} inset />
          </div>
        )}
        {memory?.errors?.length ? (
          <p role="status" className="mt-3 text-body-sm font-bold text-bubbles-sun-deep">
            Some memory counts couldn&apos;t be read right now, so they may show as zero.
          </p>
        ) : null}
        <ol className="bubbles-stagger m-0 mt-4 grid list-none gap-3 p-0 md:grid-cols-2 xl:grid-cols-5">
          {levels.map((item) => (
            <li key={item.level} className="flex flex-col rounded-3xl bg-blush p-4">
              <span className={`flex h-10 w-10 items-center justify-center rounded-2xl font-display font-semibold ${TONE[item.tone].bubble}`}>
                {item.level}
              </span>
              <span className="mt-3 font-display text-h4 text-ink">{item.title}</span>
              <span className="mt-1 flex-1 text-body-sm text-muted">{item.text}</span>
              {memoryQuery.status === "loading" && item.level !== "L0" ? (
                <Skeleton className="mt-3 h-7 w-28 rounded-full" />
              ) : (
                <span className={`${PILL} mt-3 self-start ${TONE[item.tone].chip}`}>{item.badge}</span>
              )}
            </li>
          ))}
        </ol>

        {memory?.recent?.length ? (
          <div className="mt-6">
            <h3 className="text-h4 text-ink">Recently noticed</h3>
            <ul className="m-0 mt-2 flex list-none flex-wrap gap-2 p-0">
              {memory.recent.slice(0, 6).map((item, i) => {
                const tone = TONE[toneFor(item.event_type ?? "")];
                return (
                  <li key={item.id ?? i} className={`${PILL} ${tone.chip}`}>
                    {humanize(item.event_type ?? "entry")} · {formatWhen(item.created_at)}
                  </li>
                );
              })}
            </ul>
          </div>
        ) : null}
      </section>

      <section aria-labelledby="account-title" className="flex flex-wrap items-center gap-3">
        <h2 id="account-title" className="sr-only">
          Account
        </h2>
        <Link href="/partner" className={`${BTN_SECONDARY} no-underline`}>
          Partner sharing
        </Link>
        <Link href="/settings" className={`${BTN_SECONDARY} no-underline`}>
          Settings
        </Link>
        <SignOutButton />
      </section>
    </div>
  );
}
