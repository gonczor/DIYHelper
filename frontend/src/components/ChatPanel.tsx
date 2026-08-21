import type { KeyboardEvent, ReactNode, SubmitEvent as ReactSubmitEvent } from "react";

import { KnowledgeReference, Message } from "../types";

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
          {message.content ? renderMessageContent(message) : <span className="typing">•••</span>}
        </div>
        {message.role === "assistant" && <ReferenceList references={message.references ?? []} />}
      </div>
    </article>
  );
}

function renderMessageContent(message: Message): ReactNode[] {
  const content: ReactNode[] = [];
  const markerPattern = /\[((?:\d+\s*,\s*)*\d+)\]/g;
  let cursor = 0;
  let match = markerPattern.exec(message.content);
  while (match !== null) {
    content.push(message.content.slice(cursor, match.index));
    content.push(
      renderCitationGroup(match[0], match[1], match.index, message.references ?? []),
    );
    cursor = markerPattern.lastIndex;
    match = markerPattern.exec(message.content);
  }
  content.push(message.content.slice(cursor));
  return content;
}

function renderCitationGroup(
  marker: string,
  numberList: string,
  position: number,
  references: KnowledgeReference[],
): ReactNode {
  const rendered: ReactNode[] = ["["];
  const numbers = numberList.split(",");
  let linked = false;
  for (const [index, value] of numbers.entries()) {
    if (index > 0) rendered.push(", ");
    const number = Number(value.trim());
    const reference = references[number - 1];
    const url = reference ? safeReferenceUrl(reference.url) : null;
    if (!url) {
      rendered.push(String(number));
      continue;
    }
    linked = true;
    rendered.push(
      <a
        className="citation-link"
        href={url}
        key={`citation-${number}-${position}`}
        target="_blank"
        rel="noreferrer"
      >
        {number}
      </a>,
    );
  }
  rendered.push("]");
  if (!linked) return marker;
  return (
    <span className="citation-group" key={`citation-group-${position}`}>
      {rendered}
    </span>
  );
}

function ReferenceList({ references }: { references: KnowledgeReference[] }) {
  const safeReferences = references.filter(hasSafeUrl);
  if (safeReferences.length === 0) return null;
  return (
    <div className="message-sources">
      <span>Sources</span>
      <ol>{safeReferences.map(renderReference)}</ol>
    </div>
  );
}

function renderReference(reference: KnowledgeReference, index: number) {
  const url = safeReferenceUrl(reference.url);
  if (!url) return null;
  return (
    <li key={`${reference.url}-${index}`}>
      <a href={url} target="_blank" rel="noreferrer">{reference.title || reference.url}</a>
    </li>
  );
}

function hasSafeUrl(reference: KnowledgeReference): boolean {
  return safeReferenceUrl(reference.url) !== null;
}

function safeReferenceUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}
