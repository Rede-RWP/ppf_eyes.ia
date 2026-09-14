import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { logout as apiLogout } from '../api'
import BrandMark from './BrandMark'

const NAV = [
  {
    label: 'Operação',
    items: [
      { to: '/', end: true, text: 'Dashboard' },
      { to: '/cameras', text: 'Câmeras' },
      { to: '/profiles', text: 'Ambientes' },
    ],
  },
  {
    label: 'Monitoramento',
    items: [
      { to: '/alerts', text: 'Alertas' },
      { to: '/favorites', text: 'Favoritos' },
      { to: '/reports', text: 'Relatórios' },
    ],
  },
  {
    label: 'Sistema',
    items: [{ to: '/settings', text: 'Configurações' }],
  },
]

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  useEffect(() => {
    setMenuOpen(false)
  }, [location.pathname])

  useEffect(() => {
    if (!menuOpen) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMenuOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [menuOpen])

  async function onLogout() {
    await apiLogout()
    navigate('/login')
  }

  return (
    <div className="app-shell">
      <div className="mobile-bar">
        <BrandMark compact />
        <button
          type="button"
          className="icon-btn"
          aria-label={menuOpen ? 'Fechar menu' : 'Abrir menu'}
          aria-expanded={menuOpen}
          onClick={() => setMenuOpen((v) => !v)}
        >
          {menuOpen ? '✕' : '☰'}
        </button>
      </div>

      {menuOpen ? (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Fechar menu"
          onClick={() => setMenuOpen(false)}
        />
      ) : null}

      <aside className={`sidebar${menuOpen ? ' is-open' : ''}`}>
        <div className="sidebar-top">
          <BrandMark />
        </div>
        <nav className="nav" aria-label="Principal">
          {NAV.map((group) => (
            <div key={group.label}>
              <div className="nav-group">{group.label}</div>
              {group.items.map((item) => (
                <NavLink key={item.to} to={item.to} end={item.end}>
                  {item.text}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <button className="secondary" onClick={onLogout} type="button">
            Sair
          </button>
        </div>
      </aside>

      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
