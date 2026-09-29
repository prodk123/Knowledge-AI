import {
  ChatResponse,
  DocumentStatusResponse,
  DocumentUploadResponse,
} from "./types";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ─── Error Classification ─────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public code?: string
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** Human-readable label for UI display */
  get label(): string {
    switch (this.status) {
      case 400: return "Bad request";
      case 401: return "Unauthorized";
      case 403: return "Access denied";
      case 404: return "Not found";
      case 409: return "Conflict";
      case 422: return "Validation error";
      case 429: return "Rate limited";
      case 500: return "Server error";
      case 502: return "Bad gateway";
      case 503: return "Service unavailable";
      default:  return this.status > 0 ? `HTTP ${this.status}` : "Network error";
    }
  }
}

export class NetworkError extends Error {
  constructor(message = "Could not reach the server. Check your connection.") {
    super(message);
    this.name = "NetworkError";
  }
}

function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("access_token");
  }
  return null;
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function fetchJson<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
    ...(options?.headers as Record<string, string>),
  };

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    // Pure network failure (offline, CORS, DNS, etc.)
    throw new NetworkError();
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // ignore parse failure
    }
    throw new ApiError(response.status, detail);
  }

  // 204 No Content
  if (response.status === 204) return undefined as unknown as T;
  return response.json();
}

// ─── SSE Streaming ────────────────────────────────────────────────────────────

export type SSEEvent =
  | { type: "activity"; content: string }
  | { type: "token"; content: string }
  | { type: "approval"; content: string }
  | { type: "done"; sources: import("./types").Source[]; metadata: Record<string, unknown> }
  | { type: "error"; detail: string };

export async function* streamMessage(
  conversationId: string,
  content: string,
  signal?: AbortSignal
): AsyncGenerator<SSEEvent> {
  const url = `${API_BASE_URL}/conversations/${conversationId}/messages`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...authHeaders(),
  };

  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      headers,
      body: JSON.stringify({ content }),
      signal,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new NetworkError();
  }

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch { /* ignore */ }
    throw new ApiError(response.status, detail);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() ?? "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        try {
          const event = JSON.parse(raw) as SSEEvent;
          yield event;
          if (event.type === "done" || event.type === "error") return;
        } catch {
          // malformed chunk — skip
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const api = {
  auth: {
    login: async (email: string, password: string) => {
      return fetchJson<{ access_token: string; token_type: string }>(
        "/auth/login",
        {
          method: "POST",
          body: JSON.stringify({ email, password }),
        }
      );
    },
    register: async (email: string, password: string, full_name: string) => {
      return fetchJson<{ access_token: string; token_type: string }>(
        "/auth/register",
        {
          method: "POST",
          body: JSON.stringify({ email, password, full_name }),
        }
      );
    },
    me: async () => fetchJson<import("./types").UserProfile>("/auth/me"),
  },

  conversations: {
    list: async (): Promise<import("./types").Conversation[]> =>
      fetchJson<import("./types").Conversation[]>("/conversations/"),

    get: async (id: string): Promise<import("./types").ConversationDetail> =>
      fetchJson<import("./types").ConversationDetail>(`/conversations/${id}`),

    create: async (title?: string): Promise<import("./types").Conversation> =>
      fetchJson<import("./types").Conversation>("/conversations/", {
        method: "POST",
        body: JSON.stringify({ title }),
      }),

    rename: async (
      id: string,
      title: string
    ): Promise<import("./types").Conversation> =>
      fetchJson<import("./types").Conversation>(`/conversations/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ title }),
      }),

    delete: async (id: string): Promise<void> =>
      fetchJson<void>(`/conversations/${id}`, { method: "DELETE" }),

    /**
     * Streaming version of sendMessage.
     * Returns an AsyncGenerator yielding SSEEvent objects.
     * Pass an AbortSignal to support stop-generation.
     */
    streamMessage,

    /**
     * Non-streaming fallback (kept for backward compatibility with tests).
     */
    sendMessage: async (
      id: string,
      content: string
    ): Promise<ChatResponse> =>
      fetchJson<ChatResponse>(`/conversations/${id}/messages`, {
        method: "POST",
        body: JSON.stringify({ content }),
      }),
  },

  documents: {
    list: async (): Promise<DocumentStatusResponse[]> =>
      fetchJson<DocumentStatusResponse[]>("/documents/"),

    get: async (id: string): Promise<DocumentStatusResponse> =>
      fetchJson<DocumentStatusResponse>(`/documents/${id}`),

    upload: async (file: File): Promise<DocumentUploadResponse> => {
      const formData = new FormData();
      formData.append("file", file);

      const url = `${API_BASE_URL}/documents/upload`;
      const headers = authHeaders();

      let response: Response;
      try {
        response = await fetch(url, {
          method: "POST",
          body: formData,
          headers,
        });
      } catch {
        throw new NetworkError();
      }

      if (!response.ok) {
        let detail = response.statusText;
        try {
          const body = await response.json();
          detail = body.detail || detail;
        } catch { /* ignore */ }
        throw new ApiError(response.status, detail);
      }

      return response.json();
    },

    delete: async (id: string): Promise<void> =>
      fetchJson<void>(`/documents/${id}`, { method: "DELETE" }),

    updateRoles: async (
      id: string,
      allowed_roles: string[]
    ): Promise<DocumentStatusResponse> =>
      fetchJson<DocumentStatusResponse>(`/documents/${id}/roles`, {
        method: "PATCH",
        body: JSON.stringify({ allowed_roles }),
      }),
  },

  users: {
    list: async (): Promise<import("./types").UserProfile[]> =>
      fetchJson<import("./types").UserProfile[]>("/users/"),

    updateRoles: async (
      id: string,
      roles: string[]
    ): Promise<import("./types").UserProfile> =>
      fetchJson<import("./types").UserProfile>(`/users/${id}/roles`, {
        method: "PATCH",
        body: JSON.stringify({ roles }),
      }),

    updateStatus: async (
      id: string,
      is_active: boolean
    ): Promise<import("./types").UserProfile> =>
      fetchJson<import("./types").UserProfile>(`/users/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
      }),
  },
};
