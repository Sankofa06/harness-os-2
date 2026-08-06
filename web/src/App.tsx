import { ChatView } from "./ChatView";

export function App() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <span className="app-title">Harness OS</span>
      </header>
      <ChatView />
    </div>
  );
}
