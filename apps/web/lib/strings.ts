/*
 * Centralized console copy — every new user-facing string lives here so pages
 * stay plain-first and copy stays consistent (and i18n-ready). Raw identifiers,
 * scopes and hashes never appear in this module: they belong in Inspect
 * drawers and secondary mono details.
 */

export interface GlossaryEntry {
  label: string;
  definition: string;
}

/** Plain-English definitions for platform terms, rendered by `<Term />` tooltips. */
export const glossary = {
  ontology: {
    label: "Ontology",
    definition:
      "The shared vocabulary of business objects — machines, orders, materials — that connects your data, agents, and policies. It keeps every system talking about the same things.",
  },
  autonomy_level: {
    label: "Autonomy level",
    definition:
      "How much an agent may do on its own. Lower levels only suggest actions for humans to carry out; higher levels can act directly, with policies and approvals still applying.",
  },
  egress: {
    label: "Egress",
    definition:
      "Data leaving the platform for an outside system or provider. Egress is blocked by default and only opens through an explicit policy.",
  },
  evidence: {
    label: "Evidence",
    definition:
      "The recorded proof behind a decision or action: who acted, what they saw, and which rules applied. Evidence is written to the audit ledger and cannot be edited afterwards.",
  },
  dry_run: {
    label: "Dry run",
    definition:
      "A rehearsal of an action that computes the outcome without changing anything. Use it to check what would happen before committing.",
  },
  replay: {
    label: "Replay",
    definition:
      "Re-running past decisions against a different set of policies to compare outcomes. Nothing in production changes during a replay.",
  },
  idempotency: {
    label: "Idempotency",
    definition:
      "A guarantee that repeating the same request has no additional effect. It makes retries safe after a timeout or network failure.",
  },
  connector_manifest: {
    label: "Connector manifest",
    definition:
      "The reviewed description of a connector: where its data comes from, how fields map to the ontology, and which rules govern each sync.",
  },
  policy_scope: {
    label: "Policy scope",
    definition:
      "The part of the platform a policy applies to — an entire tenant, a domain, or a specific type of action.",
  },
} satisfies Record<string, GlossaryEntry>;

export type GlossaryKey = keyof typeof glossary;

export interface PageStrings {
  eyebrow: string;
  title: string;
  description: string;
}

const nav = {
  operate: "Operate",
  dataAndModels: "Data & Models",
  governance: "Governance",
  platform: "Platform",
} as const;

/** Per-route header copy, keyed by route segment (`overview` for `/`). */
const pages = {
  overview: {
    eyebrow: nav.operate,
    title: "Overview",
    description:
      "See what needs your attention right now across approvals, workflows, and platform health.",
  },
  approvals: {
    eyebrow: nav.operate,
    title: "Approvals",
    description:
      "Review and decide on actions agents have proposed. Every decision is recorded as audit evidence.",
  },
  workflows: {
    eyebrow: nav.operate,
    title: "Workflows",
    description:
      "Follow governed workflow runs from start to finish and see exactly what is blocking them.",
  },
  agents: {
    eyebrow: nav.operate,
    title: "Agents",
    description:
      "See every registered agent, what it is allowed to do, and how its recent runs went.",
  },
  ontology: {
    eyebrow: nav.dataAndModels,
    title: "Ontology",
    description:
      "Browse the shared business vocabulary that connects your data, agents, and policies.",
  },
  connectors: {
    eyebrow: nav.dataAndModels,
    title: "Connectors",
    description:
      "Bring data in from files and external systems, with every sync governed and recorded.",
  },
  "model-routing": {
    eyebrow: nav.dataAndModels,
    title: "Models",
    description:
      "See which AI models the platform routes work to, and the calls it has actually made.",
  },
  policies: {
    eyebrow: nav.governance,
    title: "Policies",
    description:
      "Write and version the rules that decide what agents may do and when a human steps in.",
  },
  audit: {
    eyebrow: nav.governance,
    title: "Audit",
    description:
      "Search the tamper-evident record of everything that has happened on the platform.",
  },
  simulation: {
    eyebrow: nav.governance,
    title: "Simulation",
    description:
      "Replay past decisions against different policies to see what would change before you commit.",
  },
  tenants: {
    eyebrow: nav.platform,
    title: "Tenants",
    description:
      "Manage the organizations on this deployment and the resources each one can use.",
  },
  settings: {
    eyebrow: nav.platform,
    title: "Settings",
    description: "Check that the platform is healthy, connected, and ready for your team.",
  },
} satisfies Record<string, PageStrings>;

