/**
 * Typed client for the FastAPI backend.
 *
 * Every data route on the API requires the caller's Supabase JWT, so each
 * helper takes an access token rather than reading one itself — server
 * components get it from the session, and keeping it a parameter means a
 * call site can't accidentally run unauthenticated.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Paper {
  id: string;
  arxiv_id: string;
  version: number | null;
  abs_url: string;
  pdf_url: string;
  page_count: number;
  chunk_count: number;
}

/** Mirrors `api.chat.orchestrator.Citation` exactly. */
export interface Citation {
  chunk_id: string;
  page_number: number | null;
  snippet: string;
  score: number;
}

/** A chat stream event. The API emits newline-delimited JSON. */
export type ChatEvent =
  | { type: "citations"; citations: Citation[] }
  | { type: "token"; text: string }
  | { type: "done" };

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  token: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      ...init.headers,
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  return (await response.json()) as T;
}

/** FastAPI returns `{detail}`; anything else is surfaced as-is. */
async function readError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body?.detail === "string") return body.detail;
    if (Array.isArray(body?.detail)) return body.detail[0]?.msg ?? "invalid request";
    return response.statusText;
  } catch {
    return response.statusText || `request failed with ${response.status}`;
  }
}

export function listPapers(token: string): Promise<Paper[]> {
  return request<Paper[]>("/papers", token);
}

export function getPaper(token: string, paperId: string): Promise<Paper> {
  return request<Paper>(`/papers/${encodeURIComponent(paperId)}`, token);
}

export function ingestPaper(token: string, reference: string): Promise<Paper> {
  return request<Paper>("/papers", token, {
    method: "POST",
    body: JSON.stringify({ reference }),
  });
}

/**
 * Stream a grounded answer.
 *
 * Yields each event as it arrives so the UI can paint citations before the
 * first token — the API deliberately sends them first, and waiting for the
 * whole body would throw that away.
 */
export async function* streamChat(
  token: string,
  paperId: string,
  question: string,
  k = 5,
  signal?: AbortSignal,
): AsyncGenerator<ChatEvent> {
  const response = await fetch(
    `${API_URL}/papers/${encodeURIComponent(paperId)}/chat`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question, k }),
      signal,
    },
  );

  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (!response.body) {
    throw new ApiError(response.status, "response had no body to stream");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // The last piece is whatever arrived after the final newline; it may
    // be half an event, so it stays in the buffer until the next chunk.
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const event = parseEvent(line);
      if (event) yield event;
    }
  }

  const tail = parseEvent(buffer);
  if (tail) yield tail;
}

function parseEvent(line: string): ChatEvent | null {
  const trimmed = line.trim();
  if (!trimmed) return null;
  try {
    return JSON.parse(trimmed) as ChatEvent;
  } catch {
    // A malformed line is not worth killing a live answer over.
    return null;
  }
}
