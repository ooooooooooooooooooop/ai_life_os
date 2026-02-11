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
    const [deleteTargetGoalId, setDeleteTargetGoalId] = useState(null);
    const [guardianConfirmLoading, setGuardianConfirmLoading] = useState(false);
    const [anchorDiff, setAnchorDiff] = useState(null);
    const [anchorDiffLoading, setAnchorDiffLoading] = useState(false);
    const [activateAnchorLoading, setActivateAnchorLoading] = useState(false);
    const [activateAnchorModalOpen, setActivateAnchorModalOpen] = useState(false);

    const signalNameMap = {
        repeated_skip: '重复跳过',
        l2_interruption: '深度时段中断',
        stagnation: '推进停滞'
    };

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

            const [tasksRes, currentRes, retroRes, effectRes] = await Promise.allSettled([
                api.get('/tasks/list'),
                api.get('/tasks/current'),
                api.get('/retrospective', { params: { days: 7 } }),
                api.get('/anchor/effect')
            ]);
            if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value.data);
            if (currentRes.status === 'fulfilled') setCurrentTask(currentRes.value.data.task);
            if (retroRes.status === 'fulfilled') setRetrospective(retroRes.value.data);
            if (effectRes.status === 'fulfilled') setAnchorEffect(effectRes.value.data);
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
            await api.post(`/tasks/${currentTask.id}/skip`, { reason: skipReason.trim() });
            setSkipDialogOpen(false);
            setSkipReason('');
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

    const handleConfirmIntervention = async () => {
        if (!retrospective || guardianConfirmLoading) return;
        try {
            setGuardianConfirmLoading(true);
            setError(null);
            await api.post('/retrospective/confirm', {
                days: retrospective.period?.days ?? 7,
                fingerprint: retrospective.confirmation_action?.fingerprint ?? null
            });
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('确认建议失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setGuardianConfirmLoading(false);
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

                        {retrospective.display && retrospective.suggestion && (
                            <div style={{
                                background: 'rgba(139, 92, 246, 0.15)',
                                border: '1px solid rgba(139, 92, 246, 0.3)',
                                borderRadius: '8px',
                                padding: '0.75rem'
                            }}>
                                <div style={{ fontSize: '0.75rem', color: 'var(--accent-color)', fontWeight: 600 }}>建议</div>
                                <p style={{ margin: '0.25rem 0 0.5rem 0', fontSize: '0.9rem' }}>{retrospective.suggestion}</p>

                                {retrospective.confirmation_action?.required && (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                        {retrospective.confirmation_action.confirmed ? (
                                            <span style={{ fontSize: '0.8rem', color: '#86efac' }}>
                                                已确认
                                                {retrospective.confirmation_action.confirmed_at
                                                    ? ` (${retrospective.confirmation_action.confirmed_at})`
                                                    : ''}
                                            </span>
                                        ) : (
                                            <button
                                                type="button"
                                                className="btn btn-primary"
                                                onClick={handleConfirmIntervention}
                                                disabled={guardianConfirmLoading}
                                                style={{ fontSize: '0.8rem', padding: '0.35rem 0.75rem' }}
                                            >
                                                {guardianConfirmLoading ? '确认中...' : '确认已阅读建议'}
                                            </button>
                                        )}
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
                }}
                onConfirm={submitSkip}
                confirmText={actionLoading ? '提交中...' : '确认跳过'}
                disabled={actionLoading}
            >
                <p style={{ color: 'var(--text-secondary)', margin: 0 }}>请填写跳过原因，便于 Guardian 复盘。</p>
                <textarea
                    value={skipReason}
                    onChange={(e) => setSkipReason(e.target.value)}
                    rows={3}
                    style={{
                        marginTop: '0.75rem',
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
