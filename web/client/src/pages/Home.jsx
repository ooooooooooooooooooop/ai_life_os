import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../utils/api';

// 从 /state 的 visions/objectives/goals 构建与 /goals/tree 兼容的树形结构
function buildTreeFromState(visions = [], objectives = [], goals = []) {
    const layerToHorizon = (layer) => (layer === 'vision' ? 'vision' : layer === 'objective' ? 'milestone' : 'goal');
    const node = (n) => ({ ...n, horizon: layerToHorizon(n.layer), children: [] });
    const byParent = (list, parentId) => list.filter((x) => (x.parent_id || null) === parentId);

    const trees = [];
    for (const v of visions) {
        const vn = node(v);
        const objs = byParent(objectives, v.id);
        for (const o of objs) {
            const on = node(o);
            on.children = byParent(goals, o.id).map((g) => node(g));
            vn.children.push(on);
        }
        vn.children.push(...byParent(goals, v.id).map((g) => node(g)));
        trees.push(vn);
    }
    return trees;
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
    const [viewMode, setViewMode] = useState('execute'); // 'plan' | 'execute'
    const [retrospective, setRetrospective] = useState(null);
    const [weeklyReviewDue, setWeeklyReviewDue] = useState(false);

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
                if (s.identity) {
                    setProfile({
                        occupation: s.identity.occupation ?? '',
                        focus_area: s.identity.focus_area ?? '',
                        daily_hours: s.identity.daily_hours ?? '',
                        ...s.identity
                    });
                }
                const allGoals = (s.goals || []).map((g) => ({
                    ...g,
                    horizon: g.layer === 'vision' ? 'vision' : g.layer === 'objective' ? 'milestone' : 'goal'
                }));
                setGoals({
                    active: allGoals.filter((g) => g.state === 'active'),
                    completed: allGoals.filter((g) => g.state === 'completed')
                });
                setGoalTree(buildTreeFromState(s.visions || [], s.objectives || [], allGoals));
            } else {
                const [profileRes, goalsRes, treeRes] = await Promise.allSettled([
                    api.get('/onboarding/status'),
                    api.get('/goals/list'),
                    api.get('/goals/tree')
                ]);
                if (profileRes.status === 'fulfilled') setProfile(profileRes.value.data.profile);
                if (goalsRes.status === 'fulfilled') setGoals(goalsRes.value.data);
                if (treeRes.status === 'fulfilled') setGoalTree(treeRes.value.data.tree || []);
            }

            const [tasksRes, currentRes, retroRes] = await Promise.allSettled([
                api.get('/tasks/list'),
                api.get('/tasks/current'),
                api.get('/retrospective', { params: { days: 7 } })
            ]);
            if (tasksRes.status === 'fulfilled') setTasks(tasksRes.value.data);
            if (currentRes.status === 'fulfilled') setCurrentTask(currentRes.value.data.task);
            if (retroRes.status === 'fulfilled') setRetrospective(retroRes.value.data);
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
            await fetchAll(); // 刷新所有数据
        } catch (e) {
            console.error(e);
            setError('完成任务失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const handleSkip = async () => {
        if (!currentTask || actionLoading) return;
        try {
            const reason = prompt("跳过原因？");
            if (reason) {
                setActionLoading(true);
                await api.post(`/tasks/${currentTask.id}/skip`, { reason });
                await fetchAll();
            }
        } catch (e) {
            console.error(e);
            setError('跳过任务失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setActionLoading(false);
        }
    };

    const handleDeleteGoal = async (goalId, e) => {
        e?.preventDefault();
        e?.stopPropagation();
        if (!window.confirm('确定要删除这个目标吗？')) return;
        try {
            setActionLoading(true);
            await api.delete(`/goals/${goalId}`);
            await fetchAll();
        } catch (e) {
            console.error(e);
            setError('删除失败');
        } finally {
            setActionLoading(false);
        }
    };

    // 计算目标进度
    const getGoalProgress = (goalId) => {
        const goalTasks = [...tasks.pending, ...tasks.completed].filter(t => t.goal_id === goalId);
        const completedCount = tasks.completed.filter(t => t.goal_id === goalId).length;
        return { completed: completedCount, total: goalTasks.length };
    };

    if (loading) {
        return (
            <div className="container flex-center" style={{ height: '100vh' }}>
                <div className="animate-pulse">加载 AI Life OS...</div>
            </div>
        );
    }

    return (
        <div className="container">
            {/* Header + 规划/执行 切换 */}
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '1rem' }}>
                <h3 style={{ margin: 0, opacity: 0.7 }}>AI Life OS</h3>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                    <div className="view-toggle" role="tablist" style={{ display: 'flex', background: 'rgba(0,0,0,0.2)', borderRadius: '8px', padding: '2px' }}>
                        <button
                            type="button"
                            role="tab"
                            aria-selected={viewMode === 'execute'}
                            className={viewMode === 'execute' ? 'view-toggle--active' : ''}
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
                            ⚡ 执行
                        </button>
                        <button
                            type="button"
                            role="tab"
                            aria-selected={viewMode === 'plan'}
                            className={viewMode === 'plan' ? 'view-toggle--active' : ''}
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
                            🎯 规划
                        </button>
                    </div>
                    <Link to="/vision/new" className="btn btn-primary" style={{ fontSize: '0.875rem' }}>+ 愿景</Link>
                    <Link to="/goals/new" className="btn btn-secondary" style={{ fontSize: '0.875rem' }}>+ 目标</Link>
                </div>
            </header>

            {/* 周报可查看入口 */}
            {weeklyReviewDue && (
                <div style={{
                    background: 'rgba(139, 92, 246, 0.15)',
                    border: '1px solid rgba(139, 92, 246, 0.4)',
                    borderRadius: '8px',
                    padding: '0.75rem 1rem',
                    marginBottom: '1.5rem',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.5rem',
                    color: 'var(--accent-color)'
                }}>
                    <span style={{ fontSize: '1rem' }}>📋</span>
                    <span style={{ fontWeight: 500 }}>周报可查看</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.875rem' }}>— 向下滚动至「Guardian 复盘」查看本周总结与建议</span>
                </div>
            )}

            {/* Error Banner */}
            {error && (
                <div style={{
                    background: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid rgba(239, 68, 68, 0.5)',
                    borderRadius: '8px',
                    padding: '1rem',
                    marginBottom: '1.5rem',
                    color: '#fca5a5'
                }}>
                    ⚠️ {error}
                </div>
            )}

            {/* 我的信息：执行视图下收折为一行，规划视图下完整 */}
            {profile && (
                <section style={{ marginBottom: viewMode === 'execute' ? '1rem' : '2rem' }}>
                    {viewMode === 'plan' ? (
                        <>
                            <h4 style={{ color: 'var(--accent-color)', marginBottom: '1rem', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                                📋 我的信息
                            </h4>
                            <div className="glass-card" style={{ padding: '1.5rem' }}>
                                <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap' }}>
                                    <div>
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>职业</span>
                                        <div style={{ fontSize: '1.125rem', fontWeight: 500 }}>{profile.occupation || '未设置'}</div>
                                    </div>
                                    <div>
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>关注领域</span>
                                        <div style={{ fontSize: '1.125rem', fontWeight: 500 }}>{profile.focus_area || '未设置'}</div>
                                    </div>
                                    <div>
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem' }}>每日可用时间</span>
                                        <div style={{ fontSize: '1.125rem', fontWeight: 500 }}>{profile.daily_hours || '未设置'}</div>
                                    </div>
                                </div>
                            </div>
                        </>
                    ) : (
                        <p style={{ margin: 0, fontSize: '0.875rem', color: 'var(--text-secondary)' }}>
                            {profile.occupation || '未设置'} · {profile.focus_area || '未设置'} · 可用 {profile.daily_hours || '—'}
                        </p>
                    )}
                </section>
            )}

            {viewMode === 'plan' && (
            <>
            {/* 目标层级展示 - 按愿景分块 */}
            <section style={{ marginBottom: '2rem' }}>
                <h4 style={{ color: 'var(--accent-color)', marginBottom: '1rem', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    🎯 我的愿景
                </h4>

                {/* 愿景树形展示 */}
                {goalTree.length > 0 ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                        {goalTree.filter(v => v.horizon === 'vision').map(vision => (
                            <div key={vision.id} className="glass-card" style={{ padding: '1.25rem', borderLeft: '4px solid #f59e0b' }}>
                                {/* 愿景标题 */}
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                                    <div>
                                        <span style={{ color: '#f59e0b', fontSize: '0.7rem', fontWeight: 600 }}>🌟 愿景</span>
                                        <h4 style={{ margin: '0.25rem 0 0 0', fontSize: '1.125rem' }}>{vision.title}</h4>
                                    </div>
                                    <Link to={`/goals/${vision.id}/decompose`} className="btn btn-secondary" style={{ fontSize: '0.75rem', padding: '0.25rem 0.75rem' }}>
                                        + 分解
                                    </Link>
                                </div>

                                {/* 里程碑 */}
                                {vision.children?.filter(m => m.horizon === 'milestone').length > 0 && (
                                    <div style={{ marginLeft: '1rem', borderLeft: '2px solid rgba(139, 92, 246, 0.3)', paddingLeft: '1rem' }}>
                                        {vision.children.filter(m => m.horizon === 'milestone').map(milestone => (
                                            <div key={milestone.id} style={{ marginBottom: '1rem' }}>
                                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                                    <div>
                                                        <span style={{ color: '#8b5cf6', fontSize: '0.65rem', fontWeight: 600 }}>🏔️ 里程碑</span>
                                                        <h5 style={{ margin: '0.2rem 0', fontSize: '0.9375rem' }}>{milestone.title}</h5>
                                                    </div>
                                                    <Link to={`/goals/${milestone.id}/decompose`} className="btn btn-secondary" style={{ fontSize: '0.7rem', padding: '0.2rem 0.5rem' }}>
                                                        分解
                                                    </Link>
                                                </div>

                                                {/* 目标 */}
                                                {milestone.children?.filter(g => g.horizon === 'goal').length > 0 && (
                                                    <div style={{ marginLeft: '1rem', marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                                        {milestone.children.filter(g => g.horizon === 'goal').map(goal => {
                                                            const progress = getGoalProgress(goal.id);
                                                            const pct = progress.total > 0 ? Math.round(progress.completed / progress.total * 100) : 0;
                                                            return (
                                                                <div key={goal.id} style={{
                                                                    background: 'rgba(16, 185, 129, 0.1)',
                                                                    border: '1px solid rgba(16, 185, 129, 0.3)',
                                                                    borderRadius: '6px',
                                                                    padding: '0.5rem 0.75rem',
                                                                    fontSize: '0.8rem',
                                                                    display: 'flex',
                                                                    alignItems: 'center'
                                                                }}>
                                                                    <span style={{ color: '#10b981', marginRight: '4px' }}>🎯</span>
                                                                    <span style={{ marginRight: '0.5rem' }}>{goal.title}</span>
                                                                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem', flex: 1 }}>{pct}%</span>
                                                                    <button
                                                                        onClick={(e) => handleDeleteGoal(goal.id, e)}
                                                                        style={{
                                                                            border: 'none',
                                                                            background: 'none',
                                                                            color: 'rgba(239, 68, 68, 0.5)',
                                                                            cursor: 'pointer',
                                                                            padding: '0 0 0 0.5rem',
                                                                            fontSize: '1rem',
                                                                            lineHeight: 0.8
                                                                        }}
                                                                        title="删除"
                                                                    >×</button>
                                                                </div>
                                                            );
                                                        })}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                    </div>
                                )}

                                {/* 直接挂在愿景下的目标（无里程碑） */}
                                {vision.children?.filter(g => g.horizon === 'goal').length > 0 && (
                                    <div style={{ marginLeft: '1rem', marginTop: '0.5rem', display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                                        {vision.children.filter(g => g.horizon === 'goal').map(goal => {
                                            const progress = getGoalProgress(goal.id);
                                            const pct = progress.total > 0 ? Math.round(progress.completed / progress.total * 100) : 0;
                                            return (
                                                <div key={goal.id} style={{
                                                    background: 'rgba(16, 185, 129, 0.1)',
                                                    border: '1px solid rgba(16, 185, 129, 0.3)',
                                                    borderRadius: '6px',
                                                    padding: '0.5rem 0.75rem',
                                                    fontSize: '0.8rem'
                                                }}>
                                                    <span style={{ color: '#10b981' }}>🎯</span> {goal.title}
                                                    <span style={{ color: 'var(--text-secondary)', marginLeft: '0.5rem', fontSize: '0.7rem' }}>{pct}%</span>
                                                </div>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="glass-card empty-state">
                        暂无愿景。<Link to="/vision/new" className="empty-state-cta">创建愿景，开始规划</Link>
                    </div>
                )}

                {/* 独立目标（没有挂在愿景下的） */}
                {goals.active?.filter(g => !g.parent_id && g.horizon !== 'vision').length > 0 && (
                    <div style={{ marginTop: '1.5rem' }}>
                        <h5 style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginBottom: '0.75rem' }}>📋 独立目标</h5>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '0.75rem' }}>
                            {goals.active.filter(g => !g.parent_id && g.horizon !== 'vision').map(goal => {
                                const progress = getGoalProgress(goal.id);
                                const pct = progress.total > 0 ? Math.round(progress.completed / progress.total * 100) : 0;
                                return (
                                    <div key={goal.id} className="glass-card" style={{ padding: '1rem', borderLeft: '3px solid #10b981' }}>
                                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                                            <h5 style={{ margin: '0 0 0.5rem 0', fontSize: '0.875rem', paddingRight: '1rem' }}>{goal.title}</h5>
                                            <button
                                                onClick={(e) => handleDeleteGoal(goal.id, e)}
                                                style={{ border: 'none', background: 'none', color: 'rgba(239, 68, 68, 0.5)', cursor: 'pointer', fontSize: '1.2rem', lineHeight: 0.5 }}
                                                title="删除"
                                            >×</button>
                                        </div>
                                        <div style={{ background: 'rgba(255,255,255,0.1)', borderRadius: '4px', height: '4px' }}>
                                            <div style={{ background: '#10b981', height: '100%', width: `${pct}%` }} />
                                        </div>
                                        <span style={{ color: 'var(--text-secondary)', fontSize: '0.7rem' }}>{progress.completed}/{progress.total} 任务</span>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </section>

            {/* 已完成目标 - 仅规划视图 */}
            {goals.completed?.length > 0 && (
                <section style={{ marginTop: '2rem' }}>
                    <h4 style={{ color: 'var(--text-secondary)', marginBottom: '1rem', fontSize: '0.875rem' }}>
                        ✓ 已完成目标 ({goals.completed.length})
                    </h4>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                        {goals.completed.map((goal) => (
                            <span key={goal.id} style={{
                                background: 'rgba(34, 197, 94, 0.2)',
                                color: 'var(--success-color)',
                                padding: '0.25rem 0.75rem',
                                borderRadius: '999px',
                                fontSize: '0.75rem'
                            }}>
                                {goal.title}
                            </span>
                        ))}
                    </div>
                </section>
            )}
            </>
            )}

            {/* 当前任务 - 仅执行视图 */}
            {viewMode === 'execute' && (
            <section>
                <h4 style={{ color: 'var(--accent-color)', marginBottom: '1rem', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                    ⚡ 当前任务
                </h4>
                {!currentTask ? (
                    <div className="glass-card empty-state empty-state--success">
                        <h2 className="empty-state-title">🎉 全部完成</h2>
                        <p className="empty-state-desc">今日暂无待办任务</p>
                        <Link to="/goals/new" className="btn btn-primary">规划新征程</Link>
                    </div>
                ) : (
                    <div className="glass-card" style={{ padding: '2rem', position: 'relative', overflow: 'hidden' }}>
                        {/* Background Glow */}
                        <div style={{
                            position: 'absolute', top: '0', right: '0', width: '200px', height: '200px',
                            background: 'radial-gradient(circle, var(--accent-glow) 0%, transparent 70%)',
                            opacity: 0.3, pointerEvents: 'none'
                        }} />

                        <h5 style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem', marginTop: 0, fontSize: '0.875rem' }}>
                            {currentTask.goal_title}
                        </h5>
                        <h2 style={{ fontSize: '1.75rem', marginBottom: '1.5rem', lineHeight: 1.2 }}>
                            {currentTask.description}
                        </h2>

                        <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '2rem', color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                            <span>🕒 {currentTask.estimated_minutes} 分钟</span>
                            <span>📅 {currentTask.scheduled_date} {currentTask.scheduled_time !== 'Anytime' ? currentTask.scheduled_time : ''}</span>
                        </div>

                        <div style={{ display: 'flex', gap: '1rem' }}>
                            <button
                                onClick={handleComplete}
                                className="btn btn-primary"
                                style={{ padding: '0.875rem 2rem', fontSize: '1rem' }}
                                disabled={actionLoading}
                            >
                                {actionLoading ? '处理中...' : '✅ 完成任务'}
                            </button>
                            <button
                                onClick={handleSkip}
                                className="btn btn-secondary"
                                disabled={actionLoading}
                            >
                                跳过
                            </button>
                        </div>
                    </div>
                )}
            </section>
            )}

            {/* Guardian 复盘（最近 7 天 / 本周期） */}
            {retrospective && (
                <section style={{ marginTop: '2rem' }}>
                    <h4 style={{ color: 'var(--accent-color)', marginBottom: '1rem', fontSize: '0.875rem', textTransform: 'uppercase', letterSpacing: '1px' }}>
                        🛡️ Guardian 复盘
                    </h4>
                    <div className="glass-card" style={{ padding: '1.25rem' }}>
                        <p style={{ margin: '0 0 1rem 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            最近 {retrospective.period?.days ?? 7} 天 · {retrospective.period?.start_date ?? ''} 至 {retrospective.period?.end_date ?? ''}
                        </p>
                        <p style={{ margin: '0 0 1rem 0', fontSize: '1rem', lineHeight: 1.5 }}>
                            {retrospective.observations?.[0] ?? retrospective.rhythm?.summary ?? '本周期暂无总结'}
                        </p>
                        {retrospective.observations?.length > 1 && (
                            <ul style={{ margin: '0 0 1rem 0', paddingLeft: '1.25rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                                {retrospective.observations.slice(1, 3).map((obs, i) => (
                                    <li key={i}>{obs}</li>
                                ))}
                            </ul>
                        )}
                        {retrospective.display && retrospective.suggestion && (
                            <div style={{
                                background: 'rgba(139, 92, 246, 0.15)',
                                border: '1px solid rgba(139, 92, 246, 0.3)',
                                borderRadius: '8px',
                                padding: '1rem',
                                marginTop: '0.75rem'
                            }}>
                                <span style={{ fontSize: '0.75rem', color: 'var(--accent-color)', fontWeight: 600 }}>建议</span>
                                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.9rem' }}>{retrospective.suggestion}</p>
                                {retrospective.require_confirm && (
                                    <p style={{ margin: '0.5rem 0 0 0', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>请确认已读</p>
                                )}
                            </div>
                        )}
                    </div>
                </section>
            )}
        </div>
    );
}
