export interface HarnessEvent {
  event_id: string;
  type: string;
  timestamp: string;
  correlation_id: string | null;
  resource: { type: string; id: string } | null;
  context: Record<string, string>;
  payload: Record<string, unknown>;
  seq: number | null;
}

export function connectEventStream(
  baseUrl: string,
  token: string | undefined,
  filter: { session_ids?: string[]; event_types?: string[] },
  onEvent: (event: HarnessEvent) => void,
): () => void {
  const wsUrl = new URL("/api/v1/events", baseUrl.replace(/^http/, "ws"));
  if (token) wsUrl.searchParams.set("token", token);

  const socket = new WebSocket(wsUrl.toString());
  socket.addEventListener("open", () => {
    socket.send(JSON.stringify(filter));
  });
  socket.addEventListener("message", (event) => {
    onEvent(JSON.parse(event.data as string) as HarnessEvent);
  });

  return () => socket.close();
}
