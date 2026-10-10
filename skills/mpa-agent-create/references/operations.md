# MPA creation operations

[Chinese](operations.zh.md).

## Execution environment

Install VeADK from the branch/release containing this Skill using its declared dependencies and supported Python version (Python 3.10 or newer). Use that environment's Python to run the helper. An older unrelated PyPI release is not assumed compatible. This folder is independently distributable, but it does not bundle VeADK or automatically add a tool to a generic ADK Agent. Load/mount it as a local Skill in a command-capable Agent/worker, or package the folder for your Skill Space. Preserve `SKILL.md`, `scripts/`, and `references/` together.

Supply the following through the execution environment's secret configuration; do not place actual values in chat, arguments, source files, or shell history:

| Variable | Purpose |
| --- | --- |
| `VOLCENGINE_ACCESS_KEY` | Deployment identity's AK. |
| `VOLCENGINE_SECRET_KEY` | Deployment identity's SK. |
| `VOLCENGINE_SESSION_TOKEN` | Optional temporary-credential token; the existing `VOLC_SESSIONTOKEN` alias is supported. |
| `VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY` | Separate model access key for the built-in Ark model endpoint. |
| `VEADK_MPA_SKILL_OPENVIKING_API_KEY` | Required only with an OpenViking URL/resource ID. |

Without an environment AK/SK pair, VeADK uses `/var/run/secrets/iam/credential`; its JSON has `access_key_id`, `secret_access_key`, `session_token` (or `AccessKeyId`, `SecretAccessKey`, `SessionToken`). It is read on each cloud call. Use a private file delivered by the execution environment rather than committing credentials. If Studio Identity variables are inherited, their existing all-or-none validation still applies; do not invent a UserPool solely for this helper.

AK/SK must have STS caller-identity, IAM get/create/read/attach-policy and pass-role, Identity workload get/create, AIDAP Workspace/detail/branch/compute/endpoint/database/account-connection, VPC/subnet discovery/create, APIG available-zone/gateway/IM Gateway, and AgentKit Runtime/Tool/Skill Space permissions. The actual operation set is maintained by the current managed modules and `veadk/cli/frontend_deploy_policy.py`; that broader Studio policy is not a claim of least-privilege for this Skill. The helper prepares the approved Runtime/Worker execution role, but cannot grant permissions to its own AK/SK identity. Enable AgentKit, AIDAP, APIG and related products, provide model access and sufficient quota, and ensure returned PG endpoints are reachable from this process and Runtime.

## Commands

`SKILL_DIR` means the installed/mounted Skill folder. It is not a machine-specific path.

```bash
python "$SKILL_DIR/scripts/create_mpa.py" plan --name Support-Agent --description "Team assistant"
```

Read the returned `requestId`, then set the nonsecret `REQUEST_ID` to that value. After authorized plan review:

```bash
python "$SKILL_DIR/scripts/create_mpa.py" create --name Support-Agent --description "Team assistant" --request-id "$REQUEST_ID" --yes
```

Use an explicitly versioned MPA/Worker image when desired, passing identical options to plan and create:

```bash
python "$SKILL_DIR/scripts/create_mpa.py" plan --name Support-Agent --mpa-image registry.example/mpa:v1 --worker-image registry.example/worker:v1
```

Optional OpenViking uses `--openviking-url https://your-service.example` and `--openviking-resource-id ov-your-resource` together, plus the environment key. No key option exists. Do not use a console URL as the service URL. Enabled creation injects the existing `OPENVIKING_URL`, `OPENVIKING_RESOURCE_ID`, `OPENVIKING_API_KEY`, `OPENVIKING_USER=default` contract.

```bash
python "$SKILL_DIR/scripts/create_mpa.py" status --task-id "$TASK_ID"
python "$SKILL_DIR/scripts/create_mpa.py" retry --task-id "$TASK_ID" --yes
```

Every command accepts `--state-dir /private/persistent/directory`. Default is `~/.local/state/veadk/mpa-agent-create`. Use the same directory and deployment account for recovery. Plan creates no state or cloud resources. Actual creation saves a nonsecret code-profile JSON with environment references under `profiles/<request-id>.json`, task/image state in `tasks.sqlite3`, and PG recovery intents in `pg-bootstrap.sqlite3`. Directories must be private and owned by the process user, files mode `0600`; unsafe links/shared directories fail. Place this directory on durable local storage; it is not a multi-host state backend. Keep backups private and never hand-edit saved input/configuration.

## Results and recovery

Output is JSON lines: `plan`, `task` or `error`. Task events contain sanitized stage, error, resource IDs, image references and recent allowlisted diagnostics. Raw SDK/child output is discarded. Exit `0` means successful plan/status or verified creation; creation exit `1` means failure, `2` means a task is still active, and Ctrl+C returns `130` after child cleanup. A successful status command does not mean the task or Runtime is healthy: inspect its `state`.

Stages cover account/config checks, IAM role, management/business Workspace and management DB, network, gateway, Worker, business DB/skills/Runtime deployment and readiness. Runtime can require initial and final releases to inject allocated endpoints and credentials; the helper uses the existing flow. Do not declare success from a V1 release alone.

On a failed task, keep its IDs and fix the cause (permissions, quota, unavailable resource, model configuration or connectivity). `retry` reconstructs the stored input and reuses its profile/image references, never a fresh request. Credentials and OpenViking key are loaded again from the environment. If an operation's outcome is uncertain, rely on existing recovery/discovery rather than repeatedly starting new agents. Missing snapshots or changed inputs block execution; preserve the original state rather than fabricating replacement files. Active tasks are reported without being replaced. Cloud resources survive failure/cancellation and are not automatically deleted.

Defaults use public publisher images under `agentkit-platform-2112682748-cn-beijing.cr.volces.com/mpa`; resources are created in the account verified from deployment credentials. Stored `latest` references are not digest locks: later pulls can resolve different bytes. To create another agent, start a new plan and use its new request ID.
