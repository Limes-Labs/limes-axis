# Platform Settings

The Settings console exposes operational readiness posture from Axis API
contracts. It is intended for local demos, design-partner walkthroughs and
enterprise evaluation reviews where operators need to see what is ready, what
is demo-safe and what remains production hardening work.

The page does not carry browser-local settings records. If the API is
unavailable, the console renders an API-required empty state.

## API Sources

The console reads:

- `GET /ready` for API dependency and model-egress posture.
- `GET /identity/oidc/readiness` for enterprise SSO readiness checks.
- `GET /identity/session` for the API-validated actor/session boundary, whether
  the actor arrived through a bearer token or a non-revoked HTTP-only OIDC
  session cookie.
- `GET /deployment/readiness` for production blockers and deployment profile.
- `GET /support/diagnostics` for public-safe support diagnostics and redaction
  policy.

## Operator View

The Settings console shows:

- API readiness and runtime dependency reachability.
- OIDC issuer, audience, auth requirement, token binding claims,
  `openid` scope posture, authorization-code readiness, ID-token
  nonce/subject binding, federated logout readiness, session-cookie hardening
  and revocation posture.
- Deployment profile, demo-safety, production blockers and object-store
  adapter, WORM retention mode and retention-day posture.
- Support diagnostics, support blockers, redaction policy and support
  artifacts.

## Session Security View

`/settings/sessions` is the console session management surface for the
API-owned OIDC browser session lifecycle. It reads `GET /identity/session` for
the verified operator identity and `GET /identity/sessions` for the actor's
persisted browser sessions, rendered as opaque session references with status,
creation, last-seen, expiry, refresh-count and revocation metadata. The API
additionally returns per-session device metadata (a bounded user agent, the
client IP resolved under the deployment's trusted-proxy setting and a derived
device label such as "Safari on macOS") and cursor pagination fields
(`page_size`/`cursor` parameters, `has_more`/`next_cursor` in the response);
the console still renders the first page and can adopt the device labels and
pagination incrementally without a contract change. Non-current
sessions can be revoked through
`POST /identity/sessions/{session_ref}/revoke`; revoking the current session is
treated as logout and navigates to `GET /identity/oidc/logout`. A tenant-wide
listing toggle appears only when the identity read model exposes the
`identity:sessions:admin` scope, and the API still enforces that scope
server-side. The view keeps the console conventions: an API-required state when
the identity APIs are unreachable, a signed-out state with the SSO entrypoint
when no operator is authenticated, and no browser-local session records.
Cookie-session mutations from this view (and every other console mutation)
attach the `X-Axis-Csrf-Token` double-submit header from the shared request
layer; see the deployment guide's OIDC section for the full console
CSRF-and-refresh behavior.

## Object Storage Readiness

Governed connector evidence exports can use either the local filesystem adapter
for local demos or an S3-compatible adapter for production-style evaluation.
The deployment readiness report marks the object-store gate ready only when the
S3-compatible adapter has endpoint, bucket, access credentials, secure
transport, object lock and a positive retention period configured.

The Settings console and support diagnostics deliberately expose only public
posture fields such as adapter, retention mode and retention days. They never
return S3 access keys, secret keys or audit signing material.

## Boundary

This is a readiness and evaluation surface, not a production certification.
The current reports deliberately keep Enterprise blockers visible, including
refresh-token rotation, production SSO operations, production support model,
production backup/restore, KMS-backed signing, legal operations and external
security review.

## Verification

Coverage includes:

- unit tests for settings status helpers;
- unit tests for the CSRF header attach, single-retry session refresh and
  session list/revoke bindings;
- Playwright smoke coverage for the `/settings` API-required state;
- Playwright smoke coverage for the `/settings/sessions` API-required state and
  the mocked session listing, CSRF-protected revocation and tenant-wide toggle;
- sidebar navigation coverage so Settings remains reachable on short desktop
  viewports;
- live demo checks through the existing readiness and diagnostics endpoints.
