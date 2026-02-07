import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../utils/api';

export default function GoalGeneration() {
    const [candidates, setCandidates] = useState([]);
    const [generating, setGenerating] = useState(false);
    const navigate = useNavigate();

    const handleGenerate = async () => {
        setGenerating(true);
        try {
            const res = await api.post('/goals/generate', { n: 3 });
            setCandidates(res.data.candidates);
        } catch (e) {
            console.error(e);
            alert("生成失败，请检查后端日志。");
        } finally {
            setGenerating(false);
        }
    };

    const handleConfirm = async (goal) => {
        try {
            if (confirm(`确认要开启目标： "${goal.title}"?`)) {
                await api.post('/goals/confirm', { goal });
                navigate('/');
            }
        } catch (e) {
            console.error(e);
        }
    };

    if (candidates.length === 0) {
        return (
            <div className="container flex-center" style={{ minHeight: '100vh', flexDirection: 'column', textAlign: 'center' }}>
                <h1 style={{ marginBottom: '1rem' }}>设计你的成长路径</h1>
                <p style={{ color: 'var(--text-secondary)', marginBottom: '3rem', maxWidth: '500px' }}>
                    AI 将基于 Better Human Blueprint 哲学，结合你的个人情况，规划最具价值的目标。
                </p>

                <button
                    onClick={handleGenerate}
                    className="btn btn-primary"
                    style={{ fontSize: '1.25rem', padding: '1rem 3rem' }}
                    disabled={generating}
                >
                    {generating ? '正在分析与规划...' : '生成目标建议'}
                </button>
            </div>
        );
    }

    return (
        <div className="container" style={{ padding: '4rem 2rem' }}>
            <header style={{ marginBottom: '3rem', textAlign: 'center' }}>
                <h1 className="fade-in">建议目标</h1>
                <p className="fade-in" style={{ color: 'var(--text-secondary)' }}>基于 Blueprint 评估模型</p>
            </header>

            <div className="grid-cols-2 fade-in" style={{ animationDelay: '0.2s' }}>
                {candidates.map((goal) => (
                    <div key={goal.id} className="glass-card" style={{ padding: '2rem', display: 'flex', flexDirection: 'column' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
                            <h2 style={{ fontSize: '1.5rem', margin: 0 }}>{goal.title}</h2>
                            <span style={{
                                background: goal._score > 0.8 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                                color: goal._score > 0.8 ? '#34d399' : '#60a5fa',
                                padding: '0.25rem 0.75rem',
                                borderRadius: '99px',
                                fontSize: '0.875rem',
                                fontWeight: 'bold'
                            }}>
                                匹配度: {Math.round(goal._score * 100)}%
                            </span>
                        </div>

                        <p style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem', flexGrow: 1 }}>
                            {goal.description}
                        </p>

                        <div style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>
                            <strong>目标程度:</strong> {goal.target_level} <br />
                            <strong>所需资源:</strong> {goal.resource_description}
                        </div>

                        <button onClick={() => handleConfirm(goal)} className="btn btn-primary" style={{ width: '100%' }}>
                            接受挑战
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
}
