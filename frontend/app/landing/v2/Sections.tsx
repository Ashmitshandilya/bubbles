import Image from "next/image";
import Link from "next/link";
import { CaretDown } from "@phosphor-icons/react/dist/ssr";
import { AuthCta } from "./AuthCta";

/* Static sections: no client JavaScript needed. */

const TRACKED = ["Sleep", "Mood", "Cycle", "Nutrition", "Fitness", "Symptoms", "Labs", "Medicines"];

/** The page's one marquee: breadth of what Bubbles keeps track of. Content is doubled so the loop is seamless. */
export function Marquee() {
  return (
    <section className="lp-marq" aria-label="What Bubbles keeps track of">
      <div className="lp-marq__track">
        {TRACKED.map((t) => (
          <span key={t} className="lp-marq__item">
            {t}
          </span>
        ))}
        {TRACKED.map((t) => (
          <span key={`${t}-2`} className="lp-marq__item lp-marq__dup" aria-hidden="true">
            {t}
          </span>
        ))}
      </div>
    </section>
  );
}

export function Safety() {
  return (
    <section id="safety" className="lp-safe" aria-labelledby="lp-safe-h">
      <div className="lp-wrap">
        <h2 id="lp-safe-h">Careful by design</h2>
        <div className="lp-bento">
          <article className="lp-cell lp-cell--a">
            <h3>Urgent messages never reach an AI model</h3>
            <p>
              Every message is checked for emergency signs first. If one shows up, Bubbles answers with fixed, tested guidance and points you to real help. No
              model sees what you wrote.
            </p>
          </article>
          <article className="lp-cell lp-cell--b">
            <h3>Answers come with sources</h3>
            <p>Over five thousand passages from public health sources sit behind what Bubbles says. Open any of them.</p>
            <div className="lp-srcs">
              <a href="https://www.nhs.uk" target="_blank" rel="noopener noreferrer">
                NHS
              </a>
              <a href="https://medlineplus.gov" target="_blank" rel="noopener noreferrer">
                MedlinePlus
              </a>
              <a href="https://www.nin.res.in" target="_blank" rel="noopener noreferrer">
                ICMR-NIN
              </a>
            </div>
          </article>
          <article className="lp-cell lp-cell--c">
            <h3>Nothing is shared unless you switch it on</h3>
            <p>Your chats, symptoms, medicines and lab results can never be shared with anyone.</p>
          </article>
        </div>
      </div>
    </section>
  );
}

const QUESTIONS = [
  {
    q: "Does Bubbles diagnose?",
    a: "No. Bubbles helps you notice patterns and get ready for a doctor's visit. It keeps uncertainty visible and never replaces a clinician.",
  },
  { q: "Is it free?", a: "Bubbles is free while it is in early access. You will hear about any change well before it happens." },
  { q: "Who can see my data?", a: "Only you. Partner sharing is off until you turn it on, and you choose exactly what one person can see." },
  {
    q: "What if something is urgent?",
    a: "Bubbles checks every message for emergency signs before anything else. If it finds one, it shows urgent guidance and no AI model reads your message.",
  },
  { q: "Which languages can I use?", a: "You can write to Bubbles in English, Hindi or Hinglish." },
  { q: "Is there an app?", a: "Bubbles runs in your browser on a phone or a laptop. A separate app is not available yet." },
];

export function Faq() {
  return (
    <section id="faq" className="lp-faq" aria-labelledby="lp-faq-h">
      <div className="lp-wrap lp-faq__grid">
        <h2 id="lp-faq-h">Questions people ask</h2>
        <div>
          {QUESTIONS.map((item) => (
            <details key={item.q}>
              <summary>
                {item.q}
                <CaretDown size={20} weight="bold" aria-hidden="true" />
              </summary>
              <p>{item.a}</p>
            </details>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Closing() {
  return (
    <footer className="lp-final">
      <div className="lp-final__art" aria-hidden="true">
        <Image src="/brand/bubbles-hero.jpg" alt="" fill sizes="30vw" />
      </div>
      <div className="lp-wrap">
        <h2>Start remembering.</h2>
        <div className="lp-final__row">
          <p>Free while Bubbles is in early access. It takes a minute to begin.</p>
          <div className="lp-hero__cta">
            <AuthCta />
            <Link href="/login" className="lp-btn lp-btn--quiet">
              Sign in
            </Link>
          </div>
        </div>
        <div className="lp-foot">
          <p>Bubbles is a companion, not a doctor. In an emergency, call your local emergency number.</p>
          <div className="lp-foot__links">
            <span>Privacy and terms are published before public launch.</span>
          </div>
        </div>
        <div className="lp-word-mark" aria-hidden="true">
          Bubbles
        </div>
      </div>
    </footer>
  );
}
