import type { SubmitEvent as ReactSubmitEvent } from "react";

import { ConversationSummary, Task } from "../api";
import { KnowledgeScope } from "../types";
import { ConversationHistory } from "./ConversationHistory";
import { KnowledgeIngestion } from "./KnowledgeIngestion";
import { KnowledgeScopePicker } from "./KnowledgeScopePicker";

type SidebarProps = {
  conversations: ConversationSummary[];
  activeConversationId: string | undefined;
  conversationControlsDisabled: boolean;
  scope: KnowledgeScope;
  month: string;
  task: Task | undefined;
  ingestionBusy: boolean;
  onNewConversation: () => void;
  onSelectConversation: (conversationId: string) => Promise<void>;
  onDeleteConversation: (conversationId: string) => Promise<void>;
  onScopeChange: (scope: KnowledgeScope) => void;
  onMonthChange: (month: string) => void;
  onStartIngestion: (event: ReactSubmitEvent<HTMLFormElement>) => void;
};

/** Groups conversation, knowledge scope, and ingestion controls beside the chat. */
export function Sidebar(props: SidebarProps) {
  return (
    <aside className="sidebar">
      <button className="new-chat" type="button" onClick={props.onNewConversation}>
        <span>＋</span> New conversation
      </button>
      <ConversationHistory
        conversations={props.conversations}
        activeId={props.activeConversationId}
        disabled={props.conversationControlsDisabled}
        onSelect={props.onSelectConversation}
        onDelete={props.onDeleteConversation}
      />
      <KnowledgeScopePicker scope={props.scope} onChange={props.onScopeChange} />
      <KnowledgeIngestion
        month={props.month}
        task={props.task}
        busy={props.ingestionBusy}
        onMonthChange={props.onMonthChange}
        onSubmit={props.onStartIngestion}
      />
    </aside>
  );
}
