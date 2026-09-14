import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Alert } from '../api'
import AlertCard from '../components/AlertCard'

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [error, setError] = useState('')

  async function load() {
    const data = await api<Alert[]>('/api/alerts?limit=100')
    setAlerts(data)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
    const t = setInterval(() => {
      load().catch(() => undefined)
    }, 10000)
    return () => clearInterval(t)
  }, [])

  function onChange(updated: Alert) {
    setAlerts((prev) => prev.map((a) => (a.id === updated.id ? updated : a)))
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Alertas</h1>
          <p className="page-sub">
            👍 acerto · 👎 falso positivo (com comentário) · ★ guardar nos Favoritos.
          </p>
        </div>
        <div className="page-actions">
          <span className="muted">{alerts.length} alerta(s)</span>
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
          <p>Nenhum alerta ainda.</p>
        </div>
      )}
    </div>
  )
}
