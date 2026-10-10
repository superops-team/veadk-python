# 使用 AK/SK 创建 MPA 的 Skill

- 变更 ID：`mpa-provisioning-skill`；日期：2026-10-10；状态：implemented。
- [English](2026-10-10-aksk-creation-skill.md)。
- 契约：[MPA 创建 Skill](../../../specs/mpa-provisioning-skill/README.zh.md)。

## 背景与范围
Studio 已通过 `CreationTasks` 及子进程 runner 调用受管创建服务。旧 `veadk mpa provision` 命令要求私有 YAML。可移植 Skill 应让 VeADK 智能体通过环境凭据调用当前分支的创建流程，无需另写一套云 API 或启动 Studio 服务。

FR-1：交付 `skills/mpa-agent-create/SKILL.md`、中文操作参考、中文界面元数据和 Python 辅助脚本。按用户明确要求，Skill 说明和发现文本使用中文；代码标识符和命令语法保持不变。脚本使用已安装的 VeADK 受管模块；当前分支/版本是依赖，不复制到 Skill 内。
FR-2：接受 Runtime 名称和描述；根据 UUID 请求 ID 生成稳定的 `mi-` 身份。填写名称与内部资源绑定身份分离。复用北京配置、公开 `latest` 镜像标签、自动 IAM、管理/业务 Workspace、共享网络/APIG、独立业务库、Skill Space、Worker 和 Runtime 就绪检查。支持可选镜像覆盖和 OpenViking 地址/资源 ID。
FR-3：凭据使用 `VOLCENGINE_ACCESS_KEY`、`VOLCENGINE_SECRET_KEY`、可选 `VOLCENGINE_SESSION_TOKEN`（或现有挂载凭据源）；模型密钥为 `VEADK_MPA_CONFIG_MODEL_AGENT_API_KEY`。可选 OpenViking 密钥为 `VEADK_MPA_SKILL_OPENVIKING_API_KEY`。秘密不进入命令参数、保存的任务输入、快照和输出。仅有 AK/SK 不会自动开通模型访问、云产品、额度或权限。
FR-4：提供 `plan`、`create --yes`、`status` 和 `retry --yes`。计划只做本地检查。保存非敏感任务输入、已选镜像引用及使用环境秘密引用的代码配置快照。PG 启动状态与任务状态放在私有持久目录。通过 `CreationTasks` 复用安全进度、终态结果、超时/取消及原请求重试。查询状态不要求凭据；重试沿用原请求、配置和镜像引用。

非目标：修改 Studio UI/API、已有 CLI 命令或受管创建语义；发布/全局安装 Skill；真实云部署；自动删除资源；创建模型/OpenViking 服务；绑定消息渠道；将 `latest` 固定为 digest。标签变化仍是已有的已知限制。

## 场景与设计
本地已配置凭据与模型密钥时，计划校验输入并输出 ID、默认值和前置条件，不访问云端。明确授权创建并传入 `--yes` 时，执行已有 runner 直到终态；成功必须满足 `succeeded` 和 `ready`。失败时保留已建云资源，输出任务/请求/智能体 ID 与安全诊断；修复原因后重试同一任务。有其他创建运行时复用/报告其状态或已有并发错误，不自动产生替代请求。Ctrl+C 时关闭并回收子进程，保留恢复状态并返回失败。状态目录/快照缺失或不安全时，在云调用前失败。

脚本消费 `load_profile`、`studio_profile_values`、`with_creation_images`、`with_creation_resources` 和 `CreationTasks`；共享生产模块不变。Skill 说明执行环境需安装当前 VeADK 版本并具备命令执行能力。文件夹/ZIP 可作为本地 Skill 提供，不宣称自动完成 SDK Skill 注册。Python 依赖沿用 VeADK 已声明依赖。

状态目录按部署账号和主机使用；重试保持目录与账号一致。不同主机不共享 SQLite/启动状态，恢复时不切换部署账号，不编辑保存的配置。默认状态在 Git 外。文件权限和符号链接检查保护任务 DB/配置快照；快照保存占位引用而非解析后的秘密。OpenViking 必须完整填写三项；全空不注入，启用时通过现有资源契约注入 `OPENVIKING_USER=default`。鉴权、地址和密钥语义继续由已有受管服务负责。

## 任务与验收
- T-1 / AC-1（FR-1）：编写可移植的中文 Skill 说明/参考和一致的界面元数据；校验 frontmatter、链接与 Python 帮助。
- T-2 / AC-2（FR-2/FR-3）：先编写本地计划、参数校验、秘密脱敏、镜像覆盖及无云调用回归测试；使用已有 API 实现脚本。
- T-3 / AC-3（FR-4）：隔离子进程测试成功、失败/查询、中断恢复、原请求重试、秘密/快照缺失、并发及取消/回收。检查私有状态不含秘密。
- T-4 / AC-4：脚本和受管/CLI 定向测试、修改 Python 的 Ruff/Pyright、双语/空白检查及 Skill 校验。不适用前端产物/浏览器门禁：没有前端及其服务接口改动。本次功能请求没有授权提交/推送。

