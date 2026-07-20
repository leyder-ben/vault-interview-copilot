import { render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../../src/api/client";
import type { QueryRequest, QueryResponse } from "../../src/api/types";
import { AnswerPanel } from "../../src/components/AnswerPanel";

function mutationStub(
  overrides: Partial<UseMutationResult<QueryResponse, ApiError, QueryRequest>>
): UseMutationResult<QueryResponse, ApiError, QueryRequest> {
  return {
    status: "idle",
    data: undefined,
    error: null,
    reset: vi.fn(),
    ...overrides,
  } as UseMutationResult<QueryResponse, ApiError, QueryRequest>;
}

describe("AnswerPanel", () => {
  it("renders nothing when idle", () => {
    const { container } = render(
      <AnswerPanel mutation={mutationStub({ status: "idle" })} onRetry={vi.fn()} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders LoadingState while pending", () => {
    render(<AnswerPanel mutation={mutationStub({ status: "pending" })} onRetry={vi.fn()} />);
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders ErrorCard on error and wires the onRetry callback", async () => {
    const onRetry = vi.fn();
    render(
      <AnswerPanel
        mutation={mutationStub({
          status: "error",
          error: new ApiError("Can't reach the API.", 0),
        })}
        onRetry={onRetry}
      />
    );
    expect(screen.getByText("Can't reach the API.")).toBeInTheDocument();
  });

  it("renders AnswerCard on success", () => {
    const response: QueryResponse = {
      answer: { say_this: "Say this.", supporting_points: [], personal_examples: [] },
      sources: [],
      confidence: "high",
      limitations: [],
      timing_ms: { retrieval: 1, generation: 1, total: 2 },
    };
    render(
      <AnswerPanel mutation={mutationStub({ status: "success", data: response })} onRetry={vi.fn()} />
    );
    expect(screen.getByText("Say this.")).toBeInTheDocument();
  });
});
