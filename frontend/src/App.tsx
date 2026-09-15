import { Navigate, Route, Routes } from 'react-router-dom'
import type { ReactNode } from 'react'
import Layout from './components/Layout'
import { AuthProvider, useAuth, useRole } from './auth'
import AlertsPage from './pages/Alerts'
import CamerasPage from './pages/Cameras'
import DashboardPage from './pages/Dashboard'
import FavoritesPage from './pages/Favorites'
import LoginPage from './pages/Login'
import ProfilesPage from './pages/Profiles'
import ReportsPage from './pages/Reports'
import SettingsPage from './pages/Settings'
import StoresPage from './pages/Stores'
import UsersPage from './pages/Users'

function Private({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth()
  if (loading) {
    return <p className="muted" style={{ padding: '2rem' }}>Verificando sessão…</p>
  }
  if (!me) return <Navigate to="/login" replace />
  return children
}

function RoleGate({
  allow,
  children,
}: {
  allow: boolean
  children: ReactNode
}) {
  const { loading } = useAuth()
  if (loading) {
    return <p className="muted" style={{ padding: '2rem' }}>Carregando…</p>
  }
  if (!allow) return <Navigate to="/alerts" replace />
  return children
}

function GatedRoutes() {
  const role = useRole()
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <Private>
            <Layout />
          </Private>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route
          path="cameras"
          element={
            <RoleGate allow={role.canViewCameras}>
              <CamerasPage />
            </RoleGate>
          }
        />
        <Route
          path="stores"
          element={
            <RoleGate allow={role.canManageStores || role.isGestor}>
              <StoresPage />
            </RoleGate>
          }
        />
        <Route
          path="users"
          element={
            <RoleGate allow={role.canManageUsers}>
              <UsersPage />
            </RoleGate>
          }
        />
        <Route
          path="profiles"
          element={
            <RoleGate allow={role.canManageProfiles}>
              <ProfilesPage />
            </RoleGate>
          }
        />
        <Route path="alerts" element={<AlertsPage />} />
        <Route
          path="favorites"
          element={
            <RoleGate allow={!role.isOperador}>
              <FavoritesPage />
            </RoleGate>
          }
        />
        <Route
          path="reports"
          element={
            <RoleGate allow={role.canViewReports}>
              <ReportsPage />
            </RoleGate>
          }
        />
        <Route
          path="settings"
          element={
            <RoleGate allow={role.canManageSettings}>
              <SettingsPage />
            </RoleGate>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <GatedRoutes />
    </AuthProvider>
  )
}
