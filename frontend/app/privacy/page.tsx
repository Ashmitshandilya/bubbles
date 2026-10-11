import type { Metadata } from "next";
import { LegalPage } from "../legal/LegalPage";

export const metadata: Metadata = {
  title: "Privacy | Bubbles",
  description: "What Bubbles collects, why, where it is kept, who can see it and how to remove it.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy" updated="Draft of 10 October 2026">
      <section>
        <h2>The short version</h2>
        <p>
          Bubbles keeps what you log and tell it so it can remember for you. Only you can see it. We do not sell your data. Nothing is shared with another person
          unless you switch partner sharing on, and even then only the few summaries you choose.
        </p>
      </section>

      <section>
        <h2>What we collect</h2>
        <ul>
          <li>Your account details: email address and the name you give.</li>
          <li>What you log or tell Bubbles: sleep, mood, cycle, symptoms, food, activity, drinks, weight, vitals, medicines, lab results, visits and your chat messages.</li>
          <li>Technical data needed to run and protect the service: your IP address for security and rate limits, and request logs that are designed not to contain your message text.</li>
        </ul>
      </section>

      <section>
        <h2>How we use it</h2>
        <ul>
          <li>To give you answers, reminders and patterns from your own entries.</li>
          <li>To keep you safe: every message is checked for emergency signs first.</li>
          <li>To keep the service secure and working.</li>
        </ul>
      </section>

      <section>
        <h2>AI and your messages</h2>
        <p>
          A message that sounds like an emergency is handled by fixed, tested rules and is never sent to an AI model. Logging, patterns and fitness questions are also
          answered by Bubbles itself. Only open-ended questions go to an AI provider, and only after you say yes: Bubbles asks you the first time, the server checks your
          answer before anything is sent, and you can take it back at any time in Settings, under Privacy and data. When you say yes, Bubbles sends your message and a
          small amount of context from your own notes to a provider from an approved list, on its free tier, and nothing more than is needed. Each provider handles data under
          its own terms.
        </p>
        <p>Bubbles never diagnoses. It can be wrong, so please check anything important with a clinician.</p>
      </section>

      <section>
        <h2>Where your data is kept</h2>
        <p>
          Your data is stored in a managed database hosted in South Korea (Seoul). The app is served from Vercel and the API runs on Render in Singapore. These providers
          process data on our behalf, under their own terms.
        </p>
      </section>

      <section>
        <h2>Sharing</h2>
        <p>
          Partner sharing is off by default. When you turn it on, you choose which summaries one person can see: a cycle estimate, a seven night sleep average and a note
          from you. Your chats, symptoms, medicines, lab results and reports can never be shared. You can stop at any moment, from either side.
        </p>
      </section>

      <section>
        <h2>Your choices</h2>
        <ul>
          <li>Export or delete your Whole-Health data from Settings, under Your data.</li>
          <li>Delete individual entries in each tracker.</li>
          <li>Stop partner sharing at any time.</li>
          <li>
            Full account deletion is still being built. Until it is, write to us and we will delete your account and everything linked to it. The contact address will be
            published here at launch.
          </li>
        </ul>
      </section>

      <section>
        <h2>Security and keeping data</h2>
        <p>
          Data is encrypted in transit and every request is checked against your own account. No system is perfectly secure, so please use a strong password. We keep your data
          until you delete it, plus short-lived backups.
        </p>
      </section>

      <section>
        <h2>Age</h2>
        <p>Bubbles is for people aged 18 and over.</p>
      </section>

      <section>
        <h2>India</h2>
        <p>
          We aim to follow the principles of India&apos;s Digital Personal Data Protection Act, 2023: clear consent, using data only for the purpose you gave it, and your right
          to see, correct and erase it. The name of the operating company and the grievance contact will be added before launch.
        </p>
      </section>

      <section>
        <h2>Changes</h2>
        <p>If this changes in a way that matters, we will tell you inside Bubbles before it takes effect.</p>
      </section>
    </LegalPage>
  );
}
