import type { Metadata } from "next";
import { LegalPage } from "../legal/LegalPage";
import { PRIVACY_NOTICE_VERSION } from "../lib/privacy-notice-version";

export const metadata: Metadata = {
  title: "Privacy | Bubbles",
  description: "What Bubbles collects, why, where it is kept, who can see it and how to remove it.",
  alternates: { canonical: "/privacy" },
};

export default function PrivacyPage() {
  return (
    <LegalPage title="Privacy" updated={`Draft, version ${PRIVACY_NOTICE_VERSION}`}>
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
          <li>Technical data needed to run and protect the service: your IP address for security and rate limits, and request logs that are designed not to contain your message text. For operations monitoring, the person who runs Bubbles can see for a few minutes which account made a request and how long it took, never what you wrote.</li>
          <li>In the Android app, only if you turn them on: a notification address for your phone (for phone reminders) and crash reports (see below).</li>
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
        <h2>Your privacy choices</h2>
        <p>
          Everything beyond keeping your own logs is a separate choice, off until you turn it on, and you can turn it off again in one tap in Settings, under Privacy choices.
          Each time you change one, Bubbles adds a line to a list you can read there (What you agreed to).
        </p>
        <ul>
          <li>
            <strong>Answer open questions with an outside AI.</strong> Your message, your recent messages in that chat and a short summary of your profile and notes (such as your date of birth,
            gender and recent entries) go to an AI provider from an approved list, on its free tier, and nothing more than is needed. Free tiers may use what they receive to improve their services, and their staff may
            review it, which is why Bubbles replaces the names of the people you have told it about with labels such as &quot;partner&quot; before anything leaves our server, and puts the names back in the answer.
            Each provider handles data under its own terms. Turn it off and nothing more is sent. Messages that sound like an emergency, logging, patterns and fitness questions are handled by Bubbles itself and never need this.
          </li>
          <li>
            <strong>Save details Bubbles notices in chat.</strong> What you say plainly, such as how long you slept, water, meals, a walk, your weight or your mood, is saved straight to your logs. Anything that needs more care, such as a symptom, a fever, an injury, a medicine or your period, Bubbles asks about first: you choose Save or Skip, and a detail a model proposed is never saved without you. When it is off, chat still works and anything you log yourself is still saved. A fight with a partner that you mention only marks the day as a tense day in your own patterns; no words are kept.
          </li>
          <li>
            <strong>Share summaries with one person.</strong> Nothing is shared until you pick what and who. Turning it off ends all sharing at once.
          </li>
          <li>
            <strong>Reminders on your phone, and reminders by email.</strong> Reminders never contain health details. Email goes to the address you signed in with. Phone reminders go through
            Google&apos;s notification service, which only carries that plain text.
          </li>
          <li>
            <strong>Show my posts in the community.</strong> Only when you turn it on, and under the name or alias you choose.
          </li>
          <li>
            <strong>Anonymous usage counts.</strong> Listed so you can see it, but not available. Bubbles does not collect analytics.
          </li>
        </ul>
        <p>Keeping your own logs and chat is part of the service itself, because Bubbles cannot remember for you otherwise. Only you can see them.</p>
        <p>
          A message that sounds like an emergency is handled by fixed, tested rules and is never sent to an AI model. Bubbles never diagnoses. It can be wrong, so please check anything important
          with a clinician.
        </p>
      </section>

      <section>
        <h2>The record of your choices</h2>
        <p>
          Bubbles keeps a list of each choice you turn on or off: which choice, yes or no, when, from where (Settings, chat, setup or sign-up) and which version of the wording you saw. It holds no
          message text and no health details. If you use &quot;delete my data&quot;, your logs and chats are removed, every choice is switched off, and this list stays, but without your account link: only
          the choice, the date and a one-way code remain. When you sign up, Bubbles also notes that you ticked that you read the Terms and this notice.
        </p>
      </section>

      <section>
        <h2>Safe Harbor: if you are hurt at home</h2>
        <p>
          If you tell Bubbles that a partner or someone in your family is hitting or choking you, pushing you hard or against something, forcing sex, threatening to kill you or using a weapon, Bubbles answers by itself, in fixed
          wording written in advance. That message is never sent to an outside AI, even if you turned that choice on. The same is true if you tell Bubbles that you hit your partner or your child. It
          never appears in a notification, and it is never shown to a partner you are connected with.
        </p>
        <p>
          Bubbles recognises these messages by their wording, so it can miss some. Other worries about home, such as feeling controlled or afraid, are treated like any other chat: they go to an
          outside AI only if you turned that choice on.
        </p>
      </section>

      <section>
        <h2>How Bubbles learns how you like to be talked to</h2>
        <p>
          Bubbles keeps a short list of how you like to be spoken to: for example short replies, a gentle tone, the language you write in and when you are usually around. It comes from your setup answers, from the
          reasons you give when you mark a reply unhelpful, and, only if you allowed Bubbles to save details noticed in chat, from the language and time of day of your messages and a few phrases about how you cope with
          stress. With that same choice on, Bubbles may remember for up to a week that you mentioned a strong or recurring symptom, so it can ask how you are once. It does not store your messages.
        </p>
        <p>
          You can see every item at Me, How Bubbles understands you, confirm it, remove it or clear all of it. It is only used to choose words, and it is deleted with your data.
        </p>
      </section>

      <section>
        <h2>Helping improve Bubbles (optional, off by default)</h2>
        <p>
          If you turn on &ldquo;Help improve Bubbles with de-identified examples&rdquo; in Your choices, and you rate one of Bubbles&apos; replies to a simple question about the app (for example &ldquo;what can you do?&rdquo;), Bubbles
          may keep that reply with every name, number, date, place, email and link removed. It never keeps your message, and nothing in it points to you. A short code lets Bubbles count how many different people found a kind of reply
          helpful; the code changes every month and cannot be turned back into who you are. Kept examples are deleted after 90 days. Only when at least 20 different people found the same kind of reply helpful does the owner of
          Bubbles read it, and a reply is only ever used again if the owner approves it. It is never used for health, safety or relationship advice. You can turn this off at any time, and it does not change how Bubbles answers you.
        </p>
      </section>

      <section>
        <h2>Stars lens (optional, off by default)</h2>
        <p>
          If you turn on the Stars lens in Your choices, Bubbles keeps your birth date, an optional birth time and a birth place chosen from a list on its own server. Nothing is sent to a map or astrology service. From them it works
          out a traditional Moon sign, nakshatra and Sun sign (and the ascendant, if you give a birth time) and shows a few traditional words. It is for fun and reflection and never predicts anything, and Bubbles never uses it for
          health, safety or relationship decisions. Each word is checked against what Bubbles has seen about you, and only where your own history agrees can it change how Bubbles words things. Turning it off, or withdrawing the choice,
          deletes your birth date, time and place and what the lens added to how Bubbles understands you.
        </p>
      </section>

      <section>
        <h2>Country, gender and relationship questions</h2>
        <p>
          Setup can ask which country you live in, your state in India, how you describe yourself, whether you are in a relationship and who you live with. You can skip any of them. Your country picks the emergency numbers
          Bubbles shows (if you skip it, Bubbles shows India&apos;s numbers). How you describe yourself only helps choose which support lines fit and how Bubbles speaks to you. None of it changes a safety rule.
        </p>
      </section>

      <section>
        <h2>Orbit: your closest relationship</h2>
        <p>
          What you tell Bubbles in Orbit, such as drafts, notes, repair messages and what you write in Heart-to-heart, is private to you. A connected partner never sees it. Only two things can ever reach them, and only
          if you switch each one on in Privacy choices: your answer to the shared daily question and your weekly check-in (shown to both of you only once you have both answered), and now and then one kind, general line
          such as &quot;Ask how their day really was&quot;. Those lines never say what you logged or how you feel, and some of them appear whatever your week was like. Either of you can stop at any time, and leaving
          the connection ends it at once.
        </p>
        <p>
          When you ask Bubbles to help you reply to someone, the message you paste goes to an outside AI only if you allowed that choice, with the names of people you have told Bubbles about replaced by labels. Pasted text
          that describes being hurt at home or a crisis is answered by Bubbles itself and is never sent to an outside AI or saved.
        </p>
      </section>

      <section>
        <h2>Where your data is kept</h2>
        <p>
          Your data is stored in a managed database hosted in South Korea (Seoul). The app is served from Vercel and the API runs on Render in Singapore. These providers
          process data on our behalf, under their own terms.
        </p>
      </section>

      <section>
        <h2>The Android app: phone reminders and crash reports</h2>
        <p>
          Both are off until you turn them on, and Google Analytics is never used. Phone reminders (Settings, Reminders, On this phone) are delivered by Google Firebase
          Cloud Messaging. Bubbles keeps a notification address for your phone and sends only plain, fixed text such as &quot;Medicine check-in&quot;, never what you
          logged. Turning them off, signing out or deleting your data removes your phone&apos;s address. Crash reports (Settings, This device) are sent by Google Firebase
          Crashlytics when the app crashes: the phone model, Android version and where in the app it broke. They never include your entries, messages or account. Google
          processes both on our behalf, under its own terms.
        </p>
      </section>

      <section>
        <h2>Browser storage</h2>
        <p>
          Bubbles keeps only what it needs in your browser: your sign-in, a few settings and small shortcuts, such as whether the privacy veil is on and whether the home page motion is paused. Your sign-in
          stays in the tab you used and goes when you close it, unless you tick &quot;Keep me signed in on this device&quot;. There are no ads, no tracking cookies and no
          analytics.
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
          <li>Read the list of what you agreed to in Settings, under Privacy choices.</li>
          <li>Delete individual entries in each tracker.</li>
          <li>Stop partner sharing at any time.</li>
          <li>Turn phone reminders or crash reports off at any time in the Android app.</li>
          <li>Change or take back any privacy choice at any time.</li>
          <li>
            In the Android app, Me, Your choices, Delete my account erases everything and removes your sign-in. On the web, write to <a href="mailto:hello@heybubbles.in">hello@heybubbles.in</a> from the email address you signed up with and we will delete your account and everything linked to it.
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
          to see, correct and erase it. Questions, requests and grievances: <a href="mailto:hello@heybubbles.in">hello@heybubbles.in</a>. The name of the operating company will be added before launch.
        </p>
      </section>

      <section>
        <h2>Changes</h2>
        <p>If this changes in a way that matters, we will tell you inside Bubbles before it takes effect.</p>
      </section>
    </LegalPage>
  );
}
