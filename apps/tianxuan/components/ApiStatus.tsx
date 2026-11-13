"use client";

import { useEffect, useState } from "react";
import { API_BASE, fetchHealth } from "@/lib/api";

type Status = "checking" | "online" | "offline";

const labels: Record<Status, string> = {
  checking: "检查 API…",
  online: "API 已连接",
  offline: "API 未连接 · 示例数据",
};

export function ApiStatus() {
  const [status, setStatus] = useState<Status>("checking");

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
