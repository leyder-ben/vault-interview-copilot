import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ConfidenceBadge, deriveConfidenceVariant } from "../../src/components/ConfidenceBadge";

describe("deriveConfidenceVariant", () => {
  it("returns abstention for confidence: low regardless of source count", () => {
    expect(deriveConfidenceVariant("low", 0)).toBe("abstention");
    expect(deriveConfidenceVariant("low", 3)).toBe("abstention");
  });

  it("returns under-cited for high/medium confidence with zero sources", () => {
    expect(deriveConfidenceVariant("high", 0)).toBe("under-cited");
    expect(deriveConfidenceVariant("medium", 0)).toBe("under-cited");
  });

  it("returns cited for high/medium confidence with at least one source", () => {
    expect(deriveConfidenceVariant("high", 1)).toBe("cited");
    expect(deriveConfidenceVariant("medium", 2)).toBe("cited");
  });
});

describe("ConfidenceBadge rendering", () => {
  it("renders CheckCircle2 and green text for the cited state", () => {
    render(<ConfidenceBadge confidence="high" sourceCount={1} />);
    expect(screen.getByText("Cited")).toHaveClass("text-green-500");
    expect(document.querySelector("svg.lucide-circle-check")).toBeInTheDocument();
  });

  it("renders AlertTriangle and amber text for the abstention state", () => {
    render(<ConfidenceBadge confidence="low" sourceCount={0} />);
    expect(screen.getByText("No grounding found")).toHaveClass("text-amber-500");
    expect(document.querySelector("svg.lucide-triangle-alert")).toBeInTheDocument();
  });

  it("renders no icon and neutral zinc classes for the under-cited state", () => {
    render(<ConfidenceBadge confidence="high" sourceCount={0} />);
    const badge = screen.getByText("Grounded");
    expect(badge).toHaveClass("bg-zinc-700", "text-zinc-300");
    expect(badge.querySelector("svg")).not.toBeInTheDocument();
  });
});