export type PageKey = keyof typeof pages;

const commandMenu = {
  placeholder: "Search pages, entities, actions",
  empty: "No matching command.",
  apiStatus: "API status",
  actionsHeading: "Actions",
  entitiesHeading: "Entities",
  refresh: {
    label: "Refresh live state",
    detail: "Re-fetch every API-backed console.",
  },
  toggleTheme: {
    label: "Toggle color theme",
    detail: "Switch between light and dark.",
  },
  docs: {
    label: "Open product docs",
    detail: "Architecture, platform and acceptance documentation.",
    href: "https://github.com/Limes-Labs/limes-axis/tree/main/docs",
  },
} as const;

/** Approval inbox copy: decision flow, empty queue, and API-down states. */
const approvals = {
  queue: {
    eyebrow: "Queue",
    title: "Approval inbox",
  },
  decision: {
    eyebrow: "Decision",
    pending: "Pending review",
    confirmTitle: "Confirm decision",
    rationaleLabel: "Rationale (optional)",
    rationalePlaceholder: "Why you are deciding this way — recorded with the audit evidence.",
    confirm: "Confirm decision",
    cancel: "Cancel",
    persisting: "Recording decision…",
    persisted: "Recorded as evidence",
    auditLink: "View audit event",
    toastTitle: "Decision recorded",
  },
  sections: {
    evidence: "Evidence",
    risksAlternatives: "Risks & alternatives",
    dataAccessed: "Data accessed",
    inspect: "Inspect raw record",
  },
  metrics: {
    pending: "Pending",
    pendingDetail: "Waiting on a human decision",
    highRisk: "High risk",
    highRiskDetail: "Cannot execute without owner approval",
    decided: "Decided",
    decidedDetail: "Recorded as audit evidence this session",
  },
  error: {
    title: "Approval API unavailable",
    detail:
      "Axis did not receive API-backed approval records. Local fallback approval records are disabled.",
  },
  empty: {
    title: "No approvals waiting",
    detail:
      "When an agent proposes an action that needs a human decision, it will appear here for review.",
  },
} as const;

/** Agent registry copy: list, detail tabs, runs, and state panels. */
const agents = {
  list: {
    eyebrow: "Registry",
    title: "Agents",
  },
  tabs: {
    overview: "Overview",
    permissions: "Permissions & Guardrails",
    runs: "Runs",
    evidence: "Evidence",
  },
  overview: {
    owner: "Owner",
    boundary: "Operating boundary",
    modelPolicy: "Model policy",
    connectedSystems: "Connected systems",
    dataAccess: "Data access",
  },
  permissions: {
    required: "Required permissions",
    guardrails: "Guardrails",
    allowed: "Allowed actions",
    blocked: "Blocked actions",
  },
  evidence: {
    proposals: "Action proposals",
    proposalsDetail: "Read-only proposals recorded by this agent; execution needs approval.",
    workflows: "Workflow links",
    approvals: "Approval references",
    audit: "Audit links",
    lastAudit: "Last audit event",
    approvalRequired: "Needs approval",
    noApproval: "No approval needed",
    empty: "No proposals, workflow links, or approval references are recorded for this agent.",
  },
  runs: {
    title: "Live executed runs",
    detail: "Persisted run records; steps, model links and proposals are recorded values.",
    liveBadge: "Live executed",
    dryRun: "Dry run",
    linkedInvocations: "Linked model invocations",
    noInvocations: "No model invocations are linked to this run.",
    openActionRun: "Open proposed action run in approvals",
    noActionRun: "No action run was created by this run.",
    openRunAudit: "Open run audit event",
    openAudit: "Open audit",
    auditPending: "audit pending",
    empty: {
      title: "No runs recorded yet",
      detail:
        "No runs are recorded for this agent. Agent run execution is deferred by default until the execution flag is enabled on the API; run rows are never fabricated.",
    },
    error: {
      title: "Agent runs API unavailable",
      detail:
        "Axis did not receive persisted run records for this agent. Run timelines are never fabricated.",
    },
    detailError: {
      title: "Agent run detail unavailable",
      detail:
        "Axis did not receive the persisted step records for this run. Step timelines are never fabricated.",
    },
  },
  inspect: "Inspect raw record",
  error: {
    title: "Agent API unavailable",
    detail:
      "Axis did not receive API-backed agent records. Local fallback agent records are disabled.",
  },
  empty: {
    title: "No agents registered yet",
    detail:
      "Register an agent through the platform API and it will appear here with its policy boundary and run history.",
  },
  noMatch: {
    title: "No agents match the current filters",
    detail: "Adjust or reset the domain, autonomy and status filters to see registered agents.",
    reset: "Reset filters",
  },
} as const;

