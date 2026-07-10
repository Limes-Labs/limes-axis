import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ToastProvider } from "@/components/ui/toast";
import type { ApprovalInboxItem } from "@/lib/approval-demo";

const mocks = vi.hoisted(() => ({
  axisFetchJson: vi.fn(),
}));

vi.mock("@/lib/axis-api", () => ({
  axisFetchJson: mocks.axisFetchJson,
}));

vi.mock("@/lib/use-oidc-session", () => ({
  useOidcConsoleSession: () => ({ session: null }),
}));

import {
  ApprovalDecisionCard,
  useApprovalDecisionState,
} from "./approval-decision-card";

const approvalFixture: ApprovalInboxItem = {
  approval_id: "appr_supply_fixture",
  action: "Expedite fixture batch",
  risk_level: "high",
  status: "pending",
  requested_by: "agent_supply_fixture",
  owner_role: "plant-operations-owner",
  due: "Today 17:30",
  workflow_id: "wf_supply_fixture",
  domain: "Supply",
  summary: "Approve or reject a governed supply action.",
  evidence: ["risk_supply_fixture"],
  data_accessed: ["Supplier status"],
  risks: ["External shipment mutation"],
  alternatives: ["Adjust production schedule"],
  estimated_cost: "EUR 120",
  model_policy: "no-external-egress",
  required_permission: "approvals:supply:decide",
  audit_event_preview: {
    event: "approval.decision.recorded",
    actor_role: "plant-operations-owner",
    scope: "wf_supply_fixture",
    result: "pending",
  },
  decision_options: [
    {
      decision: "approve",
      label: "Approve & execute",
      consequence: "The expedite order is dispatched to the supplier.",
    },
    {
      decision: "reject",
      label: "Reject",
      consequence: "The current production plan stays unchanged.",
    },
  ],
};

const persistenceResultFixture = {
  tenant_id: "tenant_fixture",
  approval_id: "appr_supply_fixture",
  workflow_id: "wf_supply_fixture",
  action_id: "act_fixture",
  decision: "approve",
  status: "approved",
  actor_id: "plant-operations-owner-role",
  audit_event_id: "11111111-1111-4111-8111-111111111111",
  audit_event_type: "approval.decision.recorded",
  persisted: true,
  permission_decision: { allowed: true, reason: "required_scope_present" },
  workflow_signal: {
    workflow_id: "wf_supply_fixture",
    status: "signaled",
    adapter: "memory",
    signal_name: "approval_decision",
    payload: { approval_id: "appr_supply_fixture", approved: true },
  },
  workflow_signal_status: "signaled",
};

function Harness({ approval = approvalFixture }: { approval?: ApprovalInboxItem }) {
  const { decisions, errors, setDecision, setError } = useApprovalDecisionState();

  return (
    <ToastProvider>
      <ApprovalDecisionCard
        approval={approval}
        decision={decisions[approval.approval_id]}
        error={errors[approval.approval_id]}
        onDecisionChange={setDecision}
        onErrorChange={setError}
      />
    </ToastProvider>
  );
}

beforeEach(() => {
  mocks.axisFetchJson.mockReset();
});

describe("ApprovalDecisionCard", () => {
  it("shows every option's consequence text without hover", () => {
    render(<Harness />);

    expect(
      screen.getByText("The expedite order is dispatched to the supplier."),
    ).toBeVisible();
    expect(screen.getByText("The current production plan stays unchanged.")).toBeVisible();
  });

  it("does not persist until the confirm dialog is confirmed", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /Approve & execute/ }));

    // The dialog restates the option and its consequence.
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Approve & execute");
    expect(dialog).toHaveTextContent("The expedite order is dispatched to the supplier.");
    expect(mocks.axisFetchJson).not.toHaveBeenCalled();

    // Cancelling also never calls the API.
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mocks.axisFetchJson).not.toHaveBeenCalled();
  });

  it("persists through the decision endpoint with the rationale note on confirm", async () => {
    const user = userEvent.setup();
    mocks.axisFetchJson.mockResolvedValue(persistenceResultFixture);
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /Approve & execute/ }));
    await user.type(
      await screen.findByLabelText("Rationale (optional)"),
      "Supplier confirmed the slot.",
    );
    await user.click(screen.getByRole("button", { name: "Confirm decision" }));

    await waitFor(() => {
      expect(mocks.axisFetchJson).toHaveBeenCalledTimes(1);
    });
    expect(mocks.axisFetchJson).toHaveBeenCalledWith(
      "/demo/manufacturing/approvals/appr_supply_fixture/decision",
      expect.objectContaining({
        method: "POST",
        session: null,
        body: {
          decision: "approve",
          actor_id: "plant-operations-owner-role",
          actor_scopes: ["approvals:supply:decide"],
          note: "Supplier confirmed the slot.",
        },
      }),
    );
  });

  it("renders the audit-event link and a toast after a persisted decision", async () => {
    const user = userEvent.setup();
    mocks.axisFetchJson.mockResolvedValue(persistenceResultFixture);
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /Approve & execute/ }));
    await user.click(await screen.findByRole("button", { name: "Confirm decision" }));

    // Inline confirmation and the success toast both deep-link to the audit
    // event id returned by the decision API.
    const auditLinks = await screen.findAllByRole("link", { name: "View audit event" });
    expect(auditLinks).toHaveLength(2);
    for (const link of auditLinks) {
      expect(link).toHaveAttribute(
        "href",
        "/audit?event_id=11111111-1111-4111-8111-111111111111",
      );
    }
    expect(screen.getByText("Decision recorded")).toBeInTheDocument();

    // Option buttons are replaced by the recorded state.
    expect(screen.queryByRole("button", { name: /Approve & execute/ })).not.toBeInTheDocument();
  });

  it("surfaces persistence failures and keeps the options available", async () => {
    const user = userEvent.setup();
    mocks.axisFetchJson.mockRejectedValue(new Error("Axis API request failed with 503"));
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: /Approve & execute/ }));
    await user.click(await screen.findByRole("button", { name: "Confirm decision" }));

    expect(
      await screen.findByText(/Axis API request failed with 503/),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Approve & execute/ })).toBeEnabled();
  });
});
