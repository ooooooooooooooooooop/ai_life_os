# Spec-Driven 模式

适用于：全新功能、重大重构、复杂系统变更

## 目录结构

```
.taskflow/active/[task-name]/
├── requirement.md  # 需求文档
├── design.md       # 设计文档
├── tasks.md        # 任务清单
└── progress.md     # 执行进度
```

## 角色

硬分离：
- **Architect**：Phase 0-3（需求、设计、任务拆分）
- **Builder**：Phase 4（执行）

## 流程

```
Phase 0: Clarification (对话)
   ↓ [用户确认理解正确]
Phase 1: Requirement → requirement.md
   ↓ [用户批准]
Phase 2: Design → design.md
   ↓ [用户批准]
Phase 3: Tasks → tasks.md
   ↓ [用户批准]
Phase 4: Execute → 逐条执行
```

## Phase 0 规则

1. **禁止**立即创建文档或代码
2. **必须提问**：至少 3 个澄清性问题
   - 边界：包含什么？不包含什么？
   - 约束：技术限制？时间限制？
   - 优先级：哪个最重要？
3. **必须总结**：口头总结用户意图
4. **获得确认**后才能进入 Phase 1

## 门禁

硬门禁：每个 Phase 必须用户批准才能继续。

## Grounding Window

Design 前最多 6 次只读操作，结束输出 Grounding Summary。
