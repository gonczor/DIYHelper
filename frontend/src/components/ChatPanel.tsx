import type { KeyboardEvent, SubmitEvent as ReactSubmitEvent } from "react";

import { Message } from "../types";

type ChatPanelProps = {
  messages: Message[];
  question: string;
  error: string;
  busy: boolean;
  onQuestionChange: (question: string) => void;
  onQuestionKeyDown: (event: KeyboardEvent<HTMLTextAreaElement>) => void;
  onSubmit: (event: ReactSubmitEvent<HTMLFormElement>) => void;
};

/** Displays the conversation transcript and the question composer. */
export function ChatPanel({
  messages,
  question,
  error,
  busy,
  onQuestionChange,
  onQuestionKeyDown,
  onSubmit,
}: ChatPanelProps) {
  function updateQuestion(event: React.ChangeEvent<HTMLTextAreaElement>) {
    onQuestionChange(event.target.value);
  }

  return (
    <section className="chat-panel">
      {messages.length === 0 ? <EmptyChat /> : <MessageList messages={messages} busy={busy} />}
      <div className="composer-wrap">
        {error && <div className="error-banner" role="alert">{error}</div>}
        <form className="composer" onSubmit={onSubmit}>
          <label className="sr-only" htmlFor="question">Ask a DIY question</label>
          <textarea
            id="question"
            rows={1}
            placeholder="Ask about a project, component, or technique…"
            value={question}
            onChange={updateQuestion}
            onKeyDown={onQuestionKeyDown}
            disabled={busy}
          />
          <button
            className="send-button"
            type="submit"
            aria-label="Send question"
            disabled={!question.trim() || busy}
          >
            ↑
          </button>
        </form>
        <p className="composer-hint">Enter to send · Shift + Enter for a new line</p>
      </div>
    </section>
  );
}

/** Displays introductory prompts before a conversation has started. */
function EmptyChat() {
  return (
    <div className="empty-chat">
      <div className="blueprint-icon" aria-hidden="true"><span>?</span></div>
      <p className="eyebrow">Bench is clear</p>
      <h1>What are you building?</h1>
      <p>Ask about electronics, tools, materials, repairs, or ideas gathered from the DIY community.</p>
      <div className="prompt-grid">
        <span>“How do I choose a resistor for an LED?”</span>
        <span>“Explain ESP32 deep sleep simply.”</span>
        <span>“What should I know before soldering?”</span>
      </div>
    </div>
  );
}

/** Renders all messages and the current streaming indicator. */
function MessageList({ messages, busy }: { messages: Message[]; busy: boolean }) {
  return (
    <div className="messages" aria-live="polite">
      {messages.map(renderMessage)}
      {busy && <span className="streaming-label">Researching and writing…</span>}
    </div>
  );
}

function renderMessage(message: Message) {
  return (
    <article className={`message ${message.role}`} key={message.id}>
      <div className="avatar">{message.role === "user" ? "YOU" : "DIY"}</div>
      <div>
        <p className="message-author">{message.role === "user" ? "You" : "DIY Helper"}</p>
        <div className="message-content">
          {message.content || <span className="typing">•••</span>}
        </div>
      </div>
    </article>
  );
}
