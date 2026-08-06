// Hand-written client for the vertical slice; see DECISIONS.md D-012 — WEB-011
// replaces this with a client generated from /api/v1/openapi.json.

export interface Contact {
  id: string;
  handle: string;
  display_name: string;
  role_id: string | null;
  persona_ids: string[];
  binding: {
    provider: string | null;
    model: string | null;
  };
}

export interface Session {
  id: string;
  title: string;
  state: string;
  contact_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface RunOutcome {
  run_id: string;
  contact_handle: string;
  content: string;
  status: string;
}

export interface MessagesResponse {
  correlation_id: string;
  runs: RunOutcome[];
}

export class HarnessApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}

export class HarnessClient {
  constructor(
    private baseUrl: string,
    private token?: string,
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const headers = new Headers(init?.headers);
    headers.set("Content-Type", "application/json");
    if (this.token) headers.set("Authorization", `Bearer ${this.token}`);

    const resp = await fetch(`${this.baseUrl}/api/v1${path}`, { ...init, headers });
    if (!resp.ok) {
      const body = await resp.json().catch(() => ({ code: "unknown", message: resp.statusText }));
      throw new HarnessApiError(resp.status, body.code ?? "unknown", body.message ?? resp.statusText);
    }
    if (resp.status === 204) return undefined as T;
    return (await resp.json()) as T;
  }

  health(): Promise<{ status: string }> {
    return this.request("/health");
  }

  listContacts(): Promise<Contact[]> {
    return this.request("/contacts");
  }

  createContact(input: {
    handle: string;
    display_name: string;
    role?: string;
    personas?: string[];
    binding?: { provider: string; model: string };
  }): Promise<Contact> {
    return this.request("/contacts", { method: "POST", body: JSON.stringify(input) });
  }

  listSessions(): Promise<Session[]> {
    return this.request("/sessions");
  }

  createSession(title: string, contacts: string[]): Promise<Session> {
    return this.request("/sessions", { method: "POST", body: JSON.stringify({ title, contacts }) });
  }

  sendMessage(sessionId: string, content: string): Promise<MessagesResponse> {
    return this.request(`/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });
  }
}
