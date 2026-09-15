import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { AppUser, Store } from '../api'
import { useAuth, useRole } from '../auth'

const ROLE_OPTIONS = [
  { value: 'admin', label: 'Admin — acesso total' },
  { value: 'gestor', label: 'Gestor — câmeras, usuários da loja, relatórios' },
  { value: 'operador', label: 'Operador — só notificações/alertas' },
]

export default function UsersPage() {
  const { me } = useAuth()
  const { isAdmin, canManageUsers } = useRole()
  const [users, setUsers] = useState<AppUser[]>([])
  const [stores, setStores] = useState<Store[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [password, setPassword] = useState('')
  const [role, setRole] = useState('operador')
  const [storeIds, setStoreIds] = useState<number[]>([])
  const [isActive, setIsActive] = useState(true)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  const roleChoices = ROLE_OPTIONS.filter((r) => isAdmin || r.value !== 'admin')

  async function load() {
    const [u, s] = await Promise.all([
      api<AppUser[]>('/api/users'),
      api<Store[]>('/api/stores'),
    ])
    setUsers(u)
    setStores(s)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  function resetForm() {
    setEditingId(null)
    setUsername('')
    setDisplayName('')
    setPassword('')
    setRole('operador')
    setStoreIds([])
    setIsActive(true)
    setShowForm(false)
  }

  function startCreate() {
    resetForm()
    setShowForm(true)
    setInfo('')
    setError('')
  }

  function startEdit(user: AppUser) {
    setEditingId(user.id)
    setUsername(user.username)
    setDisplayName(user.display_name || '')
    setPassword('')
    setRole(user.role)
    setStoreIds(user.store_ids || [])
    setIsActive(user.is_active)
    setShowForm(true)
    setInfo('')
    setError('')
  }

  function toggleStore(id: number) {
    setStoreIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    )
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setInfo('')
    try {
      if (editingId) {
        const body: Record<string, unknown> = {
          role,
          display_name: displayName.trim() || null,
          store_ids: role === 'admin' ? [] : storeIds,
          is_active: isActive,
        }
        if (password.trim()) body.password = password.trim()
        await api(`/api/users/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        })
        setInfo('Usuário atualizado.')
      } else {
        await api('/api/users', {
          method: 'POST',
          body: JSON.stringify({
            username: username.trim(),
            password: password.trim(),
            role,
            display_name: displayName.trim() || null,
            store_ids: role === 'admin' ? [] : storeIds,
            is_active: isActive,
          }),
        })
        setInfo('Usuário criado.')
      }
      resetForm()
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar usuário')
    }
  }

  async function remove(id: number) {
    if (!confirm('Remover este usuário?')) return
    try {
      await api(`/api/users/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao remover')
    }
  }

  if (!canManageUsers) {
    return (
      <div className="page">
        <p className="flash error">Sem permissão para gerenciar usuários.</p>
      </div>
    )
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Usuários</h1>
          <p className="page-sub">
            Defina o tipo de acesso e as lojas vinculadas a cada usuário.
          </p>
        </div>
        <div className="page-actions">
          {!showForm ? (
            <button type="button" onClick={startCreate}>
              Novo usuário
            </button>
          ) : null}
        </div>
      </div>

      {showForm ? (
        <form className="panel stack" onSubmit={onSubmit}>
          <div className="panel-head">
            <h2>{editingId ? 'Editar usuário' : 'Novo usuário'}</h2>
            <button type="button" className="ghost" onClick={resetForm}>
              Fechar
            </button>
          </div>

          <div className="form-grid">
            <label>
              Usuário (login)
              <input
                required={!editingId}
                disabled={!!editingId}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                autoComplete="off"
              />
            </label>
            <label>
              Nome de exibição
              <input
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
              />
            </label>
            <label>
              Senha {editingId ? '(deixe em branco para manter)' : ''}
              <input
                type="password"
                required={!editingId}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <label>
              Tipo de usuário
              <select value={role} onChange={(e) => setRole(e.target.value)}>
                {roleChoices.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="check-row" style={{ alignSelf: 'end' }}>
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              Ativo
            </label>
          </div>

          {role !== 'admin' ? (
            <div className="store-pick">
              <div className="store-pick-head">
                <p className="hours-block-title">Lojas com acesso</p>
                <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                  Selecione pelo menos uma loja para este usuário.
                </p>
              </div>
              {stores.length ? (
                <div className="store-pick-grid">
                  {stores.map((store) => {
                    const checked = storeIds.includes(store.id)
                    return (
                      <label
                        key={store.id}
                        className={`store-pick-item${checked ? ' is-on' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleStore(store.id)}
                        />
                        <span>
                          <strong>{store.name}</strong>
                          <small>{store.cnpj || 'CNPJ não informado'}</small>
                        </span>
                      </label>
                    )
                  })}
                </div>
              ) : (
                <p className="muted">Cadastre lojas antes de vincular usuários.</p>
              )}
            </div>
          ) : (
            <p className="muted">Admin tem acesso a todas as lojas automaticamente.</p>
          )}

          {info ? <p className="flash ok">{info}</p> : null}
          {error ? <p className="flash error">{error}</p> : null}

          <div className="form-actions">
            <button type="submit">{editingId ? 'Salvar' : 'Criar usuário'}</button>
            <button type="button" className="secondary" onClick={resetForm}>
              Cancelar
            </button>
          </div>
        </form>
      ) : null}

      {!showForm && (info || error) ? (
        <p className={`flash ${error ? 'error' : 'ok'}`}>{error || info}</p>
      ) : null}

      <div className="panel">
        <div className="panel-head">
          <h2>Usuários</h2>
          <span className="muted">{users.length}</span>
        </div>
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Usuário</th>
                <th>Tipo</th>
                <th>Lojas</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id}>
                  <td>
                    <strong>{u.display_name || u.username}</strong>
                    <div className="muted">{u.username}</div>
                  </td>
                  <td>
                    <span className="badge">{u.role}</span>
                  </td>
                  <td className="muted">
                    {u.role === 'admin'
                      ? 'Todas'
                      : u.store_names.join(', ') || '—'}
                  </td>
                  <td>
                    <span className={`badge ${u.is_active ? 'online' : 'offline'}`}>
                      {u.is_active ? 'ativo' : 'inativo'}
                    </span>
                  </td>
                  <td>
                    <div className="row">
                      <button type="button" className="secondary" onClick={() => startEdit(u)}>
                        Editar
                      </button>
                      {isAdmin && u.id !== me?.id ? (
                        <button type="button" className="danger" onClick={() => remove(u.id)}>
                          Remover
                        </button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
