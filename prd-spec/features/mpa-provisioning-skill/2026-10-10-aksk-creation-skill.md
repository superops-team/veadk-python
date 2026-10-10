# AK/SK-backed MPA creation Skill

- Change ID: `mpa-provisioning-skill`; date: 2026-10-10; status: implemented.
- [Chinese](2026-10-10-aksk-creation-skill.zh.md).
- Contract: [MPA provisioning Skill](../../../specs/mpa-provisioning-skill/README.md).

## Background and scope
Studio already calls the managed provisioning service through `CreationTasks` and its child runner. The legacy `veadk mpa provision` command requires a private YAML. A portable Skill should let a VeADK agent invoke the current branch's creation flow with environment credentials without inventing a parallel set of cloud API calls or requiring a running Studio server.

FR-1: deliver `skills/mpa-agent-create/SKILL.md`, bilingual operational references, UI metadata and a Python helper. The helper uses the installed VeADK managed modules; this branch/release is a dependency, not vendored into the Skill.
FR-2: accept a Runtime name and description; generate a stable `mi-` identity from a UUID request ID. Keep the entered name separate from internal resource bindings. Reuse the Beijing profile, public `latest` image tags, automatic IAM, management/business Workspaces, shared network/APIG, independent business DB, Skill Space, Worker and Runtime readiness checks. Optional image overrides and OpenViking URL/resource ID are supported.
FR-3: credentials are `VOLCENGINE_ACCESS_KEY`, `VOLCENGINE_SECRET_KEY`, optional `VOLCENGINE_SESSION_TOKEN` (or the existing mounted credential source); the model key is `VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY`. Optional OpenViking key is `VEADK_MPA_SKILL_OPENVIKING_API_KEY`. Secrets never enter command arguments, stored task inputs, snapshots or output. AK/SK alone cannot enable model access, cloud products, quotas or permissions.
FR-4: expose `plan`, `create --yes`, `status` and `retry --yes`. Plan is local-only. Persist nonsecret task inputs, selected image references and a code-owned configuration snapshot with environment secret references. Store the PG bootstrap alongside task state in a private durable state directory. Use `CreationTasks` for sanitized progress, terminal results, timeout/cancellation and exact-request retry. Status requires no credentials; retries use the original request, profile and image references.

Non-goals: changing Studio UI/API, existing CLI commands, managed provisioning semantics, publishing/installing the Skill globally, cloud smoke deployment, auto-deleting resources, creating model/OpenViking services, channel binding, or pinning `latest` to a digest. Tag movement remains a known existing limitation.

## Scenarios and design
Given locally configured credentials and model key, a plan validates inputs and prints IDs, defaults and prerequisites without cloud calls. Given an explicitly authorized creation and `--yes`, execute the existing runner until a terminal result; success requires `succeeded` and `ready`. Given failure, retain partial cloud resources and report task/request/agent IDs and safe diagnostics; retry the same task after resolving the cause. Given another active creation, reuse/report its state or the existing concurrency error; never spawn a replacement automatically. Given Ctrl+C, close and reap the child, preserve recovery state and return failure. Given a missing or unsafe state directory/snapshot, fail before cloud calls.

The helper is a consumer of `load_profile`, `studio_profile_values`, `with_creation_images`, `with_creation_resources` and `CreationTasks`; shared production modules are unchanged. The Skill explains installation into an execution environment that has this VeADK revision and command execution capability. A folder/ZIP can be supplied as a local Skill; no automatic SDK Skill registration is claimed. Python dependencies remain those declared by VeADK.

State directory is per deployment account and host; keep the same directory and account for retries. Do not share SQLite/bootstrap files between independent hosts, switch deployment accounts during recovery, or edit saved profiles. State is outside Git by default. File permissions and symlink checks protect task DB/config snapshots; snapshots contain placeholder references rather than resolved secrets. OpenViking requires the complete triple; blank means no injection, enabled means `OPENVIKING_USER=default` via the existing resource contract. Authentication/endpoint/key semantics remain owned by the existing managed service.

