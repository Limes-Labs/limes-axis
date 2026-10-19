import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { strings } from "@/lib/strings";

import { exampleSubjects, ScenarioBanner } from "./scenario-banner";

const copy = strings.overview.scenarioBanner;

describe("ScenarioBanner", () => {
  it("lists each example section once, in page order", () => {
    expect(
      exampleSubjects([
        { subject: "Context", state: "reference" },
        { subject: "Operations", state: "live" },
        { subject: "Approvals", state: "reference" },
        { subject: "Context", state: "reference" },
        { subject: "Audit", state: "stale" },
      ]),
    ).toEqual(["Context", "Approvals"]);
  });

  it("renders nothing for live, empty, loading or failed sources", () => {
    const { container } = render(
      <ScenarioBanner
        demoScenario={false}
        sources={[
          { subject: "Context", state: "live" },
          { subject: "Operations", state: "empty" },
          { subject: "Approvals", state: "loading" },
          { subject: "Audit", state: "unavailable" },
        ]}
      />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("names the example sections in a single labelled region", () => {
    render(
      <ScenarioBanner
        demoScenario={false}
        sources={[
          { subject: "Context", state: "reference" },
          { subject: "Models", state: "reference" },
        ]}
      />,
    );

    const banner = screen.getByRole("region", { name: copy.title });
    expect(banner).toHaveTextContent(`${copy.detail} ${copy.sections(["Context", "Models"])}`);
  });

  it("explains a demo tenant whose records are all persisted", () => {
    render(<ScenarioBanner demoScenario sources={[{ subject: "Context", state: "live" }]} />);

    expect(screen.getByRole("region", { name: copy.title })).toHaveTextContent(copy.demoDetail);
  });
});
