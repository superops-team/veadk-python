# MPA 创建操作说明

[English](operations.md)。

## 执行环境

通过包含此 Skill 的 VeADK 分支/版本安装其声明的依赖，使用支持的 Python 版本（Python 3.10 或以上）。使用该环境的 Python 执行脚本，不假定无关的旧 PyPI 版本兼容。此目录可独立分发，但不打包 VeADK，也不自动给通用 ADK Agent 添加工具。在具备命令执行能力的 Agent/Worker 中加载/挂载为本地 Skill，或将目录打包上传 Skill Space。保持 `SKILL.md`、`scripts/` 和 `references/` 一起分发。

通过执行环境的秘密配置提供以下变量；实际值不进入聊天、参数、源码或 shell 历史：

| 变量 | 用途 |
| --- | --- |
| `VOLCENGINE_ACCESS_KEY` | 部署身份的 AK。 |
| `VOLCENGINE_SECRET_KEY` | 部署身份的 SK。 |
| `VOLCENGINE_SESSION_TOKEN` | 可选临时凭据 token；兼容已有 `VOLC_SESSIONTOKEN` 别名。 |
| `VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY` | 内置 Ark 模型地址使用的独立模型访问密钥。 |
| `VEADK_MPA_SKILL_OPENVIKING_API_KEY` | 仅填写 OpenViking 地址/资源 ID 时必需。 |

没有环境 AK/SK 对时，VeADK 使用 `/var/run/secrets/iam/credential`；JSON 字段为 `access_key_id`、`secret_access_key`、`session_token`（或 `AccessKeyId`、`SecretAccessKey`、`SessionToken`），每次云调用重新读取。使用执行环境交付的私有文件，不提交凭据。若继承 Studio Identity 变量，仍按现有完整组校验；不要仅为脚本虚构 UserPool。

AK/SK 需要 STS 调用身份、IAM 查询/创建/读取/绑定策略与传递角色、Identity 工作负载查询/创建、AIDAP Workspace/详情/分支/计算/地址/数据库/账号连接、VPC/子网查询/创建、APIG 可用区/网关/IM Gateway 和 AgentKit Runtime/Tool/Skill Space 权限。实际接口集合由当前受管模块和 `veadk/cli/frontend_deploy_policy.py` 维护；较宽的 Studio 策略不代表此 Skill 的最小权限策略。脚本准备已批准的 Runtime/Worker 执行角色，但不能为自己的 AK/SK 身份提权。需开通 AgentKit、AIDAP、APIG 等产品，具备模型访问和足够额度，确保返回的 PG 地址可从本进程和 Runtime 访问。

## 命令

`SKILL_DIR` 是安装/挂载的 Skill 目录，不是固定机器路径。

```bash
python "$SKILL_DIR/scripts/create_mpa.py" plan --name Support-Agent --description "Team assistant"
```

读取返回的 `requestId`，将非敏感变量 `REQUEST_ID` 设为该值。完成授权的计划审阅后：

```bash
python "$SKILL_DIR/scripts/create_mpa.py" create --name Support-Agent --description "Team assistant" --request-id "$REQUEST_ID" --yes
```

需要时可指定带版本的 MPA/Worker 镜像，计划和创建传相同选项：

```bash
python "$SKILL_DIR/scripts/create_mpa.py" plan --name Support-Agent --mpa-image registry.example/mpa:v1 --worker-image registry.example/worker:v1
```

可选 OpenViking 同时传 `--openviking-url https://your-service.example` 和 `--openviking-resource-id ov-your-resource`，并设置环境密钥。没有密钥参数。不要把控制台链接作为服务地址。启用时注入现有 `OPENVIKING_URL`、`OPENVIKING_RESOURCE_ID`、`OPENVIKING_API_KEY`、`OPENVIKING_USER=default` 契约。

```bash
python "$SKILL_DIR/scripts/create_mpa.py" status --task-id "$TASK_ID"
python "$SKILL_DIR/scripts/create_mpa.py" retry --task-id "$TASK_ID" --yes
```

每条命令都接受 `--state-dir /private/persistent/directory`，默认 `~/.local/state/veadk/mpa-agent-create`。恢复时保持目录和部署账号相同。计划不创建状态或云资源。实际创建把含环境引用的非敏感代码配置 JSON 保存到 `profiles/<request-id>.json`，任务/镜像状态保存到 `tasks.sqlite3`，PG 恢复意图保存到 `pg-bootstrap.sqlite3`。目录须私有并归进程用户所有，文件为 `0600`；不安全链接/共享目录被拒绝。使用持久本地存储，不是跨主机状态后端。备份保持私有，不手动修改已存输入/配置。

## 结果与恢复

输出是 JSON 行，类型为 `plan`、`task` 或 `error`。任务事件包含安全阶段、错误、资源 ID、镜像引用和最近白名单诊断。丢弃 SDK/子进程原始输出。退出 `0` 表示计划/状态查询成功或创建已验证成功；创建退出 `1` 表示失败，`2` 表示任务仍在运行，Ctrl+C 清理子进程后返回 `130`。状态查询成功不代表任务或 Runtime 健康，需检查 `state`。

阶段涵盖账号/配置检查、IAM 角色、管理/业务 Workspace 和管理库、网络、网关、Worker、业务库/技能/Runtime 部署及就绪。Runtime 可能需初始与最终两次发布，以注入已分配地址和凭据；脚本沿用已有流程。不能仅凭 V1 发布就宣称成功。

任务失败后保留 ID，修复原因（权限、额度、资源不可用、模型配置或网络）。`retry` 还原已存输入，复用配置/镜像引用，不生成新请求。环境中重新读取凭据和 OpenViking 密钥。接口结果不确定时依赖已有恢复/发现机制，不反复另建智能体。快照丢失或输入改变会阻止执行；保留原状态，不伪造替代文件。活动任务只报告，不替换。失败/取消后保留云资源，不自动删除。

默认使用 `agentkit-platform-2112682748-cn-beijing.cr.volces.com/mpa` 下的公开发布镜像；资源在部署凭据验证的账号下创建。已存 `latest` 引用不是 digest 锁：后续拉取可能对应不同字节。另建智能体时重新计划，使用新请求 ID。
