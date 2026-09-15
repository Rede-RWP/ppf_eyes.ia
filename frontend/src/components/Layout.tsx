import { useEffect, useMemo, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { logout as apiLogout } from '../api'
import { useAuth, useRole } from '../auth'
import BrandMark from './BrandMark'

type NavItem = { to: string; text: string; end?: boolean }
type NavGroup = { label: string; items: NavItem[] }

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const { me } = useAuth()
  const role = useRole()
  const [menuOpen, setMenuOpen] = useState(false)

  const nav = useMemo(() => {
    const groups: NavGroup[] = [
      {
        label: 'Operação',
        items: [{ to: '/', end: true, text: 'Dashboard' }],
      },
      {
        label: 'Monitoramento',
        items: [{ to: '/alerts', text: 'Alertas' }],
      },
    ]

    if (role.canViewCameras) {
      groups[0].items.push({ to: '/cameras', text: 'Câmeras' })
    }
    if (role.canManageStores || role.isGestor) {
      groups[0].items.push({ to: '/stores', text: 'Lojas' })
    }
    if (role.canManageProfiles) {
      groups[0].items.push({ to: '/profiles', text: 'Ambientes' })
    }

    if (!role.isOperador) {
      groups[1].items.push({ to: '/favorites', text: 'Favoritos' })
    }
    if (role.canViewReports) {
      groups[1].items.push({ to: '/reports', text: 'Relatórios' })
    }

    const sistema: NavItem[] = []
    if (role.canManageUsers) sistema.push({ to: '/users', text: 'Usuários' })
    if (role.canManageSettings) sistema.push({ to: '/settings', text: 'Configurações' })
    if (sistema.length) {
      groups.push({ label: 'Sistema', items: sistema })
    }
    return groups
  }, [role])

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
          {me ? (
            <p className="muted" style={{ margin: '0.5rem 0 0', fontSize: '0.8rem' }}>
              {me.display_name || me.username} · {me.role}
            </p>
          ) : null}
        </div>
        <nav className="nav" aria-label="Principal">
          {nav.map((group) => (
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
