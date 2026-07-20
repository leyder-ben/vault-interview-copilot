import { describe, expect, it } from "vitest";
import { deriveIndexStatusVariant } from "../../src/components/IndexStatusBadge";

describe("deriveIndexStatusVariant", () => {
  it("returns not-indexed when there has never been a run", () => {
    expect(deriveIndexStatusVariant(null)).toBe("not-indexed");
  });

  it("returns error when the last run failed", () => {
    expect(deriveIndexStatusVariant({ status: "failed", errors: null })).toBe("error");
  });

  it("returns error when errors is present even if status is success", () => {
    expect(deriveIndexStatusVariant({ status: "success", errors: { foo: "bar" } })).toBe("error");
  });

  it("returns healthy when status is success and there are no errors", () => {
    expect(deriveIndexStatusVariant({ status: "success", errors: null })).toBe("healthy");
  });
});
