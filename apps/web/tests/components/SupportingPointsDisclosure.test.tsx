import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SupportingPointsDisclosure } from "../../src/components/SupportingPointsDisclosure";

describe("SupportingPointsDisclosure", () => {
  it("renders nothing when both lists are empty", () => {
    const { container } = render(
      <SupportingPointsDisclosure supportingPoints={[]} personalExamples={[]} />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("is collapsed by default and expands points and examples on click", async () => {
    render(
      <SupportingPointsDisclosure
        supportingPoints={["Point one"]}
        personalExamples={[{ project: "Meridian", example: "Example one", source_chunk_ids: [1] }]}
      />
    );
    expect(screen.queryByText("Point one")).not.toBeInTheDocument();

    await userEvent.click(screen.getByText("Supporting points & examples", { exact: false }));
    expect(screen.getByText("Point one")).toBeVisible();
    expect(screen.getByText("Meridian: Example one")).toBeVisible();
  });

  it("renders each personal example's project and example text from the real object shape", async () => {
    render(
      <SupportingPointsDisclosure
        supportingPoints={[]}
        personalExamples={[
          {
            project: "Meridian",
            example: "Led the migration off legacy queues.",
            source_chunk_ids: [1, 2],
          },
          {
            project: "Whetstone",
            example: "Diagnosed the terraform drift in prod.",
            source_chunk_ids: [3],
          },
        ]}
      />
    );

    await userEvent.click(screen.getByText("Supporting points & examples", { exact: false }));
    expect(screen.getByText("Meridian: Led the migration off legacy queues.")).toBeVisible();
    expect(screen.getByText("Whetstone: Diagnosed the terraform drift in prod.")).toBeVisible();
  });
});
