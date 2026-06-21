# Contributing to Limes Axis

Limes Axis is early. The first public work is design, architecture and platform
foundation. Contributions should improve clarity, architecture, tests,
documentation or implementation without weakening the core principles.

## Principles

- Keep the open core self-hostable.
- Avoid required managed-service dependencies.
- Treat security, tenant isolation, permissions and audit as product features.
- Prefer typed schemas and explicit interfaces over implicit coupling.
- Keep public documentation public-safe.
- Do not add application code without tests and documented acceptance criteria.

## Contributor License Agreement

Limes Axis intends to require a Contributor License Agreement before accepting
substantial external contributions.

See [`CLA.md`](./CLA.md).

The CLA process is lightweight at repository launch and should receive legal
review before broad external contribution intake.

## Development Status

Application code has not been added yet. When it is added, contributions should
follow the documented development commands, test suite and review policy.

## Pull Request Expectations

Once code contributions begin:

- open a pull request against `main`;
- describe the change and why it matters;
- include tests for behavior changes;
- update docs when public behavior changes;
- keep changes scoped;
- avoid unrelated refactors;
- include security implications for auth, permissions, tenant isolation, agents,
  workflows, connectors, model routing or data egress changes.

## Reporting Security Issues

Do not open a public issue for sensitive vulnerabilities. A dedicated security
contact/process will be added before production use.

