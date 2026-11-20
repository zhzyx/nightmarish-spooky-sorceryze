import { cookies } from "next/headers";
import { EmptyState } from "@/components/EmptyState";
import { LOCALE_COOKIE, normalizeLocale, translate, type MessageKey } from "@/lib/i18n";

export default function NotFound() {
  const locale = normalizeLocale(cookies().get(LOCALE_COOKIE)?.value);
  const t = (key: MessageKey) => translate(locale, key);

  return (
    <div className="page-stack">
      <header className="page-header">
        <div className="page-title-group">
          <h1>{t("nf.title")}</h1>
          <p className="page-lede">{t("nf.lede")}</p>
        </div>
      </header>
      <EmptyState
        actionHref="/docs"
        actionLabel={t("nf.action")}
        description={t("nf.description")}
        eyebrow="404"
        title={t("nf.emptyTitle")}
      />
    </div>
  );
}
