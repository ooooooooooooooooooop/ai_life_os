# USER.md — 用户行为画像（系统观察归纳，非用户自述）

## 设计原则
# 此文件所有字段均由系统从行为数据中归纳，不依赖用户主动填写。
# 用户说出来的偏好是社会期望脚本，行为数据才反映真实驱动力。
# 每次复盘后由 retrospective.py 自动更新。

## 观察到的行为模式（系统归纳）

actual_active_hours: []         # 实际产生任务完成事件的时间段（非用户声称的）
actual_task_duration_median: "" # 实际完成任务的中位时长（非偏好声明）
frequently_completed_types: ['flourishing_session']  # 哪类任务实际完成率最高
frequently_skipped_types: ['substrate_task']  # 哪类任务实际跳过率最高
skip_pattern_context: []        # 跳过任务时的情境规律（时间段/前置任务/情绪信号）

## 观察到的本能劫持模式（系统归纳）

hijack_triggers: ['连续跳过深度工作任务']  # 反复出现的跳过/放弃情境
hijack_frequency: 0  # 本周劫持次数
resistance_pattern: ""          # 对 Guardian 干预的响应模式：responsive/resistant/inconsistent

## 脚本重写进度（系统追踪）

scripts_being_rewritten: []     # 当前正在干预的自动脚本列表
rewrite_evidence: []            # 行为数据中出现的正向改变证据
stagnant_scripts: []            # 持续干预但无改变的脚本（需要换策略）

## 基础环境（唯一允许用户声明的部分）

timezone: ""                    # 影响时间计算，允许用户告知
language: "zh"

## 元数据

last_observed: 2026-03-18  # 最后一次行为数据更新时间
observation_sample_size: 0  # 已观察的事件总数（样本量越大归纳越可信）
