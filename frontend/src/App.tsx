import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useEffect, useState, type ReactNode } from 'react'
import Layout from './components/Layout'
import { fetchMe, hasAuthMarker } from './api'
import AlertsPage from './pages/Alerts'
import CamerasPage from './pages/Cameras'
import DashboardPage from './pages/Dashboard'
import FavoritesPage from './pages/Favorites'
import LoginPage from './pages/Login'
import ProfilesPage from './pages/Profiles'
import ReportsPage from './pages/Reports'
import SettingsPage from './pages/Settings'

function Private({ children }: { children: ReactNode }) {
  const location = useLocation()
  const [checking, setChecking] = useState(true)
  const [ok, setOk] = useState(false)

  useEffect(() => {
    let alive = true
    setChecking(true)
    fetchMe().then((me) => {
      if (!alive) return
      setOk(!!me)
      setChecking(false)
    })
    return () => {
      alive = false
    }
  }, [location.pathname])

  if (checking) {
    if (hasAuthMarker()) return children
    return <p className="muted" style={{ padding: '2rem' }}>Verificando sessão…</p>
  }
  if (!ok) return <Navigate to="/login" replace />
  return children
}

export default function App() {
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
        <Route path="cameras" element={<CamerasPage />} />
        <Route path="profiles" element={<ProfilesPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="favorites" element={<FavoritesPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
