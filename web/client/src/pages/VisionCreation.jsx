import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../utils/api';

export default function VisionCreation() {
    const navigate = useNavigate();
    const [mode, setMode] = useState('recommend'); // 'recommend' | 'custom'
    const [customTitle, setCustomTitle] = useState('');
    const [customDesc, setCustomDesc] = useState('');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // 推荐选项
    const recommendedVisions = [
        { title: "实现财务自由", desc: "通过创业或投资实现被动收入超越日常开支" },
        { title: "成为行业专家", desc: "在专业领域建立权威，获得业界认可" },
        { title: "健康且精力充沛", desc: "保持身心健康，拥有充足精力追求目标" },
        { title: "建立深度连接", desc: "与家人朋友建立深层次的情感联系" }
    ];

    const handleSelect = async (title, desc) => {
        try {
            setLoading(true);
            setError(null);
            const res = await api.post('/goals/vision', {
                title,
                description: desc,
                source: 'user_selected'
            });
            if (res.data.success) {
                // 跳转到分解页面
                navigate(`/goals/${res.data.vision_id}/decompose`);
            }
        } catch (e) {
            console.error(e);
            setError('创建失败: ' + (e.response?.data?.detail || e.message));
        } finally {
            setLoading(false);
        }
    };

    const handleCustomSubmit = async () => {
        if (!customTitle.trim()) {
            setError('请输入愿景标题');
            return;
        }
        await handleSelect(customTitle, customDesc);
    };

    return (
        <div className="container" style={{ maxWidth: '600px', margin: '0 auto', paddingTop: '2rem' }}>
            <button onClick={() => navigate('/')} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: '1rem' }}>
                ← 返回
            </button>

            <h1 style={{ marginBottom: '0.5rem' }}>创建愿景</h1>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '2rem' }}>
                愿景是你的长远目标（5-10年），系统会帮你分解成可执行的任务
            </p>

            {error && (
                <div style={{
                    background: 'rgba(239, 68, 68, 0.2)',
                    border: '1px solid rgba(239, 68, 68, 0.5)',
                    borderRadius: '8px',
                    padding: '1rem',
                    marginBottom: '1.5rem',
                    color: '#fca5a5'
                }}>
                    {error}
                </div>
            )}

            {/* 模式切换 */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '2rem' }}>
                <button
                    onClick={() => setMode('recommend')}
                    className={mode === 'recommend' ? 'btn btn-primary' : 'btn btn-secondary'}
                    style={{ flex: 1 }}
                >
                    📋 选择推荐
                </button>
                <button
                    onClick={() => setMode('custom')}
                    className={mode === 'custom' ? 'btn btn-primary' : 'btn btn-secondary'}
                    style={{ flex: 1 }}
                >
                    ✏️ 自定义
                </button>
            </div>

            {mode === 'recommend' ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    {recommendedVisions.map((v, i) => (
                        <button
                            key={i}
                            onClick={() => handleSelect(v.title, v.desc)}
                            disabled={loading}
                            className="glass-card"
                            style={{
                                padding: '1.5rem',
                                textAlign: 'left',
                                cursor: 'pointer',
                                border: 'none',
                                transition: 'transform 0.2s, box-shadow 0.2s'
                            }}
                            onMouseEnter={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                            onMouseLeave={(e) => e.currentTarget.style.transform = 'translateY(0)'}
                        >
                            <h3 style={{ margin: '0 0 0.5rem 0' }}>{v.title}</h3>
                            <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.875rem' }}>{v.desc}</p>
                        </button>
                    ))}
                </div>
            ) : (
                <div className="glass-card" style={{ padding: '1.5rem' }}>
                    <div style={{ marginBottom: '1rem' }}>
                        <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>愿景标题</label>
                        <input
                            type="text"
                            value={customTitle}
                            onChange={(e) => setCustomTitle(e.target.value)}
                            placeholder="例：挣一个亿"
                            style={{
                                width: '100%',
                                padding: '0.75rem',
                                background: 'rgba(255,255,255,0.1)',
                                border: '1px solid rgba(255,255,255,0.2)',
                                borderRadius: '8px',
                                color: 'white',
                                fontSize: '1rem'
                            }}
                        />
                    </div>
                    <div style={{ marginBottom: '1.5rem' }}>
                        <label style={{ display: 'block', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>描述（可选）</label>
                        <textarea
                            value={customDesc}
                            onChange={(e) => setCustomDesc(e.target.value)}
                            placeholder="描述你的愿景..."
                            rows={3}
                            style={{
                                width: '100%',
                                padding: '0.75rem',
                                background: 'rgba(255,255,255,0.1)',
                                border: '1px solid rgba(255,255,255,0.2)',
                                borderRadius: '8px',
                                color: 'white',
                                fontSize: '1rem',
                                resize: 'vertical'
                            }}
                        />
                    </div>
                    <button
                        onClick={handleCustomSubmit}
                        disabled={loading || !customTitle.trim()}
                        className="btn btn-primary"
                        style={{ width: '100%' }}
                    >
                        {loading ? '创建中...' : '创建愿景'}
                    </button>
                </div>
            )}
        </div>
    );
}
