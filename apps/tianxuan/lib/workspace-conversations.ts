export const stages = ["direction", "plan", "design"] as const;
export type Stage = (typeof stages)[number];

export type Turn = {
  id: string;
  content: string;
  state: "pending" | "answered" | "unanswered";
  answer: string | null;
  model: string | null;
  error: number | null;
};

export type Revision = {
  revision: number;
  stage: Stage;
  body: string;
  title: string;
  acceptance: string;
  confirmed_at: string | null;
};

export type Summary = { id: string; title: string; updated_at: string };
export type Execution = { entry: string; scopes: string[]; model: string | null; call_id: string; requirement_version: number };
export type Conversation = Summary & {
  version: number;
  turns: Turn[];
  revisions: Revision[];
  current: Partial<Record<Stage, number>>;
  requirement_id: string | null;
  requirement_version: number | null;
  execution: Execution | null;
  past_executions: Execution[];
};

export type ConversationPage = { conversations: Summary[]; next: string | null };

export class WorkspaceRequestError extends Error {
  constructor(readonly status: number) {
    super(`Workspace request failed: ${status}`);
  }
}

const root = "/api/v1/workspace/conversations";

export async function workspaceRequest<T>(path = "", payload?: object): Promise<T> {
  const response = await fetch(root + path, {
    cache: "no-store",
    ...(payload && {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  });
  if (!response.ok) throw new WorkspaceRequestError(response.status);
  return response.json() as Promise<T>;
}
