---
name: unified-taskflow
description: |
  【强制】复杂任务管理系统。
  AI 必须在遇到以下情况时**先读取此 SKILL.md**，再执行任何操作：
  - 多文件变更、规划设计、新功能开发
  - 用户说"帮我想想/重构/升级/实现"
  - 任务描述超过 50 字或涉及架构变更
  禁止使用内置 agentic_mode 的 artifact 目录处理复杂任务，必须使用项目根目录下的 .taskflow/ 目录。
---

# Unified Taskflow v2.0

> 更新：2026-02-02

> [!CAUTION]
> **强制执行规则**
> 1. 遇到复杂任务时，**必须先读取本文档**，禁止直接使用内置 task_boundary
> 2. 任务管理使用项目根目录下的 `.taskflow/` 目录，**不使用**内置 artifact 目录
> 3. 必须按照下方复杂度信号判定模式，不可跳过
> 4. 如不确定是否触发，默认触发并询问用户

## 触发判断

**触发**：多文件变更、规划设计、"帮我想想/重构/升级"
**不触发**：简单问答、单行修改、明确直接指令

详见 [complexity-signals.md](references/complexity-signals.md)

## 模式选择

| 模式 | 适用 | 详情 |
|------|------|------|
| Lite | 简单调试 | [lite.md](references/lite.md) |
| Standard | 多文件变更 | [standard.md](references/standard.md) |
| Spec-Driven | 全新功能 | [spec-driven.md](references/spec-driven.md) |

## 按需加载

- 评估复杂度 → 读取 `complexity-signals.md`
- 进入 Spec-Driven → 读取 `spec-driven.md`
- 需要交互 → 读取 `interaction-design.md`

## 工作目录

```
.taskflow/
├── active/[task-name]/    # 当前任务（仅限一个）
└── archive/               # 已归档任务
```

## 核心机制

- **2-Action Rule**：每 2 次操作更新 progress.md
- **3-Strike Protocol**：3 次失败后升级用户
- **Phase 门禁**：阶段切换需确认

## 模式切换

- **升级**：识别复杂度增加 → 建议升级 → 用户确认
- **降级**：用户主动要求 → 确认风险 → 切换模式
- **退出**：用户说"停止" → 确认 → 归档进度

## 交互原则

- 选择题优先，3-4 个选项
- 每个选择点有推荐选项
- 详见 [interaction-design.md](references/interaction-design.md)

## 模板

- [template-requirement.md](references/template-requirement.md)
- [template-design.md](references/template-design.md)
- [template-tasks.md](references/template-tasks.md)

<!--
====================== BACKLOG ======================
定期清理：保留未实施项，删除已完成项

## 待实施项

T01: Phase 0 结构化问题框架
T02: Phase 验收 Checklist
T03: Pre-flight Checklist
T04: Mock Registry

## 深层思考

M1-M19: 见原始思考记录
P1-P6: 模式级思考
Q1-Q5: 本质问题

上次清理：2026-02-02
=====================================================
-->
