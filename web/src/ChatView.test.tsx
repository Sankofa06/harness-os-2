import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatView } from "./ChatView";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {}

  addEventListener(type: string, handler: (event: unknown) => void) {
    if (type === "open") this.onopen = handler as () => void;
    if (type === "message") this.onmessage = handler as (event: { data: string }) => void;
  }
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ChatView", () => {
  beforeEach(() => {
    MockWebSocket.instances = [];
    vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  });

  it("bootstraps a contact/session and displays a sent message's reply", async () => {
    const contact = {
      id: "con_1",
      handle: "builder",
      display_name: "Builder",
      role_id: null,
      persona_ids: [],
      binding: { provider: "fake", model: "fake-mini" },
    };
    const session = {
      id: "ses_1",
      title: "Harness session",
      state: "active",
      contact_ids: ["con_1"],
      created_at: "now",
      updated_at: "now",
    };

    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? "GET";
      if (url.endsWith("/contacts") && method === "GET") return jsonResponse([]);
      if (url.endsWith("/contacts") && method === "POST") return jsonResponse(contact, 201);
      if (url.endsWith("/sessions") && method === "GET") return jsonResponse([]);
      if (url.endsWith("/sessions") && method === "POST") return jsonResponse(session, 201);
      if (url.includes("/messages") && method === "POST") {
        return jsonResponse({
          correlation_id: "run_x",
          runs: [{ run_id: "run_1", contact_handle: "builder", content: "hello back", status: "succeeded" }],
        });
      }
      throw new Error(`unexpected request: ${method} ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ChatView />);

    expect(await screen.findByText("@builder")).toBeInTheDocument();

    const input = screen.getByLabelText("Message");
    await userEvent.type(input, "hi there");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => expect(screen.getByText("hello back")).toBeInTheDocument());
    expect(screen.getByText("hi there")).toBeInTheDocument();
  });
});