/** Workflow console copy: list, blocker banner, timeline, and state panels. */
const workflows = {
  list: {
    eyebrow: "Runs",
  },
  filters: {
    state: "State",
    allStates: "All states",
    domain: "Domain",
    allDomains: "All domains",
  },
  blocker: {
    title: "Waiting on a human decision",
    linkNamed: "Review blocking approval",
    linkGeneric: "Open approvals",
  },
  timeline: {
    eyebrow: "Timeline",
    title: "Runtime timeline",
    waiting: "waiting",
    columns: {
      step: "Step",
      result: "Result",
      when: "When",
      summary: "Summary",
    },
  },
  sections: {
    inputs: "Inputs",
    outputs: "Proposed outputs",
    context: "Related context",
  },
  detail: {
    runtime: "Runtime",
    owner: "Owner",
    autonomy: "Autonomy",
    started: "Started",
    expected: "Expected",
    auditScope: "Audit scope",
    replay: "Replay",
    replayReady: "Ready to replay",
    replayNotReady: "Not replay-ready yet",
    signals: "Pending signals",
    noSignals: "Nothing is waiting on this workflow.",
    controls: "Controls",
  },
  inspect: "Inspect raw record",
  error: {
    title: "Workflow API unavailable",
    detail:
      "Axis did not receive API-backed workflow records. Local fallback workflow records are disabled.",
  },
  empty: {
    title: "No workflow runs yet",
    detail:
      "When a governed workflow starts, its run will appear here with a step-by-step timeline.",
  },
  noMatch: {
    title: "No workflows match the current filters",
    detail: "Adjust or reset the state and domain filters to see workflow runs.",
    reset: "Reset filters",
  },
} as const;

