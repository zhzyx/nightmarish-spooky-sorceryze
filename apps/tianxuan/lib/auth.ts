/**
 * 会话 token 存储与请求头。
 *
 * 浏览器登录后把 token 写入 localStorage 与同站 cookie；服务端渲染可用
 * `TIANXUAN_TOKEN` 环境变量携带一个服务会话。没有 token 时退回旧的
 * `X-Actor` 头（需服务端显式开启 `TIANXUAN_ALLOW_ACTOR_HEADER=1`）。
 */

const TOKEN_KEY = "tianxuan_token";

function serverToken(): string {
  return typeof window === "undefined" ? (process.env.TIANXUAN_TOKEN ?? "") : "";
}

export function getToken(): string {
  if (typeof window === "undefined") {
    return serverToken();
  }
  return window.localStorage.getItem(TOKEN_KEY) ?? "";
}

export function saveSession(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
  document.cookie = `${TOKEN_KEY}=${encodeURIComponent(token)}; Path=/; SameSite=Lax`;
}

export function clearSession(): void {
  window.localStorage.removeItem(TOKEN_KEY);
  document.cookie = `${TOKEN_KEY}=; Path=/; Max-Age=0; SameSite=Lax`;
}

/** 优先 Bearer token；没有 token 时退回旧 X-Actor。 */
export function authHeaders(actor: string): Record<string, string> {
  const token = getToken();
  if (token) {
    return { Authorization: `Bearer ${token}` };
  }
  return actor ? { "X-Actor": actor } : {};
}
