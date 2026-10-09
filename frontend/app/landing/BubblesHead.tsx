/*
 * FINAL, APPROVED BUBBLES DESIGN (approved 2026-10-07).
 * Reference sheet: docs/brand/bubbles-identity-final.png. Do not change the drawing
 * (shapes, proportions, colours) without design sign-off; poses and animation live
 * in landing.css and story/BubblesHost.tsx.
 */
/**
 * Bubbles' head, shared by the logo and the character so both always match: a
 * baby unicorn foal in three-quarter view facing right. Built on real head
 * structure (big rounded cranium, short foal muzzle with a side nostril, cheek and
 * jaw, arched neck) with soft layered shading, a gentle eye, a pastel spiral horn
 * and a pink mane. Drawn around the cranium centre (0, 0); roughly 300 units wide
 * and 440 tall from horn tip to the base of the neck.
 *
 * `BubblesDefs` must be rendered in the same <svg> with the same `u` prefix.
 */

export const HEAD_PATH =
  "M-10-96C30-100 60-82 76-54c12 22 30 44 50 60 14 12 18 32 12 46-6 14-22 20-38 18-10 10-26 14-40 10-18 10-46 12-66 4-44-12-80-44-90-86-10-44 6-84 46-100 14-4 26-4 40 6Z";

const NECK_PATH = "M24 74C22 124 30 180 40 250H-128C-116 180-110 110-94 34Z";

