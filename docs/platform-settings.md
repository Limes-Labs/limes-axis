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
- `GET /identity/session` for the API-validated actor/session boundary.
- `GET /deployment/readiness` for production blockers and deployment profile.
- `GET /support/diagnostics` for public-safe support diagnostics and redaction
  policy.

## Operator View

The Settings console shows:

- API readiness and runtime dependency reachability.
- OIDC issuer, audience, auth requirement and token binding claims.
- Deployment profile, demo-safety, production blockers and object-store
  adapter posture.
- Support diagnostics, support blockers, redaction policy and support
  artifacts.

## Boundary

This is a readiness and evaluation surface, not a production certification.
The current reports deliberately keep Enterprise blockers visible, including
enterprise SSO hardening, production support model, production backup/restore,
WORM object storage and external security review.

## Verification

Coverage includes:

- unit tests for settings status helpers;
- Playwright smoke coverage for the `/settings` API-required state;
- sidebar navigation coverage so Settings remains reachable on short desktop
  viewports;
- live demo checks through the existing readiness and diagnostics endpoints.
