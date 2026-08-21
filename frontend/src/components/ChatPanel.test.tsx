// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "./ChatPanel";

afterEach(cleanup);

describe("ChatPanel citations", () => {
  it("links numbered citations and presents meaningful source titles", () => {
    render(
      <ChatPanel
        messages={[
          {
            id: "answer",
            role: "assistant",
            content: "The controller appears in this project [1].",
            references: [
              {
                source: "hackaday",
                url: "https://example.test/atmega-project",
                title: "An ATmega328P Project",
              },
            ],
          },
        ]}
        question=""
        error=""
        busy={false}
        onQuestionChange={vi.fn()}
        onQuestionKeyDown={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    const inlineCitation = screen.getByRole("link", { name: "1" });
    const source = screen.getByRole("link", { name: "An ATmega328P Project" });
    expect(inlineCitation.getAttribute("href")).toBe("https://example.test/atmega-project");
    expect(source.getAttribute("href")).toBe("https://example.test/atmega-project");
  });

  it("links every article in a grouped citation", () => {
    render(
      <ChatPanel
        messages={[
          {
            id: "answer",
            role: "assistant",
            content: "Related projects appear in both sources [1, 2].",
            references: [
              { source: "hackaday", url: "https://example.test/one", title: "One" },
              { source: "hackaday", url: "https://example.test/two", title: "Two" },
            ],
          },
        ]}
        question=""
        error=""
        busy={false}
        onQuestionChange={vi.fn()}
        onQuestionKeyDown={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByRole("link", { name: "1" }).getAttribute("href")).toBe(
      "https://example.test/one",
    );
    expect(screen.getByRole("link", { name: "2" }).getAttribute("href")).toBe(
      "https://example.test/two",
    );
  });

  it("does not turn unsafe or unknown markers into links", () => {
    const view = render(
      <ChatPanel
        messages={[
          {
            id: "answer",
            role: "assistant",
            content: "Unsafe [1] and unknown [2].",
            references: [{ source: "hackaday", url: "javascript:alert(1)", title: "Unsafe" }],
          },
        ]}
        question=""
        error=""
        busy={false}
        onQuestionChange={vi.fn()}
        onQuestionKeyDown={vi.fn()}
        onSubmit={vi.fn()}
      />,
    );

    expect(view.container.querySelector("a")).toBeNull();
    expect(view.container.textContent).toContain("Unsafe [1] and unknown [2].");
  });
});
