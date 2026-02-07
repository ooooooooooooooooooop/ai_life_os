# Lite 模式

适用于：Debug、单文件修改、快速修复

## 目录结构

```
.taskflow/active/[task-name]/progress.md
```

## 核心规则

1. **2-Action Rule**：每 2 次操作更新 progress.md
2. **3-Strike Protocol**：3 次失败后升级用户

## Trace Stub 格式

```markdown
## Trace Stub
**目标**：[一句话描述]
**当前假设**：[正在验证的假设]
**已排除**：[已证伪的假设]
```

## 完成条件

- 问题解决
- 用户确认可以结束
