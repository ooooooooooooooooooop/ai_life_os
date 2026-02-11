import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { api } from '../utils/api';

function buildTreeFromState(visions = [], objectives = [], goals = []) {
    const node = (n) => ({ ...n, children: [] });
    const byParent = (list, parentId) => list.filter((x) => (x.parent_id || null) === parentId);

    const trees = [];
    for (const vision of visions) {
        const visionNode = node(vision);
        const objectiveNodes = byParent(objectives, vision.id);
        for (const objective of objectiveNodes) {
            const objectiveNode = node(objective);
            objectiveNode.children = byParent(goals, objective.id).map((goal) => node(goal));
            visionNode.children.push(objectiveNode);
        }
        visionNode.children.push(...byParent(goals, vision.id).map((goal) => node(goal)));
        trees.push(visionNode);
    }
    return trees;
}

function OverlayModal({ open, title, children, onCancel, onConfirm, confirmText, disabled }) {
    if (!open) return null;
    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                background: 'rgba(0, 0, 0, 0.55)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 1000,
                padding: '1rem'
            }}
            onClick={onCancel}
        >
            <div
                className="glass-card"
                style={{ width: '100%', maxWidth: '520px', padding: '1rem' }}
                onClick={(e) => e.stopPropagation()}
            >
                <h4 style={{ marginTop: 0, marginBottom: '0.75rem' }}>{title}</h4>
                {children}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem', marginTop: '1rem' }}>
                    <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={disabled}>
                        取消
                    </button>
                    <button type="button" className="btn btn-primary" onClick={onConfirm} disabled={disabled}>
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
}

