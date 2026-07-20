import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { App } from "../src/App";

describe("App", () => {
  it("renders the app shell placeholder", () => {
    render(<App />);
    expect(screen.getByText("vault-interview-copilot")).toBeInTheDocument();
  });
});
