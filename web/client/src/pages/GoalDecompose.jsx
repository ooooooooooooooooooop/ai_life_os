import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { api } from '../utils/api';

export default function GoalDecompose() {
    const { goalId } = useParams();
    const navigate = useNavigate();

    // 状态
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState(null);

    // 流程控制: 'questions' -> 'options'
    const [step, setStep] = useState('loading');

    // 数据
    const [questions, setQuestions] = useState([]);
    const [answers, setAnswers] = useState({});
    const [optionsData, setOptionsData] = useState(null);
    const [customInput, setCustomInput] = useState('');
    const [showCustom, setShowCustom] = useState(false);

    useEffect(() => {
        initFlow();
    }, [goalId]);

    const initFlow = async () => {
        try {
            setLoading(true);
            setError(null);

            // 获取评估问题
            const res = await api.get(`/goals/${goalId}/questions`);
            const qs = res.data.questions || [];

            if (qs.length > 0) {
                setQuestions(qs);
                setStep('questions');
            } else {
                // 没有问题，直接获取选项
                await fetchOptions({});
            }
        } catch (e) {
            console.error(e);
            setError('初始化失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const handleAnswerChange = (qId, value) => {
        setAnswers(prev => ({
            ...prev,
            [qId]: value
        }));
    };

    const submitAnswers = async () => {
        // 检查是否有未回答的问题
        const missing = questions.filter(q => !answers[q.id]);
        if (missing.length > 0) {
            setError('请回答所有问题');
            return;
        }
        await fetchOptions(answers);
    };

    const fetchOptions = async (contextAnswers) => {
        try {
            setLoading(true);
            setError(null);

            const context = {};
            questions.forEach(q => {
                const answer = contextAnswers[q.id];
                if (answer) context[q.question] = answer;
            });

            const res = await api.post(`/goals/${goalId}/decompose`, {
                context: Object.keys(context).length > 0 ? context : null
            });

            setOptionsData(res.data);
            setStep('options');
        } catch (e) {
            console.error(e);
            setError('获取选项失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const handleSelect = async (option) => {
        try {
            setSubmitting(true);
            const res = await api.post(`/goals/${goalId}/decompose`, {
                selected_option: option
            });

            if (res.data.success) {
                if (res.data.tasks_created > 0) {
                    navigate('/');
                } else if (res.data.goal.horizon === 'goal') {
                    // 如果还在 goal 层级，可能继续分解？或者假设 3 层结束
                    // 根据后端逻辑，如果创建的是 goal，就会尝试分解成 tasks
                    // 如果这里 tasks_created=0，说明可能要手动分解？
                    navigate(`/goals/${res.data.goal.id}/decompose`);
                } else {
                    // 继续下一层
                    navigate(`/goals/${res.data.goal.id}/decompose`);
                }
            }
        } catch (e) {
            console.error(e);
            setError('创建失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setSubmitting(false);
        }
    };

    const handleCustomSubmit = async () => {
        if (!customInput.trim()) return;
        try {
            setSubmitting(true);
            const res = await api.post(`/goals/${goalId}/decompose`, {
                custom_input: customInput
            });

            if (res.data.success) {
                if (res.data.tasks_created > 0) {
                    navigate('/');
                } else {
                    navigate(`/goals/${res.data.goal.id}/decompose`);
                }
            }
        } catch (e) {
            console.error(e);
            setError('创建失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setSubmitting(false);
        }
    };

    if (loading) {
        return (
            <div className="container flex-center" style={{ height: '100vh' }}>
                <div className="animate-pulse">AI 正在分析...</div>
            </div>
        );
    }

    return (
        <div className="container" style={{ maxWidth: '600px', margin: '0 auto', paddingTop: '2rem' }}>
            <button onClick={() => navigate('/')} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: '1rem' }}>
                ← 返回首页
            </button>

            {error && (
                <div style={{
                    background: 'rgba(239, 68, 68, 0.2)',
                    padding: '1rem',
                    borderRadius: '8px',
                    marginBottom: '1.5rem',
                    color: '#fca5a5'
                }}>
                    {error}
                </div>
            )}

            {/* Stage 1: Questions - 选择题 + 自定义输入 标准化 */}
            {step === 'questions' && (
                <div className="glass-card" style={{ padding: '2rem' }}>
                    <h2 style={{ marginBottom: '1rem' }}>评估可行性</h2>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        在分解之前，AI 需要了解一些基本情况来提供更精准的建议。
                    </p>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', marginBottom: '2rem' }}>
                        选择一项或填写下方「其他」。
                    </p>

                    <div className="decompose-questions" style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
                        {questions.map(q => (
                            <fieldset key={q.id} className="decompose-question-block" style={{ border: 'none', margin: 0, padding: '1.25rem', background: 'rgba(255,255,255,0.03)', borderRadius: '8px' }}>
                                <legend style={{ fontWeight: 500, fontSize: '1rem', marginBottom: '1rem' }}>
                                    {q.question}
                                </legend>
                                {q.options && (
                                    <div className="decompose-options" style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
                                        {q.options.map(opt => (
                                            <button
                                                key={opt}
                                                type="button"
                                                onClick={() => handleAnswerChange(q.id, opt)}
                                                className={`btn ${answers[q.id] === opt ? 'btn-primary' : 'btn-secondary'}`}
                                                style={{ fontSize: '0.875rem', padding: '0.4rem 1rem' }}
                                                aria-pressed={answers[q.id] === opt}
                                            >
                                                {opt}
                                            </button>
                                        ))}
                                    </div>
                                )}
                                <input
                                    type="text"
                                    value={answers[q.id] || ''}
                                    onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                                    className="decompose-custom-input"
                                    style={{
                                        width: '100%',
                                        background: 'rgba(0,0,0,0.2)',
                                        border: '1px solid rgba(255,255,255,0.1)',
                                        borderRadius: '6px',
                                        padding: '0.6rem 0.75rem',
                                        color: 'inherit',
                                        fontSize: '0.9375rem'
                                    }}
                                    placeholder="其他（选填）"
                                    aria-label={`${q.question} 其他`}
                                />
                            </fieldset>
                        ))}
                    </div>

                    <button
                        onClick={submitAnswers}
                        className="btn btn-primary"
                        style={{ width: '100%', marginTop: '2rem' }}
                    >
                        生成分解方案 →
                    </button>
                </div>
            )}

            {/* Stage 2: Options - AI 选项 + 自定义输入 标准化 */}
            {step === 'options' && optionsData && (
                <>
                    <h2 style={{ marginBottom: '0.5rem' }}>选择路径</h2>
                    <p style={{ color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                        基于你的回答，AI 推荐以下 {optionsData.horizon === 'milestone' ? '里程碑阶段' : '具体目标'}。
                    </p>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.8125rem', marginBottom: '2rem' }}>
                        选择一项或填写下方「其他」。
                    </p>

                    <div className="decompose-options-list" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                        {optionsData.candidates?.map((opt, i) => (
                            <button
                                key={i}
                                type="button"
                                onClick={() => handleSelect(opt)}
                                disabled={submitting}
                                className="glass-card decompose-option-card"
                                style={{
                                    padding: '1.25rem',
                                    textAlign: 'left',
                                    cursor: submitting ? 'not-allowed' : 'pointer',
                                    border: '1px solid var(--glass-border)',
                                    opacity: submitting ? 0.6 : 1,
                                    position: 'relative',
                                    overflow: 'hidden'
                                }}
                                aria-label={`选择: ${opt.title}`}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.5rem' }}>
                                    <h4 style={{ margin: 0, fontSize: '1rem' }}>{opt.title}</h4>
                                    {opt.probability != null && (
                                        <span style={{
                                            fontSize: '0.75rem',
                                            background: opt.probability > 70 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(245, 158, 11, 0.2)',
                                            color: opt.probability > 70 ? '#10b981' : '#f59e0b',
                                            padding: '0.2rem 0.6rem',
                                            borderRadius: '12px'
                                        }}>
                                            成功率 {opt.probability}%
                                        </span>
                                    )}
                                </div>
                                <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.875rem' }}>
                                    {opt.description}
                                </p>
                                {opt.reason && (
                                    <div style={{ marginTop: '0.75rem', fontSize: '0.75rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                                        🤖 {opt.reason}
                                    </div>
                                )}
                            </button>
                        ))}

                        {/* 自定义选项 - 与上方选项卡片同风格 */}
                        {!showCustom ? (
                            <button
                                type="button"
                                onClick={() => setShowCustom(true)}
                                className="glass-card decompose-custom-trigger"
                                style={{
                                    padding: '1.25rem',
                                    textAlign: 'center',
                                    cursor: 'pointer',
                                    border: '1px dashed rgba(255,255,255,0.35)',
                                    background: 'transparent',
                                    color: 'var(--text-secondary)',
                                    fontSize: '0.9375rem'
                                }}
                            >
                                ✏️ 其他（自定义输入）
                            </button>
                        ) : (
                            <div className="glass-card decompose-custom-block" style={{ padding: '1.25rem', border: '1px solid var(--glass-border)' }}>
                                <label style={{ display: 'block', marginBottom: '0.5rem', fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                    输入你的想法，不限于以上选项
                                </label>
                                <input
                                    type="text"
                                    value={customInput}
                                    onChange={(e) => setCustomInput(e.target.value)}
                                    placeholder="例如：自己写一个目标标题..."
                                    autoFocus
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem',
                                        background: 'rgba(0,0,0,0.2)',
                                        border: '1px solid rgba(255,255,255,0.2)',
                                        borderRadius: '8px',
                                        color: 'inherit',
                                        marginBottom: '0.75rem',
                                        fontSize: '0.9375rem'
                                    }}
                                    aria-label="自定义目标"
                                />
                                <button
                                    type="button"
                                    onClick={handleCustomSubmit}
                                    disabled={submitting || !customInput.trim()}
                                    className="btn btn-primary"
                                    style={{ width: '100%' }}
                                >
                                    {submitting ? '提交中...' : '确认'}
                                </button>
                            </div>
                        )}
                    </div>
                </>
            )}
        </div>
    );
}
