import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("submits a query and renders the cited answer end to end", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((path: string) => {
        if (path === "/api/index/status") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              embedding_model: "nomic-embed-text",
              note_count: 5,
              last_run: null,
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: {
              say_this: "Terraform drift happened because state and reality diverged.",
              supporting_points: ["Ran terraform plan to detect it."],
              personal_examples: [],
            },
            sources: [
              {
                path: "Projects/Whetstone/Infrastructure.md",
                heading: "Terraform Drift",
                start_line: 42,
                end_line: 58,
                score: 0.91,
              },
            ],
            confidence: "high",
            limitations: [],
            timing_ms: { retrieval: 100, generation: 900, total: 1000 },
          }),
        });
      })
    );

    render(<App />);
    const input = screen.getByPlaceholderText("terraform drift prod...");
    await userEvent.type(input, "terraform drift prod{Enter}");

    await waitFor(() =>
      expect(
        screen.getByText("Terraform drift happened because state and reality diverged.")
      ).toBeInTheDocument()
    );
    expect(screen.getByText("Cited")).toBeInTheDocument();
  });

  it("shows the abstention state for a query with no grounding", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((path: string) => {
        if (path === "/api/index/status") {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              embedding_model: "nomic-embed-text",
              note_count: 5,
              last_run: null,
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: { say_this: "", supporting_points: [], personal_examples: [] },
            sources: [],
            confidence: "low",
            limitations: ["No relevant vault content found for this query."],
            timing_ms: { retrieval: 50, generation: 0, total: 50 },
          }),
        });
      })
    );

    render(<App />);
    const input = screen.getByPlaceholderText("terraform drift prod...");
    await userEvent.type(input, "gibberish nonexistent topic{Enter}");

    await waitFor(() => expect(screen.getByText("No grounding found")).toBeInTheDocument());
    expect(screen.getByText("No relevant vault content found for this query.")).toBeInTheDocument();
  });
});
