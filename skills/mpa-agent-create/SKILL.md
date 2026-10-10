---
name: mpa-agent-create
description: 使用火山引擎 AK/SK，通过 VeADK 的受管创建流程创建或恢复 MPA 智能体。适用于一键部署 MPA、准备前置资源，以及创建失败后的原任务重试。
---

# 创建 MPA 智能体

在已安装当前 VeADK 版本的 Python 环境中执行附带的 `scripts/create_mpa.py`。脚本复用 Studio 的受管任务执行器，无需启动 Studio 服务。可以将此目录挂载为本地技能，也可以打包后上传技能空间。加载技能不会自动安装 Python 依赖或注册工具。

使用前阅读[操作说明](references/operations.zh.md)，了解前置条件、命令、权限和失败恢复方法。

## 操作流程

1. 确认智能体名称、描述和部署账号。执行环境需已通过 `VOLCENGINE_ACCESS_KEY` / `VOLCENGINE_SECRET_KEY`、可选临时会话凭据，或已有挂载凭据源提供身份信息。另外需要模型密钥 `VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY`。不要让用户把秘密粘贴到聊天中，也不要将秘密放入命令参数。
2. 定位技能目录，使用能够导入 VeADK 的 Python 解释器。先执行 `plan --name <name>`，校验本地配置，生成 UUID 请求 ID 和稳定的内部智能体 ID，并展示镜像引用和资源计划。此步骤不调用云接口，不能确认云权限、额度或产品开通状态。
3. 向用户展示具体计划。如果用户已经明确要求在指定账号中创建该智能体，即可执行；否则先取得授权。执行 `create --name <same-name> --request-id <plan-request-id> --yes`，名称、描述及其他选项与计划保持一致。保留输出的 `taskId`、`requestId`、`agentId` 和状态目录位置。
4. 保持进程运行，向用户报告有意义的阶段变化，直到任务结束。只有命令成功退出，且 `state=succeeded`、`result.state=ready` 时，才能报告创建成功。返回 Runtime、技能空间和网关 ID，不返回访问密钥或签名地址。
5. 失败时报告阶段、安全错误信息或诊断，以及任务 ID。修复已确认的原因后，使用原账号和状态目录执行 `retry --task-id <id> --yes`。不要为了避开结果不确定的创建任务而生成新 ID。确实要创建另一个智能体时，重新生成计划和请求 ID。启用 OpenViking 时需在环境中重新提供密钥，脚本不会持久保存该密钥。
6. 使用 `status --task-id <id>` 查询已保存的任务状态。查询不要求云凭据或模型密钥，也不代表实时检查 Runtime 健康状态。创建或重试返回退出码 `2` 表示已有任务仍在运行，不自动另起进程或取消该任务。取消或超时后保留部分资源和状态，以便恢复。

## 资源与安全边界

- 内置部署地域为 `cn-beijing`，资源属于 AK/SK 核验后的账号。默认镜像地址中的 `2112682748` 表示公开镜像发布账号，不是部署账号。
- 默认镜像为 `.../mpa/mpa_agent:latest` 和 `.../mpa/mpa_codex_worker:latest`。脚本不会扫描标签或固定镜像摘要，`latest` 更新后实际拉取内容可能变化。需要固定版本时，手动指定版本或摘要。
- 准备或复用管理工作空间及数据库（`mpa_admin_workspace/mpa_admin_db`），以及独立的业务工作空间（`mpa_business_workspace`），每个智能体使用独立逻辑库。共享网络和 APIG 记录按账号、地域区分。手填名称用于 Runtime/Worker 展示，内部 `mi-` 身份仍单独保留。
- IAM、工作负载身份、PG、VPC/子网、标准型 APIG/IM Gateway、业务库、技能空间、Worker 和 Runtime 就绪检查沿用 VeADK 的现有受管服务。任务失败后，不使用临时拼写的接口调用自行重复创建资源。
- OpenViking 为可选项，服务地址、资源 ID 和环境 API Key 必须同时提供。全部留空不注入配置；启用时沿用现有流程注入 `OPENVIKING_USER=default`，不会创建 OpenViking 服务。
- 同一账号、主机使用相同的私有状态目录。数据库、配置快照、凭据和云服务原始日志不得加入项目包、Git 提交或技能压缩包。本技能不会删除云资源。