export function BubblesDefs({ u }: { u: string }) {
  return (
    <defs>
      <radialGradient id={`${u}-fur`} cx="0.42" cy="0.3" r="0.78">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset="0.55" stopColor="#FCF8FC" />
        <stop offset="0.85" stopColor="#F0E6F2" />
        <stop offset="1" stopColor="#DCCDE4" />
      </radialGradient>
      <linearGradient id={`${u}-furSide`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#E9DDEE" />
        <stop offset="0.45" stopColor="#F8F2F9" />
        <stop offset="1" stopColor="#FFFFFF" />
      </linearGradient>
      <linearGradient id={`${u}-limb`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset="0.6" stopColor="#F5EDF6" />
        <stop offset="1" stopColor="#DDCDE4" />
      </linearGradient>
      <radialGradient id={`${u}-muzzle`} cx="0.6" cy="0.45" r="0.6">
        <stop offset="0" stopColor="#FFF0F6" />
        <stop offset="0.7" stopColor="#FBE3EE" stopOpacity="0.85" />
        <stop offset="1" stopColor="#FBE3EE" stopOpacity="0" />
      </radialGradient>
      <linearGradient id={`${u}-mane`} x1="0" y1="0" x2="0.3" y2="1">
        <stop offset="0" stopColor="#FFB9DA" />
        <stop offset="0.5" stopColor="#FF86C0" />
        <stop offset="1" stopColor="#E55FA3" />
      </linearGradient>
      <linearGradient id={`${u}-maneLight`} x1="0" y1="0" x2="0.4" y2="1">
        <stop offset="0" stopColor="#FFD6EA" />
        <stop offset="1" stopColor="#FF9ACB" />
      </linearGradient>
      <linearGradient id={`${u}-maneDeep`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#F27BB6" />
        <stop offset="1" stopColor="#C9529A" />
      </linearGradient>
      <linearGradient id={`${u}-horn`} x1="0" y1="1" x2="0.3" y2="0">
        <stop offset="0" stopColor="#F6C98E" />
        <stop offset="0.5" stopColor="#FFE6BF" />
        <stop offset="1" stopColor="#FFFBF2" />
      </linearGradient>
      <linearGradient id={`${u}-hoof`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#FFC8E1" />
        <stop offset="1" stopColor="#E98ABB" />
      </linearGradient>
      <linearGradient id={`${u}-iris`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#2A1226" />
        <stop offset="0.55" stopColor="#5A2F55" />
        <stop offset="1" stopColor="#9C6A92" />
      </linearGradient>
      <radialGradient id={`${u}-blush`} cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor="#FF8DBD" stopOpacity="0.6" />
        <stop offset="1" stopColor="#FF8DBD" stopOpacity="0" />
      </radialGradient>
      <linearGradient id={`${u}-earInner`} x1="0" y1="1" x2="0" y2="0">
        <stop offset="0" stopColor="#F59AC4" />
        <stop offset="1" stopColor="#FFD3E6" />
      </linearGradient>
      <linearGradient id={`${u}-coat`} x1="0" y1="0" x2="1" y2="0.2">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset="0.5" stopColor="#F9F6FD" />
        <stop offset="1" stopColor="#DDD3EC" />
      </linearGradient>
      <linearGradient id={`${u}-coatBack`} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stopColor="#EEE7F6" />
        <stop offset="1" stopColor="#DCD2EB" />
      </linearGradient>
      <linearGradient id={`${u}-cap`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset="1" stopColor="#E7E1F3" />
      </linearGradient>
      <linearGradient id={`${u}-scrub`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#FFA6CF" />
        <stop offset="1" stopColor="#F06BA8" />
      </linearGradient>
      <radialGradient id={`${u}-metal`} cx="0.35" cy="0.3" r="0.75">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset="0.5" stopColor="#F4DCE7" />
        <stop offset="1" stopColor="#C99AB4" />
      </radialGradient>
      <radialGradient id={`${u}-ground`} cx="0.5" cy="0.5" r="0.5">
        <stop offset="0" stopColor="#3A1F45" stopOpacity="0.3" />
        <stop offset="1" stopColor="#3A1F45" stopOpacity="0" />
      </radialGradient>
      <linearGradient id={`${u}-badge`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#FFEFF6" />
        <stop offset="1" stopColor="#FFD4E8" />
      </linearGradient>
      <filter id={`${u}-soft`} x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="7" />
      </filter>
      <filter id={`${u}-softer`} x="-30%" y="-30%" width="160%" height="160%">
        <feGaussianBlur stdDeviation="3" />
      </filter>
      <clipPath id={`${u}-headClip`}>
        <path d={HEAD_PATH} />
      </clipPath>
      <clipPath id={`${u}-neckClip`}>
        <path d={NECK_PATH} />
      </clipPath>
    </defs>
  );
}

/** The neck, drawn separately so the character can tuck it into the coat collar. */
export function BubblesNeck({ u, still = false }: { u: string; still?: boolean }) {
  return (
    <g className={still ? undefined : "cf-neck"}>
      <path d={NECK_PATH} fill={`url(#${u}-furSide)`} />
      <g clipPath={`url(#${u}-neckClip)`}>
        {/* shadow under the jaw */}
        <ellipse cx="-30" cy="92" rx="90" ry="26" fill="#CDB8D8" opacity="0.75" filter={`url(#${u}-soft)`} />
      </g>
    </g>
  );
}

export function BubblesHead({
  u,
  cap = false,
  detail = true,
  still = false,
  neck = true,
}: {
  u: string;
  /** small nurse cap pinned between the ears */
  cap?: boolean;
  /** strands, lashes and secondary highlights; off for tiny sizes */
  detail?: boolean;
  /** a fixed portrait (the logo): no animation hooks, no alternate expressions */
  still?: boolean;
  /** include the neck (the character draws it separately, under the coat) */
  neck?: boolean;
}) {
  const url = (name: string) => `url(#${u}-${name})`;
  const cls = (name: string) => (still ? undefined : name);
  return (
    <g className={cls("cf-headart")}>
      {/* mane down the back of the neck */}
      <g className={cls("cf-mane")}>
        <path
          d="M-18-102C-74-114-124-78-128-24c-4 44 16 76 4 120-10 38-30 64-22 104 4 22 18 40 36 50-8-20-6-42 6-60 10 14 26 22 44 22-14-20-18-46-10-72 8-26 6-56-6-86-10-26-10-56 4-82 12-22 32-40 54-46-6-6-12-8-24-10Z"
          fill={url("mane")}
        />
        <path
          d="M-70-70c-24 24-30 58-22 92 8 34 4 66-12 96 22-10 36-38 34-70-2-34-14-70 0-118Z"
          fill={url("maneDeep")}
          opacity="0.75"
        />
        {detail && (
          <path
            d="M-96-60c-18 28-18 60-8 92 8 28 6 58-8 84M-46-92c-20 20-26 46-20 74"
            fill="none"
            stroke="#FFD8EB"
            strokeWidth="4"
            strokeLinecap="round"
            opacity="0.85"
          />
        )}
      </g>

      {neck && <BubblesNeck u={u} still={still} />}

      {/* far ear (behind the head) */}
      <g className={cls("cf-ear cf-ear--far")}>
        <path d="M40-84C46-114 62-138 86-152c4 28-4 52-20 72Z" fill={url("furSide")} />
        <path d="M50-90c4-18 14-34 28-44 2 18-4 34-14 46Z" fill={url("earInner")} opacity="0.85" />
      </g>

      {/* head */}
      <path d={HEAD_PATH} fill={url("fur")} />
      <g clipPath={url("headClip")}>
        {/* soft pink muzzle tip */}
        <ellipse cx="114" cy="40" rx="42" ry="38" fill={url("muzzle")} />
        {detail && (
          <>
            {/* core shadow under the jaw and behind the cheek */}
            <ellipse cx="-30" cy="92" rx="120" ry="34" fill="#DACAE3" opacity="0.6" filter={url("soft")} />
            {/* cheek plane: separates the round cheek from the muzzle */}
            <path d="M62-10C68 14 74 38 86 64" fill="none" stroke="#E8DBEF" strokeWidth="13" strokeLinecap="round" opacity="0.8" filter={url("softer")} />
            {/* eye socket */}
            <ellipse cx="38" cy="-24" rx="28" ry="28" fill="#EEE3F2" opacity="0.8" filter={url("softer")} />
            {/* forehead and nasal bridge highlight */}
            <path d="M0-84C36-80 62-56 84-28s30 30 46 34" fill="none" stroke="#FFFFFF" strokeWidth="16" strokeLinecap="round" opacity="0.95" filter={url("softer")} />
            {/* round cheek highlight */}
            <ellipse cx="0" cy="12" rx="44" ry="32" fill="#FFFFFF" opacity="0.7" filter={url("soft")} />
          </>
        )}
      </g>

      {/* cheek blush */}
      <ellipse cx="40" cy="26" rx="21" ry="10" fill={url("blush")} />

      {/* nostril and mouth */}
      <path d="M118 22c5-4 12-3 15 2" fill="none" stroke="#C88AAB" strokeWidth="3.4" strokeLinecap="round" />
      {detail && <ellipse cx="126" cy="25" rx="4.6" ry="2.4" fill="#C88AAB" opacity="0.35" />}
      <path className={cls("cf-smile")} d="M88 61c7 5 16 5 22-1" fill="none" stroke="#8A3E68" strokeWidth="3.4" strokeLinecap="round" />
      {!still && <path className="cf-mouth" d="M89 59c3 10 17 11 21 0Z" fill="#B44579" />}

      {/* eye */}
      <g className={cls("cf-eye")} transform="translate(-19 -10) scale(1.1)">
        <g className={cls("cf-eye-open")}>
          {detail && <path d="M38-42c10-8 26-8 36 2" fill="none" stroke="#E2D2E9" strokeWidth="3" strokeLinecap="round" />}
          <path d="M38-16c0-18 12-26 22-22 10 4 14 18 10 32-4 12-18 16-26 10-6-4-6-12-6-20Z" fill={url("iris")} />
          <g className={cls("cf-pupil")}>
            <ellipse cx="56" cy="-13" rx="7" ry="10" fill="#160814" />
            <ellipse cx="49" cy="-24" rx="4.6" ry="5.4" fill="#FFFFFF" />
            {detail && <circle cx="62" cy="-1" r="2" fill="#FFFFFF" opacity="0.85" />}
          </g>
          <path d="M35-21C40-38 60-44 73-29" fill="none" stroke="#2A1430" strokeWidth="4.4" strokeLinecap="round" />
          {detail && <path d="M37-25l-10-6M37-18l-11-1" stroke="#2A1430" strokeWidth="3" strokeLinecap="round" />}
          {detail && <path d="M44 6c8 4 18 2 24-4" fill="none" stroke="#CDB3D2" strokeWidth="2" strokeLinecap="round" />}
        </g>
        {!still && <path className="cf-eye-happy" d="M38-14c8-14 26-14 34 0" fill="none" stroke="#2A1430" strokeWidth="4.6" strokeLinecap="round" />}
      </g>

      {/* mane locks draped over the back of the head and neck (volume) */}
      <g className={cls("cf-mane cf-mane--front")}>
        <path
          d="M-46-92C-82-70-100-28-96 24c4 50-8 92-22 132 18-6 32-26 38-52 8-34 6-74 10-108 4-34 16-62 34-82Z"
          fill={url("maneLight")}
        />
        {detail && <path d="M-60-74c-20 26-26 60-22 96" fill="none" stroke="#FFEAF4" strokeWidth="3.4" strokeLinecap="round" opacity="0.9" />}
      </g>

      {/* near ear */}
      <g className={cls("cf-ear cf-ear--near")}>
        <path d="M-40-80C-58-106-62-138-54-168c24 16 38 42 40 72Z" fill={url("fur")} />
        <path d="M-40-94c-10-18-13-38-10-58 14 12 22 30 22 48Z" fill={url("earInner")} />
      </g>

      {/* nurse cap, pinned between the ears */}
      {cap && (
        <g className={cls("cf-cap")} transform="rotate(-12 -4 -108)">
          <path d="M-52-100c0-28 22-46 48-46s48 18 48 46c-24 8-72 8-96 0Z" fill={url("cap")} />
          <path d="M-54-100c26 10 74 10 100 0l2 10c-28 10-76 10-104 0Z" fill="#FFFFFF" />
          <path d="M-54-95c26 10 74 10 100 0" fill="none" stroke="#FF8DC0" strokeWidth="2.6" />
          <path d="M-12-130h9v-9h9v9h9v9H6v9h-9v-9h-9Z" fill="#FF5FA8" />
        </g>
      )}

      {/* horn */}
      <g className={cls("cf-horn")}>
        <path d="M18-88C26-118 38-150 58-184c6 38 0 72-12 104Z" fill={url("horn")} />
        {detail && <path d="M21-98l26-8M26-116l24-8M33-134l20-7M41-152l16-5M50-168l9-3" stroke="#F4AFCB" strokeWidth="3.6" strokeLinecap="round" opacity="0.8" />}
        {detail && <path d="M32-96c4-28 12-54 22-76" fill="none" stroke="#FFFFFF" strokeWidth="3" strokeLinecap="round" opacity="0.8" />}
      </g>

      {/* forelock falling between the ears */}
      <path
        d="M-22-98C6-112 46-104 64-78c-14-6-30-6-42 0 2 8 0 18-8 26-6-14-20-24-38-28 2-6 2-12 2-18Z"
        fill={url("maneLight")}
      />
      {detail && <path d="M-6-98c22-4 44 2 58 16" fill="none" stroke="#FFE8F3" strokeWidth="3" strokeLinecap="round" opacity="0.9" />}

      {/* heart hair clip */}
      {detail && (
        <path
          className={cls("cf-clip")}
          d="M-92-58c-3-6-13-5-13 3 0 6 8 11 13 14 5-3 13-8 13-14 0-8-10-9-13-3Z"
          fill="#FF6FB2"
          stroke="#FFFFFF"
          strokeWidth="2.4"
        />
      )}
    </g>
  );
}
