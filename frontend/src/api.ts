export type QuestionEvent = {
  event: "metadata" | "text" | "done" | "error";
  conversation_id?: string;
  text?: string;
  message?: string;
};

export type QuestionRequest = {
  question: string;
  sources?: string[] | null;
  conversation_id?: string;
};

export type Task = {
  id: string;
  type: string;
  status: "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED";
  parameters: Record<string, unknown>;
  details: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export type ConversationSummary = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
};

export type Conversation = {
  id: string;
  messages: Array<{ role: "user" | "model"; content: string }>;
  created_at: string;
  updated_at: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

type ApiErrorBody = { detail?: string };

export function parseEventBlock(block: string): QuestionEvent | null {
  const data = block
    .split("\n")
    .filter(isDataLine)
    .map(removeDataPrefix)
    .join("\n");

  if (!data) return null;

  try {
    return JSON.parse(data) as QuestionEvent;
  } catch {
    return null;
  }
}

export async function streamQuestion(
  token: string,
  payload: QuestionRequest,
  onEvent: (event: QuestionEvent) => void,
): Promise<void> {
  const response = await fetch("/api/questions", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });

  if (!response.ok) throw await responseError(response);
  if (!response.body) throw new ApiError("The server returned an empty response.", 500);

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const result = await reader.read();
    buffer += decoder.decode(result.value, { stream: !result.done });
    const blocks = buffer.split("\n\n");
    buffer = blocks.pop() ?? "";
    blocks.map(parseEventBlock).filter(isQuestionEvent).forEach(onEvent);
    if (result.done) break;
  }

  const finalEvent = parseEventBlock(buffer);
  if (finalEvent) onEvent(finalEvent);
}

export async function createIngestionTask(
  token: string,
  targetMonth?: string,
): Promise<Task> {
  const response = await fetch("/api/knowledge-ingestion/tasks", {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ source: "hackaday", target_month: targetMonth || null }),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as Task;
}

export async function getTask(token: string, taskId: string): Promise<Task> {
  const response = await fetch(`/api/tasks/${encodeURIComponent(taskId)}`, {
    headers: { "X-Auth-Token": token },
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as Task;
}

export async function listConversations(token: string): Promise<ConversationSummary[]> {
  const response = await fetch("/api/conversations", {
    headers: tokenHeader(token),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as ConversationSummary[];
}

export async function getConversation(
  token: string,
  conversationId: string,
): Promise<Conversation> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    headers: tokenHeader(token),
  });
  if (!response.ok) throw await responseError(response);
  return (await response.json()) as Conversation;
}

export async function deleteConversation(
  token: string,
  conversationId: string,
): Promise<void> {
  const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}`, {
    method: "DELETE",
    headers: tokenHeader(token),
  });
  if (!response.ok) throw await responseError(response);
}

function authHeaders(token: string): HeadersInit {
  return { "Content-Type": "application/json", ...tokenHeader(token) };
}

function tokenHeader(token: string): Record<string, string> {
  return { "X-Auth-Token": token };
}

async function responseError(response: Response): Promise<ApiError> {
  let message = `Request failed (${response.status}).`;
  try {
    const body = (await response.json()) as ApiErrorBody;
    if (body.detail) message = body.detail;
  } catch {
    // Keep the status-based fallback for non-JSON errors.
  }
  return new ApiError(message, response.status);
}

function isDataLine(line: string): boolean {
  return line.startsWith("data:");
}

function removeDataPrefix(line: string): string {
  return line.slice(5).trimStart();
}

function isQuestionEvent(event: QuestionEvent | null): event is QuestionEvent {
  return event !== null;
}
