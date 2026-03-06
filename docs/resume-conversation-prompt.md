# AI Life OS - 重开对话提示词

---

## 📋 项目背景

**项目名称**: AI Life OS
**当前版本**: v3.0 Eudaimonia Guardian Edition
**项目状态**: 生产就绪
**最后更新**: 2026-03-06

**项目简介**: AI Life OS 是一个由 AI 驱动的个人生活操作系统，通过Guardian系统帮助用户管理时间、习惯和目标，守护用户走向更好的生活。

---

## 🎯 当前状态

### 已完成功能
- ✅ Phase 1-6 全部完成
- ✅ 事件溯源系统（Schema v1.0）
- ✅ Guardian复盘引擎（5种偏差信号）
- ✅ 本能劫持检测（任务放弃、重复推迟）
- ✅ Safe Mode（完整用户体验）
- ✅ Authority系统（三级干预级别）
- ✅ 文件传感器（反证信号检测）
- ✅ 性能优化（53.3%提升）

### 系统指标
- **测试**: 183项通过，0项失败
- **性能**: 复盘生成18.52ms（优化前37.51ms）
- **代码**: 10,944行核心代码，无技术债务
- **文档**: 完整文档体系

---

## 📂 关键文件位置

### 核心代码
- `core/retrospective.py` - Guardian复盘引擎（3786行）
- `core/event_sourcing.py` - 事件溯源
- `core/file_sensor.py` - 文件传感器
- `core/config_cache.py` - 配置缓存
- `core/objective_engine/registry.py` - GoalRegistry单例

### 文档
- `docs/roadmap_2026.md` - 路线图
- `docs/project-status-summary.md` - 项目状态总结
- `docs/api-documentation.md` - API文档
- `README_zh.md` - 项目介绍

### 任务归档
- `.taskflow/archive/iteration9-evidence-loop/` - 证据化闭环
- `.taskflow/archive/iteration10-instinct-hijack-detection/` - 本能劫持检测
- `.taskflow/archive/iteration11-safe-mode-enhancement/` - Safe Mode完善
- `.taskflow/archive/iteration12-authority-enhancement/` - Authority系统增强
- `.taskflow/archive/iteration13-system-optimization/` - 系统优化
- `.taskflow/archive/iteration14-config-cache/` - 配置缓存
- `.taskflow/archive/iteration15-goal-registry-singleton/` - GoalRegistry单例
- `.taskflow/archive/iteration16-file-sensors/` - 文件传感器

---

## 🚀 下一步工作

### 短期（1周内）
1. 扩展文件传感器监控范围
2. 实现实时文件监控
3. 建立性能监控体系

### 中期（1个月内）
1. 不确定性处理优化
2. 用户体验优化
3. 机器学习集成

---

## 💡 重开对话提示词

```
你好，我是AI Life OS项目的开发者。

项目当前状态：
- 版本：v3.0 Eudaimonia Guardian Edition
- 状态：生产就绪
- 测试：183项通过，0项失败
- 性能：复盘生成18.52ms（优化前37.51ms，提升53.3%）

已完成功能：
- Phase 1-6 全部完成
- 事件溯源系统（Schema v1.0）
- Guardian复盘引擎（5种偏差信号）
- 本能劫持检测（任务放弃、重复推迟）
- Safe Mode（完整用户体验）
- Authority系统（三级干预级别）
- 文件传感器（反证信号检测）
- 性能优化（配置缓存、GoalRegistry单例）

关键文件：
- core/retrospective.py - Guardian复盘引擎
- core/file_sensor.py - 文件传感器
- docs/project-status-summary.md - 项目状态总结

下一步工作：
- 扩展文件传感器监控范围
- 实现实时文件监控
- 建立性能监控体系

请帮我继续推进项目开发。
```

---

## 📊 快速参考

### 测试命令
```bash
# 运行所有测试
python -m pytest tests/ -v --tb=short

# 运行特定测试
python -m pytest tests/test_file_sensor.py -v

# 性能测试
python -c "from core.retrospective import build_guardian_retrospective_response; import time; s=time.time(); build_guardian_retrospective_response(7); print(f'{(time.time()-s)*1000:.2f}ms')"
```

### 关键API
```python
# Guardian复盘
from core.retrospective import build_guardian_retrospective_response
response = build_guardian_retrospective_response(7)

# 文件传感器
from core.file_sensor import scan_files, analyze_file_signals
changes = scan_files()
signals = analyze_file_signals(24)

# 状态重建
from core.event_sourcing import rebuild_state
state = rebuild_state()
```

---

## 🎯 注意事项

1. **测试隔离**: 使用`clear_goal_registry_singleton` fixture确保测试隔离
2. **单例模式**: GoalRegistry使用单例模式，测试时需清除
3. **配置缓存**: YAML配置已缓存，修改配置后需清除缓存
4. **文件传感器**: 首次使用需先扫描文件

---

**使用说明**: 复制上面的"重开对话提示词"到新对话中，即可快速恢复项目上下文。
