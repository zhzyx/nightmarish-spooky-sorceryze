"use client";

import { useEffect, useState } from "react";
import { API_BASE, fetchHealth } from "@/lib/api";
import { useI18n } from "@/lib/i18n-client";

type Status = "checking" | "online" | "offline";

export function ApiStatus() {
  const { t } = useI18n();
  const [status, setStatus] = useState<Status>("checking");
  const labels: Record<Status, string> = {
    checking: t("api.checking"),
    online: t("api.online"),
    offline: t("api.offline"),
  };

  useEffect(() => {
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 1500);
    fetchHealth(controller.signal)
      .then(() => setStatus("online"))
      .catch(() => setStatus("offline"))
      .finally(() => window.clearTimeout(timer));
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, []);

  return (
    <p className={`api-status api-status-${status}`} title={API_BASE}>
      <span className="api-status-dot" aria-hidden="true" />
      {labels[status]}
    </p>
  );
}
