import { authHeaders } from "@/lib/auth";

export type ConfigType = "number" | "integer" | "boolean" | "string" | "enum" | "json" | "reference";
export interface ConfigEntry {
  id: string;
  name: string;
  description: string;
  kind: "parameter" | "content";
  type: ConfigType;
  value: unknown;
  default: unknown;
  min?: number;
  max?: number;
  options?: string[];
}
export interface ConfigFeature {
  id: string;
  name: string;
  description: string;
  document_id?: string | null;
  entries: ConfigEntry[];
}
export interface ConfigProject { id: string; title: string; version: number; features: ConfigFeature[] }
export interface ConfigProjectSummary { id: string; title: string; version: number; feature_count: number; entry_count: number }
export interface ConfigClient { id: string; name: string; version: number; status: "pending" | "applied" | "failed"; error: string; last_seen: string | number }
export class ConfigRequestError extends Error {
  constructor(public status: number, message: string) { super(message); }
}
const root = "/api/v1/game-config/projects";
async function request<T>(path: string, actor: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(path, {
    method, cache: "no-store", credentials: "same-origin",
    headers: { ...authHeaders(actor), ...(body === undefined ? {} : { "Content-Type": "application/json" }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  if (!response.ok) {
    let detail = "";
    try {
      const data = await response.json();
      const value = data.detail ?? data.error ?? data.message;
      detail = typeof value === "string" ? value : JSON.stringify(value ?? "");
    } catch { /* Keep the HTTP status when the proxy returns a non-JSON error. */ }
    throw new ConfigRequestError(response.status, `${response.status}${detail ? ` · ${detail}` : ""}`);
  }
  return response.json() as Promise<T>;
}
export async function listConfigProjects(actor: string) {
  return (await request<{ projects: ConfigProjectSummary[] }>(root, actor)).projects;
}
export function createConfigProject(actor: string, title: string) {
  return request<ConfigProject>(root, actor, "POST", { title, features: [] });
}
export function readConfigProject(actor: string, id: string) {
  return request<ConfigProject>(`${root}/${encodeURIComponent(id)}`, actor);
}
export function saveConfigProject(actor: string, id: string, title: string, features: ConfigFeature[], expected_version: number) {
  return request<ConfigProject>(`${root}/${encodeURIComponent(id)}`, actor, "PUT", { title, features, expected_version });
}
export async function readConfigClients(actor: string, id: string) {
  return (await request<{ clients: ConfigClient[] }>(`${root}/${encodeURIComponent(id)}/clients`, actor)).clients;
}
export async function restoreConfigProject(actor: string, id: string, version: number, expected_version: number) {
  await request(`/api/v1/docs/${encodeURIComponent(id)}/versions/${version}/restore`, actor, "POST", { expected_version });
  return readConfigProject(actor, id);
}

// Text drafts preserve incomplete numbers and malformed JSON without sending them.
export interface EntryDraft extends Omit<ConfigEntry, "value" | "default" | "min" | "max" | "options"> {
  value: string; default: string; min: string; max: string; options: string;
}
export interface FeatureDraft extends Omit<ConfigFeature, "entries"> { entries: EntryDraft[] }
export interface ProjectDraft { title: string; features: FeatureDraft[] }
export function projectDraft(project: ConfigProject): ProjectDraft {
  return { title: project.title, features: project.features.map(feature => ({
    ...feature, description: feature.description ?? "", document_id: feature.document_id ?? "",
    entries: feature.entries.map(entry => ({
      ...entry, description: entry.description ?? "",
      value: valueText(entry.type, entry.value), default: valueText(entry.type, entry.default),
      min: entry.min === undefined ? "" : String(entry.min), max: entry.max === undefined ? "" : String(entry.max),
      options: (entry.options ?? []).join("\n"),
    })),
  })) };
}
function valueText(type: ConfigType, value: unknown): string {
  return type === "json" || type === "reference" ? JSON.stringify(value, null, 2) : String(value);
}
export function parseDraft(draft: ProjectDraft): { title: string; features: ConfigFeature[] } {
  if (!draft.title.trim()) throw new Error("title");
  const portableNumber = (value: number) => Number.isFinite(value) && (!Number.isInteger(value) || Number.isSafeInteger(value));
  const number = (text: string) => {
    if (!text.trim() || !portableNumber(Number(text))) throw new Error("portable number");
    return Number(text);
  };
  const features = draft.features.map(feature => ({ ...feature, document_id: feature.document_id || null,
    entries: feature.entries.map(entry => {
      const parse = (text: string) => {
        if (entry.type === "number" || entry.type === "integer") {
          const value = number(text);
          if (entry.type === "integer" && !Number.isInteger(value)) throw new Error("integer");
          return value;
        }
        if (entry.type === "boolean") {
          if (text !== "true" && text !== "false") throw new Error("boolean");
          return text === "true";
        }
        if (entry.type === "json" || entry.type === "reference") {
          return JSON.parse(text, (_key, value) => {
            if (typeof value === "number" && !portableNumber(value)) throw new Error("portable JSON number");
            return value;
          });
        }
        return text;
      };
      const { min, max, options, ...rest } = entry;
      return { ...rest, value: parse(entry.value), default: parse(entry.default),
        ...(min.trim() ? { min: number(min) } : {}), ...(max.trim() ? { max: number(max) } : {}),
        ...(entry.type === "enum" ? { options: options.split("\n").filter(option => option.length > 0) } : {}),
      };
    }),
  }));
  return { title: draft.title, features };
}

/** Merge independent edits by stable ID; local values win only the listed conflicts. */
export function mergeConfigDrafts(base: ProjectDraft, local: ProjectDraft, remote: ProjectDraft): { draft: ProjectDraft; conflicts: string[] } {
  const conflicts: string[] = [];
  const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);
  function merge(b: unknown, l: unknown, r: unknown, path: string): unknown {
    if (same(l, b)) return r;
    if (same(r, b) || same(l, r)) return l;
    if (Array.isArray(b) && Array.isArray(l) && Array.isArray(r) && (path === "features" || path.endsWith(".entries"))) {
      const ids = Array.from(new Set([...r, ...l].map(item => item.id as string)));
      return ids.map(id => merge(b.find(item => item.id === id), l.find(item => item.id === id), r.find(item => item.id === id), `${path}.${id}`)).filter(item => item !== undefined);
    }
    if (b && l && r && typeof b === "object" && typeof l === "object" && typeof r === "object" && !Array.isArray(b) && !Array.isArray(l) && !Array.isArray(r)) {
      const bo = b as Record<string, unknown>, lo = l as Record<string, unknown>, ro = r as Record<string, unknown>;
      return Object.fromEntries(Array.from(new Set([...Object.keys(bo), ...Object.keys(lo), ...Object.keys(ro)]))
        .map(key => [key, merge(bo[key], lo[key], ro[key], path ? `${path}.${key}` : key)]));
    }
    conflicts.push(path);
    return l;
  }
  return { draft: merge(base, local, remote, "") as ProjectDraft, conflicts };
}