/** Connector console copy: list, detail tabs, wizard, and preview-sync runs. */
const connectors = {
  list: {
    eyebrow: "Registry",
    registeredPill: "Registered",
  },
  header: {
    addConnector: "Add connector",
    updated: "Updated",
  },
  pendingActivation: {
    title: "Sync activation pending",
    detail:
      "This connector was just registered. Its data previews and governed sync runs become available once the platform activates the manifest.",
  },
  metrics: {
    connectors: { label: "Connectors", detail: "Registered data sources" },
    runs: { label: "Runs", detail: "Governed sync runs recorded" },
    pendingProposals: {
      label: "Pending proposals",
      detail: "Ontology proposals awaiting promotion",
    },
    egressPolicies: {
      label: "Egress policies",
      detail: "Approved outbound data boundaries",
    },
    evidenceIssues: {
      label: "Evidence issues",
      detail: "Open audit-evidence findings",
    },
    unavailable: "—",
  },
  tabs: {
    overview: "Overview",
    dataSchema: "Data & Schema",
    runs: "Runs",
    governance: "Governance & Evidence",
  },
  overview: {
    type: "Type",
    version: "Version",
    source: "Source",
    syncModes: "Sync modes",
    boundary: "Runtime boundary",
    credentials: "Credentials",
    payloadPolicy: "Payload policy",
    egressPolicy: "Egress boundary",
    permissions: "Required permissions",
    blocked: "Blocked operations",
    manifest: "Registered manifest",
    manifestMissing: "No manifest registered yet — registering one records audit evidence.",
    manifestRegisteredBy: "Registered by",
  },
  schema: {
    mappingTitle: "Field mapping",
    mappingDetail: "How source columns map to the shared ontology.",
    columns: {
      source: "Source column",
      target: "Target field",
      ontology: "Ontology target",
      type: "Type",
      required: "Required",
    },
    requiredYes: "Required",
    requiredNo: "Optional",
    sampleTitle: "Sample rows",
    sampleDetail: "Reference sample used for preview and validation.",
    sampleEmpty: "No sample rows are recorded for this connector.",
  },
  governance: {
    handles: {
      title: "Credential handles",
      detail: "References to secrets held in the vault — never raw values.",
      empty: "No credential handles are registered for this connector.",
      error: "Credential handle records could not be loaded.",
    },
    leases: {
      title: "Credential leases",
      detail: "Time-boxed grants that let a governed run use a credential handle.",
      empty: "No credential leases are recorded for this connector.",
      error: "Credential lease records could not be loaded.",
    },
    egress: {
      title: "Egress policies",
      detail: "Outbound data boundaries approved for this connector.",
      empty: "No egress policies are recorded for this connector.",
      error: "Egress policy records could not be loaded.",
    },
    invariants: {
      title: "Evidence invariants",
      detail: "Findings where governed records are missing audit evidence.",
      allClear: "All evidence invariants hold — every governed record has audit evidence.",
      error: "Evidence invariant findings could not be loaded.",
    },
  },
  runs: {
    title: "Governed runs",
    detail: "Recorded sync runs for this connector; every stage writes audit evidence.",
    empty: "No runs are recorded for this connector yet.",
    error: "Connector run records could not be loaded.",
    columns: {
      run: "Run",
      status: "Status",
      mode: "Mode",
      when: "When",
      evidence: "Evidence",
    },
    openAudit: "Open audit",
    auditPending: "audit pending",
    validate: {
      action: "Validate",
      running: "Validating…",
      readyTitle: "Validation passed",
      blockedTitle: "Validation found issues",
      rows: "rows checked",
      accepted: "accepted",
      rejected: "rejected",
      columnsChecked: "columns checked",
      error: "The preview endpoint could not validate this connector.",
    },
    sync: {
      action: "Run sync (preview)",
      running: "Running…",
      ssoGate: "Sign in with SSO to run governed syncs.",
      leaseMissing:
        "Preview sync needs an active credential lease for this connector before it can run.",
      manifestMissing:
        "Preview sync needs a registered manifest in the active preview state before it can run.",
      stages: {
        create: {
          title: "Create run record",
          detail: "Records the governed run and its schedule evidence.",
        },
        dispatch: {
          title: "Dispatch sync",
          detail: "Hands the scheduled run to the sync dispatcher.",
        },
        execute: {
          title: "Execute sync",
          detail: "Runs the governed sync within the preview boundary.",
        },
      },
      pending: "Waiting",
      success: "Completed",
      failure: "Failed",
      auditTrail: "Audit evidence",
    },
  },
  wizard: {
    title: "Add connector",
    description: "Register a governed data source. Registration records audit evidence and never starts a live sync.",
    back: "Back",
    next: "Next",
    cancel: "Cancel",
    submit: "Register connector",
    submitting: "Registering…",
    ssoGate: "Sign in with SSO to register connectors.",
    typeStep: {
      title: "What are you connecting?",
      csvTitle: "CSV file",
      csvDetail: "Upload a file, preview its rows, and map columns to the ontology.",
      dbTitle: "External database",
      dbDetail: "Register a read-only database source by connection profile — metadata only.",
    },
    csvStep: {
      template: "Mapping template",
      templateDetail: "Previews validate your file against this connector's field mapping.",
      file: "CSV file",
      preview: "Preview file",
      previewing: "Previewing…",
      noTemplates:
        "No CSV mapping templates are available from the connector registry, so the file cannot be previewed.",
      readyTitle: "Preview ready",
      blockedTitle: "Preview blocked",
      issuesTitle: "Validation issues",
      rows: "rows",
      accepted: "accepted",
      rejected: "rejected",
      entitiesTitle: "Proposed entities",
      previewError: "The CSV preview endpoint is unavailable.",
      fileReadError: "The selected file could not be read.",
    },
    dbStep: {
      profile: "Connection profile",
      profileDetail: "Named, pre-approved profile — never a raw connection string.",
      schema: "Schema",
      table: "Table",
      credentialHandle: "Credential handle",
      template: "Connector template",
      preview: "Preview metadata",
      previewing: "Previewing…",
      noTemplates:
        "No external database connector templates are available from the connector registry.",
      readyTitle: "Metadata preview ready",
      blockedTitle: "Metadata preview blocked",
      columnsTitle: "Mapped columns",
      previewError: "The external database preview endpoint is unavailable.",
    },
    reviewStep: {
      title: "Review and register",
      connectorId: "Connector id",
      displayName: "Display name",
      type: "Type",
      records: "Sample records",
      conflict: "A connector with this id already exists. Choose a different connector id.",
      forbidden: "Your session is not allowed to register connectors for this tenant.",
      validationFailed: "The manifest was rejected by the API.",
      genericError: "The connector manifest could not be registered.",
      toastTitle: "Connector registered",
      toastDetail: "The manifest was recorded with audit evidence.",
    },
  },
  error: {
    title: "Connector API unavailable",
    detail:
      "Axis did not receive API-backed connector records. Local fallback connector records are disabled.",
  },
  empty: {
    title: "No connectors yet",
    detail:
      "Connect a file or an external system and its governed syncs will appear here.",
    action: "Add your first connector",
  },
} as const;

