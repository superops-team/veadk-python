# MPA 创建 Skill

- 组件 ID：`mpa-provisioning-skill`；修订：2026-10-10；状态：有效。
- [English](README.md)。
- [设计与验证](../../prd-spec/features/mpa-provisioning-skill/2026-10-10-aksk-creation-skill.zh.md)。

## 职责与入口
`skills/mpa-agent-create` 是可移植 Skill 目录，含 `scripts/create_mpa.py`。它指导具备命令执行能力的 VeADK 智能体调用当前 VeADK 版本的受管创建链路。不自行注册到 Agent 或启动 Studio。调用方在执行环境安装 VeADK 并加载/挂载 Skill。已有受管服务负责云资源创建与恢复。

## 契约
- CON-1：`plan` 只使用本地配置，不分配云资源。创建/重试要求 `--yes` 和用户授权。成功退出必须满足受管任务确认成功；失败不转为空结果成功。
- CON-2：`create` 要求 UUID 请求 ID；派生内部 ID 在同一请求中稳定。名称沿用已有 Runtime 校验。`retry` 读取原任务输入、配置快照与镜像引用。修改同一请求的输入被拒绝。另建智能体需要新请求 ID。
- CON-3：AK/SK、可选会话 token、模型密钥及可选 OpenViking 密钥来自已有环境/凭据源。仅保存含环境引用的非敏感快照。不接受秘密 CLI 参数，不向 stdout 输出秘密或子进程原始日志。OpenViking 要求三项完整并使用已有注入契约。
- CON-4：状态默认在 Git 外的 `~/.local/state/veadk/mpa-agent-create`；目录私有，快照/任务 DB 为 `0600`，拒绝不安全符号链接。同一账号/主机保留状态。PG 启动状态使用相同持久目录。状态可能含资源 ID 和操作者填写的描述，应视为私有信息。
- CON-5：`status` 读取已有任务状态，不加载云凭据/模型配置。进度/结果使用已有白名单阶段/ID 和安全诊断。退出/Ctrl+C 等待 `CreationTasks.close()` 并回收子进程；保留已建云资源以恢复。活动任务仅报告，不替换或取消其他进程的工作。
- CON-6：内置地域/默认镜像、共享 Workspace/网络/APIG 及智能体独立数据库/Skill Space/Worker/Runtime 行为沿用当前配置。`latest` 是标签，不是不可变镜像版本。产品开通、IAM 授权、额度、模型访问和地址可达性仍是前置条件。现有 Studio/CLI 契约不变。

## 验证
脚本测试隔离凭据、状态和子进程，不调用云服务。受管定向回归验证复用边界；Skill 校验检查打包元数据。真实云创建需要独立授权的冒烟步骤，本地测试不证明云端通过。实际结果见设计。
