import { Navigate, Outlet } from 'react-router-dom';
import { useApp } from '../store/AppContext';
import { Shell } from './Shell';

/** Authenticated area: requires a user and an onboarded profile. */
export function AppLayout() {
  const { state } = useApp();
  if (!state.user) return <Navigate to="/login" replace />;
  if (!state.profile) return <Navigate to="/onb" replace />;
  return (
    <Shell>
      <Outlet />
    </Shell>
  );
}
