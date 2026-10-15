import type { Metadata } from "next";

import PageHeader from "@/components/league/PageHeader";

export const metadata: Metadata = { title: "Privacy" };

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="section-title">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-muted [&_strong]:text-white">{children}</div>
    </section>
  );
}

export default function PrivacyPage() {
  return (
    <>
      <PageHeader eyebrow="The Development League" title="Privacy">
        What this website records about you, why, and who can see it.
      </PageHeader>
      <div className="mx-auto max-w-3xl px-4 pb-16">
        <Section title="Visit statistics">
          <p>
            To see what people use and improve the site, it records <strong>the pages you open, how long you stay on them, and what you do there</strong>: buttons you press, options you pick (a team, a week, a replay speed), links you follow and things you save. We never record what you type into text boxes or passwords.
          </p>
          <p>
            We also note your <strong>type of device, system and browser</strong> (for example &quot;Android phone, Chrome&quot;) and the site or app that sent you here, if it says.
          </p>
        </Section>
        <Section title="If you are not signed in">
          <p>
            You stay anonymous. Your visits on one day are grouped under a random code made from your connection and browser. <strong>The code changes every day and your IP address is not stored</strong>, so you cannot be followed from one day to the next.
          </p>
        </Section>
        <Section title="If you are signed in">
          <p>
            <strong>Your activity is linked to your account</strong> (your name and team), so league staff can see which pages you used and what you did, day by day. This helps us support teams and fix problems.
          </p>
        </Section>
        <Section title="No cookies for tracking, no outside services">
          <p>
            Statistics are kept in the league&apos;s own database. They are not shared with or sold to anyone, and no advertising or third-party tracking services are used. The only cookies are the ones that keep you signed in and secure.
          </p>
        </Section>
        <Section title="Who can see it and for how long">
          <p>
            Only league staff can see the statistics. Detailed records are deleted after about 13 months.
          </p>
          <p>
            Questions, or want your records removed? Ask the league staff.
          </p>
        </Section>
      </div>
    </>
  );
}
