import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { QueryInput } from "../../src/components/QueryInput";

describe("QueryInput", () => {
  it("auto-focuses on mount", () => {
    render(<QueryInput onSubmit={vi.fn()} disabled={false} />);
    expect(screen.getByPlaceholderText("terraform drift prod...")).toHaveFocus();
  });

  it("calls onSubmit with the trimmed query when Enter is pressed", async () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} disabled={false} />);
    const input = screen.getByPlaceholderText("terraform drift prod...");

    await userEvent.type(input, "  terraform drift prod  {Enter}");
    expect(onSubmit).toHaveBeenCalledWith("terraform drift prod");
  });

  it("does not call onSubmit on Enter when the input is empty", async () => {
    const onSubmit = vi.fn();
    render(<QueryInput onSubmit={onSubmit} disabled={false} />);
    const input = screen.getByPlaceholderText("terraform drift prod...");

    await userEvent.type(input, "{Enter}");
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("focuses the input when '/' is pressed while it isn't already focused", async () => {
    render(
      <div>
        <button>elsewhere</button>
        <QueryInput onSubmit={vi.fn()} disabled={false} />
      </div>
    );
    const input = screen.getByPlaceholderText("terraform drift prod...");
    const elsewhere = screen.getByRole("button", { name: "elsewhere" });
    elsewhere.focus();
    expect(input).not.toHaveFocus();

    await userEvent.keyboard("/");
    expect(input).toHaveFocus();
  });
});
