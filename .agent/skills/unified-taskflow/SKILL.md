---
name: unified-taskflow
description: |
  【强制】复杂任务管理系统。
  AI 必须在遇到以下情况时**先读取此 SKILL.md**，再执行任何操作：
  - 多文件变更、规划设计、新功能开发
  - 用户说"帮我想想/重构/升级/实现"
  禁止使用内置 agentic_mode 的 artifact 目录处理复杂任务，必须使用项目根目录下的 .taskflow/ 目录。
---

# Unified Taskflow v3.0

> 更新：2026-02-13

> [!CAUTION]
> **核心规则**
> 1. 遇到复杂任务时，**必须先读取本文档**，禁止直接使用内置 task_boundary
> 2. 任务管理使用项目根目录下的 `.taskflow/` 目录，**不使用**内置 artifact 目录
> 3. 禁止跨阶段推理 — 执行时不能跳回规划，规划时不能偷跑代码
> 4. 如不确定是否触发，默认触发并询问用户

## 触发判断

**触发**：多文件变更、规划设计、"帮我想想/重构/升级/实现"
**不触发**：简单问答、单行修改、明确直接指令

## 按需加载

- 进入 Phase 0 → 读取 [phase0-clarification.md](references/phase0-clarification.md)
- 需要交互决策 → 读取 [interaction-design.md](references/interaction-design.md)
- 治理规则细节 → 读取 [governance.md](references/governance.md)
- Re-grounding 细节 → 读取 [regrounding-protocol.md](references/regrounding-protocol.md)

## 工作流

### Phase 0: 理解快照（Understanding Snapshot）

**目的**：确保 Agent 正确理解用户需求，生成防幻觉锚点。

1. **禁止**立即创建文档或代码
2. Agent 输出**理解快照**：
   - 用户意图（一句话）
   - 识别到的歧义点
   - Agent 的假设
3. 用户确认或修正
4. 写入 `anchor.md`（北极星文件）

> 问题框架（参考，不强制全部使用）：边界 / 约束 / 优先级 / 风险
> 详见 [phase0-clarification.md](references/phase0-clarification.md)

### 执行（Elastic Execution）

弹性深度 — 根据任务复杂度自然展开，无固定档位：

- **简单任务**：anchor.md → 直接执行 → 更新 checkpoint.md
- **中等任务**：anchor.md → 拟定计划（口头或 checkpoint 中记录）→ 执行 → 更新 checkpoint.md
- **复杂任务**：anchor.md → 生成 design.md → 执行 → 持续更新 checkpoint.md

执行期间遵守：
- **2-Action Rule**：每 2 次操作更新 checkpoint.md
- **3-Strike Protocol**：同一问题 3 次失败后升级给用户
- **Re-grounding Protocol**：定期回读 anchor.md 检测偏移

### 完成（Completion）

1. 最终 Re-grounding — 读取 anchor.md 确认所有完成标准已满足
2. 向用户报告完成状态
3. 归档任务（移入 archive/）

## 运行机制

### 2-Action Rule

每 2 次操作（文件读写、代码修改等）更新一次 checkpoint.md：
- 记录做了什么
- 记录发现了什么
- 下一步计划

> Debug 窗口例外：调试时放宽为 4-Action，但保持 3-Strike

### 3-Strike Protocol

同一问题连续失败 3 次：
1. Strike 1 — 记录问题和尝试方案
2. Strike 2 — 换一个方向，记录
3. Strike 3 — **停止尝试**，升级给用户，提供已排除方案列表

### Re-grounding Protocol（强制回读）

防止上下文膨胀导致目标偏移的核心机制：

- **触发**：每完成一个子任务 / 每 3-5 步 / 遇到不确定性时
- **动作**：读取 anchor.md → 与当前工作比对 → 输出对齐判定
- **偏移处理**：发现偏移时暂停 → 报告用户 → 等待指示

> 详见 [regrounding-protocol.md](references/regrounding-protocol.md)

### RIPER-Core 思维规则

1. 根因解优先 — 禁止用配置/降级掩盖问题
2. 显式因果链 — Why → Condition → Limitation
3. 无魔法数字 — 常数必须来自输入/约束
4. 明确变量 — 信息不足立即暂停询问

## 工作目录

```text
.taskflow/
├── index.json
├── active/[task-name]/
│   ├── anchor.md          # 北极星文件（必须）
│   ├── checkpoint.md      # 校验点记录（必须）
│   └── design.md          # 技术设计（按需）
└── archive/               # 已归档任务
```

## 交互原则

- 选择题优先，3-4 个选项
- 每个选择点有推荐选项
- 详见 [interaction-design.md](references/interaction-design.md)

## 引用文件

| 文件 | 用途 |
|------|------|
| [phase0-clarification.md](references/phase0-clarification.md) | Phase 0 理解快照流程细节 |
| [regrounding-protocol.md](references/regrounding-protocol.md) | Re-grounding 回读规则 |
| [governance.md](references/governance.md) | 目录隔离、生命周期、治理规范 |
| [interaction-design.md](references/interaction-design.md) | 交互设计原则 |
| [anchor.md 模板](assets/templates/anchor.md) | Grounding Anchor 模板 |
| [checkpoint.md 模板](assets/templates/checkpoint.md) | 校验点记录模板 |
| [design.md 模板](assets/templates/design.md) | 技术设计模板（按需） |
