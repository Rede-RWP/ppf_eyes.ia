const SESSION_FLAG = 'ppf_eyes_authed'

export function markAuthed() {
  sessionStorage.setItem(SESSION_FLAG, '1')
}

export function clearAuth() {
  sessionStorage.removeItem(SESSION_FLAG)
}

export function hasAuthMarker(): boolean {
  return sessionStorage.getItem(SESSION_FLAG) === '1'
}

export function mediaUrl(path?: string | null): string | undefined {
  if (!path) return undefined
  const clean = path.replace(/^\/+/, '')
  if (clean.startsWith('snapshots/') || clean.startsWith('favorites/')) {
    return `/media/${clean}`
  }
  return `/media/snapshots/${clean}`
}

async function parseError(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data.detail === 'string') return data.detail
    return JSON.stringify(data.detail || data)
  } catch {
    return res.statusText || 'Erro na requisição'
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const res = await fetch(path, {
    ...options,
    headers,
    credentials: 'include',
  })
  if (res.status === 401) {
    clearAuth()
    if (!window.location.pathname.includes('/login')) {
      window.location.href = '/login'
    }
    throw new Error('Não autenticado')
  }
  if (!res.ok) throw new Error(await parseError(res))
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export async function login(username: string, password: string) {
  const body = new URLSearchParams()
  body.set('username', username)
  body.set('password', password)
  const res = await fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
    credentials: 'include',
  })
  if (!res.ok) throw new Error(await parseError(res))
  const data = await res.json()
  markAuthed()
  return data
}

export async function logout() {
  try {
    await api('/api/auth/logout', { method: 'POST' })
  } catch {
    // ignore
  } finally {
    clearAuth()
  }
}

export async function fetchMe(): Promise<Me | null> {
  try {
    const me = await api<Me>('/api/auth/me')
    markAuthed()
    return me
  } catch {
    clearAuth()
    return null
  }
}

export type Me = {
  id: number
  username: string
  role: 'admin' | 'gestor' | 'operador' | string
  display_name?: string | null
  store_ids: number[]
  is_active: boolean
}

export type StoreHour = {
  weekday: number
  label: string
  opens_at?: string | null
  closes_at?: string | null
  is_closed: boolean
}

export type Store = {
  id: number
  name: string
  cnpj?: string | null
  is_active: boolean
  hours: StoreHour[]
  cameras_count: number
  created_at: string
  updated_at: string
}

export type AppUser = {
  id: number
  username: string
  role: string
  display_name?: string | null
  store_ids: number[]
  store_names: string[]
  is_active: boolean
  created_at: string
}

export type Settings = {
  active_provider: string
  openai_model: string
  gemini_model: string
  claude_model: string
  analysis_interval_sec: number
  cooldown_minutes: number
  confidence_threshold: number
  respect_store_hours?: boolean
  motion_enabled?: boolean
  motion_check_interval_sec?: number
  motion_sensitivity?: number
  motion_pixel_threshold?: number
  motion_cooldown_sec?: number
  ai_heartbeat_sec?: number
  rule_sem_touca: boolean
  rule_fardamento: boolean
  rule_sem_epi: boolean
  base_prompt: string
  openai_api_key_set: boolean
  gemini_api_key_set: boolean
  anthropic_api_key_set: boolean
}

export type Camera = {
  id: number
  name: string
  rtsp_url_masked: string
  location?: string | null
  store_id?: number | null
  store_name?: string | null
  profile_id?: number | null
  profile_name?: string | null
  enabled: boolean
  interval_sec?: number | null
  status: string
  last_seen_at?: string | null
  last_frame_path?: string | null
  last_error?: string | null
}

export type MonitorProfile = {
  id: number
  name: string
  slug: string
  description?: string | null
  environment_type: string
  rule_sem_touca: boolean
  rule_fardamento: boolean
  rule_sem_epi: boolean
  rule_celular: boolean
  phone_max_minutes: number
  rule_tempo_espera: boolean
  wait_max_minutes: number
  uniform_expected?: string | null
  extra_instructions?: string | null
  custom_prompt?: string | null
  is_default: boolean
  cameras_count: number
}

export type ParameterItem = {
  key: string
  label: string
  description: string
  where: string
  default: string
}

export type ReportChatMessage = {
  id: number
  role: 'user' | 'assistant' | string
  content: string
  created_at: string
}

export type Alert = {
  id: number
  camera_id: number
  camera_name?: string | null
  violations: string[]
  description: string
  confidence: number
  snapshot_path?: string | null
  feedback?: string | null
  feedback_comment?: string | null
  favorited?: boolean
  favorite_path?: string | null
  favorited_at?: string | null
  created_at: string
}

export type Dashboard = {
  cameras_total: number
  cameras_online: number
  cameras_offline: number
  alerts_today: number
  recent_alerts: Alert[]
}
