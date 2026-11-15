import type { Metadata, Viewport } from "next";
import { cookies } from "next/headers";
import type { ReactNode } from "react";
import { AppShell } from "@/components/AppShell";
import { LOCALE_COOKIE, normalizeLocale } from "@/lib/i18n";
import { I18nProvider } from "@/lib/i18n-client";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "天璇 · AI-native 工作空间",
    template: "%s · 天璇",
  },
  description:
    "天璇：文曲文档、司南工单与多宝代码仓库统一在一套安静的工作空间里。",
  applicationName: "天璇",
  authors: [{ name: "GongGong" }],
};

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
