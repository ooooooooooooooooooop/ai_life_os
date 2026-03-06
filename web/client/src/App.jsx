import { useState, useEffect } from 'react';
import { Routes, Route, useNavigate, useLocation } from 'react-router-dom';
import { api } from './utils/api';

// Components
import Navbar from './components/Navbar';
import { ToastProvider } from './components/Toast';
import ErrorBoundary from './components/ErrorBoundary';

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
      <div className="min-h-screen flex items-center justify-center bg-slate-900">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-400">Loading AI Life OS...</p>
        </div>
      </div>
    );
  }

  return (
    <ErrorBoundary>
      <ToastProvider>
        <div className="min-h-screen bg-slate-900">
          {/* Dynamic Background */}
          <div className="fixed inset-0 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 -z-10" />

          {/* Navbar */}
          {location.pathname !== '/onboarding' && <Navbar />}

          {/* Main Content */}
          <main className="py-8">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/onboarding" element={<Onboarding />} />
              <Route path="/goals/new" element={<GoalGeneration />} />
              <Route path="/vision/new" element={<VisionCreation />} />
              <Route path="/goals/:goalId/decompose" element={<GoalDecompose />} />
            </Routes>
          </main>
        </div>
      </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
