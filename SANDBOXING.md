# Sandbox Model and Limitations

This document describes how Steward sandboxes tool execution today, the known limitations, and operational recommendations. It applies to the current tool set (code execution is limited to `run_js`).

## Overview

- Isolation uses a per-invocation subprocess that hosts a QuickJS context. There is **no stronger OS sandbox** (no namespaces, no seccomp, no container boundary), but the worker process is terminated on timeout.
- Two main controls are used: wall-clock timeout via process termination and minimal API surface. Memory is not capped.

## QuickJS (`run_js`)

- **Runtime**: Each call spins up a new subprocess and QuickJS context; both die at the end of the call.
- **Timeouts**: `timeoutMs` (default `STEWARD_JS_TIMEOUT_MS`) governs the worker lifespan; on expiry the process is terminated. There is no in-VM interrupt handler; tight loops run until the process is killed.
- **Host surface**: Only `console.log/warn/error` and a `SANDBOX_ROOT` string are injected. No `process`, `require`, `fs`, or timers. All state is confined to the context lifetime.
- **Loading from file**: The tool can load JS from a `path` argument, but the file must be inside the current workspace (enforced via `ensure_inside_workspace`). This is read-only and does not expose an FS API to the sandboxed code.
- **Network**: Disabled by default. If `allowNetwork` is true, a minimal `fetch` shim is added that calls Python `requests.get` with a 5s timeout. Responses are returned as text; there is no URL allow/deny list or response size cap beyond the overall output truncation (`STEWARD_JS_MAX_OUTPUT_BYTES`).
- **Filesystem**: No host FS access is exposed. `SANDBOX_ROOT` is informational only and not enforced.
- **Async**: The shimmed `fetch` is async in signature but uses a blocking host call; there is no job-drain loop beyond the process lifetime.

### QuickJS Limitations & Risks

- **Process co-residency**: The worker is a subprocess, but memory is unbounded and can DoS the host until killed on timeout.
- **Network trust**: When `allowNetwork` is true, outbound HTTP(S) uses host `requests`; no filtering, rate limits, or response size caps beyond output truncation.
- **No module sandbox**: There is no module loader; globals can still be mutated freely.
- **No resource accounting**: No CPU or memory quotas other than the wall-clock timeout.
- **Side-channel/host reachability**: If future globals are injected, JS could reach them; keep the surface minimal.

## Operational Guidance

- Keep `allowNetwork` off unless required; when on, assume untrusted code can reach the internet.
- Set strict `timeoutMs` per call; prefer small defaults for untrusted inputs.
- Run Steward inside an OS/container sandbox (namespaces, cgroups, seccomp, or VM) to reduce DoS/blast radius.
- Treat tool output as untrusted; do not render it as HTML without sanitization.

## Gaps / Future Hardening

- Add real filesystem policies (e.g., an in-memory FS with optional seeding, and explicit denies for path escapes).
- Add memory limits or watchdogs for QuickJS runtimes (currently none).
- Consider per-request process isolation (worker subprocess) for stronger blast-radius reduction.
- Optionally remove the network bridge entirely, or proxy it with allow/deny lists and response size caps.
