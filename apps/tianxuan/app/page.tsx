import type { Metadata } from "next";
import { cookies } from "next/headers";
import { DashboardWorkspace } from "@/components/DashboardWorkspace";
import { currentActor, fetchIssues } from "@/lib/server-api";
import { LOCALE_COOKIE, normalizeLocale, translate } from "@/lib/i18n";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return { title: translate(locale, "nav.home") };
}

export default async function DashboardPage() {
  const actor = await currentActor();
  const issues = actor ? await fetchIssues(actor).catch(() => null) : null;
  return <DashboardWorkspace key={actor || "signed-out"} issues={issues} signedIn={Boolean(actor)} />;
}
