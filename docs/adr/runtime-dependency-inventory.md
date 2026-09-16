# ADR: Static runtime dependency inventory

Status: Proposed, unmerged. The complete-checkout inventory guard and 112 targeted
regression tests pass; full repository verification and PR CI remain pending.
Related issue: #869. Parent workstream: #473.

## Context

Settings and deployment flags describe intended configuration. They do not by
themselves show whether every dependency is local or whether an application has
made external network requests. Duplicating configuration declarations in an
inventory would create competing defaults and long-term drift.

## Decision

Keep runtime configuration and trust decisions in their current owners. Add a
versioned descriptive dependency manifest, a bundled JSON Schema, a logical
local-only capability plan and a generated human-readable matrix.

The offline checker discovers references from source without importing the
application. Every detected endpoint-related setting needs one inventory owner;
metadata references are identified as metadata rather than granted dial authority.
Profile omissions require reasons. Required services, bundled assets and preloaded
artifacts have distinct dispositions.

Use a conservative, explicit review baseline for Compose and Helm topology.
Changes to known files, or addition/removal of topology files in the documented
scope, invalidate the baseline. Do not implement a partial YAML/Go-template parser
and do not rely on an undeclared transitive YAML dependency. Matrix generation
cannot automatically update baseline digests.

## Ownership and integration

The inventory lives in documentation. Its script and contract tests are offline
development tooling. The API test suite runs the complete-checkout guard using
its existing `jsonschema` development dependency. Runtime packages do not import
the checker. No settings, feature flags, permissions, provider fallbacks, network
rules or deployment resources change.

## Consequences and limits

This avoids a second configuration loader and an unversioned parallel Markdown
table. Changes to endpoint declarations become visible during normal API testing.
Topology baselines are coarse: unrelated formatting changes also require review.
That cost is explicit and preferable here to a parser that silently misses a Helm
or Compose construct. A later semantic extractor may replace the fingerprint gate
only with equivalent failure coverage and a supported parser dependency.

The current source scanner is intentionally bounded and conservative. Dynamic
endpoint construction, arbitrary nested settings, third-party behavior, customer
overrides and runtime network traffic remain outside its proof. Source digests
are revision evidence, not signatures or proof that every line has been reviewed.
The sample plan is not a deployable production configuration.

## Verification required before acceptance

The candidate's schema, synthetic regression tests and source parsing checks do
not replace a complete checkout, locked installation, full inventory reconciliation,
repository checks or CI on the actual PR head. Do not close issue #869 or mark this
ADR accepted until those checks and its acceptance criteria are satisfied.