## 风险与审查
权限、产品开通、额度和网络可达性需要真实云验证，不属于本次范围。脚本不能承诺任意 AK/SK 都能成功。旧 VeADK 安装包可能缺少受管 API；报告版本依赖，不静默回退到旧创建链路。不确定结果需要持久状态；已有云端发现和幂等逻辑仍是权威。复用经过验证的 `CreationTasks`，不重新实现子进程监督，保持脚本小而完整。

因 `review-spec` 不可用，执行直接审查：范围、契约、秘密传输、状态身份、取消、兼容性及双语等价性已审查。用户批准：2026-10-10 用户明确要求在新分支继续此前提出的 Skill 和可执行脚本方案。实现审查无剩余阻塞问题。T-1–T-4 和 AC-1–AC-4 已在批准的本地范围内完成；不宣称云验证结果。

## 验证记录

执行日期：2026-10-10。验证范围：`feat/mpa-development-20261010` 分支新增 Skill/脚本、测试及配对设计/规范，基于 `f7576c4080da6230e263eac20ab5d32644405ed5` 和未提交的增量修改。已有无关的 `frontend/package-lock.json` 修改排除并保留。

| 检查 | 结果与证据 |
| --- | --- |
| 回归先行 | `fail`，符合预期：初始 15 个用例无法导入尚未创建的脚本。实现后修复了验证中发现的启动状态文件缺失导致查询/重试失败的问题。 |
| 脚本及复用边界定向测试 | `pass`：`uv run --no-sync --extra dev pytest tests/skills/test_mpa_agent_create_skill.py tests/integrations/mpa_managed tests/cli/test_frontend_deploy_iam.py -q`；701 通过，其中 23 个 Skill 用例。保留已有弃用警告。 |
| Python 检查/格式 | `pass`：两份新增 Python 文件的 `uv tool run --from ruff==0.11.12 ruff check` 和 `ruff format --check`。使用临时工具环境，没有修改机器全局配置。 |
| Python 类型检查 | `pass`：`uv tool run --from pyright pyright --pythonpath .venv/bin/python skills/mpa-agent-create/scripts/create_mpa.py tests/skills/test_mpa_agent_create_skill.py`；0 错误/警告。 |
| Skill 校验与打包 | `pass`：skill-creator 的 `quick_validate.py`；ZIP 通过 Studio 的 `validate_skill_archive` 导入校验。只打包五份预期 Skill 文件，排除状态、缓存与凭据。 |
| CLI 集成 | `pass`：实际脚本子进程使用隔离的测试环境执行 `plan`；一个 JSON 事件，没有写入状态。`--help` 正常。没有创建云资源。 |
| 定向 hooks 与秘密扫描 | `pass`：`uv run --no-sync --extra dev pre-commit run --files <全部十份新增文件>`；Ruff、格式和 YAML 扫描通过。仅扫描暂存区的 Gitleaks hook 不覆盖未跟踪文件；另用直接 Gitleaks 目录扫描覆盖全部新增文件。 |
| 文档 | `pass`：双语/标识符审查、本地链接存在性、行尾空白/末尾换行检查及 `git diff --check`。 |
| 前端/浏览器/产物 | `not_applicable`：没有前端及其服务端接口修改。 |
| 全仓库回归 | `not_run`：共享实现和依赖未改变；受影响的受管/CLI 测试覆盖复用边界。 |
| 全文件 pre-commit | `not_run`：没有要求提交；定向检查避免改动用户无关修改。今后提交前仍需同步分支并执行全文件门禁。 |
| 真实部署 | `not_run`：本次 Skill 实现未授权真实云创建；产品开通、IAM、额度和地址可达性尚未验证。 |

### 中文说明后续调整

2026-10-10，用户要求 Skill 内容只用中文。翻译 `SKILL.md` 和界面元数据，保留中文操作参考，移除冗余英文版本。设计与组件规范仍保持英中配对。本次为文档/元数据翻译，不改 Python、命令语法、状态、权限或创建契约，无需递归 PRD。基于 `9ce16beb` 加本次翻译修改验证：Skill 校验、本地链接/空白、ZIP 导入及定向 pre-commit 为 `pass`；运行时回归为 `not_applicable`，因为可执行代码未变。更新后的压缩包包含四份 Skill 文件。上方首次实现记录描述原来的五文件压缩包。
