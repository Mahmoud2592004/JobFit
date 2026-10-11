import { Navigate, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/AppLayout';
import ApplicationDetail from './pages/ApplicationDetail';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import Help from './pages/Help';
import Jobs from './pages/Jobs';
import Landing from './pages/Landing';
import Onboarding from './pages/Onboarding';
import Preferences from './pages/Preferences';
import Profile from './pages/Profile';
import Resumes from './pages/Resumes';
import Settings from './pages/Settings';
import Tailor from './pages/Tailor';
import Tracker from './pages/Tracker';

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Auth mode="login" />} />
      <Route path="/signup" element={<Auth mode="signup" />} />
      <Route path="/onb" element={<Onboarding />} />
      <Route element={<AppLayout />}>
        <Route path="/dash" element={<Dashboard />} />
        <Route path="/jobs" element={<Jobs />} />
        <Route path="/jobs/:id" element={<Jobs />} />
        <Route path="/tailor/:jobId" element={<Tailor />} />
        <Route path="/tailor/:jobId/:resumeId" element={<Tailor />} />
        <Route path="/res" element={<Resumes />} />
        <Route path="/track" element={<Tracker />} />
        <Route path="/track/:id" element={<ApplicationDetail />} />
        <Route path="/prof" element={<Profile />} />
        <Route path="/prefs" element={<Preferences />} />
        <Route path="/set" element={<Settings />} />
        <Route path="/help" element={<Help />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