/** Overview control-room copy: hero, needs-attention strip, posture, feed. */
const overview = {
  hero: {
    error: {
      title: "Operations API unavailable",
      detail:
        "Axis did not receive API-backed overview records. Local fallback overview records are disabled.",
    },
  },
  needsAttention: {
    eyebrow: "Needs attention",
    review: "Review & decide",
    openWorkflows: "Open workflows",
    openAudit: "Open audit",
    approvalsUnavailable: "Pending approvals could not be loaded from the approval API.",
    overviewUnavailable: "Workflow and risk signals could not be loaded from the overview API.",
    allClear: {
      title: "All clear — nothing waiting on you",
      detail: "No pending approvals, blocked workflows, or active risk signals right now.",
    },
    error: {
      title: "Attention items unavailable",
      detail:
        "Axis did not receive API-backed approval, workflow, or risk records. Local fallback records are disabled.",
    },
  },
  posture: {
    agents: { label: "Agents", link: "Manage agents" },
    workflows: { label: "Workflows", link: "Open workflows" },
    connectors: { label: "Connectors", link: "Manage connectors" },
    policies: { label: "Policies", link: "Review policies" },
    models: { label: "Models", link: "View routing" },
    unavailable: "Unavailable",
  },
  evidenceFeed: {
    eyebrow: "Evidence feed",
    title: "Recent audit evidence",
    openAudit: "Open audit",
    viewEvent: "View event",
    sparklineCaption: "Recent audit events by category",
    error: {
      title: "Audit evidence API unavailable",
      detail:
        "Axis did not receive API-backed audit events. Local fallback audit records are disabled.",
    },
    empty: {
      title: "No audit evidence yet",
      detail: "Governed actions write append-only evidence that will appear here.",
    },
  },
  sideRail: {
    health: "System health",
    quickActions: "Quick actions",
    error: {
      title: "System health unavailable",
      detail: "Axis did not receive the API-backed records that drive the health radar.",
    },
  },
  artifact: {
    eyebrow: "Operations artifact runtime",
    title: "Generate governed evidence",
    description:
      "Each action calls the live Axis API, persists a tenant-scoped artifact, and writes audit evidence.",
    ssoTitle: "Browser SSO required for artifact generation",
    ssoDetail:
      "Sign in with the API-owned OIDC session before creating daily briefs or risk scenarios.",
    signIn: "Sign in with SSO",
    error: {
      title: "Operations snapshot API unavailable",
      detail:
        "Artifact generation needs the persisted operations snapshot. Local fallback operations records are disabled.",
    },
  },
} as const;

/** Audit explorer copy: plain-first integrity summary and export action. */
const audit = {
  integrity: {
    eyebrow: "Integrity & Export",
    title: "Export bundle",
    download: "Download export bundle",
    inspect: "Inspect raw proofs",
    ledger: {
      verified: "Ledger verified — hash chain intact",
      unverified: "Ledger verification failed — hash chain not confirmed",
      detail: "Every event is hashed and chained; tampering breaks the chain.",
    },
    retention: {
      enforced: "Retention enforced",
      notEnforced: "Retention not enforced for this export",
      legalHold: "Retention paused — legal hold active",
      legalHoldDetail: "Records are excluded from disposal while the legal hold stands.",
    },
    signature: {
      verified: "Ledger signature verified",
      verifiedDetail: "The export manifest and hash chain are signed.",
      notConfigured: "Signature: not configured",
      notConfiguredDetail:
        "The hash-chain proof is present, but no signing key is configured.",
    },
    error: {
      title: "Audit export API unavailable",
      detail:
        "Axis did not receive an API-backed audit export manifest. Local export manifests are disabled.",
    },
  },
  error: {
    title: "Audit API unavailable",
    detail:
      "Axis did not receive API-backed audit records. Local fallback audit records are disabled.",
  },
  noRecords: {
    title: "Audit API returned no records",
    detail: "The audit API responded without ledger records for this tenant.",
  },
} as const;

