import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { MonitorProfile } from '../api'

type FormState = {
  name: string
  environment_type: string
  description: string
  rule_sem_touca: boolean
  rule_fardamento: boolean
  rule_sem_epi: boolean
  rule_celular: boolean
  phone_max_minutes: number
  rule_tempo_espera: boolean
  wait_max_minutes: number
  uniform_expected: string
  extra_instructions: string
  is_default: boolean
}

const emptyForm: FormState = {
  name: '',
  environment_type: 'geral',
  description: '',
  rule_sem_touca: false,
  rule_fardamento: false,
  rule_sem_epi: false,
  rule_celular: false,
  phone_max_minutes: 5,
  rule_tempo_espera: false,
  wait_max_minutes: 10,
  uniform_expected: '',
  extra_instructions: '',
  is_default: false,
}

const ENV_OPTIONS = [
  { value: 'cozinha', label: 'Cozinha' },
  { value: 'escritorio', label: 'Escritório' },
  { value: 'recepcao', label: 'Recepção' },
  { value: 'delivery', label: 'Delivery' },
  { value: 'atendimento_salao', label: 'Atendimento salão' },
  { value: 'salao_pizzaria', label: 'Salão pizzaria' },
  { value: 'corredor', label: 'Corredor' },
  { value: 'geral', label: 'Geral' },
]

