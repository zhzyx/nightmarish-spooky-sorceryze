"use client";

import { useEffect, useState } from "react";
import { useIdentity } from "@/components/IdentityProvider";
import { getToken } from "@/lib/auth";

const ENV_ACTOR = process.env.NEXT_PUBLIC_TIANXUAN_ACTOR ?? "";

/**
 * 客户端身份入口。
 *
 * 优先使用构建期 `NEXT_PUBLIC_TIANXUAN_ACTOR`（兼容旧部署）；未配置时，若浏览器
 * 已保存会话 token，则返回占位值 `"session"`，让面板通过 `authHeaders` 发送
 * Bearer token。首帧与 SSR 一致（返回环境值），挂载后才切换到 `"session"`，
 * 避免 hydration 不匹配。
 */
export function useActor(): string {
  const identity = useIdentity();
  const [actor, setActor] = useState(ENV_ACTOR);
  useEffect(() => {
    if (ENV_ACTOR) {
      return;
    }
    if (getToken()) {
      setActor("session");
    }
  }, []);
  return identity?.id ?? actor;
}
