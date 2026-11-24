import type { Metadata } from "next";
import { cookies } from "next/headers";
import { GameConfigPanel } from "@/components/GameConfigPanel";
import { LOCALE_COOKIE, normalizeLocale, translate } from "@/lib/i18n";
import "./game-config.css";

export const dynamic = "force-dynamic";
export function generateMetadata(): Metadata {
  return { title: translate(normalizeLocale(cookies().get(LOCALE_COOKIE)?.value), "nav.gameConfig") };
}
export default function GameConfigPage() { return <GameConfigPanel />; }
