import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchMe, type Me } from './api'

type AuthCtx = {
  me: Me | null
  loading: boolean
  refresh: () => Promise<void>
}

const Ctx = createContext<AuthCtx>({ me: null, loading: true, refresh: async () => undefined })

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  async function refresh() {
    setLoading(true)
    const data = await fetchMe()
    setMe(data)
    setLoading(false)
  }

  useEffect(() => {
    refresh().catch(() => {
      setMe(null)
      setLoading(false)
    })
  }, [])

  return <Ctx.Provider value={{ me, loading, refresh }}>{children}</Ctx.Provider>
}

export function useAuth() {
  return useContext(Ctx)
}

export function useRole() {
  const { me } = useAuth()
  const role = me?.role || 'operador'
  return {
    role,
    isAdmin: role === 'admin',
    isGestor: role === 'gestor',
    isOperador: role === 'operador',
    canManageStores: role === 'admin',
    canManageUsers: role === 'admin' || role === 'gestor',
    canManageCameras: role === 'admin',
    canViewCameras: role === 'admin' || role === 'gestor',
    canViewReports: role === 'admin' || role === 'gestor',
    canManageSettings: role === 'admin',
    canManageProfiles: role === 'admin',
  }
}