/** Models page copy: the reference-vs-live distinction and tab labels. */
const models = {
  explainer:
    "Reference routing shows the governed routing design; live invocations are the calls the platform actually executed.",
  tabs: {
    reference: "Reference routing",
    live: "Live invocations",
  },
  reference: {
    error: {
      title: "Routing API unavailable",
      detail:
        "Axis did not receive API-backed model routing records. Local fallback routing records are disabled.",
    },
    noRecords: {
      title: "Routing API returned no records",
      detail: "The model routing API responded without route records for this tenant.",
    },
  },
  live: {
    invocationsError: {
      title: "Model invocation API unavailable",
      detail:
        "Axis did not receive persisted model invocation records. Live invocation rows are never fabricated.",
    },
    endpointsError: {
      title: "Model endpoint API unavailable",
      detail:
        "Axis did not receive the model endpoint registry. Endpoint cards are never fabricated.",
    },
  },
} as const;

/** Policy pages copy: detail tabs and plain-first authoring-scope lines. */
const policyDetail = {
  tabs: {
    conditions: "Conditions",
    revisions: "Revisions",
    evaluate: "Evaluate",
  },
  authorAccess: {
    summary: "You need policy author access to create policies.",
    detail: "Authoring creates revision 1 and records audit evidence.",
  },
  reviseAccess: {
    summary: "You need policy author access to append revisions.",
    detail:
      "Revisions are append-only and safe to retry; the policy scope is fixed at authoring time.",
  },
  error: {
    title: "Policy API unavailable",
    registryDetail:
      "Axis did not receive API-backed platform policy records. Local fallback policy records are disabled.",
    detailDetail:
      "Axis did not receive an API-backed platform policy. Local fallback policy records are disabled.",
  },
} as const;

/** Simulation console copy: run-replay form and baseline-vs-simulated result. */
const simulation = {
  run: {
    eyebrow: "Run replay",
    title: "Compare policy outcomes over recorded history",
    description:
      "Re-run recorded decisions against a policy set and see what would change. Nothing in production changes during a replay.",
    fields: {
      workflow: "Workflow id (optional)",
      workflowPlaceholder: "All recorded workflows",
      limit: "History window (events)",
      retentionDays: "Retention window (days)",
      legalHold: "Apply legal hold",
      baselineSet: "Baseline policy set (optional)",
      candidateSet: "Candidate policy set (optional)",
      connector: "Connector id (optional)",
      comparisonHint:
        "Leave the policy-set fields empty to replay against the recorded policy history.",
    },
    submit: "Run replay",
    running: "Running replay…",
    error: {
      title: "Replay run failed",
      detail: "The replay API rejected this run. Adjust the parameters and try again.",
    },
    result: {
      eyebrow: "Replay result",
      baseline: "Baseline",
      simulated: "Simulated",
      changed: "Changed",
      unchanged: "Unchanged",
      decisionsTitle: "Decision comparison",
      policySetTitle: "Policy-set comparison",
      inspect: "Inspect raw result",
      empty: {
        title: "No decisions to compare",
        detail:
          "The replay window returned no policy decisions. Widen the history window or clear the workflow filter.",
      },
    },
  },
  error: {
    title: "Replay API unavailable",
    detail:
      "Axis did not receive API-backed replay artifacts. Local fallback replay records are disabled.",
  },
  noArtifacts: {
    title: "Replay API returned no artifacts",
    detail: "The replay API responded without simulation artifacts for this tenant.",
  },
} as const;

/** Guided-setup checklist copy for empty and partially onboarded tenants. */
const onboarding = {
  eyebrow: "Guided setup",
  title: "Set up your governed platform",
  description:
    "Five steps take you from an empty tenant to a governed workflow with recorded audit evidence.",
  progressLabel: "Setup progress",
  stepsComplete: "setup steps complete",
  exploreDemo: {
    label: "Explore with demo data",
    comingSoon: "Coming with demo provisioning",
  },
  compact: {
    show: "Show setup steps",
    hide: "Hide setup steps",
  },
  stepDone: "Done",
  steps: {
    connectors: {
      title: "Connect a system",
      why: "Bring governed data in from a file or an external system.",
      cta: "Open connectors",
    },
    ontology: {
      title: "Import ontology entities",
      why: "Give agents and policies a shared vocabulary for your business objects.",
      cta: "Open ontology",
    },
    policies: {
      title: "Define a policy",
      why: "Set the rules that decide what agents may do and when a human steps in.",
      cta: "Open policies",
    },
    agents: {
      title: "Register an agent",
      why: "Register an agent with an explicit autonomy level and permission boundary.",
      cta: "Open agents",
    },
    workflows: {
      title: "Run a governed workflow",
      why: "See a workflow run end to end with evidence recorded at every step.",
      cta: "Open workflows",
    },
  },
} as const;

