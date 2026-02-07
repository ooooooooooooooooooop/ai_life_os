# unified-taskflow 治理规范 v1.1

## 一、目录隔离（强制）

### 1.1 目录结构

```text
.taskflow/
├── index.json           # 任务索引
├── active/              # 当前活跃任务（仅限一个）
│   └── [task-name]/
└── archive/             # 归档任务
    └── [YYYY-MM-DD]_[task-name]_v[N]/
```

### 1.2 规则

| 规则 | 描述 |
|------|------|
| 单活跃限制 | `active/` 下同时只允许一个任务 |
| 隔离检查 | 新任务开始前必须检查 `active/` |
| 归档命名 | `日期_任务名_版本` |

### 1.3 生命周期状态

```text
NEW → ACTIVE → COMPLETED / ABANDONED
         ↑          ↓
         ←── RESUMED ──
```

---

## 二、档位定义

| 档位 | 门禁 | 角色 | 目录内容 |
|------|------|------|----------|
| Lite | 无 | 单角色 | `progress.md` |
| Standard | 软 | 软分离 | `task_plan.md` + `progress.md` |
| Spec-Driven | 硬 | Architect/Builder | 全链路文档 |

---

## 三、档位切换

- **默认**：Standard
- **升级**：AI 可建议，单向
- **降级**：需用户确认风险

---

## 四、门禁例外

### Grounding Window
- 最多 6 次只读
- 结束输出 Summary

### Debug Window
- 2-Action 放宽为 4-Action
- 保留 3-Strike

---

## 五、最小记录

| 档位 | 要求 |
|------|------|
| Lite | Trace Stub |
| Standard | `task_plan.md` 完整 |
| Spec-Driven | 全链路 |

---

## 六、角色分离

| 模式 | 规则 |
|------|------|
| Lite | 单角色，禁跨阶段推理 |
| Standard | 软分离，显式标注 `[Planning]`/`[Executing]` |
| Spec-Driven | 硬分离，切换需批准 |

---

## 七、Traceability

| 档位 | 要求 |
|------|------|
| Lite | 无 |
| Standard | 推荐 |
| Spec-Driven | 强制全链路 |
