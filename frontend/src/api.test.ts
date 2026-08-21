import { describe, expect, it, vi } from "vitest";

import {
  ApiError,
  deleteConversation,
  getTask,
  listConversations,
  parseEventBlock,
  streamQuestion,
} from "./api";

describe("parseEventBlock", () => {
  it("parses an SSE event with JSON data", () => {
    expect(
      parseEventBlock(
        'event: metadata\ndata: {"event":"metadata","conversation_id":"abc","references":[{"source":"hackaday","url":"https://example.test/article","title":"Article"}]}',
      ),
    ).toEqual({
      event: "metadata",
      conversation_id: "abc",
      references: [
        { source: "hackaday", url: "https://example.test/article", title: "Article" },
      ],
    });
  });

  it("returns null for comments and malformed blocks", () => {
    expect(parseEventBlock(": keep-alive")).toBeNull();
    expect(parseEventBlock("event: text\ndata: not-json")).toBeNull();
  });
});

describe("streamQuestion", () => {
  it("surfaces the API detail when a request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response('{"detail":"invalid authentication token"}', {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    await expect(
      streamQuestion("bad-token", { question: "Help" }, vi.fn()),
    ).rejects.toEqual(new ApiError("invalid authentication token", 401));
  });
});

describe("getTask", () => {
  it("loads an authenticated task by id", async () => {
    const task = {
      id: "task-123",
      type: "knowledge_ingestion",
      status: "RUNNING",
      parameters: {},
      details: {},
      result: null,
      error: null,
      created_at: "2026-08-19T09:00:00Z",
      started_at: "2026-08-19T09:00:01Z",
      finished_at: null,
    };
    const fetchMock = vi.fn().mockResolvedValue(Response.json(task));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getTask("secret", "task-123")).resolves.toEqual(task);
    expect(fetchMock).toHaveBeenCalledWith("/api/tasks/task-123", {
      headers: { "X-Auth-Token": "secret" },
    });
  });
});

describe("conversations", () => {
  it("lists conversations with authentication", async () => {
    const conversations = [{ id: "conversation-1", title: "ESP32 help" }];
    const fetchMock = vi.fn().mockResolvedValue(Response.json(conversations));
    vi.stubGlobal("fetch", fetchMock);

    await expect(listConversations("secret")).resolves.toEqual(conversations);
    expect(fetchMock).toHaveBeenCalledWith("/api/conversations", {
      headers: { "X-Auth-Token": "secret" },
    });
  });

  it("deletes a conversation with authentication", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await deleteConversation("secret", "conversation-1");

    expect(fetchMock).toHaveBeenCalledWith("/api/conversations/conversation-1", {
      method: "DELETE",
      headers: { "X-Auth-Token": "secret" },
    });
  });
});