/**
 * System status (settings) copy: tabs, per-panel state copy, and the
 * plain-English what-to-do line behind every "Action required" pill.
 */
const settingsPanelUnavailable = "Local fallback settings records are disabled.";

const settings = {
  pageTitle: "System status",
  source: {
    live: "Live system status",
    loading: "Loading system status",
    required: "API required",
  },
  tabs: {
    readiness: "Readiness",
    identity: "Identity",
    deployment: "Deployment",
    support: "Support",
  },
  inspect: "Inspect raw report",
  ready: {
    eyebrow: "Runtime dependencies",
    title: "Axis API boundary",
    dependencyReachable: "reachable",
    dependencyNotConfigured: "not configured",
    egressTitle: "External model egress",
    egressDetail:
      "Reported live by the platform API; egress stays blocked unless a policy opens it.",
    error: {
      title: "Readiness API unavailable",
      detail: `Axis did not receive the API readiness report. ${settingsPanelUnavailable}`,
    },
  },
  gates: {
    eyebrow: "Deployment readiness",
    title: "Production gates",
    demoSafe: "Demo safe",
    productionReady: "Production ready",
    blockersTitle: "Production blockers",
    noBlockers: "All production gates are clear.",
  },
  oidc: {
    eyebrow: "Identity and SSO",
    title: "OIDC readiness",
    issuer: "Issuer",
    audience: "Audience",
    authRequired: "Auth required",
    actorClaim: "Actor claim",
    error: {
      title: "Identity readiness API unavailable",
      detail: `Axis did not receive the OIDC readiness report. ${settingsPanelUnavailable}`,
    },
  },
  session: {
    eyebrow: "Browser session",
    title: "Your session",
    actor: "Actor",
    tenant: "Tenant",
    mode: "Mode",
    authenticated: "Authenticated",
    publicActor: "Public evaluation",
    manageSessions: "Manage browser sessions",
    error: {
      title: "Session API unavailable",
      detail: `Axis did not receive the identity session read model. ${settingsPanelUnavailable}`,
    },
  },
  deployment: {
    eyebrow: "Deployment posture",
    environment: "Environment",
    demoSafe: "Demo safe",
    productionReady: "Production ready",
    objectStore: "Object store",
    wormRetention: "WORM retention",
    retentionMode: "Retention mode",
    retentionDays: "Retention days",
    error: {
      title: "Deployment readiness API unavailable",
      detail: `Axis did not receive the deployment readiness report. ${settingsPanelUnavailable}`,
    },
  },
  support: {
    eyebrow: "Support diagnostics",
    title: "Public-safe support bundle",
    safeToShare: "Safe to share",
    demoSupport: "Demo support",
    productionSupport: "Production support",
    objectRetention: "Object retention",
    retentionActionRequired: "Action required",
    error: {
      title: "Support diagnostics API unavailable",
      detail: `Axis did not receive the support diagnostics report. ${settingsPanelUnavailable}`,
    },
  },
  /**
   * One-line plain-English guidance per readiness check id, shown next to
   * every "Action required" pill. The raw API detail stays as secondary mono
   * text. Keys mirror the check ids emitted by the platform API.
   */
  guidance: {
    // OIDC readiness checks (/identity/oidc/readiness)
    auth_required:
      "Turn on required OIDC verification for the API before moving past local demos.",
    https_issuer: "Use an HTTPS issuer URL from your enterprise IdP before production.",
    explicit_jwks_url:
      "Configure the JWKS URL explicitly from your IdP instead of deriving it from the issuer.",
    asymmetric_algorithms:
      "Allow only asymmetric signing algorithms (for example RS256) for token verification.",
    openid_scope:
      "Add the openid scope to the OIDC client configuration so ID tokens can be issued.",
    tenant_claim: "Set the token claim that carries the tenant so sessions bind to the right tenant.",
    actor_claim: "Set the token claim that identifies the acting user.",
    authorization_code_client:
      "Register a browser SSO client with your IdP and configure its client id.",
    authorization_endpoint: "Point the authorization endpoint at an HTTPS URL from your IdP.",
    token_endpoint: "Point the token endpoint at an HTTPS URL from your IdP.",
    end_session_endpoint:
      "Configure an HTTPS end-session endpoint so signing out also ends the IdP session.",
    post_logout_redirect:
      "Set an HTTPS post-logout redirect so sign-out returns people to the console.",
    session_cookie_signing:
      "Provide an operator-managed signing secret for browser session cookies.",
    secure_session_cookie:
      "Enable the Secure attribute so session cookies only travel over HTTPS.",
    host_prefixed_session_cookie:
      "Enable Secure cookies with the __Host- prefix so sessions bind to this host.",
    refresh_credential_encryption:
      "Provide a refresh-credential encryption key of at least 32 characters.",
    session_idle_timeout: "Set an idle timeout above zero so unattended sessions expire.",
    session_absolute_timeout:
      "Set an absolute session lifetime above zero so sessions always expire.",
    // Deployment readiness checks (/deployment/readiness)
    oidc_enterprise_sso:
      "Resolve the identity checks on the Identity tab to make SSO enterprise-ready.",
    oidc_secure_cookie_session:
      "Serve the API and console over HTTPS with Secure, signed, time-boxed session cookies.",
    external_model_egress_disabled:
      "Keep external model egress off, or govern it with tenant policy and audit controls.",
    api_rate_limiting:
      "Enable API rate limiting before exposing the platform to production traffic.",
    network_egress_restricted:
      "Restrict outbound network traffic with a network policy and an explicit allowlist.",
    deployment_tenancy_profile:
      "Declare the tenancy mode plus isolation, data-residency, and operator-access evidence.",
    live_connector_execution_disabled:
      "Keep live connector execution off until provider policies and runbooks are in place.",
    ontology_graph_mutation_posture:
      "Configure a TypeDB address and enable ontology reads before promoting graph nodes.",
    audit_ledger_signing_configured:
      "Configure an audit ledger signing key so evidence exports are signed.",
    production_object_store_adapter:
      "Configure S3-compatible object storage with credentials, TLS, and WORM retention.",
    observability_instrumentation:
      "Enable OpenTelemetry and point the exporter at your collector to emit traces.",
    production_dr_procedures:
      "Document backup and disaster-recovery runbooks with RPO/RTO targets and rehearsal evidence.",
    // Support diagnostics checks (/support/diagnostics)
    demo_support_ready:
      "Resolve the deployment posture issues so a demo walkthrough is safe to run.",
    production_support_model:
      "Define a 24x7 support model with response targets, escalation paths, and a status page.",
    production_support_commitments:
      "Put signed support commitments, a staffing model, and legal SLA terms in place.",
    support_slo_targets: "Set S1-S4 response targets ordered from shortest to longest.",
    support_escalation_channels:
      "Configure at least two escalation channel classes for production support.",
  } satisfies Record<string, string>,
  guidanceFallback: "Review the technical detail below and update the platform configuration.",
} as const;