## Tasks and acceptance
- T-1 / AC-1 (FR-1): write portable Skill instructions, bilingual references and matching UI metadata; validate frontmatter, links and Python help.
- T-2 / AC-2 (FR-2/FR-3): regression tests first for local plan, validation, secret redaction, image overrides and no cloud calls; implement helper using existing APIs.
- T-3 / AC-3 (FR-4): isolated child-process tests for success, failure/status, interrupted recovery, exact retry, missing secrets/snapshot, concurrency, and cancellation/reaping. Inspect private state for secret absence.
- T-4 / AC-4: targeted helper and managed/CLI tests, Ruff/Pyright for changed Python, bilingual/whitespace checks and skill validator. No frontend assets/browser gate applies: no frontend or its server interface changes. No commit/push is authorized by this feature request.

## Risks and review
Permissions/product enablement/quota/network reachability require live cloud verification, which is outside this change. The helper cannot promise any AK/SK pair succeeds. An installed old VeADK package may lack managed APIs; report the dependency requirement rather than silently falling back to legacy creation. Durable state is necessary for uncertain outcomes; existing cloud discovery/idempotency remains authoritative. Keep the helper small by reusing tested `CreationTasks`, not reimplementing child supervision.

Direct review replaces unavailable `review-spec`: scope, contracts, secret transport, state identity, cancellation, compatibility and bilingual equivalence reviewed. User approval: on 2026-10-10 the user explicitly asked to continue the previously proposed Skill plus executable helper on the new branch. Implementation review found no remaining blockers. T-1–T-4 and AC-1–AC-4 are complete within the approved local scope; no cloud result is claimed.

## Verification record

Execution date: 2026-10-10. Tested scope: the added Skill/helper, its tests and paired design/spec documents on `feat/mpa-development-20261010`, based on `f7576c4080da6230e263eac20ab5d32644405ed5`, with an uncommitted additive diff. The existing unrelated `frontend/package-lock.json` change is excluded and preserved.

| Check | Outcome and evidence |
| --- | --- |
| Regression first | `fail` as expected: 15 initial cases could not import the not-yet-created helper. Implementation then fixed the demonstrated missing-bootstrap status/retry issue. |
| Targeted helper and reused boundary tests | `pass`: `uv run --no-sync --extra dev pytest tests/skills/test_mpa_agent_create_skill.py tests/integrations/mpa_managed tests/cli/test_frontend_deploy_iam.py -q`; 701 passed, including 23 Skill cases. Existing deprecation warnings remain. |
| Python lint/format | `pass`: `uv tool run --from ruff==0.11.12 ruff check` and `ruff format --check` for the two new Python files. Temporary tool environment; no machine-global configuration changes. |
| Python type checks | `pass`: `uv tool run --from pyright pyright --pythonpath .venv/bin/python skills/mpa-agent-create/scripts/create_mpa.py tests/skills/test_mpa_agent_create_skill.py`; 0 errors/warnings. |
| Skill validation and packaging | `pass`: skill-creator `quick_validate.py`; ZIP import validated with Studio's `validate_skill_archive`. Only the five intended Skill files are packaged, excluding state, caches and credentials. |
| CLI integration | `pass`: actual helper subprocess `plan` with isolated fixture environment; one JSON event, no state writes. `--help` works. No cloud creation. |
| Scoped hooks and secrets | `pass`: `uv run --no-sync --extra dev pre-commit run --files <all ten added files>`; Ruff, formatting and YAML scan passed. The staged-only Gitleaks hook does not scan untracked files; an additional direct Gitleaks directory scan covers all added files. |
| Documents | `pass`: paired-language/identifier review, local link existence, trailing-whitespace/final-newline checks and `git diff --check`. |
| Frontend/browser/assets | `not_applicable`: no frontend or supporting server interface changes. |
| Full repository regression | `not_run`: shared implementation and dependencies are unchanged; the affected managed/CLI tests cover the reused boundaries. |
| Full all-files pre-commit | `not_run`: no commit requested; scoped checks avoid mutating unrelated user changes. Required synchronization/all-files gates remain necessary before a future commit. |
| Live deployment | `not_run`: real cloud creation was not authorized for this Skill implementation; product enablement, IAM, quota and endpoint reachability remain unverified. |
