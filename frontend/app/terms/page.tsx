import type { Metadata } from "next";
import { LegalPage } from "../legal/LegalPage";

export const metadata: Metadata = {
  title: "Terms | Bubbles",
  description: "The rules for using Bubbles, in plain words.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <LegalPage title="Terms of use" updated="Draft of 10 October 2026">
      <section>
        <h2>What Bubbles is</h2>
        <p>
          Bubbles is a health companion. It helps you notice patterns, keep your history in one place and get ready for a doctor&apos;s visit. It is not a doctor, it does not
          diagnose, and it is not for emergencies. If something feels urgent, call your local emergency number now (112 in India).
        </p>
      </section>

      <section>
        <h2>Using Bubbles</h2>
        <ul>
          <li>You must be 18 or older.</li>
          <li>Give accurate details and keep your password safe. You are responsible for what happens in your account.</li>
          <li>Do not misuse the service: no attempts to break it, overload it or read other people&apos;s data, and no unlawful content.</li>
          <li>Only add health information about yourself, or about someone who has agreed.</li>
        </ul>
      </section>

      <section>
        <h2>Your information</h2>
        <p>
          What you log stays yours. You allow Bubbles to store and process it to run the service for you, as described in the Privacy page. You can export or delete your data
          from Settings.
        </p>
      </section>

      <section>
        <h2>Early access</h2>
        <p>
          Bubbles is free while it is in early access. Features can change or pause, and we cannot promise it will always be available. We will tell you before anything
          that affects you changes.
        </p>
      </section>

      <section>
        <h2>Health information is general</h2>
        <p>
          What Bubbles says is general information and your own logged patterns. It may be incomplete or wrong. It never replaces advice from a qualified clinician, and you
          should not delay or skip care because of something Bubbles said.
        </p>
      </section>

      <section>
        <h2>Orbit is support, not therapy or advice</h2>
        <p>
          Orbit helps you think about and talk about your relationships. It is not couples therapy, counselling, or legal advice, and it only ever knows your side of a story. It will not tell you to stay or to leave.
          If you feel unsafe at home, the help lines it shows are public numbers and Bubbles is not an emergency service: call your local emergency number if you are in danger.
        </p>
      </section>

      <section>
        <h2>Our responsibility</h2>
        <p>
          We work to keep Bubbles accurate, safe and secure, but it is provided as it is. To the extent the law allows, we are not liable for decisions you make based on it.
          Nothing here limits rights you have under the law that cannot be limited.
        </p>
      </section>

      <section>
        <h2>Ending</h2>
        <p>You can stop using Bubbles at any time. We may suspend an account that breaks these terms or puts others at risk.</p>
      </section>

      <section>
        <h2>Law and contact</h2>
        <p>
          These terms are governed by the laws of India. Contact: <a href="mailto:hello@heybubbles.in">hello@heybubbles.in</a>. The operating company and its address will be added before the public launch.
        </p>
      </section>
    </LegalPage>
  );
}
