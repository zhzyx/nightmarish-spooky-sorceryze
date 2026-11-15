"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  LOCALE_COOKIE,
  normalizeLocale,
  translate,
  type Locale,
  type MessageKey,
} from "@/lib/i18n";

interface I18nContextValue {
  locale: Locale;
  t: (key: MessageKey) => string;
  setLocale: (locale: Locale) => void;
}

const I18nContext = createContext<I18nContextValue | null>(null);

function readCookie(name: string): string {
  if (typeof document === "undefined") {
    return "";
  }
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return "";
}

function readLocale(fallback: Locale): Locale {
  if (typeof window === "undefined") {
    return fallback;
  }
  const fromCookie = readCookie(LOCALE_COOKIE);
  if (fromCookie) {
    return normalizeLocale(fromCookie);
  }
  const stored = window.localStorage.getItem(LOCALE_COOKIE);
  return stored ? normalizeLocale(stored) : fallback;
}

export function I18nProvider({
  children,
  initialLocale = "zh",
}: {
  children: ReactNode;
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale);

  useEffect(() => {
    const next = readLocale(initialLocale);
    setLocaleState(next);
    document.documentElement.lang = next === "en" ? "en" : "zh-CN";
  }, [initialLocale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    document.documentElement.lang = next === "en" ? "en" : "zh-CN";
    document.cookie = `${LOCALE_COOKIE}=${next}; Path=/; SameSite=Lax; Max-Age=31536000`;
    window.localStorage.setItem(LOCALE_COOKIE, next);
  }, []);

  const value = useMemo<I18nContextValue>(
    () => ({
      locale,
      setLocale,
      t: (key: MessageKey) => translate(locale, key),
    }),
    [locale, setLocale],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext);
  if (context === null) {
    throw new Error("useI18n must be used inside I18nProvider");
  }
  return context;
}
