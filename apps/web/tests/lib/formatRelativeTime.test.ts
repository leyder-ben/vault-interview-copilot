import { describe, expect, it, vi } from "vitest";
import { formatRelativeTime } from "../../src/lib/formatRelativeTime";

describe("formatRelativeTime", () => {
  it("returns 'unknown time' for a null timestamp", () => {
    expect(formatRelativeTime(null)).toBe("unknown time");
  });

  it("returns minutes-ago for a timestamp under an hour old", () => {
    const now = new Date("2026-07-19T12:00:00Z");
    vi.setSystemTime(now);
    expect(formatRelativeTime("2026-07-19T11:45:00Z")).toBe("15m ago");
    vi.useRealTimers();
  });

  it("returns hours-ago for a timestamp under a day old", () => {
    const now = new Date("2026-07-19T12:00:00Z");
    vi.setSystemTime(now);
    expect(formatRelativeTime("2026-07-19T10:00:00Z")).toBe("2h ago");
    vi.useRealTimers();
  });
});
