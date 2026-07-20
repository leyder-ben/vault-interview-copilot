import { afterEach, describe, expect, it, vi } from "vitest";
import { getIndexStatus, postQuery } from "../../src/api/client";

describe("postQuery", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on a successful response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: { say_this: "hi", supporting_points: [], personal_examples: [] },
          sources: [],
          confidence: "high",
          limitations: [],
          timing_ms: { retrieval: 1, generation: 1, total: 2 },
        }),
      })
    );

    const result = await postQuery({ query: "test" });
    expect(result.answer.say_this).toBe("hi");
  });

  it("throws the fixed generic message on a 5xx response with a non-JSON body", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers({ "content-type": "text/plain" }),
        json: async () => {
          throw new Error("not json");
        },
      })
    );

    await expect(postQuery({ query: "test" })).rejects.toThrow(
      "Something went wrong generating an answer."
    );
  });

  it("throws the fixed generic message on a 5xx response even when the body is JSON with a detail field", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({ detail: "Internal exception: /home/ben/secret/path.py line 42" }),
      })
    );

    await expect(postQuery({ query: "test" })).rejects.toThrow(
      "Something went wrong generating an answer."
    );
  });

  it("surfaces the detail message on a 4xx validation error (array-of-objects detail shape)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        headers: new Headers({ "content-type": "application/json" }),
        json: async () => ({
          detail: [{ loc: ["body", "query"], msg: "field required", type: "value_error.missing" }],
        }),
      })
    );

    await expect(postQuery({ query: "test" })).rejects.toThrow("field required");
  });

  it("throws a connection-failure message when fetch itself rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network down")));

    await expect(postQuery({ query: "test" })).rejects.toThrow("Can't reach the API.");
  });
});

describe("getIndexStatus", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns parsed JSON on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ embedding_model: "nomic-embed-text", note_count: 12, last_run: null }),
      })
    );

    const result = await getIndexStatus();
    expect(result.note_count).toBe(12);
  });
});
