"use client";

import { createContext, useContext, useState, type ReactNode } from "react";
import { useI18n } from "@/lib/i18n-client";
import { normalizeTheme, THEME_COOKIE } from "@/lib/theme";

type Theme = ReturnType<typeof normalizeTheme>;
const ThemeContext = createContext<{ theme: Theme; setTheme: (theme: Theme) => void } | null>(null);

export function ThemeProvider({ initialTheme, children }: { initialTheme: Theme; children: ReactNode }) {
  const [theme, setPreference] = useState(initialTheme);

  function setTheme(next: Theme) {
    setPreference(next);
    document.documentElement.dataset.theme = next;
    document.cookie = `${THEME_COOKIE}=${next}; Path=/; SameSite=Lax; Max-Age=31536000`;
  }

  return <ThemeContext.Provider value={{ theme, setTheme }}>{children}</ThemeContext.Provider>;
}

export function ThemeSelect() {
  const appearance = useContext(ThemeContext);
  const { locale } = useI18n();
  const zh = locale === "zh";
  if (!appearance) throw new Error("ThemeSelect requires ThemeProvider");

  return (
    <select aria-label={zh ? "外观" : "Appearance"} className="theme-select" value={appearance.theme}
      onChange={(event) => appearance.setTheme(normalizeTheme(event.target.value))}>
      <option value="system">{zh ? "跟随系统" : "System"}</option>
      <option value="light">{zh ? "浅色" : "Light"}</option>
      <option value="dark">{zh ? "深色" : "Dark"}</option>
    </select>
  );
}
