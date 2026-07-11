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
  ontology,
  overview,
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
