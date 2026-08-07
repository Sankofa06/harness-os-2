import { useCallback, useEffect, useRef, useState } from "react";

import { connectEventStream, type HarnessEvent } from "./api/events";
import { getApiBase, getApiToken } from "./api/config";
import { HarnessApiError, HarnessClient, type Contact, type Session } from "./api/client";

interface DisplayMessage {
  id: string;
  author: string;
  content: string;
  streaming?: boolean;
}

const DEFAULT_CONTACT_HANDLE = "builder";

export function ChatView() {
  const [client] = useState(() => new HarnessClient(getApiBase(), getApiToken()));
  const [status, setStatus] = useState<"connecting" | "ready" | "error">("connecting");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [session, setSession] = useState<Session | null>(null);
  const [messages, setMessages] = useState<DisplayMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const streamingRunId = useRef<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        let allContacts = await client.listContacts();
        let builder = allContacts.find((c) => c.handle === DEFAULT_CONTACT_HANDLE);
        if (!builder) {
          try {
            builder = await client.createContact({
              handle: DEFAULT_CONTACT_HANDLE,
              display_name: "Builder",
              role: "coder",
              binding: { provider: "fake", model: "fake-mini" },
            });
            allContacts = [...allContacts, builder];
          } catch (err) {
            // Two mounts of this effect (React StrictMode double-invokes effects in
            // dev) can race to create the same handle; the loser re-fetches instead
            // of surfacing the other mount's success as a fatal error.
            if (!(err instanceof HarnessApiError) || err.code !== "conflict") throw err;
            allContacts = await client.listContacts();
            builder = allContacts.find((c) => c.handle === DEFAULT_CONTACT_HANDLE);
            if (!builder) throw err;
          }
        }
        if (cancelled) return;
        setContacts(allContacts);

        const sessions = await client.listSessions();
        const newSession =
          sessions[0] ?? (await client.createSession("Harness session", [builder.handle]));
        if (cancelled) return;
        setSession(newSession);
        setStatus("ready");
      } catch (err) {
        if (cancelled) return;
        setErrorMessage(err instanceof Error ? err.message : String(err));
        setStatus("error");
      }
    }

    void bootstrap();
    return () => {
      cancelled = true;
    };
  }, [client]);

  useEffect(() => {
    if (!session) return;
    const disconnect = connectEventStream(
      getApiBase(),
      getApiToken(),
      { session_ids: [session.id], event_types: ["inference.token", "inference.completed"] },
      (event: HarnessEvent) => {
        if (event.type === "inference.token" && event.resource) {
          const runId = event.resource.id;
          const delta = String(event.payload.delta ?? "");
          streamingRunId.current = runId;
          setMessages((prev) => {
            const existing = prev.find((m) => m.id === runId);
            if (existing) {
              return prev.map((m) =>
                m.id === runId ? { ...m, content: m.content + delta } : m,
              );
            }
            return [...prev, { id: runId, author: "…", content: delta, streaming: true }];
          });
        }
      },
    );
    return disconnect;
  }, [session]);

  const sendMessage = useCallback(async () => {
    if (!session || !draft.trim() || sending) return;
    const content = draft;
    setDraft("");
    setSending(true);
    setMessages((prev) => [
      ...prev,
      { id: `local-${Date.now()}`, author: "you", content },
    ]);
    try {
      const response = await client.sendMessage(session.id, content);
      setMessages((prev) => {
        const withoutStreamPlaceholders = prev.filter((m) => !m.streaming);
        const finalMessages = response.runs.map((run) => ({
          id: run.run_id,
          author: run.contact_handle,
          content: run.content,
        }));
        return [...withoutStreamPlaceholders, ...finalMessages];
      });
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setSending(false);
    }
  }, [client, session, draft, sending]);

  if (status === "connecting") {
    return <div className="panel-center">Connecting to Harness…</div>;
  }
  if (status === "error") {
    return (
      <div className="panel-center panel-error">
        Could not reach the Harness API at {getApiBase()}: {errorMessage}
      </div>
    );
  }

  return (
    <div className="chat-view">
      <aside className="rail">
        <h2>Contacts</h2>
        <ul className="contact-list">
          {contacts.map((c) => (
            <li key={c.id} className="contact-chip">
              <span className="contact-handle">@{c.handle}</span>
              <span className="contact-model">{c.binding.model ?? "unbound"}</span>
            </li>
          ))}
        </ul>
      </aside>
      <main className="conversation">
        <div className="messages" role="log" aria-live="polite">
          {messages.map((m) => (
            <div key={m.id} className={`message message-${m.author === "you" ? "user" : "agent"}`}>
              <span className="message-author">{m.author}</span>
              <span className="message-content">{m.content}</span>
            </div>
          ))}
        </div>
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            void sendMessage();
          }}
        >
          <input
            aria-label="Message"
            placeholder="Message… use @handle to address a contact"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            disabled={sending}
          />
          <button type="submit" disabled={sending || !draft.trim()}>
            Send
          </button>
        </form>
      </main>
    </div>
  );
}
