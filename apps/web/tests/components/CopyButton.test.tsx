import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { CopyButton } from "../../src/components/CopyButton";

describe("CopyButton", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("copies only the given text, not any surrounding content", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });

    render(<CopyButton text="Terraform state drift happened because..." />);
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));

    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith("Terraform state drift happened because...");
    expect(await screen.findByText("Copied")).toBeInTheDocument();
  });
});