export default function ProfilesPage() {
  const [profiles, setProfiles] = useState<MonitorProfile[]>([])
  const [form, setForm] = useState<FormState>(emptyForm)
  const [editingId, setEditingId] = useState<number | null>(null)
  const [showForm, setShowForm] = useState(false)
  const [error, setError] = useState('')
  const [info, setInfo] = useState('')

  async function load() {
    const data = await api<MonitorProfile[]>('/api/profiles')
    setProfiles(data)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setInfo('')
    const payload = {
      name: form.name.trim(),
      environment_type: form.environment_type,
      description: form.description.trim() || null,
      rule_sem_touca: form.rule_sem_touca,
      rule_fardamento: form.rule_fardamento,
      rule_sem_epi: form.rule_sem_epi,
      rule_celular: form.rule_celular,
      phone_max_minutes: form.phone_max_minutes,
      rule_tempo_espera: form.rule_tempo_espera,
      wait_max_minutes: form.wait_max_minutes,
      uniform_expected: form.uniform_expected.trim() || null,
      extra_instructions: form.extra_instructions.trim() || null,
      is_default: form.is_default,
    }
    try {
      if (editingId) {
        await api(`/api/profiles/${editingId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        })
        setInfo('Perfil atualizado.')
      } else {
        await api('/api/profiles', { method: 'POST', body: JSON.stringify(payload) })
        setInfo('Perfil criado.')
      }
      setForm(emptyForm)
      setEditingId(null)
      setShowForm(false)
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar perfil')
    }
  }

  function startCreate() {
    setEditingId(null)
    setForm(emptyForm)
    setShowForm(true)
    setInfo('')
    setError('')
  }

  function startEdit(p: MonitorProfile) {
    setEditingId(p.id)
    setShowForm(true)
    setForm({
      name: p.name,
      environment_type: p.environment_type,
      description: p.description || '',
      rule_sem_touca: p.rule_sem_touca,
      rule_fardamento: p.rule_fardamento,
      rule_sem_epi: p.rule_sem_epi,
      rule_celular: !!p.rule_celular,
      phone_max_minutes: p.phone_max_minutes ?? 5,
      rule_tempo_espera: !!p.rule_tempo_espera,
      wait_max_minutes: p.wait_max_minutes ?? 10,
      uniform_expected: p.uniform_expected || '',
      extra_instructions: p.extra_instructions || '',
      is_default: p.is_default,
    })
    setInfo('')
    setError('')
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  function cancelForm() {
    setEditingId(null)
    setForm(emptyForm)
    setShowForm(false)
  }

  async function remove(id: number) {
    if (!confirm('Remover este perfil?')) return
    try {
      await api(`/api/profiles/${id}`, { method: 'DELETE' })
      await load()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao remover')
    }
  }

  function rulesLabel(p: MonitorProfile) {
    const parts: string[] = []
    if (p.rule_sem_touca) parts.push('touca')
    if (p.rule_fardamento) parts.push('farda')
    if (p.rule_sem_epi) parts.push('EPI')
    if (p.rule_celular) parts.push(`celular>${p.phone_max_minutes ?? 5}min`)
    if (p.rule_tempo_espera) parts.push(`espera>${p.wait_max_minutes ?? 10}min`)
    return parts.length ? parts.join(', ') : 'sem regras'
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Ambientes</h1>
          <p className="page-sub">
            Perfis por tipo de local. Cada câmera herda as regras — touca, farda, celular e tempo
            de espera.
          </p>
        </div>
        <div className="page-actions">
          {!showForm ? (
            <button type="button" onClick={startCreate}>
              Novo ambiente
            </button>
          ) : null}
        </div>
      </div>

      {showForm ? (
        <form className="panel stack" onSubmit={onSubmit}>
          <div className="panel-head">
            <h2>{editingId ? 'Editar ambiente' : 'Novo ambiente'}</h2>
            <button type="button" className="ghost" onClick={cancelForm}>
              Fechar
            </button>
          </div>

          <div className="form-grid">
            <label>
              Nome do perfil
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Ex.: Cozinha Loja Centro"
              />
            </label>
            <label>
              Tipo de ambiente
              <select
                value={form.environment_type}
                onChange={(e) => setForm({ ...form, environment_type: e.target.value })}
              >
                {ENV_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="full">
              Descrição
              <input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
              />
            </label>
          </div>

          <div className="panel-section">
            <span className="section-label">Regras de monitoramento</span>
            <div className="rules-grid">
              <label className={`rule-card${form.rule_sem_touca ? ' is-on' : ''}`}>
                <div className="rule-card-top">
                  <input
                    type="checkbox"
                    checked={form.rule_sem_touca}
                    onChange={(e) => setForm({ ...form, rule_sem_touca: e.target.checked })}
                  />
                  <div className="rule-card-copy">
                    <strong>Touca / cabelo</strong>
                    <span>Exigir proteção de cabelo na área.</span>
                  </div>
                </div>
              </label>

              <label className={`rule-card${form.rule_fardamento ? ' is-on' : ''}`}>
                <div className="rule-card-top">
                  <input
                    type="checkbox"
                    checked={form.rule_fardamento}
                    onChange={(e) => setForm({ ...form, rule_fardamento: e.target.checked })}
                  />
                  <div className="rule-card-copy">
                    <strong>Fardamento</strong>
                    <span>Comparar com o uniforme esperado abaixo.</span>
                  </div>
                </div>
              </label>

              <label className={`rule-card${form.rule_sem_epi ? ' is-on' : ''}`}>
                <div className="rule-card-top">
                  <input
                    type="checkbox"
                    checked={form.rule_sem_epi}
                    onChange={(e) => setForm({ ...form, rule_sem_epi: e.target.checked })}
                  />
                  <div className="rule-card-copy">
                    <strong>EPI</strong>
                    <span>Capacete, luvas ou outros EPIs exigidos.</span>
                  </div>
                </div>
              </label>

              <label className={`rule-card${form.rule_celular ? ' is-on' : ''}`}>
                <div className="rule-card-top">
                  <input
                    type="checkbox"
                    checked={form.rule_celular}
                    onChange={(e) => setForm({ ...form, rule_celular: e.target.checked })}
                  />
                  <div className="rule-card-copy">
                    <strong>Celular excessivo</strong>
                    <span>Alerta após uso contínuo acima do limite.</span>
                  </div>
                </div>
                {form.rule_celular ? (
                  <div
                    className="rule-param"
                    onClick={(e) => e.preventDefault()}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    <span className="muted" style={{ fontSize: '0.8rem', display: 'block', marginBottom: 4 }}>
                      Limite (minutos)
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={240}
                      value={form.phone_max_minutes}
                      onChange={(e) =>
                        setForm({ ...form, phone_max_minutes: Number(e.target.value) || 5 })
                      }
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>
                ) : null}
              </label>

              <label className={`rule-card${form.rule_tempo_espera ? ' is-on' : ''}`}>
                <div className="rule-card-top">
                  <input
                    type="checkbox"
                    checked={form.rule_tempo_espera}
                    onChange={(e) => setForm({ ...form, rule_tempo_espera: e.target.checked })}
                  />
                  <div className="rule-card-copy">
                    <strong>Tempo de espera</strong>
                    <span>Recepção, corredor ou fila sem atendimento.</span>
                  </div>
                </div>
                {form.rule_tempo_espera ? (
                  <div
                    className="rule-param"
                    onClick={(e) => e.preventDefault()}
                    onKeyDown={(e) => e.stopPropagation()}
                  >
                    <span className="muted" style={{ fontSize: '0.8rem', display: 'block', marginBottom: 4 }}>
                      Limite (minutos)
                    </span>
                    <input
                      type="number"
                      min={1}
                      max={480}
                      value={form.wait_max_minutes}
                      onChange={(e) =>
                        setForm({ ...form, wait_max_minutes: Number(e.target.value) || 10 })
                      }
                      onClick={(e) => e.stopPropagation()}
                    />
                  </div>
                ) : null}
              </label>
            </div>
          </div>

          <div className="panel-section form-grid">
            <label className="full">
              Uniforme / farda esperada
              <textarea
                value={form.uniform_expected}
                onChange={(e) => setForm({ ...form, uniform_expected: e.target.value })}
                placeholder="Ex.: camisa preta Pizza Pizza + calça preta"
              />
            </label>
            <label className="full">
              Instruções extras para a IA
              <textarea
                value={form.extra_instructions}
                onChange={(e) => setForm({ ...form, extra_instructions: e.target.value })}
                placeholder="Ex.: não alerte clientes no salão"
              />
            </label>
            <label className="check-row full">
              <input
                type="checkbox"
                checked={form.is_default}
                onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
              />
              Usar como perfil padrão sugerido ao cadastrar câmeras
            </label>
          </div>

          {info ? <p className="flash ok">{info}</p> : null}
          {error ? <p className="flash error">{error}</p> : null}

          <div className="form-actions">
            <button type="submit">{editingId ? 'Salvar alterações' : 'Criar ambiente'}</button>
            <button type="button" className="secondary" onClick={cancelForm}>
              Cancelar
            </button>
          </div>
        </form>
      ) : null}

      {!showForm && error ? <p className="flash error">{error}</p> : null}

      <div className="panel">
        <div className="panel-head">
          <h2>Perfis cadastrados</h2>
          <span className="muted">{profiles.length} ambiente(s)</span>
        </div>

        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Perfil</th>
                <th>Regras</th>
                <th>Farda</th>
                <th>Câmeras</th>
                <th>Ações</th>
              </tr>
            </thead>
            <tbody>
              {profiles.map((p) => (
                <tr key={p.id}>
                  <td>
                    <strong>{p.name}</strong>
                    <div className="muted">
                      {p.environment_type}
                      {p.is_default ? ' · padrão' : ''}
                    </div>
                    {p.description ? <div className="muted">{p.description}</div> : null}
                  </td>
                  <td>
                    <span className="badge">{rulesLabel(p)}</span>
                  </td>
                  <td className="muted" style={{ maxWidth: 260 }}>
                    {p.uniform_expected || '—'}
                  </td>
                  <td>{p.cameras_count}</td>
                  <td>
                    <div className="row">
                      <button type="button" className="secondary" onClick={() => startEdit(p)}>
                        Editar
                      </button>
                      <button type="button" className="danger" onClick={() => remove(p.id)}>
                        Remover
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="entity-grid">
          {profiles.map((p) => (
            <article key={p.id} className="entity-card">
              <div className="entity-card-head">
                <div>
                  <strong>{p.name}</strong>
                  <div className="muted">
                    {p.environment_type}
                    {p.is_default ? ' · padrão' : ''}
                  </div>
                </div>
                <span className="badge">{p.cameras_count} cam</span>
              </div>
              {p.description ? <p className="muted" style={{ margin: 0 }}>{p.description}</p> : null}
              <div className="entity-meta">
                <span className="badge">{rulesLabel(p)}</span>
              </div>
              <p className="muted" style={{ margin: 0, fontSize: '0.88rem' }}>
                {p.uniform_expected || 'Sem farda definida'}
              </p>
              <div className="row">
                <button type="button" className="secondary" onClick={() => startEdit(p)}>
                  Editar
                </button>
                <button type="button" className="danger" onClick={() => remove(p.id)}>
                  Remover
                </button>
              </div>
            </article>
          ))}
        </div>

        {!profiles.length ? (
          <div className="empty-state">
            <p>Nenhum ambiente ainda.</p>
            <button type="button" onClick={startCreate}>
              Criar primeiro ambiente
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
