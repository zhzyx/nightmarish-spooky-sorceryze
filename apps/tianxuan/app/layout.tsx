import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { LOCALE_COOKIE, normalizeLocale, translate } from "@/lib/i18n";
import { I18nProvider } from "@/lib/i18n-client";
import "./globals.css";

export function generateMetadata(): Metadata {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return {
    title: {
      default: translate(locale, "meta.title"),
      template: translate(locale, "meta.template"),
    },
    description: translate(locale, "meta.description"),
    applicationName: translate(locale, "meta.applicationName"),
    authors: [{ name: "GongGong" }],
  };
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#0B0E11",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  return (
    <html lang={locale === "en" ? "en" : "zh-CN"}>
      <body>
        <I18nProvider initialLocale={locale}>
          <AppShell>{children}</AppShell>
        </I18nProvider>
      </body>
    </html>
  );
}
