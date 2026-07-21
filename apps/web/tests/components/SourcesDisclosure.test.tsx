import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { QuerySource } from "../../src/api/types";
import { SourcesDisclosure } from "../../src/components/SourcesDisclosure";

const sources: QuerySource[] = [
  {
    path: "Projects/Whetstone/Infrastructure.md",
    heading: "Terraform Drift",
    start_line: 42,
    end_line: 58,
    score: 0.91,
  },
];

describe("SourcesDisclosure", () => {
  it("renders nothing when there are no sources", () => {
    const { container } = render(<SourcesDisclosure sources={[]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("is collapsed by default and expands source details on click", async () => {
    render(<SourcesDisclosure sources={sources} />);
    expect(screen.queryByText("Projects/Whetstone/Infrastructure.md")).not.toBeInTheDocument();

    await userEvent.click(screen.getByText("Sources (1)", { exact: false }));
    expect(screen.getByText("Projects/Whetstone/Infrastructure.md")).toBeVisible();
    expect(screen.getByText(/Terraform Drift/)).toBeVisible();
  });

  it("renders lines without a dangling separator when heading is null", async () => {
    const sourcesWithNullHeading: QuerySource[] = [
      {
        path: "Projects/Meridian/Overview.md",
        heading: null,
        start_line: 1,
        end_line: 10,
        score: 0.75,
      },
    ];
    render(<SourcesDisclosure sources={sourcesWithNullHeading} />);

    await userEvent.click(screen.getByText("Sources (1)", { exact: false }));
    expect(screen.getByText("lines 1-10")).toBeVisible();
  });
});