export default function Home() {
    const [profile, setProfile] = useState(null);
    const [goals, setGoals] = useState({ active: [], completed: [] });
    const [goalTree, setGoalTree] = useState([]);
    const [tasks, setTasks] = useState({ pending: [], completed: [] });
    const [currentTask, setCurrentTask] = useState(null);
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState(false);
    const [error, setError] = useState(null);
    const [viewMode, setViewMode] = useState('execute');
    const [retrospective, setRetrospective] = useState(null);
    const [weeklyReviewDue, setWeeklyReviewDue] = useState(false);
    const [anchorSnapshot, setAnchorSnapshot] = useState(null);
    const [alignmentOverview, setAlignmentOverview] = useState(null);
    const [weeklyAlignmentTrend, setWeeklyAlignmentTrend] = useState(null);
    const [anchorEffect, setAnchorEffect] = useState(null);

    const [skipDialogOpen, setSkipDialogOpen] = useState(false);
    const [skipReason, setSkipReason] = useState('');
    const [skipContext, setSkipContext] = useState('recovering');
    const [deleteTargetGoalId, setDeleteTargetGoalId] = useState(null);
    const [guardianResponseLoading, setGuardianResponseLoading] = useState(false);
    const [guardianResponseContext, setGuardianResponseContext] = useState('recovering');
    const [anchorDiff, setAnchorDiff] = useState(null);
    const [anchorDiffLoading, setAnchorDiffLoading] = useState(false);
    const [activateAnchorLoading, setActivateAnchorLoading] = useState(false);
    const [activateAnchorModalOpen, setActivateAnchorModalOpen] = useState(false);
    const [guardianConfig, setGuardianConfig] = useState(null);
    const [guardianConfigLoading, setGuardianConfigLoading] = useState(false);
    const [guardianConfigSaving, setGuardianConfigSaving] = useState(false);
    const [guardianConfigDirty, setGuardianConfigDirty] = useState(false);
    const [guardianConfigSavedAt, setGuardianConfigSavedAt] = useState(null);
    const [l2SessionActionLoading, setL2SessionActionLoading] = useState(false);
    const [l2InterruptReason, setL2InterruptReason] = useState('context_switch');
    const [l2StartIntention, setL2StartIntention] = useState('');
    const [l2ResumeStep, setL2ResumeStep] = useState('');
    const [l2CompletionReflection, setL2CompletionReflection] = useState('');
    const [recoveryBatchLoading, setRecoveryBatchLoading] = useState(false);

    const signalNameMap = {
        repeated_skip: '重复跳过',
        l2_interruption: '深度时段中断',
        stagnation: '推进停滞'
    };
    const escalationStageMap = {
        gentle_nudge: '温和提醒',
        firm_reminder: '坚定提醒',
        periodic_check: '周期检查'
    };
    const responseContextLabelMap = {
        recovering: '恢复精力',
        resource_blocked: '资源受阻',
        task_too_big: '任务过大',
        instinct_escape: '本能逃避'
    };
    const responseContextHintMap = {
        recovering: '先恢复状态，再继续推进。',
        resource_blocked: '当前被资源或外部条件卡住。',
        task_too_big: '先拆成最小下一步，降低启动阻力。',
        instinct_escape: '正在被即时满足牵引，偏离长期价值。'
    };
    const l2InterruptReasonLabelMap = {
        context_switch: '上下文切换',
        external_interrupt: '外部打断',
        energy_drop: '精力下滑',
        tooling_blocked: '工具阻塞',
        other: '其他'
    };
    const supportModeLabelMap = {
        support_heavy: '支持优先',
        balanced: '支持/覆盖平衡',
        override_heavy: '覆盖优先',
        insufficient_data: '数据不足'
    };
    const responseContextOptions = [
        { value: 'recovering', label: '恢复精力' },
        { value: 'resource_blocked', label: '资源受阻' },
        { value: 'task_too_big', label: '任务过大' },
        { value: 'instinct_escape', label: '本能逃避' }
    ];

    const severityStyleMap = {
        high: { background: 'rgba(239, 68, 68, 0.2)', color: '#fca5a5', border: '1px solid rgba(239, 68, 68, 0.4)' },
        medium: { background: 'rgba(245, 158, 11, 0.2)', color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.35)' },
        info: { background: 'rgba(59, 130, 246, 0.2)', color: '#93c5fd', border: '1px solid rgba(59, 130, 246, 0.35)' }
    };
    const alignmentLevelStyleMap = {
        high: { color: '#86efac', border: '1px solid rgba(34, 197, 94, 0.4)', background: 'rgba(34, 197, 94, 0.15)' },
        medium: { color: '#fcd34d', border: '1px solid rgba(245, 158, 11, 0.4)', background: 'rgba(245, 158, 11, 0.15)' },
        low: { color: '#fca5a5', border: '1px solid rgba(239, 68, 68, 0.4)', background: 'rgba(239, 68, 68, 0.15)' },
        unknown: { color: '#cbd5e1', border: '1px solid rgba(148, 163, 184, 0.35)', background: 'rgba(148, 163, 184, 0.12)' }
    };

    const formatAlignmentLevel = (level) => {
        if (level === 'high') return '高对齐';
        if (level === 'medium') return '中对齐';
        if (level === 'low') return '低对齐';
        return '待评估';
    };

    useEffect(() => {
        fetchAll();
    }, []);

    useEffect(() => {
        const latestContext = retrospective?.response_action?.latest?.context;
        if (latestContext) {
            setGuardianResponseContext(latestContext);
            return;
        }
        const defaultContext = retrospective?.response_action?.default_context;
        if (defaultContext) {
            setGuardianResponseContext(defaultContext);
        }
    }, [retrospective?.response_action?.fingerprint]);

    useEffect(() => {
        const options = retrospective?.l2_session_action?.interrupt?.reason_options || [];
        if (!Array.isArray(options) || options.length === 0) return;
        const allowed = new Set(options.map((opt) => opt?.value).filter(Boolean));
        if (!allowed.has(l2InterruptReason)) {
            setL2InterruptReason(options[0]?.value || 'context_switch');
        }
    }, [retrospective?.l2_session_action?.active_session_id]);

    useEffect(() => {
        const minimalStep = retrospective?.l2_session_action?.resume?.minimal_step
            || retrospective?.l2_session?.resume_hint
            || '';
        if (minimalStep) {
            setL2ResumeStep(minimalStep);
        } else if (!retrospective?.l2_session?.resume_ready) {
            setL2ResumeStep('');
        }
    }, [
        retrospective?.l2_session_action?.resume?.session_id,
        retrospective?.l2_session?.resume_ready,
        retrospective?.l2_session?.resume_hint
    ]);

    const fetchAll = async () => {
        try {
            setLoading(true);
            setError(null);

            const stateRes = await api.get('/state').catch(() => null);
            if (stateRes?.data) {
                const s = stateRes.data;
                setWeeklyReviewDue(Boolean(s.weekly_review_due));
                setAnchorSnapshot(s.anchor || null);
                setAlignmentOverview(s.alignment?.goal_summary || null);
                setWeeklyAlignmentTrend(s.alignment?.weekly_trend || null);
                if (s.identity) {
                    setProfile({
                        occupation: s.identity.occupation ?? '',
                        focus_area: s.identity.focus_area ?? '',
                        daily_hours: s.identity.daily_hours ?? '',
                        ...s.identity
                    });
                }
                const allGoals = s.goals || [];
                setGoals({
                    active: allGoals.filter((g) => g.state === 'active'),
                    completed: allGoals.filter((g) => g.state === 'completed')
                });
                setGoalTree(buildTreeFromState(s.visions || [], s.objectives || [], allGoals));
            } else {
                setAnchorSnapshot(null);
                setAlignmentOverview(null);
                setWeeklyAlignmentTrend(null);
                setAnchorEffect(null);
                setGuardianConfig(null);
                const [profileRes, goalsRes, treeRes] = await Promise.allSettled([
                    api.get('/onboarding/status'),
                    api.get('/goals'),
                    api.get('/goals/tree')
                ]);
                if (profileRes.status === 'fulfilled') setProfile(profileRes.value.data.profile);
                if (goalsRes.status === 'fulfilled') {
                    const nodes = goalsRes.value.data.goals || [];
                    setGoals({
                        active: nodes.filter((g) => g.state === 'active'),
                        completed: nodes.filter((g) => g.state === 'completed')
                    });
                }
                if (treeRes.status === 'fulfilled') setGoalTree(treeRes.value.data.tree || []);
            }

            const [tasksRes, currentRes, retroRes, effectRes, guardianConfigRes] = await Promise.allSettled([
                api.get('/tasks/list'),
                api.get('/tasks/current'),
                api.get('/retrospective', { params: { days: 7 } }),
                api.get('/anchor/effect'),
                api.get('/guardian/config')
            ]);
            if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value.data);
            if (currentRes.status === 'fulfilled') setCurrentTask(currentRes.value.data.task);
            if (retroRes.status === 'fulfilled') setRetrospective(retroRes.value.data);
            if (effectRes.status === 'fulfilled') setAnchorEffect(effectRes.value.data);
            if (guardianConfigRes.status === 'fulfilled') {
                setGuardianConfig(guardianConfigRes.value.data?.config || null);
                setGuardianConfigDirty(false);
            }
        } catch (e) {
            console.error(e);
            setError('加载数据失败');
        } finally {
            setLoading(false);
        }
    };

    const handleComplete = async () => {
        if (!currentTask || actionLoading) return;
        try {
            setActionLoading(true);
            setError(null);
            await api.post(`/tasks/${currentTask.id}/complete`);
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('完成任务失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const openSkipDialog = () => {
        if (!currentTask || actionLoading) return;
        setSkipReason('');
        setSkipContext('recovering');
        setSkipDialogOpen(true);
    };

    const submitSkip = async () => {
        if (!currentTask || actionLoading) return;
        if (!skipReason.trim()) {
            setError('请输入跳过原因');
            return;
        }
        try {
            setActionLoading(true);
            setError(null);
            await api.post(`/tasks/${currentTask.id}/skip`, {
                reason: skipReason.trim(),
                context: skipContext
            });
            setSkipDialogOpen(false);
            setSkipReason('');
            setSkipContext('recovering');
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('跳过任务失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const askDeleteGoal = (goalId, e) => {
        e?.preventDefault();
        e?.stopPropagation();
        if (actionLoading) return;
        setDeleteTargetGoalId(goalId);
    };

    const confirmDeleteGoal = async () => {
        if (!deleteTargetGoalId || actionLoading) return;
        try {
            setActionLoading(true);
            setError(null);
            await api.delete(`/goals/${deleteTargetGoalId}`);
            setDeleteTargetGoalId(null);
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('删除失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const handleGuardianResponse = async (action) => {
        if (!retrospective || guardianResponseLoading) return;
        try {
            setGuardianResponseLoading(true);
            setError(null);
            await api.post('/retrospective/respond', {
                days: retrospective.period?.days ?? 7,
                fingerprint:
                    retrospective.response_action?.fingerprint
                    ?? retrospective.confirmation_action?.fingerprint
                    ?? null,
                action,
                context: guardianResponseContext
            });
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('提交 Guardian 响应失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setGuardianResponseLoading(false);
        }
    };

    const handleConfirmIntervention = async () => {
        await handleGuardianResponse('confirm');
    };

    const handleApplyRecoveryBatch = async () => {
        if (recoveryBatchLoading) return;
        try {
            setRecoveryBatchLoading(true);
            setError(null);
            await api.post('/tasks/recovery/batch/apply');
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('应用恢复批处理失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setRecoveryBatchLoading(false);
        }
    };

    const handleL2SessionAction = async (action) => {
        if (l2SessionActionLoading) return;
        const actionSpec = retrospective?.l2_session_action || {};
        const activeSessionId = retrospective?.l2_session?.active_session_id || null;
        const resumeSessionId = retrospective?.l2_session?.resume_session_id
            || actionSpec?.resume?.session_id
            || null;
        const endpointMap = {
            start: actionSpec.start?.endpoint || '/l2/session/start',
            resume: actionSpec.resume?.endpoint || '/l2/session/resume',
            interrupt: actionSpec.interrupt?.endpoint || '/l2/session/interrupt',
            complete: actionSpec.complete?.endpoint || '/l2/session/complete'
        };
        const endpoint = endpointMap[action];
        if (!endpoint) return;

        const payload = {};
        if (action !== 'start' && action !== 'resume' && activeSessionId) {
            payload.session_id = activeSessionId;
        }
        if (action === 'resume' && resumeSessionId) {
            payload.session_id = resumeSessionId;
        }
        if (action === 'interrupt') {
            payload.reason = l2InterruptReason;
        }
        if (action === 'start') {
            const intention = (l2StartIntention || '').trim();
            if (intention) payload.intention = intention;
        }
        if (action === 'resume') {
            const step = (l2ResumeStep || '').trim();
            if (step) payload.resume_step = step;
        }
        if (action === 'complete') {
            const reflection = (l2CompletionReflection || '').trim();
            if (reflection) payload.reflection = reflection;
        }

        try {
            setL2SessionActionLoading(true);
            setError(null);
            await api.post(endpoint, payload);
            if (action === 'start') {
                setL2StartIntention('');
            } else if (action === 'resume') {
                setL2ResumeStep('');
            } else if (action === 'complete') {
                setL2CompletionReflection('');
            }
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('更新 L2 会话失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setL2SessionActionLoading(false);
        }
    };

    const handleCheckAnchorDiff = async () => {
        if (anchorDiffLoading) return;
        try {
            setAnchorDiffLoading(true);
            setError(null);
            const res = await api.get('/anchor/diff');
            setAnchorDiff(res.data || null);
        } catch (e) {
            console.error(e);
            setError('检查 Anchor 变更失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setAnchorDiffLoading(false);
        }
    };

    const handleActivateAnchor = async () => {
        if (activateAnchorLoading) return;
        try {
            setActivateAnchorLoading(true);
            setError(null);
            const res = await api.post('/anchor/activate', { force: false });
            if (res.data?.effect) {
                setAnchorEffect(res.data.effect);
            }
            if (res.data?.status === 'noop') {
                setError('Anchor 内容无变化，无需激活');
            }
            setActivateAnchorModalOpen(false);
            setAnchorDiff(null);
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('激活 Anchor 失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setActivateAnchorLoading(false);
        }
    };

    const updateGuardianConfigField = (section, key, rawValue) => {
        setGuardianConfig((prev) => {
            if (!prev?.thresholds) return prev;
            return {
                ...prev,
                thresholds: {
                    ...prev.thresholds,
                    [section]: {
                        ...(prev.thresholds?.[section] || {}),
                        [key]: rawValue
                    }
                }
            };
        });
        setGuardianConfigDirty(true);
    };

    const updateGuardianInterventionLevel = (value) => {
        setGuardianConfig((prev) => {
            if (!prev) return prev;
            return { ...prev, intervention_level: value };
        });
        setGuardianConfigDirty(true);
    };

    const refreshGuardianConfig = async () => {
        if (guardianConfigLoading) return;
        try {
            setGuardianConfigLoading(true);
            const res = await api.get('/guardian/config');
            setGuardianConfig(res.data?.config || null);
            setGuardianConfigDirty(false);
        } catch (e) {
            console.error(e);
            setError('刷新阈值配置失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setGuardianConfigLoading(false);
        }
    };

    const saveGuardianConfig = async () => {
        if (!guardianConfig || guardianConfigSaving) return;
        try {
            setGuardianConfigSaving(true);
            setError(null);
            const payload = {
                intervention_level: guardianConfig.intervention_level || 'SOFT',
                deviation_signals: {
                    repeated_skip: Number(guardianConfig.thresholds?.deviation_signals?.repeated_skip ?? 2),
                    l2_interruption: Number(guardianConfig.thresholds?.deviation_signals?.l2_interruption ?? 1),
                    stagnation_days: Number(guardianConfig.thresholds?.deviation_signals?.stagnation_days ?? 3)
                },
                l2_protection: {
                    high: Number(guardianConfig.thresholds?.l2_protection?.high ?? 0.75),
                    medium: Number(guardianConfig.thresholds?.l2_protection?.medium ?? 0.5)
                }
            };
            if (guardianConfig.authority) {
                payload.authority = {
                    escalation: {
                        window_days: Number(guardianConfig.authority?.escalation?.window_days ?? 7),
                        firm_reminder_resistance: Number(guardianConfig.authority?.escalation?.firm_reminder_resistance ?? 2),
                        periodic_check_resistance: Number(guardianConfig.authority?.escalation?.periodic_check_resistance ?? 4)
                    },
                    safe_mode: {
                        enabled: Boolean(guardianConfig.authority?.safe_mode?.enabled ?? true),
                        resistance_threshold: Number(guardianConfig.authority?.safe_mode?.resistance_threshold ?? 5),
                        min_response_events: Number(guardianConfig.authority?.safe_mode?.min_response_events ?? 3),
                        max_confirmation_ratio: Number(guardianConfig.authority?.safe_mode?.max_confirmation_ratio ?? 0.34),
                        recovery_confirmations: Number(guardianConfig.authority?.safe_mode?.recovery_confirmations ?? 2),
                        cooldown_hours: Number(guardianConfig.authority?.safe_mode?.cooldown_hours ?? 24)
                    }
                };
            }
            const res = await api.put('/guardian/config', payload);
            setGuardianConfig(res.data?.config || guardianConfig);
            setGuardianConfigDirty(false);
            setGuardianConfigSavedAt(new Date().toISOString());
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('保存 Guardian 阈值失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setGuardianConfigSaving(false);
        }
    };

    const getGoalProgress = (goalId) => {
        const goalTasks = [...(tasks.pending || []), ...(tasks.completed || [])].filter((t) => t.goal_id === goalId);
        const completedCount = (tasks.completed || []).filter((t) => t.goal_id === goalId).length;
        return { completed: completedCount, total: goalTasks.length };
    };

    const standaloneGoals = useMemo(
        () => (goals.active || []).filter((g) => !g.parent_id && g.layer !== 'vision'),
        [goals.active]
    );
    const anchorDiffStatus = anchorDiff?.diff?.status || null;
    const canActivateAnchor = anchorDiffStatus === 'new' || anchorDiffStatus === 'changed';
    const effectBeforeAvg = Number(anchorEffect?.before?.avg_score);
    const effectAfterAvg = Number(anchorEffect?.after?.avg_score);
    const hasEffectDelta = Number.isFinite(effectBeforeAvg) && Number.isFinite(effectAfterAvg);
    const effectDeltaLabel = hasEffectDelta
        ? `${effectAfterAvg - effectBeforeAvg >= 0 ? '+' : ''}${(effectAfterAvg - effectBeforeAvg).toFixed(1)}`
        : '--';
    const l2ProtectionRatio = Number(retrospective?.l2_protection?.ratio);
    const l2ProtectionLabel = Number.isFinite(l2ProtectionRatio)
        ? `${Math.round(l2ProtectionRatio * 100)}%`
        : '--';
    const l2ProtectionLevel = retrospective?.l2_protection?.level || 'unknown';
    const l2ProtectionColorMap = {
        high: '#86efac',
        medium: '#fcd34d',
        low: '#fca5a5',
        unknown: '#cbd5e1'
    };
    const l2TrendPoints = (retrospective?.l2_protection?.trend || []).slice(-7);
    const l2ThresholdHigh = Number(retrospective?.l2_protection?.thresholds?.high);
    const l2ThresholdMedium = Number(retrospective?.l2_protection?.thresholds?.medium);
    const l2ThresholdLabel = Number.isFinite(l2ThresholdHigh) && Number.isFinite(l2ThresholdMedium)
        ? `阈值: 高 ≥ ${Math.round(l2ThresholdHigh * 100)}% · 中 ≥ ${Math.round(l2ThresholdMedium * 100)}%`
        : null;
    const guardianAuthority = retrospective?.authority || {};
    const guardianEscalation = guardianAuthority?.escalation || {};
    const guardianSafeMode = guardianAuthority?.safe_mode || {};
    const guardianEscalationStage = guardianEscalation?.stage || 'gentle_nudge';
    const guardianEscalationLabel = escalationStageMap[guardianEscalationStage] || guardianEscalationStage;
    const guardianLatestResponse = retrospective?.response_action?.latest || null;
    const guardianLatestRecoveryStep = guardianLatestResponse?.recovery_step || null;
    const guardianRole = retrospective?.guardian_role || {};
    const guardianRoleRepresentingLabel = guardianRole?.representing_label || '价值自我';
    const guardianRoleFacingLabel = guardianRole?.facing_label || '本能自我';
    const guardianRoleMessage = guardianRole?.message || '系统正在代表价值自我，守护长期目标。';
    const guardianLatestResponseContextLabel = guardianLatestResponse?.context_label
        || responseContextLabelMap[guardianLatestResponse?.context]
        || guardianLatestResponse?.context
        || '--';
    const humanizationMetrics = retrospective?.humanization_metrics || {};
    const recoveryAdoptionMetric = humanizationMetrics?.recovery_adoption_rate || {};
    const recoveryAdoptionRate = Number(recoveryAdoptionMetric?.rate);
    const recoveryAdoptionLabel = Number.isFinite(recoveryAdoptionRate)
        ? `${Math.round(recoveryAdoptionRate * 100)}%`
        : '--';
    const frictionLoadMetric = humanizationMetrics?.friction_load || {};
    const frictionLoadScore = Number(frictionLoadMetric?.score);
    const frictionLoadLabel = Number.isFinite(frictionLoadScore)
        ? `${Math.round(frictionLoadScore * 100)}%`
        : '--';
    const frictionLoadLevel = frictionLoadMetric?.level || 'unknown';
    const frictionLoadColorMap = {
        high: '#fca5a5',
        medium: '#fcd34d',
        low: '#86efac',
        unknown: '#cbd5e1'
    };
    const supportVsOverrideMetric = humanizationMetrics?.support_vs_override || {};
    const supportVsOverrideRatio = Number(supportVsOverrideMetric?.support_ratio);
    const supportVsOverrideLabel = Number.isFinite(supportVsOverrideRatio)
        ? `${Math.round(supportVsOverrideRatio * 100)}%`
        : '--';
    const supportVsOverrideMode = supportVsOverrideMetric?.mode || 'insufficient_data';
    const supportVsOverrideModeLabel = supportModeLabelMap[supportVsOverrideMode] || supportVsOverrideMode;
    const interventionPolicy = retrospective?.intervention_policy || {};
    const interventionPolicyModeMap = {
        support_recovery: '支持恢复',
        focused_override: '坚定纠偏',
        low_frequency_observe: '低频观察',
        balanced_intervention: '平衡干预'
    };
    const interventionPolicyMode = interventionPolicy?.mode || 'balanced_intervention';
    const interventionPolicyLabel = interventionPolicyModeMap[interventionPolicyMode] || interventionPolicyMode;
    const interventionFrictionBudget = interventionPolicy?.friction_budget || {};
    const reminderWindowLabel = interventionFrictionBudget?.window_hours
        ? `${interventionFrictionBudget.recent_prompt_count ?? 0}/${interventionFrictionBudget.max_prompts ?? '--'} (${interventionFrictionBudget.window_hours}h)`
        : '--';
    const interventionSuppressed = Boolean(interventionFrictionBudget?.suppressed);
    const interventionCooldownLabel = interventionFrictionBudget?.cooldown_active
        ? `${interventionFrictionBudget.cooldown_remaining_minutes ?? 0} 分钟`
        : '无';
    const northStarMetrics = retrospective?.north_star_metrics || {};
    const northStarTargets = northStarMetrics?.targets_met || {};
    const mundaneCoverageMetric = northStarMetrics?.mundane_automation_coverage || {};
    const mundaneCoverageRate = Number(mundaneCoverageMetric?.rate);
    const mundaneCoverageLabel = Number.isFinite(mundaneCoverageRate)
        ? `${Math.round(mundaneCoverageRate * 100)}%`
        : '--';
    const l2BloomMetric = northStarMetrics?.l2_bloom_hours || {};
    const l2BloomHours = Number(l2BloomMetric?.hours);
    const l2BloomBaseline = Number(l2BloomMetric?.baseline_hours);
    const l2BloomDeltaRatio = Number(l2BloomMetric?.delta_ratio);
    const l2BloomHoursLabel = Number.isFinite(l2BloomHours) ? `${l2BloomHours.toFixed(1)}h` : '--';
    const l2BloomDeltaLabel = Number.isFinite(l2BloomDeltaRatio)
        ? `${l2BloomDeltaRatio >= 0 ? '+' : ''}${Math.round(l2BloomDeltaRatio * 100)}%`
        : '--';
    const humanTrustMetric = northStarMetrics?.human_trust_index || {};
    const humanTrustScore = Number(humanTrustMetric?.score);
    const humanTrustLabel = Number.isFinite(humanTrustScore)
        ? `${Math.round(humanTrustScore * 100)}%`
        : '--';
    const alignmentDeltaMetric = northStarMetrics?.alignment_delta_weekly || {};
    const alignmentDeltaValue = Number(alignmentDeltaMetric?.delta);
    const alignmentDeltaLabel = Number.isFinite(alignmentDeltaValue)
        ? `${alignmentDeltaValue >= 0 ? '+' : ''}${alignmentDeltaValue.toFixed(1)}`
        : '--';
    const northStarMetCount = Number(northStarTargets?.met_count);
    const northStarTotal = Number(northStarTargets?.total);
    const northStarSummaryLabel = Number.isFinite(northStarMetCount) && Number.isFinite(northStarTotal) && northStarTotal > 0
        ? `${northStarMetCount}/${northStarTotal} 达标`
        : '暂无达标统计';
    const metricStatusLabel = (flag) => {
        if (flag === true) return '达标';
        if (flag === false) return '未达标';
        return '待评估';
    };
    const explainability = retrospective?.explainability || {};
    const guardianExplainWhy = explainability?.why_this_suggestion
        || retrospective?.suggestion
        || '暂无解释';
    const guardianExplainNext = explainability?.what_happens_next
        || '系统将继续观察并在下一轮复盘更新建议。';
    const guardianExplainSignals = Array.isArray(explainability?.active_signals)
        ? explainability.active_signals
        : [];
    const l2Session = retrospective?.l2_session || {};
    const l2SessionAction = retrospective?.l2_session_action || {};
    const l2SessionActive = Boolean(l2Session?.active_session);
    const l2SessionActiveId = l2Session?.active_session_id || null;
    const l2SessionResumeReady = Boolean(l2Session?.resume_ready);
    const l2SessionResumeId = l2Session?.resume_session_id || l2SessionAction?.resume?.session_id || null;
    const l2SessionResumeHint = l2SessionAction?.resume?.minimal_step || l2Session?.resume_hint || '';
    const l2SessionCompletionRate = Number(l2Session?.completion_rate);
    const l2SessionCompletionLabel = Number.isFinite(l2SessionCompletionRate)
        ? `${Math.round(l2SessionCompletionRate * 100)}%`
        : '--';
    const l2SessionRecoveryRate = Number(l2Session?.recovery_rate);
    const l2SessionRecoveryLabel = Number.isFinite(l2SessionRecoveryRate)
        ? `${Math.round(l2SessionRecoveryRate * 100)}%`
        : '--';
    const l2MicroRitual = l2Session?.micro_ritual || {};
    const l2StartIntentionRate = Number(l2MicroRitual?.start_intention_rate);
    const l2StartIntentionRateLabel = Number.isFinite(l2StartIntentionRate)
        ? `${Math.round(l2StartIntentionRate * 100)}%`
        : '--';
    const l2CompletionReflectionRate = Number(l2MicroRitual?.completion_reflection_rate);
    const l2CompletionReflectionRateLabel = Number.isFinite(l2CompletionReflectionRate)
        ? `${Math.round(l2CompletionReflectionRate * 100)}%`
        : '--';
    const l2SessionRecentEvents = (l2Session?.recent_events || []).slice(-3).reverse();
    const l2InterruptReasonOptions = l2SessionAction?.interrupt?.reason_options?.length > 0
        ? l2SessionAction.interrupt.reason_options
        : [
            { value: 'context_switch', label: '上下文切换' },
            { value: 'external_interrupt', label: '外部打断' },
            { value: 'energy_drop', label: '精力下滑' },
            { value: 'tooling_blocked', label: '工具阻塞' },
            { value: 'other', label: '其他' }
        ];
    const guardianThresholds = guardianConfig?.thresholds || {};
    const deviationCfg = guardianThresholds.deviation_signals || {};
    const l2Cfg = guardianThresholds.l2_protection || {};
    const blueprintNarrative = retrospective?.blueprint_narrative || {};
    const blueprintDimensions = blueprintNarrative?.dimensions || {};
    const blueprintNarrativeCard = blueprintNarrative?.narrative_card || {};
    const pendingRecoveryCount = (tasks.pending || []).filter((task) => String(task?.id || '').endsWith('_recovery')).length;

    if (loading) {
        return (
            <div className="container flex-center" style={{ height: '100vh' }}>
                <div className="animate-pulse">加载 AI Life OS...</div>
            </div>
        );
    }

    return (
        <div className="container">
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                <h3 style={{ margin: 0, opacity: 0.75 }}>AI Life OS</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div role="tablist" style={{ display: 'flex', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '2px' }}>
                        <button
                            type="button"
                            role="tab"
                            aria-selected={viewMode === 'execute'}
                            onClick={() => setViewMode('execute')}
                            style={{
                                padding: '0.35rem 0.75rem',
                                borderRadius: '6px',
                                border: 'none',
                                background: viewMode === 'execute' ? 'var(--accent-color)' : 'transparent',
                                color: viewMode === 'execute' ? '#fff' : 'var(--text-secondary)',
                                cursor: 'pointer',
                                fontSize: '0.8125rem',
                                fontWeight: 500
                            }}
                        >
                            执行
                        </button>
                        <button
                            type="button"
                            role="tab"
                            aria-selected={viewMode === 'plan'}
                            onClick={() => setViewMode('plan')}
                            style={{
                                padding: '0.35rem 0.75rem',
                                borderRadius: '6px',
                                border: 'none',
                                background: viewMode === 'plan' ? 'var(--accent-color)' : 'transparent',
                                color: viewMode === 'plan' ? '#fff' : 'var(--text-secondary)',
                                cursor: 'pointer',
                                fontSize: '0.8125rem',
                                fontWeight: 500
                            }}
                        >
                            规划
                        </button>
                    </div>
                    <Link to="/vision/new" className="btn btn-primary" style={{ fontSize: '0.875rem' }}>+ 愿景</Link>
                    <Link to="/goals/new" className="btn btn-secondary" style={{ fontSize: '0.875rem' }}>+ 目标</Link>
                </div>
            </header>

            {weeklyReviewDue && (
                <div style={{
                    background: 'rgba(139, 92, 246, 0.15)',
                    border: '1px solid rgba(139, 92, 246, 0.4)',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    marginBottom: '1rem',
                    color: 'var(--accent-color)'
                }}>
                    本周复盘可查看，向下滚动到 Guardian 复盘。
                </div>
            )}

            {error && (
                <div style={{
                    background: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid rgba(239, 68, 68, 0.5)',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    marginBottom: '1rem',
                    color: '#fca5a5'
                }}>
                    {error}
                </div>
            )}

            {profile && (
                <section style={{ marginBottom: '1.5rem' }}>
                    <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                        {profile.occupation || '未设置'} · {profile.focus_area || '未设置'} · 可用 {profile.daily_hours || '--'}
                    </p>
                </section>
            )}

            {viewMode === 'plan' && (
                <section style={{ marginBottom: '1.5rem' }}>
                    <h4 style={{ color: 'var(--accent-color)', marginBottom: '0.75rem', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                        我的愿景与目标
                    </h4>
                    <div className="glass-card" style={{ padding: '0.9rem', marginBottom: '0.9rem' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                            <div>
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>价值对齐视图</div>
                                <div style={{ marginTop: '0.2rem', fontSize: '0.9rem' }}>
                                    {anchorSnapshot?.active
                                        ? `Anchor ${anchorSnapshot.version || ''}`
                                        : '未激活 Anchor'}
                                </div>
                            </div>
                            <div style={{ display: 'flex', gap: '0.65rem', flexWrap: 'wrap' }}>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    平均对齐: {alignmentOverview?.avg_score ?? '--'}
                                </span>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    高 {alignmentOverview?.distribution?.high ?? 0}
                                </span>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    中 {alignmentOverview?.distribution?.medium ?? 0}
                                </span>
                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                    低 {alignmentOverview?.distribution?.low ?? 0}
                                </span>
                            </div>
                        </div>
                        <div style={{ marginTop: '0.6rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {weeklyAlignmentTrend?.summary || '暂无周对齐趋势数据'}
                        </div>
                        {anchorEffect?.available && (
                            <div
                                style={{
                                    marginTop: '0.6rem',
                                    border: '1px solid rgba(59, 130, 246, 0.35)',
                                    background: 'rgba(59, 130, 246, 0.12)',
                                    borderRadius: '8px',
                                    padding: '0.55rem 0.65rem',
                                    fontSize: '0.78rem',
                                    color: '#bfdbfe'
                                }}
                            >
                                <div>
                                    最近一次生效: 影响 {anchorEffect.affected_count ?? 0}/{anchorEffect.total_processed ?? 0} 个目标，平均分变化 {effectDeltaLabel}
                                </div>
                                {anchorEffect.anchor_version && (
                                    <div style={{ marginTop: '0.2rem', color: 'var(--text-secondary)' }}>
                                        Anchor 版本: {anchorEffect.anchor_version}
                                        {anchorEffect.generated_at ? ` · ${anchorEffect.generated_at}` : ''}
                                    </div>
                                )}
                            </div>
                        )}
                        <div style={{ marginTop: '0.7rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                            <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={handleCheckAnchorDiff}
                                disabled={anchorDiffLoading}
                                style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                            >
                                {anchorDiffLoading ? '检查中...' : '检查 Anchor 变更'}
                            </button>
                            {canActivateAnchor && (
                                <button
                                    type="button"
                                    className="btn btn-primary"
                                    onClick={() => setActivateAnchorModalOpen(true)}
                                    disabled={activateAnchorLoading}
                                    style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                                >
                                    激活新 Anchor
                                </button>
                            )}
                        </div>
                        {anchorDiff?.diff && (
                            <div style={{ marginTop: '0.65rem', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                                <div>
                                    变更状态: {anchorDiff.diff.status}
                                    {anchorDiff.diff.version_change ? ` (${anchorDiff.diff.version_change})` : ''}
                                </div>
                                {(anchorDiff.diff.added_commitments?.length > 0 || anchorDiff.diff.removed_commitments?.length > 0) && (
                                    <div style={{ marginTop: '0.25rem' }}>
                                        承诺变化: +{anchorDiff.diff.added_commitments?.length || 0} / -{anchorDiff.diff.removed_commitments?.length || 0}
                                    </div>
                                )}
                                {(anchorDiff.diff.added_anti_values?.length > 0 || anchorDiff.diff.removed_anti_values?.length > 0) && (
                                    <div style={{ marginTop: '0.15rem' }}>
                                        反价值变化: +{anchorDiff.diff.added_anti_values?.length || 0} / -{anchorDiff.diff.removed_anti_values?.length || 0}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {goalTree.length > 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                            {goalTree.filter((v) => v.layer === 'vision').map((vision) => (
                                <div key={vision.id} className="glass-card" style={{ padding: '1rem', borderLeft: '4px solid #f59e0b' }}>
                                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.75rem' }}>
                                        <div>
                                            <div style={{ color: '#f59e0b', fontSize: '0.75rem' }}>愿景</div>
                                            <h5 style={{ margin: '0.25rem 0 0 0' }}>{vision.title}</h5>
                                        </div>
                                        <Link to={`/goals/${vision.id}/decompose`} className="btn btn-secondary" style={{ fontSize: '0.75rem' }}>
                                            + 分解
                                        </Link>
                                    </div>

                                    {(vision.children || []).length > 0 && (
                                        <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                            {vision.children.map((child) => {
                                                const progress = getGoalProgress(child.id);
                                                const pct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;
                                                const alignmentLevel = String(child.alignment_level || 'unknown').toLowerCase();
                                                const alignmentStyle = alignmentLevelStyleMap[alignmentLevel] || alignmentLevelStyleMap.unknown;
                                                return (
                                                    <div key={child.id} style={{
                                                        background: 'rgba(255,255,255,0.03)',
                                                        border: '1px solid var(--glass-border)',
                                                        borderRadius: '8px',
                                                        padding: '0.6rem 0.75rem'
                                                    }}>
                                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                                                            <div>
                                                                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{child.layer}</div>
                                                                <div>{child.title}</div>
                                                                <div style={{ marginTop: '0.25rem' }}>
                                                                    <span
                                                                        style={{
                                                                            ...alignmentStyle,
                                                                            fontSize: '0.7rem',
                                                                            borderRadius: '999px',
                                                                            padding: '0.12rem 0.4rem',
                                                                            fontWeight: 600
                                                                        }}
                                                                    >
                                                                        {formatAlignmentLevel(alignmentLevel)} {Number.isFinite(child.alignment_score) ? `· ${child.alignment_score}` : ''}
                                                                    </span>
                                                                </div>
                                                            </div>
                                                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                                <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{pct}%</span>
                                                                <button
                                                                    onClick={(e) => askDeleteGoal(child.id, e)}
                                                                    style={{ border: 'none', background: 'none', color: 'rgba(239, 68, 68, 0.6)', cursor: 'pointer', fontSize: '1rem' }}
                                                                    title="删除"
                                                                >
                                                                    ×
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="glass-card" style={{ padding: '1rem' }}>
                            暂无愿景。<Link to="/vision/new">创建愿景</Link>
                        </div>
                    )}

                    {standaloneGoals.length > 0 && (
                        <div style={{ marginTop: '1rem' }}>
                            <h5 style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>独立目标</h5>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.75rem' }}>
                                {standaloneGoals.map((goal) => {
                                    const progress = getGoalProgress(goal.id);
                                    const pct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;
                                    const alignmentLevel = String(goal.alignment_level || 'unknown').toLowerCase();
                                    const alignmentStyle = alignmentLevelStyleMap[alignmentLevel] || alignmentLevelStyleMap.unknown;
                                    return (
                                        <div key={goal.id} className="glass-card" style={{ padding: '0.8rem' }}>
                                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                                <div style={{ fontSize: '0.9rem' }}>{goal.title}</div>
                                                <button
                                                    onClick={(e) => askDeleteGoal(goal.id, e)}
                                                    style={{ border: 'none', background: 'none', color: 'rgba(239, 68, 68, 0.6)', cursor: 'pointer' }}
                                                    title="删除"
                                                >
                                                    ×
                                                </button>
                                            </div>
                                            <div style={{ marginTop: '0.35rem' }}>
                                                <span
                                                    style={{
                                                        ...alignmentStyle,
                                                        fontSize: '0.7rem',
                                                        borderRadius: '999px',
                                                        padding: '0.12rem 0.4rem',
                                                        fontWeight: 600
                                                    }}
                                                >
                                                    {formatAlignmentLevel(alignmentLevel)} {Number.isFinite(goal.alignment_score) ? `· ${goal.alignment_score}` : ''}
                                                </span>
                                            </div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>{progress.completed}/{progress.total} 任务 · {pct}%</div>
                                        </div>
                                    );
                                })}
                            </div>
                        </div>
                    )}
                </section>
            )}

            {viewMode === 'execute' && (
                <section>
                    <h4 style={{ color: 'var(--accent-color)', marginBottom: '0.75rem', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                        当前任务
                    </h4>
                    {pendingRecoveryCount > 0 && (
                        <div style={{ marginBottom: '0.6rem', display: 'flex', justifyContent: 'flex-end' }}>
                            <button
                                type="button"
                                className="btn btn-secondary"
                                onClick={handleApplyRecoveryBatch}
                                disabled={recoveryBatchLoading || actionLoading}
                                style={{ fontSize: '0.76rem', padding: '0.28rem 0.7rem' }}
                            >
                                {recoveryBatchLoading ? '应用中...' : `一键应用恢复批处理 (${pendingRecoveryCount})`}
                            </button>
                        </div>
                    )}
                    {!currentTask ? (
                        <div className="glass-card" style={{ padding: '1rem' }}>
                            今日暂无待办任务。
                        </div>
                    ) : (
                        <div className="glass-card" style={{ padding: '1.25rem' }}>
                            <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>{currentTask.goal_title}</div>
                            <h3 style={{ marginTop: '0.25rem' }}>{currentTask.description}</h3>
                            <div style={{ display: 'flex', gap: '1rem', color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                                <span>{currentTask.estimated_minutes} 分钟</span>
                                <span>{currentTask.scheduled_date} {currentTask.scheduled_time !== 'Anytime' ? currentTask.scheduled_time : ''}</span>
                            </div>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button onClick={handleComplete} className="btn btn-primary" disabled={actionLoading}>
                                    {actionLoading ? '处理中...' : '完成任务'}
                                </button>
                                <button onClick={openSkipDialog} className="btn btn-secondary" disabled={actionLoading}>
                                    跳过
                                </button>
                            </div>
                        </div>
                    )}
                </section>
            )}

            {retrospective && (
                <section style={{ marginTop: '2rem' }}>
                    <h4 style={{ color: 'var(--accent-color)', marginBottom: '0.75rem', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                        Guardian 复盘
                    </h4>
                    <div className="glass-card" style={{ padding: '1rem' }}>
                        <p style={{ margin: '0 0 0.75rem 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            最近 {retrospective.period?.days ?? 7} 天 · {retrospective.period?.start_date ?? ''} 至 {retrospective.period?.end_date ?? ''}
                        </p>
                        <p style={{ margin: '0 0 0.75rem 0' }}>
                            {retrospective.observations?.[0] ?? retrospective.rhythm?.summary ?? '本周期暂无总结'}
                        </p>
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Authority 升级级别</div>
                                <div style={{ fontSize: '0.86rem', fontWeight: 600 }}>{guardianEscalationLabel}</div>
                            </div>
                            <div style={{ marginTop: '0.25rem', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                                窗口 {guardianEscalation.window_days ?? 7} 天 · 抵抗 {guardianEscalation.resistance_count ?? 0}
                                / 响应 {guardianEscalation.response_count ?? 0}
                            </div>
                        </div>
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: interventionSuppressed
                                    ? '1px solid rgba(245, 158, 11, 0.45)'
                                    : '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: interventionSuppressed
                                    ? 'rgba(245, 158, 11, 0.1)'
                                    : 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>干预节奏策略</div>
                                <div style={{ fontSize: '0.86rem', fontWeight: 600 }}>{interventionPolicyLabel}</div>
                            </div>
                            <div style={{ marginTop: '0.25rem', fontSize: '0.73rem', color: 'var(--text-secondary)' }}>
                                原因: {interventionPolicy?.reason || '暂无策略说明'}
                            </div>
                            <div style={{ marginTop: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                提醒预算: {reminderWindowLabel} · 冷却: {interventionCooldownLabel}
                            </div>
                            {interventionSuppressed && (
                                <div style={{ marginTop: '0.2rem', fontSize: '0.72rem', color: '#fcd34d' }}>
                                    当前轮次触发了摩擦预算，建议已暂缓展示。
                                </div>
                            )}
                        </div>
                        {guardianSafeMode.enabled && (
                            <div
                                style={{
                                    marginBottom: '0.75rem',
                                    border: guardianSafeMode.active
                                        ? '1px solid rgba(245, 158, 11, 0.45)'
                                        : '1px solid rgba(148, 163, 184, 0.3)',
                                    borderRadius: '8px',
                                    padding: '0.65rem 0.75rem',
                                    background: guardianSafeMode.active
                                        ? 'rgba(245, 158, 11, 0.14)'
                                        : 'rgba(148, 163, 184, 0.08)'
                                }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                    <div style={{ fontSize: '0.82rem', fontWeight: 600 }}>
                                        Safe Mode {guardianSafeMode.active ? '已开启' : '未开启'}
                                    </div>
                                    {guardianSafeMode.entered_at && (
                                        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                            {guardianSafeMode.active ? '进入于' : '最近结束于'} {guardianSafeMode.active ? guardianSafeMode.entered_at : (guardianSafeMode.exited_at || guardianSafeMode.entered_at)}
                                        </div>
                                    )}
                                </div>
                                {guardianSafeMode.reason && (
                                    <div style={{ marginTop: '0.25rem', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                                        原因: {guardianSafeMode.reason}
                                    </div>
                                )}
                            </div>
                        )}
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: 'rgba(255,255,255,0.03)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>L2 保护率</div>
                                <div style={{ fontSize: '0.9rem', fontWeight: 700, color: l2ProtectionColorMap[l2ProtectionLevel] || l2ProtectionColorMap.unknown }}>
                                    {l2ProtectionLabel}
                                </div>
                            </div>
                            <div style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                                {retrospective.l2_protection?.summary || '暂无 L2 保护数据'}
                            </div>
                            <div style={{ marginTop: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                完成 {retrospective.l2_protection?.protected ?? 0} · 中断 {retrospective.l2_protection?.interrupted ?? 0}
                            </div>
                            {l2ThresholdLabel && (
                                <div style={{ marginTop: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                    {l2ThresholdLabel}
                                </div>
                            )}
                            {l2TrendPoints.length > 0 && (
                                <div style={{ marginTop: '0.5rem', display: 'grid', gap: '0.25rem' }}>
                                    {l2TrendPoints.map((point) => {
                                        const ratio = Number(point?.ratio);
                                        const ratioPct = Number.isFinite(ratio) ? Math.round(ratio * 100) : null;
                                        const barWidth = ratioPct !== null ? `${Math.max(0, Math.min(100, ratioPct))}%` : '0%';
                                        return (
                                            <div
                                                key={point.date}
                                                style={{
                                                    display: 'grid',
                                                    gridTemplateColumns: '52px 1fr 44px',
                                                    gap: '0.35rem',
                                                    alignItems: 'center'
                                                }}
                                            >
                                                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                                    {(point.date || '').slice(5)}
                                                </span>
                                                <div
                                                    style={{
                                                        height: '6px',
                                                        borderRadius: '999px',
                                                        background: 'rgba(255,255,255,0.12)',
                                                        overflow: 'hidden'
                                                    }}
                                                >
                                                    <div
                                                        style={{
                                                            width: barWidth,
                                                            height: '100%',
                                                            background: ratioPct === null
                                                                ? 'rgba(148, 163, 184, 0.4)'
                                                                : 'rgba(34, 197, 94, 0.8)'
                                                        }}
                                                    />
                                                </div>
                                                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textAlign: 'right' }}>
                                                    {ratioPct === null ? '--' : `${ratioPct}%`}
                                                </span>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>人性化指标</div>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                    恢复采纳 · 摩擦负荷 · 支持/覆盖
                                </div>
                            </div>
                            <div style={{ marginTop: '0.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem' }}>
                                <div style={{ border: '1px solid rgba(148,163,184,0.25)', borderRadius: '8px', padding: '0.45rem 0.5rem', background: 'rgba(2, 6, 23, 0.2)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>恢复采纳率</div>
                                    <div style={{ marginTop: '0.12rem', fontSize: '0.94rem', fontWeight: 700 }}>{recoveryAdoptionLabel}</div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                        {recoveryAdoptionMetric?.adopted ?? 0}/{recoveryAdoptionMetric?.suggested ?? 0} 已采纳
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                        {recoveryAdoptionMetric?.summary || '暂无恢复建议数据'}
                                    </div>
                                </div>
                                <div style={{ border: '1px solid rgba(148,163,184,0.25)', borderRadius: '8px', padding: '0.45rem 0.5rem', background: 'rgba(2, 6, 23, 0.2)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>摩擦负荷</div>
                                    <div style={{ marginTop: '0.12rem', fontSize: '0.94rem', fontWeight: 700, color: frictionLoadColorMap[frictionLoadLevel] || frictionLoadColorMap.unknown }}>
                                        {frictionLoadLabel}
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                        级别: {frictionLoadLevel}
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                        {frictionLoadMetric?.summary || '暂无摩擦负荷数据'}
                                    </div>
                                </div>
                                <div style={{ border: '1px solid rgba(148,163,184,0.25)', borderRadius: '8px', padding: '0.45rem 0.5rem', background: 'rgba(2, 6, 23, 0.2)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>支持/覆盖比</div>
                                    <div style={{ marginTop: '0.12rem', fontSize: '0.94rem', fontWeight: 700 }}>{supportVsOverrideLabel}</div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                        {supportVsOverrideModeLabel} · 支持 {supportVsOverrideMetric?.support_count ?? 0} / 覆盖 {supportVsOverrideMetric?.override_count ?? 0}
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                        {supportVsOverrideMetric?.summary || '暂无支持/覆盖数据'}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>North-Star 指标</div>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>{northStarSummaryLabel}</div>
                            </div>
                            <div style={{ marginTop: '0.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem' }}>
                                <div style={{ border: '1px solid rgba(148,163,184,0.25)', borderRadius: '8px', padding: '0.45rem 0.5rem', background: 'rgba(2, 6, 23, 0.2)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>L1 自动化覆盖率</div>
                                    <div style={{ marginTop: '0.12rem', fontSize: '0.94rem', fontWeight: 700 }}>{mundaneCoverageLabel}</div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                        机会 {mundaneCoverageMetric?.l1_recovery_opportunities ?? 0} · 采纳 {mundaneCoverageMetric?.adopted_auto_recovery ?? 0}
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                        {metricStatusLabel(mundaneCoverageMetric?.met_target)}
                                    </div>
                                </div>
                                <div style={{ border: '1px solid rgba(148,163,184,0.25)', borderRadius: '8px', padding: '0.45rem 0.5rem', background: 'rgba(2, 6, 23, 0.2)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>L2 Bloom 时长</div>
                                    <div style={{ marginTop: '0.12rem', fontSize: '0.94rem', fontWeight: 700 }}>{l2BloomHoursLabel}</div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                        基线 {Number.isFinite(l2BloomBaseline) ? `${l2BloomBaseline.toFixed(1)}h` : '--'} · 变化 {l2BloomDeltaLabel}
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                        {metricStatusLabel(l2BloomMetric?.met_target)}
                                    </div>
                                </div>
                                <div style={{ border: '1px solid rgba(148,163,184,0.25)', borderRadius: '8px', padding: '0.45rem 0.5rem', background: 'rgba(2, 6, 23, 0.2)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>Human Trust Index</div>
                                    <div style={{ marginTop: '0.12rem', fontSize: '0.94rem', fontWeight: 700 }}>{humanTrustLabel}</div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                        支持 {Number.isFinite(Number(humanTrustMetric?.components?.support_ratio)) ? `${Math.round(Number(humanTrustMetric?.components?.support_ratio) * 100)}%` : '--'} · 采纳 {Number.isFinite(Number(humanTrustMetric?.components?.adoption_rate)) ? `${Math.round(Number(humanTrustMetric?.components?.adoption_rate) * 100)}%` : '--'}
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                        {metricStatusLabel(humanTrustMetric?.met_target)}
                                    </div>
                                </div>
                                <div style={{ border: '1px solid rgba(148,163,184,0.25)', borderRadius: '8px', padding: '0.45rem 0.5rem', background: 'rgba(2, 6, 23, 0.2)' }}>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>周对齐增量</div>
                                    <div style={{ marginTop: '0.12rem', fontSize: '0.94rem', fontWeight: 700 }}>{alignmentDeltaLabel}</div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                        本周 {alignmentDeltaMetric?.current_week_avg ?? '--'} · 上周 {alignmentDeltaMetric?.previous_week_avg ?? '--'}
                                    </div>
                                    <div style={{ marginTop: '0.15rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                        {metricStatusLabel(alignmentDeltaMetric?.met_target)}
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>L2 会话状态</div>
                                <div style={{ fontSize: '0.84rem', fontWeight: 600 }}>
                                    {l2SessionActive ? `进行中 · ${l2SessionActiveId || '--'}` : '未进行'}
                                </div>
                            </div>
                            <div style={{ marginTop: '0.22rem', fontSize: '0.73rem', color: 'var(--text-secondary)' }}>
                                启动 {l2Session.started ?? 0} · 完成 {l2Session.completed ?? 0}
                                · 中断 {l2Session.interrupted ?? 0} · 恢复 {l2Session.resumed ?? 0}
                                · 完结率 {l2SessionCompletionLabel} · 恢复率 {l2SessionRecoveryLabel}
                            </div>
                            <div style={{ marginTop: '0.22rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                开始意图采纳 {l2StartIntentionRateLabel} · 完成反馈采纳 {l2CompletionReflectionRateLabel}
                            </div>
                            <div style={{ marginTop: '0.48rem', display: 'grid', gap: '0.45rem' }}>
                                <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                    <input
                                        type="text"
                                        value={l2StartIntention}
                                        onChange={(e) => setL2StartIntention(e.target.value)}
                                        placeholder={l2SessionAction?.ritual?.start_intention_prompt || '开始前写一句本次会话意图'}
                                        disabled={l2SessionActionLoading || l2SessionActive}
                                        style={{
                                            minWidth: '260px',
                                            flex: '1 1 260px',
                                            borderRadius: '6px',
                                            border: '1px solid rgba(255,255,255,0.2)',
                                            background: 'rgba(0,0,0,0.25)',
                                            color: 'white',
                                            padding: '0.25rem 0.4rem',
                                            fontSize: '0.74rem'
                                        }}
                                    />
                                    <button
                                        type="button"
                                        className="btn btn-primary"
                                        onClick={() => handleL2SessionAction('start')}
                                        disabled={l2SessionActionLoading || l2SessionActive}
                                        style={{ fontSize: '0.76rem', padding: '0.25rem 0.7rem' }}
                                    >
                                        {l2SessionActionLoading ? '处理中...' : '开始 L2 会话'}
                                    </button>
                                </div>
                                {(l2SessionResumeReady || l2SessionResumeHint) && (
                                    <div style={{ display: 'grid', gap: '0.3rem' }}>
                                        <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                            {l2SessionResumeId ? `可恢复会话: ${l2SessionResumeId}` : '检测到可恢复会话'}
                                            {l2Session?.resume_reason_label ? ` · 原因 ${l2Session.resume_reason_label}` : ''}
                                        </div>
                                        <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                            <input
                                                type="text"
                                                value={l2ResumeStep}
                                                onChange={(e) => setL2ResumeStep(e.target.value)}
                                                placeholder={l2SessionResumeHint || '写下恢复后的最小回归步骤'}
                                                disabled={l2SessionActionLoading || !l2SessionResumeReady}
                                                style={{
                                                    minWidth: '260px',
                                                    flex: '1 1 260px',
                                                    borderRadius: '6px',
                                                    border: '1px solid rgba(255,255,255,0.2)',
                                                    background: 'rgba(0,0,0,0.25)',
                                                    color: 'white',
                                                    padding: '0.25rem 0.4rem',
                                                    fontSize: '0.74rem'
                                                }}
                                            />
                                            <button
                                                type="button"
                                                className="btn btn-secondary"
                                                onClick={() => handleL2SessionAction('resume')}
                                                disabled={l2SessionActionLoading || !l2SessionResumeReady}
                                                style={{ fontSize: '0.76rem', padding: '0.25rem 0.65rem' }}
                                            >
                                                恢复会话
                                            </button>
                                        </div>
                                    </div>
                                )}
                                <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', alignItems: 'center' }}>
                                    <input
                                        type="text"
                                        value={l2CompletionReflection}
                                        onChange={(e) => setL2CompletionReflection(e.target.value)}
                                        placeholder={l2SessionAction?.ritual?.complete_reflection_prompt || '完成后写一句反馈'}
                                        disabled={l2SessionActionLoading || !l2SessionActive}
                                        style={{
                                            minWidth: '220px',
                                            flex: '1 1 220px',
                                            borderRadius: '6px',
                                            border: '1px solid rgba(255,255,255,0.2)',
                                            background: 'rgba(0,0,0,0.25)',
                                            color: 'white',
                                            padding: '0.25rem 0.4rem',
                                            fontSize: '0.74rem'
                                        }}
                                    />
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={() => handleL2SessionAction('complete')}
                                        disabled={l2SessionActionLoading || !l2SessionActive}
                                        style={{ fontSize: '0.76rem', padding: '0.25rem 0.65rem' }}
                                    >
                                        完成会话
                                    </button>
                                    <select
                                        value={l2InterruptReason}
                                        onChange={(e) => setL2InterruptReason(e.target.value)}
                                        disabled={l2SessionActionLoading || !l2SessionActive}
                                        style={{
                                            borderRadius: '6px',
                                            border: '1px solid rgba(255,255,255,0.2)',
                                            background: 'rgba(0,0,0,0.25)',
                                            color: 'white',
                                            padding: '0.25rem 0.35rem',
                                            fontSize: '0.74rem'
                                        }}
                                    >
                                        {l2InterruptReasonOptions.map((opt) => (
                                            <option key={`l2_reason_${opt.value}`} value={opt.value}>
                                                {opt.label || l2InterruptReasonLabelMap[opt.value] || opt.value}
                                            </option>
                                        ))}
                                    </select>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={() => handleL2SessionAction('interrupt')}
                                        disabled={l2SessionActionLoading || !l2SessionActive}
                                        style={{ fontSize: '0.76rem', padding: '0.25rem 0.65rem' }}
                                    >
                                        记录中断
                                    </button>
                                </div>
                            </div>
                            {l2Session.latest && (
                                <div style={{ marginTop: '0.35rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                    最近会话事件: {l2Session.latest.type || '--'}
                                    {l2Session.latest.reason_label ? ` · ${l2Session.latest.reason_label}` : ''}
                                    {l2Session.latest.timestamp ? ` · ${l2Session.latest.timestamp}` : ''}
                                </div>
                            )}
                            {l2SessionRecentEvents.length > 0 && (
                                <div style={{ marginTop: '0.4rem', display: 'grid', gap: '0.28rem' }}>
                                    {l2SessionRecentEvents.map((ev, idx) => (
                                        <div
                                            key={`l2_evt_${idx}`}
                                            style={{
                                                fontSize: '0.71rem',
                                                color: 'var(--text-secondary)',
                                                background: 'rgba(0,0,0,0.2)',
                                                borderRadius: '6px',
                                                padding: '0.28rem 0.42rem'
                                            }}
                                        >
                                            [{ev.type || 'unknown'}] {ev.detail || '--'}
                                            {ev.timestamp ? ` · ${ev.timestamp}` : ''}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Blueprint Narrative Loop</div>
                                <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                    {blueprintNarrativeCard?.title || 'How This Week Served Long-Term Value'}
                                </div>
                            </div>
                            <div style={{ marginTop: '0.22rem', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                                {blueprintNarrativeCard?.summary || '暂无叙事摘要'}
                            </div>
                            {blueprintNarrativeCard?.alignment_trend && (
                                <div style={{ marginTop: '0.22rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                    对齐趋势: {blueprintNarrativeCard.alignment_trend}
                                </div>
                            )}
                            <div style={{ marginTop: '0.45rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.4rem' }}>
                                {['wisdom', 'experience', 'connection'].map((key) => {
                                    const dimension = blueprintDimensions?.[key] || {};
                                    return (
                                        <div
                                            key={`blueprint_dim_${key}`}
                                            style={{
                                                border: '1px solid rgba(148,163,184,0.25)',
                                                borderRadius: '8px',
                                                padding: '0.4rem 0.45rem',
                                                background: 'rgba(2, 6, 23, 0.2)'
                                            }}
                                        >
                                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.35rem', alignItems: 'center' }}>
                                                <div style={{ fontSize: '0.73rem', textTransform: 'capitalize' }}>{key}</div>
                                                <div style={{ fontSize: '0.68rem', color: dimension?.progress ? '#86efac' : '#fca5a5' }}>
                                                    {dimension?.progress ? '有进展' : '待加强'}
                                                </div>
                                            </div>
                                            <div style={{ marginTop: '0.18rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                                {dimension?.summary || '--'}
                                            </div>
                                            {Array.isArray(dimension?.evidence) && dimension.evidence.length > 0 && (
                                                <div style={{ marginTop: '0.25rem', display: 'grid', gap: '0.2rem' }}>
                                                    {dimension.evidence.slice(-2).map((ev, idx) => (
                                                        <div key={`dim_ev_${key}_${idx}`} style={{ fontSize: '0.67rem', color: 'var(--text-secondary)' }}>
                                                            [{ev.type || 'event'}] {ev.detail || '--'}
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                            <div style={{ marginTop: '0.42rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                下周强化: {blueprintNarrativeCard?.reinforce_behavior || '--'}
                            </div>
                            <div style={{ marginTop: '0.18rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                下周减少: {blueprintNarrativeCard?.reduce_behavior || '--'}
                            </div>
                        </div>
                        <div
                            style={{
                                marginBottom: '0.75rem',
                                border: '1px solid rgba(255,255,255,0.12)',
                                borderRadius: '8px',
                                padding: '0.65rem 0.75rem',
                                background: 'rgba(255,255,255,0.02)'
                            }}
                        >
                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Guardian 阈值配置</div>
                                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={refreshGuardianConfig}
                                        disabled={guardianConfigLoading || guardianConfigSaving}
                                        style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem' }}
                                    >
                                        {guardianConfigLoading ? '刷新中...' : '刷新'}
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-primary"
                                        onClick={saveGuardianConfig}
                                        disabled={!guardianConfigDirty || guardianConfigSaving}
                                        style={{ fontSize: '0.72rem', padding: '0.2rem 0.6rem' }}
                                    >
                                        {guardianConfigSaving ? '保存中...' : '保存阈值'}
                                    </button>
                                </div>
                            </div>
                            {guardianConfig ? (
                                <div style={{ marginTop: '0.5rem', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '0.45rem' }}>
                                    <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        干预级别
                                        <select
                                            value={guardianConfig.intervention_level || 'SOFT'}
                                            onChange={(e) => updateGuardianInterventionLevel(e.target.value)}
                                            style={{ borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.25)', color: 'white', padding: '0.25rem 0.35rem' }}
                                        >
                                            <option value="OBSERVE_ONLY">OBSERVE_ONLY</option>
                                            <option value="SOFT">SOFT</option>
                                            <option value="ASK">ASK</option>
                                        </select>
                                    </label>
                                    <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        重复跳过阈值
                                        <input
                                            type="number"
                                            min="1"
                                            value={deviationCfg.repeated_skip ?? 2}
                                            onChange={(e) => updateGuardianConfigField('deviation_signals', 'repeated_skip', e.target.value)}
                                            style={{ borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.25)', color: 'white', padding: '0.25rem 0.35rem' }}
                                        />
                                    </label>
                                    <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        L2 中断阈值
                                        <input
                                            type="number"
                                            min="1"
                                            value={deviationCfg.l2_interruption ?? 1}
                                            onChange={(e) => updateGuardianConfigField('deviation_signals', 'l2_interruption', e.target.value)}
                                            style={{ borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.25)', color: 'white', padding: '0.25rem 0.35rem' }}
                                        />
                                    </label>
                                    <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        停滞天数阈值
                                        <input
                                            type="number"
                                            min="1"
                                            value={deviationCfg.stagnation_days ?? 3}
                                            onChange={(e) => updateGuardianConfigField('deviation_signals', 'stagnation_days', e.target.value)}
                                            style={{ borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.25)', color: 'white', padding: '0.25rem 0.35rem' }}
                                        />
                                    </label>
                                    <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        L2 高阈值
                                        <input
                                            type="number"
                                            min="0"
                                            max="1"
                                            step="0.01"
                                            value={l2Cfg.high ?? 0.75}
                                            onChange={(e) => updateGuardianConfigField('l2_protection', 'high', e.target.value)}
                                            style={{ borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.25)', color: 'white', padding: '0.25rem 0.35rem' }}
                                        />
                                    </label>
                                    <label style={{ display: 'grid', gap: '0.2rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        L2 中阈值
                                        <input
                                            type="number"
                                            min="0"
                                            max="1"
                                            step="0.01"
                                            value={l2Cfg.medium ?? 0.5}
                                            onChange={(e) => updateGuardianConfigField('l2_protection', 'medium', e.target.value)}
                                            style={{ borderRadius: '6px', border: '1px solid rgba(255,255,255,0.2)', background: 'rgba(0,0,0,0.25)', color: 'white', padding: '0.25rem 0.35rem' }}
                                        />
                                    </label>
                                </div>
                            ) : (
                                <div style={{ marginTop: '0.45rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                    当前无法加载配置，点击“刷新”重试。
                                </div>
                            )}
                            {guardianConfigSavedAt && (
                                <div style={{ marginTop: '0.35rem', fontSize: '0.7rem', color: 'var(--text-secondary)' }}>
                                    上次保存: {guardianConfigSavedAt}
                                </div>
                            )}
                        </div>

                        {retrospective.display && retrospective.suggestion && (
                            <div style={{
                                background: 'rgba(139, 92, 246, 0.15)',
                                border: '1px solid rgba(139, 92, 246, 0.3)',
                                borderRadius: '8px',
                                padding: '0.75rem'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: 'var(--accent-color)', fontWeight: 600 }}>建议</div>
                                <p style={{ margin: '0.25rem 0 0.5rem 0', fontSize: '0.9rem' }}>{retrospective.suggestion}</p>
                                <div
                                    style={{
                                        marginBottom: '0.55rem',
                                        borderRadius: '8px',
                                        border: '1px solid rgba(255,255,255,0.15)',
                                        background: 'rgba(2, 6, 23, 0.18)',
                                        padding: '0.45rem 0.55rem'
                                    }}
                                >
                                    <div style={{ fontSize: '0.74rem', fontWeight: 600 }}>
                                        为什么是这个建议
                                    </div>
                                    <div style={{ marginTop: '0.2rem', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                                        {guardianExplainWhy}
                                    </div>
                                    <div style={{ marginTop: '0.38rem', fontSize: '0.74rem', fontWeight: 600 }}>
                                        接下来会发生什么
                                    </div>
                                    <div style={{ marginTop: '0.2rem', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                                        {guardianExplainNext}
                                    </div>
                                    {guardianExplainSignals.length > 0 && (
                                        <div style={{ marginTop: '0.32rem', fontSize: '0.71rem', color: 'var(--text-secondary)' }}>
                                            信号: {guardianExplainSignals.join(' · ')}
                                        </div>
                                    )}
                                </div>
                                <div
                                    style={{
                                        marginBottom: '0.55rem',
                                        borderRadius: '8px',
                                        border: '1px solid rgba(255,255,255,0.15)',
                                        background: 'rgba(255,255,255,0.04)',
                                        padding: '0.45rem 0.55rem'
                                    }}
                                >
                                    <div style={{ fontSize: '0.75rem', fontWeight: 600 }}>
                                        当前代表: {guardianRoleRepresentingLabel} · 面向: {guardianRoleFacingLabel}
                                    </div>
                                    <div style={{ marginTop: '0.2rem', fontSize: '0.74rem', color: 'var(--text-secondary)' }}>
                                        {guardianRoleMessage}
                                    </div>
                                </div>

                                <div style={{ marginBottom: '0.5rem', display: 'grid', gap: '0.25rem' }}>
                                    <label style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        当前意图
                                    </label>
                                    <select
                                        value={guardianResponseContext}
                                        onChange={(e) => setGuardianResponseContext(e.target.value)}
                                        style={{
                                            borderRadius: '6px',
                                            border: '1px solid rgba(255,255,255,0.2)',
                                            background: 'rgba(0,0,0,0.25)',
                                            color: 'white',
                                            padding: '0.32rem 0.4rem',
                                            maxWidth: '220px'
                                        }}
                                    >
                                        {responseContextOptions.map((opt) => (
                                            <option key={opt.value} value={opt.value}>
                                                {opt.label}
                                            </option>
                                        ))}
                                    </select>
                                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        {responseContextHintMap[guardianResponseContext] || ''}
                                    </div>
                                </div>

                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                    <button
                                        type="button"
                                        className="btn btn-primary"
                                        onClick={handleConfirmIntervention}
                                        disabled={guardianResponseLoading || retrospective.confirmation_action?.confirmed}
                                        style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                                    >
                                        {retrospective.confirmation_action?.confirmed
                                            ? '已确认'
                                            : guardianResponseLoading ? '提交中...' : '确认建议'}
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={() => handleGuardianResponse('snooze')}
                                        disabled={guardianResponseLoading}
                                        style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                                    >
                                        稍后处理
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={() => handleGuardianResponse('dismiss')}
                                        disabled={guardianResponseLoading}
                                        style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                                    >
                                        暂不采纳
                                    </button>
                                </div>
                                {retrospective.confirmation_action?.required && !retrospective.confirmation_action?.confirmed && (
                                    <div style={{ marginTop: '0.35rem', fontSize: '0.75rem', color: '#fcd34d' }}>
                                        当前为 ASK 模式，需要最终确认。
                                    </div>
                                )}
                                {guardianLatestResponse && (
                                    <div style={{ marginTop: '0.35rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        最近响应: {guardianLatestResponse.action || '--'}
                                        {guardianLatestResponse.timestamp ? ` · ${guardianLatestResponse.timestamp}` : ''}
                                        {guardianLatestResponseContextLabel ? ` · ${guardianLatestResponseContextLabel}` : ''}
                                    </div>
                                )}
                                {guardianLatestRecoveryStep && (
                                    <div style={{ marginTop: '0.3rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                        恢复下一步: {guardianLatestRecoveryStep}
                                    </div>
                                )}
                            </div>
                        )}

                        {retrospective.suggestion_sources?.length > 0 && (
                            <div style={{ marginTop: '0.75rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                                <div style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 600 }}>
                                    建议来源（可追溯）
                                </div>
                                {retrospective.suggestion_sources.map((src, idx) => {
                                    const severityStyle = severityStyleMap[src.severity] || severityStyleMap.info;
                                    return (
                                        <div
                                            key={`${src.signal || 'signal'}_${idx}`}
                                            style={{
                                                border: '1px solid var(--glass-border)',
                                                borderRadius: '8px',
                                                padding: '0.65rem',
                                                background: 'rgba(255,255,255,0.03)'
                                            }}
                                        >
                                            <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
                                                    <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>
                                                        {signalNameMap[src.signal] || src.signal}
                                                    </span>
                                                    <span style={{ ...severityStyle, fontSize: '0.7rem', borderRadius: '999px', padding: '0.1rem 0.4rem', fontWeight: 600 }}>
                                                        {String(src.severity || 'info').toUpperCase()}
                                                    </span>
                                                </div>
                                                <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>
                                                    命中 {src.count ?? 0} / 阈值 {src.threshold ?? '-'}
                                                </span>
                                            </div>
                                            <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{src.summary}</p>
                                            {src.evidence?.length > 0 && (
                                                <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
                                                    {src.evidence.map((ev, evIdx) => (
                                                        <div
                                                            key={`${src.signal || 'signal'}_ev_${evIdx}`}
                                                            style={{
                                                                fontSize: '0.75rem',
                                                                color: 'var(--text-secondary)',
                                                                background: 'rgba(0,0,0,0.2)',
                                                                borderRadius: '6px',
                                                                padding: '0.35rem 0.5rem'
                                                            }}
                                                        >
                                                            <div>[{ev.type || 'unknown'}] {ev.detail || 'no detail'}</div>
                                                            <div style={{ opacity: 0.85 }}>
                                                                {ev.timestamp || 'no timestamp'} {ev.event_id ? ` · ${ev.event_id}` : ''}
                                                            </div>
                                                        </div>
                                                    ))}
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )}
                    </div>
                </section>
            )}

            <OverlayModal
                open={skipDialogOpen}
                title="跳过当前任务"
                onCancel={() => {
                    if (actionLoading) return;
                    setSkipDialogOpen(false);
                    setSkipReason('');
                    setSkipContext('recovering');
                }}
                onConfirm={submitSkip}
                confirmText={actionLoading ? '提交中...' : '确认跳过'}
                disabled={actionLoading}
            >
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>请填写跳过原因，便于 Guardian 复盘。</p>
                <div style={{ marginTop: '0.65rem', display: 'grid', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                        跳过上下文
                    </label>
                    <select
                        value={skipContext}
                        onChange={(e) => setSkipContext(e.target.value)}
                        style={{
                            borderRadius: '6px',
                            border: '1px solid rgba(255,255,255,0.2)',
                            background: 'rgba(0,0,0,0.25)',
                            color: 'white',
                            padding: '0.35rem 0.45rem',
                            maxWidth: '240px'
                        }}
                    >
                        {responseContextOptions.map((opt) => (
                            <option key={`skip_ctx_${opt.value}`} value={opt.value}>
                                {opt.label}
                            </option>
                        ))}
                    </select>
                    <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                        {responseContextHintMap[skipContext] || ''}
                    </div>
                </div>
                <textarea
                    value={skipReason}
                    onChange={(e) => setSkipReason(e.target.value)}
                    rows={3}
                    style={{
                        marginTop: '0.6rem',
                        width: '100%',
                        borderRadius: '8px',
                        border: '1px solid rgba(255,255,255,0.2)',
                        padding: '0.65rem',
                        background: 'rgba(0,0,0,0.25)',
                        color: 'white',
                        resize: 'vertical'
                    }}
                    placeholder="例如：当前上下文不足，计划明天上午处理"
                />
            </OverlayModal>

            <OverlayModal
                open={Boolean(deleteTargetGoalId)}
                title="删除目标"
                onCancel={() => {
                    if (actionLoading) return;
                    setDeleteTargetGoalId(null);
                }}
                onConfirm={confirmDeleteGoal}
                confirmText={actionLoading ? '删除中...' : '确认删除'}
                disabled={actionLoading}
            >
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
                    删除后该目标将从当前视图移除。是否继续？
                </p>
            </OverlayModal>

            <OverlayModal
                open={activateAnchorModalOpen}
                title="激活新 Anchor"
                onCancel={() => {
                    if (activateAnchorLoading) return;
                    setActivateAnchorModalOpen(false);
                }}
                onConfirm={handleActivateAnchor}
                confirmText={activateAnchorLoading ? '激活中...' : '确认激活'}
                disabled={activateAnchorLoading}
            >
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>
                    激活后 Guardian 与目标对齐会切换到新的价值锚点版本。是否继续？
                </p>
            </OverlayModal>
        </div>
    );
}
