import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import type { ReactNode } from "react";
import { currentIdentity } from "@/lib/server-api";
import { IdentityProvider } from "@/components/IdentityProvider";
import { AppShell } from "@/components/AppShell";
import { ThemeProvider } from "@/components/ThemeSelect";
import { LOCALE_COOKIE, normalizeLocale, translate } from "@/lib/i18n";
import { I18nProvider } from "@/lib/i18n-client";
import { normalizeTheme, THEME_COOKIE } from "@/lib/theme";
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
};

export default async function RootLayout({ children }: { children: ReactNode }) {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const identity = await currentIdentity();
  const theme = normalizeTheme(cookies().get(THEME_COOKIE)?.value);
  return (
    <html data-theme={theme} lang={locale === "en" ? "en" : "zh-CN"}>
      <body>
        <I18nProvider initialLocale={locale}>
          <ThemeProvider initialTheme={theme}>
            <IdentityProvider identity={identity}><AppShell>{children}</AppShell></IdentityProvider>
          </ThemeProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
