# AI Life OS 功能迭代方案（基于设计初衷）

> 创建日期：2026-02-10  
> 适用版本：当前 `main` 分支（FastAPI + React + Event Sourcing + Goal Registry）

## 1. 设计初衷（从文档与代码抽象）

项目核心不是“任务清单工具”，而是“价值对齐的执行操作系统”，有三条主线：

1. `Blueprint First`
- 系统应优先服从用户的长期价值（Blueprint Self），而非即时冲动。
- 相关设计来源：`docs/core_design.md`、`docs/roadmap_2026.md`。

2. `Guardian as Steward`
- 系统不是被动记录，而是主动调度与干预。
- 关键动作：识别偏离、给出提示、保护高价值时间块。

3. `Dual-Layer Optimization`
- L1（Substrate）：低认知负荷、高效率执行日常维护型任务。
- L2（Flourishing）：高认知投入，保障深度工作与成长型目标。

## 2. 当前实现基线（已具备）

- 后端入口与 API 框架完整：`main.py`、`web/backend/app.py`、`web/backend/routers/*`
- 目标与任务主链路可运行：
  - 目标域服务：`core/goal_service.py`
  - 执行调度：`core/steward.py`、`scheduler/daily_tick.py`
  - 任务派发：`core/task_dispatcher.py`
- 持久化基础：
  - 事件日志：`core/event_sourcing.py`
  - 目标注册表：`core/objective_engine/registry.py`
  - 快照管理：`core/snapshot_manager.py`
- 前端流程闭环基础具备：
  - onboarding -> vision/goal -> decompose -> home 执行视图

## 3. 当前主要缺口（阻碍迭代效率）

1. 状态一致性缺口
- `event_log` 与 `goal_registry` 是双写路径，缺少统一事务语义与冲突检测。

2. Guardian 能力落地不足
- 文档有完整干预分层与传感器设计，但运行态更多停留在“建议与静态规则”。

3. 可观测性和验证不足
- 现有测试覆盖小，难支撑快速迭代；业务指标（如 L2 保护率）未形成稳定看板。

## 4. 功能迭代路线（建议 3 个迭代）

## Iteration 1：一致性与可观测性（1-2 周）

目标：把“能跑”升级为“可持续迭代”。

功能项：
- 统一目标写入链路（GoalRegistry 写入必须附带标准事件）。
- 引入事件 schema/version 字段与简单回放校验脚本。
- 增强 API 审计返回（每次规划输出统一 `decision_reason`、`used_state_fields`）。
- 扩展回归测试（goal/task/state 路径）。

建议落点：
- `core/goal_service.py`
- `core/event_sourcing.py`
- `web/backend/routers/api.py`
- `tests/`

验收标准：
- 回放状态与实时状态一致率可验证（核心路径 100%）。
- 关键 API（`/state`、`/sys/cycle`）具备稳定结构化审计字段。

## Iteration 2：Guardian 干预 MVP（2 周）

目标：将“理念”变成“可交互功能”。

功能项：
- 干预等级实现：`OBSERVE_ONLY / SOFT / ASK`（配置已存在，补全行为差异）。
- 增加“偏离信号”检测：重复 skip、L2 时段被 L1 打断、长时间无推进。
- 为 `/retrospective` 增加“干预建议来源说明”（基于哪些事件触发）。
- 前端展示“建议可追溯证据”（避免黑盒感）。

建议落点：
- `core/retrospective.py`
- `core/steward.py`
- `config/blueprint.yaml`
- `web/client/src/pages/Home.jsx`

验收标准：
- 用户可看到干预等级、触发信号与建议文本。
- 建议出现可追溯到事件类型，不再是纯文本黑盒。

## Iteration 3：Anchor + 目标闭环强化（2 周）

目标：把长期价值锚点接入日常执行。

功能项：
- 打通 Anchor 生命周期：生成草案 -> 差异对比 -> 激活 -> 生效反馈。
- 目标树增加“与 Anchor 关联度”字段（创建/确认时计算）。
- 周复盘输出“目标对齐度趋势”（不仅统计完成率）。
- 前端增加“价值对齐视图”（计划页显示对齐状态）。

建议落点：
- `cli/anchor_cmd.py`
- `core/blueprint_anchor.py`
- `core/goal_service.py`
- `web/client/src/pages/Home.jsx`

验收标准：
- 新建目标可以显示其与 Anchor 的关系（高/中/低或 score）。
- 周复盘能说明“做了很多”与“做对了”是否一致。

## 5. 实施优先级（从现在开始）

P0（先做）：
- Iteration 1 全部

P1（随后）：
- Iteration 2 干预信号 + 可追溯展示

P2（增强）：
- Iteration 3 Anchor 深度整合

## 6. 非目标（本轮不建议）

- 多租户与账号体系（当前是单用户本地范式）
- 复杂外部集成（如多日历、多设备同步）
- 大规模 UI 重构（先保证策略闭环真实有效）

## 7. 风险与控制

- 风险：规则先行导致“过拟合提示”，用户感到被控制。
- 控制：优先启用 `SOFT`，保留 `ASK`；先做可追溯，不做强制阻断。

- 风险：一致性改造引入回放兼容问题。
- 控制：加 event schema version + 迁移脚本 + 回放测试。

---

结论：  
先把“状态一致性 + 审计可追溯”打牢，再推进 Guardian 干预 MVP，最后做 Anchor 深度对齐。这样最符合项目设计初衷，也最能降低后续迭代成本。

