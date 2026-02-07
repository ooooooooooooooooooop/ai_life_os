# Standard 模式

适用于：多文件变更、中等复杂度任务

## 目录结构

```
.taskflow/active/[task-name]/
├── task_plan.md    # 任务计划
└── progress.md     # 执行进度
```

## 角色

软分离：
- **[Planning]**：规划变更范围和步骤
- **[Executing]**：执行具体变更

## 流程

```
1. 创建 task_plan.md（含变更列表）
   ↓ [用户确认]
2. 逐步执行，更新 progress.md
   ↓
3. 完成后归档
```

## task_plan.md 结构

```markdown
# [任务名]

## 目标
[一句话描述]

## 变更列表
- [ ] 文件 A: ...
- [ ] 文件 B: ...

## 风险
- ...
```

## 门禁

软门禁：建议用户确认计划，但不强制。
