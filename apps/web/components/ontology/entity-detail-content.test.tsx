import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  buildOntologyEntityDetail,
  entityAttention,
  resolveRelatedNodes,
  type ManufacturingOntology,
  type ManufacturingOntologyEntityDetail,
} from "@/lib/ontology-demo";

import { EntityDetailContent } from "./entity-detail-content";
import { ontologyFixture } from "./ontology-fixtures";

const attentionOntology: ManufacturingOntology = {
  ...ontologyFixture,
  nodes: ontologyFixture.nodes.map((node) =>
    node.node_id === "asset_line_2"
      ? { ...node, status: "action_required", summary: "Packaging line is waiting on a quality hold." }
      : node.node_id === "policy_egress"
        ? { ...node, status: "watch" }
        : node,
  ),
};

function lineTwoDetail(
  overrides: Partial<ManufacturingOntologyEntityDetail> = {},
): ManufacturingOntologyEntityDetail {
  const detail = buildOntologyEntityDetail(attentionOntology, "asset_line_2");
  if (!detail) {
    throw new Error("fixture entity missing");
  }
  return { ...detail, ...overrides };
}

describe("entityAttention", () => {
  it("is null for a ready entity", () => {
    const ready = buildOntologyEntityDetail(ontologyFixture, "asset_line_1");
    expect(ready && entityAttention(ready)).toBeNull();
  });

  it("explains a non-ready entity from its summary, connected peers and related queue", () => {
    const attention = entityAttention(
      lineTwoDetail({ related_approvals: ["appr_hold"], related_workflows: ["wf_hold"] }),
    );

    expect(attention).toMatchObject({
      status: "action_required",
      reason: "Packaging line is waiting on a quality hold.",
      link: { kind: "approvals", href: "/approvals" },
    });
    expect(attention?.peers.map((peer) => peer.label)).toEqual(["Egress Policy"]);
  });

  it("resolves related ids to connected node labels and keeps unknown ids", () => {
    const detail = lineTwoDetail();
    expect(resolveRelatedNodes(detail, ["policy_egress", "wf_unknown"])).toEqual([
      { id: "policy_egress", node: expect.objectContaining({ label: "Egress Policy" }) },
      { id: "wf_unknown", node: null },
    ]);
  });
});

describe("EntityDetailContent", () => {
  it("shows why an Action Required entity needs action, with links", () => {
    render(<EntityDetailContent detail={lineTwoDetail({ related_approvals: ["appr_hold"] })} />);

    const callout = screen.getByRole("region", { name: "Why this needs action" });
    expect(callout).toHaveTextContent("Packaging line is waiting on a quality hold.");
    expect(within(callout).getByRole("link", { name: "Egress Policy" })).toHaveAttribute(
      "href",
      expect.stringContaining("policy_egress"),
    );
    expect(within(callout).getByRole("link", { name: "Review approvals" })).toHaveAttribute(
      "href",
      "/approvals",
    );
  });

  it("does not show an attention callout for a ready entity", () => {
    const ready = buildOntologyEntityDetail(ontologyFixture, "asset_line_1");
    render(<EntityDetailContent detail={ready!} />);

    expect(screen.queryByRole("region", { name: /Why this/ })).toBeNull();
  });

  it("names relationships and related records by display name, not raw ids", () => {
    render(
      <EntityDetailContent
        detail={lineTwoDetail({ related_workflows: ["org_fixture_plant", "wf_unknown_flow"] })}
      />,
    );

    // Relationship rows read as direction, relation and peer name.
    expect(screen.getByText(/Incoming · Operates · Fixture Plant/)).toHaveAttribute(
      "title",
      "rel_plant_line_2",
    );
    expect(screen.getAllByText("Ontology · read")[0]).toHaveAttribute("title", "ontology:read");
    expect(screen.getAllByText(/Owner: Quality owner · Verified/).length).toBeGreaterThan(0);
    // Related ids resolve to labels; an id the detail cannot name is humanized.
    expect(screen.getAllByRole("link", { name: "Fixture Plant" }).length).toBeGreaterThan(0);
    expect(screen.getByText("Unknown flow")).toHaveAttribute("title", "wf_unknown_flow");
    expect(screen.queryByText("wf_unknown_flow")).toBeNull();
    expect(screen.queryByText("rel_plant_line_2")).toBeNull();
  });

  it("renders Type and Domain at metadata size instead of display size", () => {
    render(<EntityDetailContent detail={lineTwoDetail()} />);

    const facts = document.querySelector("[data-entity-facts]") as HTMLElement;
    const type = within(facts).getByText("Asset");
    const domain = within(facts).getByText("Quality");
    for (const value of [type, domain]) {
      expect(value.tagName).toBe("DD");
      expect(value).not.toHaveClass("font-display");
      expect(value.className).not.toMatch(/text-2xl/);
    }
    expect(within(facts).getByText("asset_line_2")).toHaveClass("font-mono", "text-xs");
  });
});
