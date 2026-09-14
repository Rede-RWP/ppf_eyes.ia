import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Alert, Dashboard } from '../api'
import AlertCard from '../components/AlertCard'

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [error, setError] = useState('')

  async function load() {
    const d = await api<Dashboard>('/api/dashboard')
    setData(d)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
    const t = setInterval(() => {
      load().catch(() => undefined)
    }, 10000)
    return () => clearInterval(t)
  }, [])

  function onChange(updated: Alert) {
    if (!data) return
    setData({
      ...data,
      recent_alerts: data.recent_alerts.map((a) => (a.id === updated.id ? updated : a)),
    })
  }

  if (!data) {
    return <p className="muted">{error || 'Carregando dashboard…'}</p>
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Dashboard</h1>
          <p className="page-sub">Visão geral do monitoramento em tempo quase real.</p>
        </div>
        <div className="page-actions">
          <Link to="/cameras" className="muted">
            Gerenciar câmeras
          </Link>
          <Link to="/reports">Relatórios</Link>
        </div>
      </div>

      <div className="grid-stats">
        <div className="stat">
          <span>Câmeras</span>
          <strong>{data.cameras_total}</strong>
        </div>
        <div className="stat">
          <span>Online</span>
          <strong>{data.cameras_online}</strong>
        </div>
        <div className="stat">
          <span>Offline</span>
          <strong>{data.cameras_offline}</strong>
        </div>
        <div className="stat">
          <span>Alertas hoje</span>
          <strong>{data.alerts_today}</strong>
        </div>
      </div>

      <div className="panel">
        <div className="panel-head">
          <h2>Alertas recentes</h2>
          <Link to="/alerts">Ver todos</Link>
        </div>
        {data.recent_alerts.length ? (
          <div className="alert-grid">
            {data.recent_alerts.map((alert) => (
              <AlertCard key={alert.id} alert={alert} onChange={onChange} />
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <p>Sem alertas recentes. Cadastre câmeras e configure a API.</p>
            <div className="row" style={{ justifyContent: 'center' }}>
              <Link to="/cameras">
                <button type="button">Câmeras</button>
              </Link>
              <Link to="/settings">
                <button type="button" className="secondary">
                  Configurações
                </button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
