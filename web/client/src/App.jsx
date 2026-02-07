import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { api } from './utils/api';

// Pages
import Home from './pages/Home';
import Onboarding from './pages/Onboarding';
import GoalGeneration from './pages/GoalGeneration';
import VisionCreation from './pages/VisionCreation';
import GoalDecompose from './pages/GoalDecompose';

function App() {
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    checkStatus();
  }, []);

  const checkStatus = async () => {
    try {
      const res = await api.get('/onboarding/status');
      if (!res.data.completed) {
        if (location.pathname !== '/onboarding') {
          navigate('/onboarding');
        }
      }
    } catch (e) {
      console.error("Failed to check status", e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex-center" style={{ height: '100vh' }}>
        <div className="animate-pulse">Loading AI Life OS...</div>
      </div>
    );
  }

  return (
    <div className="app-container">
      {/* Dynamic Background */}
      <div style={{
        position: 'fixed',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        background: 'radial-gradient(circle at 50% 50%, #1e293b 0%, #0f172a 100%)',
        zIndex: -1
      }} />

      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/onboarding" element={<Onboarding />} />
        <Route path="/goals/new" element={<GoalGeneration />} />
        <Route path="/vision/new" element={<VisionCreation />} />
        <Route path="/goals/:goalId/decompose" element={<GoalDecompose />} />
      </Routes>
    </div>
  );
}

export default App;
