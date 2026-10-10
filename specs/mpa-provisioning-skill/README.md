# MPA provisioning Skill

- Component ID: `mpa-provisioning-skill`; revision: 2026-10-10; status: active.
- [Chinese](README.zh.md).
- [Design and verification](../../prd-spec/features/mpa-provisioning-skill/2026-10-10-aksk-creation-skill.md).

## Ownership and entry points
`skills/mpa-agent-create` is a portable Skill folder with `scripts/create_mpa.py`. It guides command-capable VeADK agents to invoke this VeADK revision's managed creation flow. It does not register itself in an Agent or start Studio. The caller installs VeADK and loads/mounts the Skill in its execution environment. Existing managed services own cloud resource provisioning and recovery.

## Contract
- CON-1: `plan` uses local configuration only and does not allocate cloud resources. Creation/retry require `--yes` and user authorization. Successful exit requires the managed task's verified success; failures never become empty success.
- CON-2: `create` requires a UUID request ID; the derived internal ID is stable for that request. Names follow existing Runtime validation. `retry` reads the original task input, configuration snapshot and image references. Changing a request's inputs is rejected. An additional agent requires a new request ID.
- CON-3: AK/SK, optional session token, model key and optional OpenViking key come from the established environment/credential source. Store only nonsecret snapshots with environment references. No secret CLI flags, stdout secret values or raw child logs. OpenViking requires all three fields and uses the existing injection contract.
- CON-4: State defaults outside Git to `~/.local/state/veadk/mpa-agent-create`; directories are private, snapshots/task DB are mode `0600`, and unsafe symlinks are rejected. Preserve state for one account/host. PG bootstrap uses the same durable state directory. State may contain resource IDs and operator-entered descriptions; treat it as private.
- CON-5: `status` reads existing task state without loading cloud credentials/model configuration. Progress/results use existing allowlisted stages/IDs and safe diagnostics. Shutdown/Ctrl+C awaits `CreationTasks.close()` and reaps child processes; partial cloud resources remain for recovery. An active task is reported without replacing or cancelling another process's work.
- CON-6: Built-in region/default images, shared Workspaces/network/APIG and agent-specific database/Skill Space/Worker/Runtime behavior follow the current profile. `latest` is a tag, not an immutable image version. Product enablement, IAM authorization, quota, model access and endpoint reachability remain prerequisites. Existing Studio/CLI contracts are unchanged.

## Verification
Skill instructions, discovery text, UI metadata and operational reference use Chinese at the user's request. Executable identifiers and command syntax remain unchanged; this localization does not alter CON-1–CON-6. The design and this component spec retain their English/Chinese counterparts.

Helper tests isolate credentials/state/child processes and never call a provider. Targeted managed regression tests verify the reused boundaries; Skill validation checks packaging metadata. Live provider creation is a separate authorized smoke procedure and is not implied by local tests. See the design for actual outcomes.
