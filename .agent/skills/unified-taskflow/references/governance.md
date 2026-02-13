# unified-taskflow 治理规范 v3.0

## 一、目录隔离（强制）

### 1.1 目录结构

```text
.taskflow/
├── index.json           # 任务索引
├── active/              # 当前活跃任务（仅限一个）
│   └── [task-name]/
│       ├── anchor.md        # 北极星文件（必须）
│       ├── checkpoint.md    # 校验点记录（必须）
│       └── design.md        # 技术设计（按需）
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

## 二、anchor.md 更新协议

anchor.md 是任务的唯一真相来源，修改需遵守：

| 场景 | 动作 |
|------|------|
| Phase 0 完成时 | 首次创建，由用户确认内容 |
| 用户修改需求时 | 更新对应字段，记录变更原因 |
| Agent 发现歧义时 | 暂停执行，提议修改，用户确认后更新 |
| 禁止 | Agent 单方面修改 anchor.md 而不告知用户 |

---

## 三、Re-grounding 触发规则

| 触发条件 | 动作 |
|----------|------|
| 子任务完成 | 回读 anchor.md，写入对齐判定到 checkpoint.md |
| 每 3-5 步操作 | 同上 |
| 遇到不确定性 | 同上，若偏移则暂停请示用户 |
| 用户补充新信息 | 先更新 anchor.md，再回读确认 |

---

## 四、门禁例外

### Debug Window
- 2-Action Rule 放宽为 4-Action
- 保留 3-Strike Protocol
- 连续失败时触发额外 Re-grounding

---

## 五、最小记录

| 文件 | 要求 |
|------|------|
| anchor.md | 必须，Phase 0 完成后创建 |
| checkpoint.md | 必须，执行期间持续更新 |
| design.md | 按需，复杂任务时生成 |
