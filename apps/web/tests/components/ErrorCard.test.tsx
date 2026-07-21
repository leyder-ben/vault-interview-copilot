import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ErrorCard } from "../../src/components/ErrorCard";

describe("ErrorCard", () => {
  it("renders XCircle and red text, and calls onRetry when clicked", async () => {
    const onRetry = vi.fn();
    render(<ErrorCard message="Can't reach the API." onRetry={onRetry} />);

    expect(screen.getByText("Can't reach the API.")).toBeInTheDocument();
    expect(document.querySelector("svg.lucide-circle-x")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
