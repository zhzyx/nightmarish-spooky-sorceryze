export const THEME_COOKIE = "tianxuan_theme";

export function normalizeTheme(value?: string): "system" | "light" | "dark" {
  return value === "light" || value === "dark" ? value : "system";
}
