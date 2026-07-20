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
        personalExamples={["Example one"]}
      />
    );
    expect(screen.queryByText("Point one")).not.toBeInTheDocument();

    await userEvent.click(screen.getByText("Supporting points & examples", { exact: false }));
    expect(screen.getByText("Point one")).toBeVisible();
    expect(screen.getByText("Example one")).toBeVisible();
  });
});
