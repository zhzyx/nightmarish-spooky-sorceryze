"use client";

import { useActor } from "@/lib/use-actor";

import { useEffect, useState } from "react";
import { fetchDocExternalLinks, type ApiExternalLink } from "@/lib/api";
import { formatMessage } from "@/lib/i18n";
import { useI18n } from "@/lib/i18n-client";

export function DocExternalSource({ docId }: { docId: string }) {
  const actor = useActor();
  const { t } = useI18n();
  const [links, setLinks] = useState<ApiExternalLink[] | null>(null);

  useEffect(() => {
    if (!actor) {
      setLinks([]);
      return;
    }
    let active = true;
    fetchDocExternalLinks(docId, actor)
      .then((rows) => {
        if (active) {
          setLinks(rows);
        }
      })
      .catch(() => {
        if (active) {
          setLinks([]);
        }
      });
    return () => {
      active = false;
    };
  }, [docId, actor]);

  if (!links || links.length === 0) {
    return null;
  }

  return (
    <section className="panel" aria-labelledby="external-source-title">
      <div className="section-heading">
        <div>
          <h2 id="external-source-title">{t("external.title")}</h2>
        </div>
        <span className="section-note">{formatMessage(t("external.note"), { count: links.length })}</span>
      </div>
      <div className="reading-list live-list">
        {links.map((link) => (
          <div className="reading-item" key={link.id}>
            <span className="reading-index">枢</span>
            <span className="reading-copy">
              <strong>{link.external_id}</strong>
              <span>{link.system} · {link.target_type}</span>
            </span>
            {link.external_id.startsWith("http") ? (
              <button
                className="btn btn-ghost"
                type="button"
                onClick={() => window.open(link.external_id, "_blank", "noopener,noreferrer")}
              >
                {t("external.open")}
              </button>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  );
}
