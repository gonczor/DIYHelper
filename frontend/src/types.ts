/** A message rendered in the chat transcript. */
export type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
};

/** The reference material Gemini may use when answering a question. */
export type KnowledgeScope = "all" | "hackaday" | "general";
