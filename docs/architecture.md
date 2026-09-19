# Architecture

## Boundaries

The service keeps shallow modules under `src/` while preserving four logical boundaries:

1. `api`: versioned HTTP transport, authentication and request validation.
2. `application`: metadata-resolution use cases and bounded-loop orchestration.
3. `domain`: provider-neutral identities, candidates, evidence and decisions.
4. `infrastructure`: Douban and OpenAI-compatible adapters, persistence and telemetry.

Dependencies point inward even though the filesystem is intentionally flat. Matching and resolver
policy must not depend on FastAPI, OpenAI or provider-specific response classes.

## Resolution policy

Deterministic normalization and matching remain the primary path. The model is an optional rescue
path for empty or ambiguous searches. It may propose queries and rank verified candidates, but it
must never invent or persist an external identifier that was not returned by a provider adapter.

The resolver loop is bounded by rounds, tool calls and timeout. A timeout, missing key or provider
failure produces a structured fallback response instead of making the client feature unavailable.

## Client compatibility

The Android client keeps its local Douban implementation until the remote API has been deployed and
validated. Remote resolution is feature-configured; transport failure falls back to the local path.
