import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type {
  IdentitySessionReadModel,
  ManufacturingNotificationCenter,
  ManufacturingPlatformNotification,
} from "@/lib/platform-overview";

const mocks = vi.hoisted(() => ({
  axisFetchParsedJson: vi.fn(),
}));

vi.mock("@/lib/axis-api", () => ({
  axisFetchParsedJson: mocks.axisFetchParsedJson,
}));

import { NotificationPanel } from "./notification-panel";

const identitySession: IdentitySessionReadModel = {
  authenticated: true,
  mode: "oidc",
  actor_id: "operator_acme",
  tenant_id: "tenant_acme",
  scopes: ["notifications:acknowledge"],
  expires_at: null,
  api_auth_required: true,
  enterprise_sso_ready: true,
  readiness_status: "ready",
  issuer: "",
  audience: "",
  jwks_source: "disabled",
  session_boundary: "secure_oidc_cookie",
  capabilities: [],
  limitations: [],
  notes: [],
};

function notification(
  overrides: Partial<ManufacturingPlatformNotification> & { notification_id: string },
): ManufacturingPlatformNotification {
  return {
    category: "risk",
    severity: "watch",
    title: overrides.notification_id,
    detail: "Fixture notification detail.",
    source: "fixture",
    route: "/overview",
    occurred_at: "2026-07-24T09:00:00Z",
    owner_role: null,
    related_workflow_id: null,
    related_approval_id: null,
    evidence_refs: [],
    action_label: "Open",
    read_state: "unread",
    acknowledged_by: null,
    acknowledged_at: null,
    acknowledgement_reason: null,
    ...overrides,
  };
}

const center: ManufacturingNotificationCenter = {
  tenant_id: "tenant_acme",
  plant_name: "Fixture Plant",
  scenario: "Fixture scenario",
  as_of: "2026-07-24T09:00:00Z",
  unread_count: 2,
  action_required_count: 0,
  watch_count: 2,
  notifications: [
    notification({ notification_id: "notif_slow" }),
    notification({ notification_id: "notif_fast" }),
  ],
  generation_boundary: "boundary-1",
  notes: [],
};

/** A deferred promise so the test can control exactly when a fetch resolves. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  mocks.axisFetchParsedJson.mockReset();
});

describe("NotificationPanel acknowledgement", () => {
  it("does not clear the pending flag for a still in-flight item when a later ack completes first", async () => {
    const user = userEvent.setup();
    const slow = deferred<unknown>();
    const fast = deferred<unknown>();
    mocks.axisFetchParsedJson.mockReturnValueOnce(slow.promise);
    mocks.axisFetchParsedJson.mockReturnValueOnce(fast.promise);

    render(
      <NotificationPanel
        center={center}
        identitySession={identitySession}
        onAcknowledged={vi.fn()}
        session={null}
      />,
    );

    const slowRow = screen.getByLabelText(/notif_slow/);
    const fastRow = screen.getByLabelText(/notif_fast/);
    const slowButton = within(slowRow).getByRole("button");
    const fastButton = within(fastRow).getByRole("button");

    await user.click(slowButton);
    expect(slowButton).toHaveTextContent("Saving");
    expect(slowButton).toBeDisabled();

    await user.click(fastButton);
    expect(fastButton).toHaveTextContent("Saving");
    expect(fastButton).toBeDisabled();

    // The fast request completes first. Acknowledging it must not clear the
    // pending flag for the still in-flight slow request and re-enable its
    // button for a double submit.
    fast.resolve({});
    await waitFor(() => expect(fastButton).not.toBeDisabled());
    expect(slowButton).toHaveTextContent("Saving");
    expect(slowButton).toBeDisabled();

    slow.resolve({});
    await waitFor(() => expect(slowButton).not.toBeDisabled());
  });

  it("announces an acknowledgement failure with role=alert", async () => {
    const user = userEvent.setup();
    mocks.axisFetchParsedJson.mockRejectedValueOnce(new Error("network down"));

    render(
      <NotificationPanel
        center={center}
        identitySession={identitySession}
        onAcknowledged={vi.fn()}
        session={null}
      />,
    );

    const slowRow = screen.getByLabelText(/notif_slow/);
    await user.click(within(slowRow).getByRole("button"));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Axis could not persist the acknowledgement.",
    );
  });
});
