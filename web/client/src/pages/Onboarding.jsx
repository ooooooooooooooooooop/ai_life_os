import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../utils/api';

export default function Onboarding() {
    const [question, setQuestion] = useState(null);
    const [answer, setAnswer] = useState('');
    const [loading, setLoading] = useState(true);
    const navigate = useNavigate();

    useEffect(() => {
        fetchQuestion();
    }, []);

    const fetchQuestion = async () => {
        try {
            const res = await api.get('/onboarding/status');
            if (res.data.completed) {
                navigate('/goals/new'); // Initial flow: onboard -> generate goals
                return;
            }
            setQuestion(res.data.next_question);
            setAnswer('');
        } catch (e) {
            console.error(e);
        } finally {
            setLoading(false);
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        if (!answer.trim()) return;

        setLoading(true);
        try {
            await api.post('/onboarding/answer', { answer });
            await fetchQuestion(); // Fetch next
        } catch (e) {
            console.error(e);
            setLoading(false);
        }
    };

    if (!question && loading) return null;

    return (
        <div className="container flex-center" style={{ minHeight: '100vh', flexDirection: 'column' }}>
            <div className="glass-card" style={{ padding: '3rem', width: '100%', maxWidth: '600px' }}>
                <h2 className="fade-in" style={{ marginBottom: '1.5rem', color: 'var(--text-secondary)', fontSize: '1rem', textTransform: 'uppercase', letterSpacing: '2px' }}>
                    建立用户画像
                </h2>

                <h1 className="fade-in" style={{ marginBottom: '2rem', lineHeight: '1.2' }}>
                    {question?.text}
                </h1>

                <form onSubmit={handleSubmit} className="fade-in" style={{ animationDelay: '0.2s' }}>
                    <input
                        autoFocus
                        type="text"
                        value={answer}
                        onChange={(e) => setAnswer(e.target.value)}
                        placeholder={question?.placeholder}
                        style={{
                            fontSize: '1.5rem',
                            padding: '1.5rem',
                            marginBottom: '2rem',
                            background: 'rgba(0,0,0,0.3)'
                        }}
                    />

                    <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                        <button type="submit" className="btn btn-primary" disabled={!answer.trim() || loading}>
                            {loading ? '思考中...' : '继续 ->'}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
}
