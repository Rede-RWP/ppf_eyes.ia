import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { Store, StoreHour } from '../api'
import { useRole } from '../auth'

type HourForm = {
  weekday: number
  label: string
  short: string
  opens_at: string
  closes_at: string
  is_closed: boolean
}

const DAYS = [
  { label: 'Segunda-feira', short: 'Seg' },
  { label: 'Terça-feira', short: 'Ter' },
  { label: 'Quarta-feira', short: 'Qua' },
  { label: 'Quinta-feira', short: 'Qui' },
  { label: 'Sexta-feira', short: 'Sex' },
  { label: 'Sábado', short: 'Sáb' },
  { label: 'Domingo', short: 'Dom' },
]

function normalizeTime(value: string): string {
  const raw = (value || '').trim()
  const m = raw.match(/^(\d{1,2}):(\d{2})$/)
  if (!m) return raw
  const h = Math.min(23, Math.max(0, Number(m[1])))
  const min = Math.min(59, Math.max(0, Number(m[2])))
  return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`
}

function defaultHours(): HourForm[] {
  return DAYS.map((d, weekday) => ({
    weekday,
    label: d.label,
    short: d.short,
    opens_at: '10:00',
    closes_at: weekday >= 5 ? '23:00' : '22:00',
    is_closed: false,
  }))
}

function hoursFromStore(hours: StoreHour[]): HourForm[] {
  const byDay = new Map(hours.map((h) => [h.weekday, h]))
  return DAYS.map((d, weekday) => {
    const h = byDay.get(weekday)
    const closed = Boolean(h?.is_closed)
    return {
      weekday,
      label: d.label,
      short: d.short,
      opens_at: normalizeTime(h?.opens_at || '10:00'),
      closes_at: normalizeTime(h?.closes_at || (weekday >= 5 ? '23:00' : '22:00')),
      is_closed: closed,
    }
  })
}

export default function StoresPage() {
  const { canManageStores } = useRole()
  const [stores, setStores] = useState<Store[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [cnpj, setCnpj] = useState('')
  const [isActive, setIsActive] = useState(true)
  const [hours, setHours] = useState<HourForm[]>(defaultHours())
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  async function load() {
    const data = await api<Store[]>('/api/stores')
    setStores(data)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  function clearFormFields() {
    setEditingId(null)
    setName('')
    setCnpj('')
    setIsActive(true)
    setHours(defaultHours())
  }

  function resetForm() {
    clearFormFields()
    setShowForm(false)
  }

  function startCreate() {
    clearFormFields()
    setShowForm(true)
    setInfo('')
    setError('')
  }

  function startEdit(store: Store) {
    setEditingId(store.id)
    setName(store.name)
    setCnpj(store.cnpj || '')
    setIsActive(store.is_active)
    setHours(hoursFromStore(store.hours || []))
    setShowForm(true)
    setInfo('')
    setError('')
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setInfo('')
    const payload = {
      name: name.trim(),
      cnpj: cnpj.trim() || null,
      is_active: isActive,
      hours: hours.map((h) => ({
        weekday: h.weekday,
        opens_at: h.is_closed ? null : normalizeTime(h.opens_at),
        closes_at: h.is_closed ? null : normalizeTime(h.closes_at),
        is_closed: h.is_closed,
      })),
    }
    try {
      if (editingId) {
        await api(`/api/stores/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
        setInfo('Loja atualizada.')
      } else {
        await api('/api/stores', { method: 'POST', body: JSON.stringify(payload) })
        setInfo('Loja cadastrada.')
      }
      resetForm()
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar loja')
    }
  }

  async function remove(id: number) {
    if (!confirm('Remover esta loja?')) return
    try {
      await api(`/api/stores/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao remover')
    }
  }

  function updateHour(weekday: number, patch: Partial<HourForm>) {
    setHours((prev) => prev.map((h) => (h.weekday === weekday ? { ...h, ...patch } : h)))
  }

  function setAllOpen(open: boolean) {
    setHours((prev) =>
      prev.map((h) => ({
        ...h,
        is_closed: !open,
        opens_at: h.opens_at || '10:00',
        closes_at: h.closes_at || (h.weekday >= 5 ? '23:00' : '22:00'),
      })),
    )
  }

  function copyMondayToWeekdays() {
    const monday = hours.find((h) => h.weekday === 0)
    if (!monday) return
    setHours((prev) =>
      prev.map((h) =>
        h.weekday >= 1 && h.weekday <= 4
          ? {
              ...h,
              is_closed: monday.is_closed,
              opens_at: monday.opens_at,
              closes_at: monday.closes_at,
            }
          : h,
      ),
    )
  }

  function formatHoursSummary(store: Store) {
    const open = (store.hours || []).filter((h) => !h.is_closed)
    if (!open.length) return 'Fechada todos os dias'
    return open
      .map((h) => `${h.label.slice(0, 3)} ${h.opens_at}–${h.closes_at}`)
      .join(' · ')
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Lojas</h1>
          <p className="page-sub">Cadastre unidades com CNPJ e horário de funcionamento.</p>
        </div>
        <div className="page-actions">
          {canManageStores && !showForm ? (
            <button type="button" onClick={startCreate}>
              Nova loja
            </button>
          ) : null}
        </div>
      </div>

      {showForm && canManageStores ? (
        <form className="panel stack" onSubmit={onSubmit}>
          <div className="panel-head">
            <h2>{editingId ? 'Editar loja' : 'Nova loja'}</h2>
            <button type="button" className="ghost" onClick={resetForm}>
              Fechar
            </button>
          </div>

          <div className="form-grid">
            <label>
              Nome da loja
              <input required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label>
              CNPJ
              <input
                placeholder="00.000.000/0000-00"
                value={cnpj}
                onChange={(e) => setCnpj(e.target.value)}
              />
            </label>
            <label className="check-row" style={{ alignSelf: 'end' }}>
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
              />
              Loja ativa
            </label>
          </div>

          <section className="hours-block">
            <div className="hours-block-head">
              <div>
                <p className="hours-block-title">Horário de funcionamento</p>
                <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                  Ative o dia e informe abertura e fechamento.
                </p>
              </div>
              <div className="hours-block-actions">
                <button type="button" className="ghost" onClick={() => setAllOpen(true)}>
                  Abrir todos
                </button>
                <button type="button" className="ghost" onClick={() => setAllOpen(false)}>
                  Fechar todos
                </button>
                <button type="button" className="ghost" onClick={copyMondayToWeekdays}>
                  Copiar seg → sex
                </button>
              </div>
            </div>

            <div className="hours-list">
              {hours.map((h) => (
                <div
                  key={h.weekday}
                  className={`hours-row${h.is_closed ? ' is-closed' : ''}`}
                >
                  <button
                    type="button"
                    className={`hours-toggle${h.is_closed ? '' : ' is-on'}`}
                    aria-pressed={!h.is_closed}
                    onClick={() => updateHour(h.weekday, { is_closed: !h.is_closed })}
                  >
                    <span className="hours-toggle-knob" />
                    <span className="hours-day">
                      <strong>{h.short}</strong>
                      <small>{h.label}</small>
                    </span>
                  </button>

                  {h.is_closed ? (
                    <p className="hours-closed-label">Fechado</p>
                  ) : (
                    <div className="hours-times">
                      <label>
                        Abre
                        <input
                          type="time"
                          required
                          value={h.opens_at}
                          onChange={(e) =>
                            updateHour(h.weekday, { opens_at: e.target.value || '10:00' })
                          }
                        />
                      </label>
                      <span className="hours-sep" aria-hidden>
                        →
                      </span>
                      <label>
                        Fecha
                        <input
                          type="time"
                          required
                          value={h.closes_at}
                          onChange={(e) =>
                            updateHour(h.weekday, { closes_at: e.target.value || '22:00' })
                          }
                        />
                      </label>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </section>

          {info ? <p className="flash ok">{info}</p> : null}
          {error ? <p className="flash error">{error}</p> : null}

          <div className="form-actions">
            <button type="submit">{editingId ? 'Salvar' : 'Cadastrar loja'}</button>
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
          <h2>Lojas cadastradas</h2>
          <span className="muted">{stores.length} loja(s)</span>
        </div>

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Loja</th>
                <th>CNPJ</th>
                <th>Horário</th>
                <th>Câmeras</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {stores.map((store) => (
                <tr key={store.id}>
                  <td>
                    <strong>{store.name}</strong>
                  </td>
                  <td className="muted">{store.cnpj || '—'}</td>
                  <td className="muted" style={{ maxWidth: 280, fontSize: '0.85rem' }}>
                    {formatHoursSummary(store)}
                  </td>
                  <td>
                    <span className="badge">{store.cameras_count}</span>
                  </td>
                  <td>
                    <span className={`badge ${store.is_active ? 'online' : 'offline'}`}>
                      {store.is_active ? 'ativa' : 'inativa'}
                    </span>
                  </td>
                  <td>
                    {canManageStores ? (
                      <div className="row">
                        <button type="button" className="secondary" onClick={() => startEdit(store)}>
                          Editar
                        </button>
                        <button type="button" className="danger" onClick={() => remove(store.id)}>
                          Remover
                        </button>
                      </div>
                    ) : (
                      <span className="muted">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="entity-grid">
          {stores.map((store) => (
            <article key={store.id} className="entity-card">
              <div className="entity-card-head">
                <div>
                  <strong>{store.name}</strong>
                  <div className="muted">{store.cnpj || 'CNPJ não informado'}</div>
                </div>
                <span className={`badge ${store.is_active ? 'online' : 'offline'}`}>
                  {store.is_active ? 'ativa' : 'inativa'}
                </span>
              </div>
              <div className="entity-meta">
                <span className="badge">{store.cameras_count} câmera(s)</span>
              </div>
              <p className="muted" style={{ margin: 0, fontSize: '0.85rem', lineHeight: 1.45 }}>
                {formatHoursSummary(store)}
              </p>
              {canManageStores ? (
                <div className="row">
                  <button type="button" className="secondary" onClick={() => startEdit(store)}>
                    Editar
                  </button>
                  <button type="button" className="danger" onClick={() => remove(store.id)}>
                    Remover
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>

        {!stores.length ? (
          <div className="empty-state">
            <p>Nenhuma loja cadastrada.</p>
            {canManageStores ? (
              <button type="button" onClick={startCreate}>
                Cadastrar primeira loja
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
