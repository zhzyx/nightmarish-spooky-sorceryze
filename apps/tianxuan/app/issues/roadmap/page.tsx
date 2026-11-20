"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { authHeaders } from "@/lib/auth";
import { useActor } from "@/lib/use-actor";
import styles from "@/components/IssueWork.module.css";

type Item = { id: string; title: string; status: string; progress: number; logged_minutes: number; plan: {
  roadmap: string; milestone: string; iteration: string; status: string; estimated_minutes: number;
} };

export default function Roadmap() {
  const actor = useActor();
  const [items, setItems] = useState<Item[]>([]);
  const [message, setMessage] = useState("正在读取路线图…");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setItems([]);
    setMessage("正在读取路线图…");
    fetch("/api/v1/work/roadmap", { headers: authHeaders(actor), cache: "no-store", signal: controller.signal })
      .then(async response => {
        if (!response.ok) throw Error("读取失败（" + response.status + "）");
        const data: { items: Item[] } = await response.json();
        if (controller.signal.aborted) return;
        setItems(data.items);
        setMessage(data.items.length ? "" : "没有可见工单");
      }).catch(error => { if (!controller.signal.aborted) setMessage(String(error)); });
    return () => controller.abort();
  }, [actor, refresh]);

  const groups = new Map<string, Map<string, Item[]>>();
  for (const item of items) {
    const route = item.plan.roadmap || "待安排";
    const milestone = item.plan.milestone || "未设里程碑";
    const milestones = groups.get(route) ?? new Map<string, Item[]>();
    const tickets = milestones.get(milestone) ?? [];
    tickets.push(item);
    milestones.set(milestone, tickets);
    groups.set(route, milestones);
  }
  return <div className={`page-stack ${styles.work}`}>
    <Link href="/issues">返回工单看板</Link>
    <h1>工单路线图</h1>
    <button onClick={() => setRefresh(n => n + 1)}>刷新路线图</button>
    <p role="status">{message}</p>
    {Array.from(groups, ([route, milestones]) => <section key={route}>
      <h2>{route}</h2>
      {Array.from(milestones, ([milestone, tickets]) => <article key={milestone}>
        <h3>{milestone}</h3>
        <ul>{tickets.map(item => <li key={item.id}><Link href={"/issues/" + encodeURIComponent(item.id)}>{item.title}</Link>
          <p>当前阶段 {item.status} · {item.progress}%</p>
          <p>{[item.plan.iteration, item.plan.status].filter(Boolean).join(" · ")}　已登记 {item.logged_minutes} / 预计 {item.plan.estimated_minutes} 分钟</p>
        </li>)}</ul>
      </article>)}
    </section>)}
  </div>;
}
