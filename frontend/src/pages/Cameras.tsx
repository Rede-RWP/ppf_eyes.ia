import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api, mediaUrl } from '../api'
import type { Camera, MonitorProfile, Store } from '../api'
import { useRole } from '../auth'

type FormState = {
  name: string
  rtsp_url: string
  location: string
  store_id: string
  profile_id: string
  enabled: boolean
  interval_sec: string
}

const emptyForm: FormState = {
  name: '',
  rtsp_url: '',
  location: '',
  store_id: '',
  profile_id: '',
  enabled: true,
  interval_sec: '',
}

export default function CamerasPage() {
  const { canManageCameras } = useRole()
  const [cameras, setCameras] = useState<Camera[]>([])
  const [profiles, setProfiles] = useState<MonitorProfile[]>([])
  const [stores, setStores] = useState<Store[]>([])
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')
  const [preview, setPreview] = useState<string | undefined>()

  async function load() {
    const [cams, profs, storeList] = await Promise.all([
      api<Camera[]>('/api/cameras'),
      api<MonitorProfile[]>('/api/profiles'),
      api<Store[]>('/api/stores'),
    ])
    setCameras(cams)
    setProfiles(profs)
    setStores(storeList.filter((s) => s.is_active))
    setForm((f) => {
      const next = { ...f }
      if (!next.profile_id) {
        const def = profs.find((p) => p.is_default) || profs[0]
        if (def) next.profile_id = String(def.id)
      }
      if (!next.store_id && storeList.length) {
        next.store_id = String(storeList[0].id)
      }
      return next
    })
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
    const t = setInterval(() => {
      load().catch(() => undefined)
    }, 10000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!canManageCameras) return
    setError('')
    setInfo('')
    const profileId = form.profile_id ? Number(form.profile_id) : null
    const storeId = form.store_id ? Number(form.store_id) : null
    if (!storeId) {
      setError('Selecione a loja da câmera')
      return
    }
    const payload = {
      name: form.name.trim(),
      rtsp_url: form.rtsp_url.trim(),
      location: form.location.trim() || null,
      store_id: storeId,
      profile_id: profileId,
      enabled: form.enabled,
      interval_sec: form.interval_sec ? Number(form.interval_sec) : null,
    }
    try {
      if (editingId) {
        const body: Record<string, unknown> = {
          name: payload.name,
          location: payload.location,
          store_id: payload.store_id,
          profile_id: payload.profile_id,
          enabled: payload.enabled,
          interval_sec: payload.interval_sec,
        }
        if (payload.rtsp_url && !payload.rtsp_url.includes('***')) {
          body.rtsp_url = payload.rtsp_url
        }
        await api(`/api/cameras/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(body),
        })
        setInfo('Câmera atualizada.')
      } else {
        await api('/api/cameras', {
          method: 'POST',
          body: JSON.stringify(payload),
        })
        setInfo('Câmera cadastrada.')
      }
      const def = profiles.find((p) => p.is_default) || profiles[0]
      setForm({
        ...emptyForm,
        profile_id: def ? String(def.id) : '',
        store_id: stores[0] ? String(stores[0].id) : '',
      })
      setEditingId(null)
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar câmera')
    }
  }

  function startCreate() {
    const def = profiles.find((p) => p.is_default) || profiles[0]
    setEditingId(null)
    setForm({
      ...emptyForm,
      profile_id: def ? String(def.id) : '',
      store_id: stores[0] ? String(stores[0].id) : '',
    })
    setShowForm(true)
    setPreview(undefined)
    setInfo('')
    setError('')
  }

  function startEdit(cam: Camera) {
    if (!canManageCameras) return
    setEditingId(cam.id)
    setShowForm(true)
    setForm({
      name: cam.name,
      rtsp_url: cam.rtsp_url_masked,
      location: cam.location || '',
      store_id: cam.store_id ? String(cam.store_id) : '',
      profile_id: cam.profile_id ? String(cam.profile_id) : '',
      enabled: cam.enabled,
      interval_sec: cam.interval_sec ? String(cam.interval_sec) : '',
    })
    setPreview(mediaUrl(cam.last_frame_path))
    setInfo('')
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function cancelForm() {
    const def = profiles.find((p) => p.is_default) || profiles[0]
    setEditingId(null)
    setForm({
      ...emptyForm,
      profile_id: def ? String(def.id) : '',
      store_id: stores[0] ? String(stores[0].id) : '',
    })
    setShowForm(false)
  }

  async function remove(id: number) {
    if (!canManageCameras) return
    if (!confirm('Remover esta câmera?')) return
    await api(`/api/cameras/${id}`, { method: 'DELETE' })
    await load()
  }

  async function test(id: number) {
    setInfo('')
    setError('')
    try {
      const res = await api<{ ok: boolean; message: string; preview_path?: string }>(
        `/api/cameras/${id}/test`,
        { method: 'POST' },
      )
      setInfo(res.message)
      if (res.preview_path) setPreview(mediaUrl(res.preview_path))
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha no teste RTSP')
    }
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Câmeras</h1>
          <p className="page-sub">
            Associe cada câmera a uma <Link to="/stores">loja</Link> e a um{' '}
            <Link to="/profiles">ambiente</Link> de regras.
          </p>
        </div>
        <div className="page-actions">
          {canManageCameras && !showForm ? (
            <button type="button" onClick={startCreate}>
              Nova câmera
            </button>
          ) : null}
        </div>
      </div>

      {showForm && canManageCameras ? (
        <form className="panel stack" onSubmit={onSubmit}>
          <div className="panel-head">
            <h2>{editingId ? 'Editar câmera' : 'Nova câmera'}</h2>
            <button type="button" className="ghost" onClick={cancelForm}>
              Fechar
            </button>
          </div>

          <div className="form-grid">
            <label>
              Nome
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label>
              Loja
              <select
                required
                value={form.store_id}
                onChange={(e) => setForm({ ...form, store_id: e.target.value })}
              >
                <option value="">Selecione…</option>
                {stores.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Local / zona (opcional)
              <input
                placeholder="Ex.: cozinha, salão"
                value={form.location}
                onChange={(e) => setForm({ ...form, location: e.target.value })}
              />
            </label>
            <label className="full">
              Ambiente / perfil de regras
              <select
                required
                value={form.profile_id}
                onChange={(e) => setForm({ ...form, profile_id: e.target.value })}
              >
                <option value="">Selecione…</option>
                {profiles.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} ({p.environment_type})
                  </option>
                ))}
              </select>
            </label>
            <label className="full">
              URL RTSP
              <input
                required={!editingId}
                placeholder="rtsp://admin:senha@IP:554/h264/ch1/main/av_stream"
                value={form.rtsp_url}
                onChange={(e) => setForm({ ...form, rtsp_url: e.target.value })}
              />
            </label>
            <label>
              Intervalo (seg, opcional)
              <input
                type="number"
                min={5}
                value={form.interval_sec}
                onChange={(e) => setForm({ ...form, interval_sec: e.target.value })}
              />
            </label>
            <label className="check-row" style={{ alignSelf: 'end' }}>
              <input
                type="checkbox"
                checked={form.enabled}
                onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
              />
              Monitoramento ativo
            </label>
          </div>

          {info ? <p className="flash ok">{info}</p> : null}
          {error ? <p className="flash error">{error}</p> : null}

          <div className="form-actions">
            <button type="submit">{editingId ? 'Salvar alterações' : 'Adicionar câmera'}</button>
            <button type="button" className="secondary" onClick={cancelForm}>
              Cancelar
            </button>
          </div>
        </form>
      ) : null}

      {preview ? (
        <div className="panel">
          <div className="panel-head">
            <h2>Preview</h2>
          </div>
          <img className="preview" src={preview} alt="Preview da câmera" />
        </div>
      ) : null}

      {!showForm && (info || error) ? (
        <p className={`flash ${error ? 'error' : 'ok'}`}>{error || info}</p>
      ) : null}

      <div className="panel">
        <div className="panel-head">
          <h2>Câmeras cadastradas</h2>
          <span className="muted">{cameras.length} câmera(s)</span>
        </div>

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Nome</th>
                <th>Loja</th>
                <th>Ambiente</th>
                <th>Status</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {cameras.map((cam) => (
                <tr key={cam.id}>
                  <td>
                    <strong>{cam.name}</strong>
                    <div className="muted">{cam.location || '—'}</div>
                  </td>
                  <td>
                    <span className="badge">{cam.store_name || 'sem loja'}</span>
                  </td>
                  <td>
                    <span className="badge">{cam.profile_name || 'sem perfil'}</span>
                  </td>
                  <td>
                    <span className={`badge ${cam.status}`}>{cam.status}</span>
                    {!cam.enabled ? <div className="muted">pausada</div> : null}
                  </td>
                  <td>
                    <div className="row">
                      {canManageCameras ? (
                        <button type="button" className="secondary" onClick={() => startEdit(cam)}>
                          Editar
                        </button>
                      ) : null}
                      <button type="button" className="secondary" onClick={() => test(cam.id)}>
                        Testar
                      </button>
                      {canManageCameras ? (
                        <button type="button" className="danger" onClick={() => remove(cam.id)}>
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

        <div className="entity-grid">
          {cameras.map((cam) => (
            <article key={cam.id} className="entity-card">
              <div className="entity-card-head">
                <div>
                  <strong>{cam.name}</strong>
                  <div className="muted">
                    {cam.store_name || 'Sem loja'}
                    {cam.location ? ` · ${cam.location}` : ''}
                  </div>
                </div>
                <span className={`badge ${cam.status}`}>{cam.status}</span>
              </div>
              <div className="entity-meta">
                <span className="badge">{cam.profile_name || 'sem perfil'}</span>
              </div>
              <div className="row">
                {canManageCameras ? (
                  <button type="button" className="secondary" onClick={() => startEdit(cam)}>
                    Editar
                  </button>
                ) : null}
                <button type="button" className="secondary" onClick={() => test(cam.id)}>
                  Testar
                </button>
                {canManageCameras ? (
                  <button type="button" className="danger" onClick={() => remove(cam.id)}>
                    Remover
                  </button>
                ) : null}
              </div>
            </article>
          ))}
        </div>

        {!cameras.length ? (
          <div className="empty-state">
            <p>Nenhuma câmera cadastrada ainda.</p>
            {canManageCameras ? (
              <button type="button" onClick={startCreate}>
                Cadastrar primeira câmera
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
