---
name: mpa-agent-create
description: Create or resume an MPA agent with VeADK's managed provisioning flow using Volcengine AK/SK credentials. Use for one-click MPA deployment, prerequisite preparation, and failed creation recovery.
---

# Create an MPA agent

Use the bundled `scripts/create_mpa.py` with a Python environment containing the VeADK revision that ships this Skill. It calls the same managed task runner as Studio; a Studio web server is unnecessary. The folder can be mounted as a local Skill or uploaded as a Skill archive. Loading the Skill alone does not install Python dependencies or register tools.

Read [references/operations.md](references/operations.md) for prerequisites, commands, permissions and recovery. [中文操作说明](references/operations.zh.md) contains equivalent guidance.

## Workflow

1. Confirm the intended name, description and deployment account. Credentials must already be available to the execution environment through `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`, optional session token, or the existing mounted credential source. The model key is separately required as `VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY`. Do not ask the user to paste secrets into chat or put them in command arguments.
2. Locate the Skill folder and use an interpreter that can import VeADK. Run `plan --name <name>` first. This validates local configuration, produces a UUID request ID and stable internal agent ID, and shows the image references and resource plan. It makes no cloud calls and cannot verify permissions, quotas or product enablement.
3. Present the concrete plan. If the user already explicitly asked to create this agent in the identified account, that request authorizes execution; otherwise obtain approval before cloud mutation. Run `create --name <same-name> --request-id <plan-request-id> --yes` with the same description/options used for the plan. Preserve the emitted `taskId`, `requestId`, `agentId` and state-directory location.
4. Keep the process attached and relay meaningful stage changes until terminal state. Report success only when the command exits successfully with `state=succeeded` and `result.state=ready`. Return the Runtime, Skill Space and gateway IDs. There is no returned access key or signed endpoint.
5. On failure, report the stage, safe error/diagnostic and task ID. Fix the demonstrated cause and use `retry --task-id <id> --yes` with the original account and state directory. Do not generate a new ID to escape an uncertain creation outcome. A genuinely separate agent requires a new plan/request ID. Re-supply the OpenViking key in the environment when enabled; it is not persisted.
6. Use `status --task-id <id>` to inspect stored task state. Status works without cloud/model credentials and is not a live Runtime health check. Exit code `2` from creation/retry means an existing task is active; do not start another process or cancel it automatically. Preserve partial resources and state on cancellation or timeout.

## Resource and security boundaries

- Built-in deployment region is `cn-beijing`; the verified AK/SK account owns resources. The `2112682748` segment in default image URLs identifies the public image publisher, not the deployment account.
- Default images are `.../mpa/mpa_agent:latest` and `.../mpa/mpa_codex_worker:latest`. The helper does not enumerate tags or pin digests; a moving `latest` tag can change actual image bytes. Use explicit version/digest overrides when immutable deployment is required.
- Prepare/reuse one management Workspace (`mpa_admin_workspace/mpa_admin_db`) and a distinct business Workspace (`mpa_business_workspace`) with separate logical databases per agent. Shared network/APIG records are scoped to account and region. The entered name controls Runtime/Worker display names; internal `mi-` identity remains separate.
- IAM, workload identity, PG, VPC/subnets, standard APIG/IM Gateway, business DB, Skill Space, Worker and Runtime readiness follow VeADK's existing managed service. Do not independently recreate these resources with ad hoc APIs after a failed task.
- OpenViking is optional: all of URL, resource ID and environment API key are required. Blank fields inject no OpenViking configuration. The existing flow injects `OPENVIKING_USER=default` when enabled; it does not create an OpenViking service.
- Use the same private state directory for one account/host. Never include its databases, profile snapshots, credentials or raw provider logs in a project bundle, Git commit or Skill archive. No cloud resources are deleted by this Skill.
