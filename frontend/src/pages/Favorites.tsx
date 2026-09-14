import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Alert } from '../api'
import AlertCard from '../components/AlertCard'

export default function FavoritesPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState('')

  async function load() {
    const data = await api<Alert[]>('/api/favorites')
    setAlerts(data)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  function onChange(updated: Alert) {
    if (!updated.favorited) {
      setAlerts((prev) => prev.filter((a) => a.id !== updated.id))
      return
    }
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Favoritos</h1>
          <p className="page-sub">
            Fotos marcadas com ★ — cópia permanente em disco.
          </p>
        </div>
        <div className="page-actions">
          <Link to="/alerts">Ir para alertas</Link>
        </div>
      </div>

      {error ? <p className="flash error">{error}</p> : null}

      {alerts.length ? (
        <div className="alert-grid">
          {alerts.map((alert) => (
            <AlertCard key={alert.id} alert={alert} onChange={onChange} />
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <p>Nenhum favorito ainda. Marque ★ nos alertas.</p>
          <Link to="/alerts">
            <button type="button" className="secondary">
              Ver alertas
            </button>
          </Link>
        </div>
      )}
    </div>
  )
}
