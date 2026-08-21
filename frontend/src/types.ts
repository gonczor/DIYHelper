/** A message rendered in the chat transcript. */
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  references?: KnowledgeReference[];
};

export type KnowledgeReference = {
  source: string;
  url: string;
  title?: string | null;
};

/** The reference material Gemini may use when answering a question. */
export type KnowledgeScope = "all" | "hackaday" | "general";
