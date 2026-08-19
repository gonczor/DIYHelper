import { ConversationSummary } from "../api";

type ConversationHistoryProps = {
  conversations: ConversationSummary[];
  activeId: string | undefined;
  disabled: boolean;
  onSelect: (conversationId: string) => Promise<void>;
  onDelete: (conversationId: string) => Promise<void>;
};

/** Lists saved conversations and exposes selection and deletion controls. */
export function ConversationHistory({
  conversations,
  activeId,
  disabled,
  onSelect,
  onDelete,
}: ConversationHistoryProps) {
  function renderConversation(conversation: ConversationSummary) {
    function selectItem() {
      void onSelect(conversation.id);
    }

    function deleteItem(event: React.MouseEvent<HTMLButtonElement>) {
      event.stopPropagation();
      void onDelete(conversation.id);
    }

    return (
      <div
        className={conversation.id === activeId ? "conversation-item active" : "conversation-item"}
        key={conversation.id}
      >
        <button
          className="conversation-select"
          type="button"
          onClick={selectItem}
          disabled={disabled}
          title={conversation.title}
        >
          <span>{conversation.title}</span>
          <small>{formatConversationDate(conversation.updated_at)}</small>
        </button>
        <button
          className="conversation-delete"
          type="button"
          onClick={deleteItem}
          disabled={disabled}
          aria-label={`Delete ${conversation.title}`}
          title="Delete conversation"
        >
          ×
        </button>
      </div>
    );
  }

  return (
    <section className="conversation-history">
      <p className="eyebrow">Conversations</p>
      {conversations.length === 0 && <p className="empty-history">No saved conversations yet.</p>}
      <div className="conversation-list">{conversations.map(renderConversation)}</div>
    </section>
  );
}

function formatConversationDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(
    new Date(value),
  );
}
