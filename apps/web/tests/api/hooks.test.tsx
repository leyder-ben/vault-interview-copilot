import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import * as client from "../../src/api/client";
import { useIndexStatus, useQueryAnswer } from "../../src/api/hooks";
import type { IndexStatusResponse, QueryResponse } from "../../src/api/types";

function wrapper({ children }: { children: ReactNode }) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("useIndexStatus", () => {
  it("fetches and returns index status via getIndexStatus", async () => {
    const status: IndexStatusResponse = {
      embedding_model: "nomic-embed-text",
      note_count: 42,
      last_run: null,
    };
    vi.spyOn(client, "getIndexStatus").mockResolvedValue(status);

    const { result } = renderHook(() => useIndexStatus(), { wrapper });
    await waitFor(() => expect(result.current.data).toEqual(status));
  });
});

describe("useQueryAnswer", () => {
  it("calls postQuery with the mutation payload and exposes its result", async () => {
    const response: QueryResponse = {
      answer: { say_this: "hi", supporting_points: [], personal_examples: [] },
      sources: [],
      confidence: "high",
      limitations: [],
      timing_ms: { retrieval: 1, generation: 1, total: 2 },
    };
    const postQuerySpy = vi.spyOn(client, "postQuery").mockResolvedValue(response);

    const { result } = renderHook(() => useQueryAnswer(), { wrapper });
    result.current.mutate({ query: "terraform drift" });

    await waitFor(() => expect(result.current.data).toEqual(response));
    expect(postQuerySpy).toHaveBeenCalledWith({ query: "terraform drift" });
  });
});