const ontology = {
  legend: {
    label: "Ontology graph legend",
    entity: "Entity",
    selected: "Selected",
    relation: "Relation",
    hint: "Click or press Enter on a node to open its entity detail",
  },
  graph: {
    controlsLabel: "Ontology graph controls",
    zoomIn: "Zoom in",
    zoomOut: "Zoom out",
    resetView: "Reset view",
  },
  sheet: {
    eyebrow: "Ontology entity",
    openFullPage: "Open full page",
    error: {
      title: "Entity API unavailable",
      detail:
        "Axis did not receive an API-backed ontology entity. Local fallback entity records are disabled.",
    },
    notFound: {
      title: "Entity not found",
      detail:
        "No ontology entity exists with this id. It may have been renamed or removed from the graph.",
    },
  },
} as const;

export const strings = {
  nav,
  commandMenu,
  agents,
  approvals,
  audit,
  connectors,
  models,
  onboarding,
  ontology,
  overview,
  policyDetail,
  settings,
  simulation,
  workflows,
  states: {
    loading: "Loading…",
    error: {
      title: "This data could not be loaded",
      detail: "The console could not reach the platform API. Check your connection and try again.",
      retry: "Try again",
    },
    empty: {
      title: "Nothing here yet",
      detail: "Records will appear here as soon as they exist.",
    },
  },
  pages,
} as const;
