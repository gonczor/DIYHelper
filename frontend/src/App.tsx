import { useCallback, useEffect, useState } from "react";
import type { KeyboardEvent, SubmitEvent as ReactSubmitEvent } from "react";

import {
  ConversationSummary,
  createIngestionTask,
  deleteConversation,
  getConversation,
  listConversations,
  QuestionEvent,
  streamQuestion,
  Task,
} from "./api";
import "./App.css";
import { ChatPanel } from "./components/ChatPanel";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { TokenGate } from "./components/TokenGate";
import { KnowledgeScope, Message } from "./types";
import { useTaskPolling } from "./useTaskPolling";

const TOKEN_KEY = "diy-helper-auth-token";

/** Coordinates authentication, conversation state, chat streaming, and knowledge ingestion. */
function App() {
  const [token, setToken] = useState(readToken);
  const [draftToken, setDraftToken] = useState(token);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [scope, setScope] = useState<KnowledgeScope>("all");
  const [conversationId, setConversationId] = useState<string>();
  const [isAnswering, setIsAnswering] = useState(false);
  const [error, setError] = useState("");
  const [month, setMonth] = useState("");
  const [task, setTask] = useState<Task>();
  const [isStartingTask, setIsStartingTask] = useState(false);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [isLoadingConversation, setIsLoadingConversation] = useState(false);

  useTaskPolling(token, task, setTask, setError);

  const refreshConversations = useCallback(
    async function refreshConversations() {
      if (!token) return;
      try {
        setConversations(await listConversations(token));
      } catch (caughtError) {
        setError(errorMessage(caughtError));
      }
    },
    [token],
  );

  useEffect(
    function refreshHistoryAfterTokenChange() {
      if (!token) return;
      let cancelled = false;

      function storeConversations(loadedConversations: ConversationSummary[]) {
        if (!cancelled) setConversations(loadedConversations);
      }

      function reportConversationError(caughtError: unknown) {
        if (!cancelled) setError(errorMessage(caughtError));
      }

      function cancelConversationRefresh() {
        cancelled = true;
      }

      void listConversations(token).then(storeConversations, reportConversationError);
      return cancelConversationRefresh;
    },
    [token],
  );

  function saveToken(event: ReactSubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanToken = draftToken.trim();
    if (!cleanToken) return;
    localStorage.setItem(TOKEN_KEY, cleanToken);
    setToken(cleanToken);
  }

  function changeToken() {
    setToken("");
    setDraftToken("");
    localStorage.removeItem(TOKEN_KEY);
  }

  function startNewConversation() {
    setMessages([]);
    setConversationId(undefined);
    setError("");
  }

  async function selectConversation(selectedConversationId: string) {
    if (isAnswering || isLoadingConversation) return;
    setIsLoadingConversation(true);
    setError("");
    try {
      const selected = await getConversation(token, selectedConversationId);
      setMessages(selected.messages.map(messageFromApi));
      setConversationId(selected.id);
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsLoadingConversation(false);
    }
  }

  async function removeConversation(removedConversationId: string) {
    if (!window.confirm("Delete this conversation permanently?")) return;
    setError("");
    try {
      await deleteConversation(token, removedConversationId);
      if (conversationId === removedConversationId) startNewConversation();
      await refreshConversations();
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    }
  }

  async function submitQuestion(event: ReactSubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuestion = question.trim();
    if (!cleanQuestion || isAnswering) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: cleanQuestion,
    };
    const answerId = crypto.randomUUID();
    setMessages(function addPendingAnswer(current) {
      return [
        ...current,
        userMessage,
        { id: answerId, role: "assistant", content: "" },
      ];
    });
    setQuestion("");
    setError("");
    setIsAnswering(true);

    function handleQuestionEvent(streamEvent: QuestionEvent) {
      if (streamEvent.conversation_id) setConversationId(streamEvent.conversation_id);
      if (streamEvent.event === "metadata" && streamEvent.references) {
        setMessages(function addAnswerReferences(current) {
          return updateMessageReferences(current, answerId, streamEvent.references ?? []);
        });
      }
      if (streamEvent.event === "text" && streamEvent.text) {
        setMessages(function appendText(current) {
          return updateMessage(current, answerId, streamEvent.text ?? "");
        });
      }
      if (streamEvent.event === "error") {
        setError(streamEvent.message ?? "The answer could not be generated.");
      }
      if (streamEvent.event === "done") void refreshConversations();
    }

    try {
      await streamQuestion(
        token,
        {
          question: cleanQuestion,
          sources: sourcesForScope(scope),
          conversation_id: conversationId,
        },
        handleQuestionEvent,
      );
    } catch (caughtError) {
      setError(errorMessage(caughtError));
      setMessages(function removeEmptyAnswer(current) {
        return current.filter(function keepMessage(message) {
          return message.id !== answerId || message.content !== "";
        });
      });
    } finally {
      setIsAnswering(false);
    }
  }

  function handleQuestionKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function startIngestion(event: ReactSubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsStartingTask(true);
    setError("");
    try {
      setTask(await createIngestionTask(token, month));
    } catch (caughtError) {
      setError(errorMessage(caughtError));
    } finally {
      setIsStartingTask(false);
    }
  }

  if (!token) {
    return (
      <TokenGate
        draftToken={draftToken}
        onDraftTokenChange={setDraftToken}
        onSubmit={saveToken}
      />
    );
  }

  return (
    <div className="app-shell">
      <Header onChangeToken={changeToken} />
      <main className="workspace">
        <Sidebar
          conversations={conversations}
          activeConversationId={conversationId}
          conversationControlsDisabled={isAnswering || isLoadingConversation}
          scope={scope}
          month={month}
          task={task}
          ingestionBusy={isStartingTask}
          onNewConversation={startNewConversation}
          onSelectConversation={selectConversation}
          onDeleteConversation={removeConversation}
          onScopeChange={setScope}
          onMonthChange={setMonth}
          onStartIngestion={startIngestion}
        />
        <ChatPanel
          messages={messages}
          question={question}
          error={error}
          busy={isAnswering}
          onQuestionChange={setQuestion}
          onQuestionKeyDown={handleQuestionKeyDown}
          onSubmit={submitQuestion}
        />
      </main>
    </div>
  );
}

function readToken(): string {
  return localStorage.getItem(TOKEN_KEY) ?? "";
}

function sourcesForScope(scope: KnowledgeScope): string[] | null {
  if (scope === "hackaday") return ["hackaday"];
  if (scope === "general") return [];
  return null;
}

function updateMessage(messages: Message[], id: string, text: string): Message[] {
  return messages.map(function appendToMatchingMessage(message) {
    return message.id === id ? { ...message, content: message.content + text } : message;
  });
}

function updateMessageReferences(
  messages: Message[],
  id: string,
  references: NonNullable<Message["references"]>,
): Message[] {
  return messages.map(function addReferencesToMatchingMessage(message) {
    return message.id === id ? { ...message, references } : message;
  });
}

function messageFromApi(message: {
  role: "user" | "model";
  content: string;
  references?: Message["references"];
}): Message {
  return {
    id: crypto.randomUUID(),
    role: message.role === "user" ? "user" : "assistant",
    content: message.content,
    references: message.references,
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

export default App;
