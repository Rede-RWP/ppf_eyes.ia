import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import type { Settings } from '../api'

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null)
  const [openaiKey, setOpenaiKey] = useState('')
  const [geminiKey, setGeminiKey] = useState('')
  const [claudeKey, setClaudeKey] = useState('')
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)

  async function load() {
    const data = await api<Settings>('/api/settings')
    setSettings(data)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    if (!settings) return
    setSaving(true)
    setMsg('')
    setError('')
    try {
      const payload: Record<string, unknown> = {
        active_provider: settings.active_provider,
        openai_model: settings.openai_model,
        gemini_model: settings.gemini_model,
        claude_model: settings.claude_model,
        analysis_interval_sec: Number(settings.analysis_interval_sec),
        cooldown_minutes: Number(settings.cooldown_minutes),
        confidence_threshold: Number(settings.confidence_threshold),
        rule_sem_touca: settings.rule_sem_touca,
        rule_fardamento: settings.rule_fardamento,
        rule_sem_epi: settings.rule_sem_epi,
        base_prompt: settings.base_prompt,
      }
      const savedKeys: string[] = []
      if (openaiKey.trim()) {
        payload.openai_api_key = openaiKey.trim()
        savedKeys.push('OpenAI')
      }
      if (geminiKey.trim()) {
        payload.gemini_api_key = geminiKey.trim()
        savedKeys.push('Gemini')
      }
      if (claudeKey.trim()) {
        payload.anthropic_api_key = claudeKey.trim()
        savedKeys.push('Claude')
      }

      const updated = await api<Settings>('/api/settings', {
        method: 'PUT',
        body: JSON.stringify(payload),
      })
      setSettings(updated)
      setOpenaiKey('')
      setGeminiKey('')
      setClaudeKey('')
      const keyMsg = savedKeys.length
        ? ` Keys salvas: ${savedKeys.join(', ')}.`
        : ' (nenhuma key nova — só opções gerais).'
      setMsg(`Configurações salvas.${keyMsg}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar')
    } finally {
      setSaving(false)
    }
  }

  async function testAi() {
    setTesting(true)
    setMsg('')
    setError('')
    try {
      const res = await api<{ ok: boolean; message: string; provider: string; model?: string }>(
        '/api/settings/test-ai',
        { method: 'POST', body: '{}' },
      )
      setMsg(`${res.message} — provedor ${res.provider}${res.model ? ` / ${res.model}` : ''}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Falha no teste de IA')
    } finally {
      setTesting(false)
    }
  }

  if (!settings) {
    return <p className="muted">{error || 'Carregando…'}</p>
  }

  const providerLabel =
    settings.active_provider === 'openai'
      ? 'OpenAI'
      : settings.active_provider === 'gemini'
        ? 'Gemini'
        : 'Claude'

  const activeKeySet =
    settings.active_provider === 'openai'
      ? settings.openai_api_key_set
      : settings.active_provider === 'gemini'
        ? settings.gemini_api_key_set
        : settings.anthropic_api_key_set

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Configurações</h1>
          <p className="page-sub">
            Provedor de IA e parâmetros globais. Regras por local ficam em{' '}
            <Link to="/profiles">Ambientes</Link>.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="secondary" onClick={testAi} disabled={testing}>
            {testing ? 'Testando…' : 'Testar IA'}
          </button>
        </div>
      </div>

      <div className="panel">
        <div className="status-pills">
          <span className={`badge ${activeKeySet ? 'online' : 'offline'}`}>
            Ativo: {providerLabel} — {activeKeySet ? 'key OK' : 'key ausente'}
          </span>
          <span className={`badge ${settings.openai_api_key_set ? 'online' : 'offline'}`}>
            OpenAI {settings.openai_api_key_set ? 'OK' : '—'}
          </span>
          <span className={`badge ${settings.gemini_api_key_set ? 'online' : 'offline'}`}>
            Gemini {settings.gemini_api_key_set ? 'OK' : '—'}
          </span>
          <span className={`badge ${settings.anthropic_api_key_set ? 'online' : 'offline'}`}>
            Claude {settings.anthropic_api_key_set ? 'OK' : '—'}
          </span>
        </div>
      </div>

      <form className="panel stack" onSubmit={onSubmit}>
        <div className="panel-section">
          <span className="section-label">Provedor</span>
          <div className="form-grid">
            <label className="full">
              Provedor ativo
              <select
                value={settings.active_provider}
                onChange={(e) => setSettings({ ...settings, active_provider: e.target.value })}
              >
                <option value="openai">OpenAI (GPT-4o Vision)</option>
                <option value="gemini">Google Gemini</option>
                <option value="claude">Anthropic Claude</option>
              </select>
            </label>
          </div>
          <p className="muted" style={{ margin: '0.75rem 0 0' }}>
            Cole só a key do provedor ativo. Campos vazios mantêm a key já salva.
          </p>
        </div>

        <div className="panel-section">
          <span className="section-label">API keys e modelos</span>
          <div className="form-grid">
            <label>
              OpenAI API key{' '}
              {settings.openai_api_key_set ? (
                <span className="badge online">salva</span>
              ) : (
                <span className="badge offline">vazia</span>
              )}
              <input
                type="text"
                autoComplete="off"
                spellCheck={false}
                placeholder={settings.openai_api_key_set ? 'Deixe vazio para manter' : 'sk-…'}
                value={openaiKey}
                onChange={(e) => setOpenaiKey(e.target.value)}
              />
            </label>
            <label>
              Modelo OpenAI
              <input
                value={settings.openai_model}
                onChange={(e) => setSettings({ ...settings, openai_model: e.target.value })}
              />
            </label>
            <label>
              Gemini API key{' '}
              {settings.gemini_api_key_set ? (
                <span className="badge online">salva</span>
              ) : (
                <span className="badge offline">vazia</span>
              )}
              <input
                type="text"
                autoComplete="off"
                spellCheck={false}
                placeholder={settings.gemini_api_key_set ? 'Deixe vazio para manter' : 'AIza…'}
                value={geminiKey}
                onChange={(e) => setGeminiKey(e.target.value)}
              />
            </label>
            <label>
              Modelo Gemini
              <input
                value={settings.gemini_model}
                onChange={(e) => setSettings({ ...settings, gemini_model: e.target.value })}
              />
            </label>
            <label>
              Anthropic API key{' '}
              {settings.anthropic_api_key_set ? (
                <span className="badge online">salva</span>
              ) : (
                <span className="badge offline">vazia</span>
              )}
              <input
                type="text"
                autoComplete="off"
                spellCheck={false}
                placeholder={
                  settings.anthropic_api_key_set ? 'Deixe vazio para manter' : 'sk-ant-…'
                }
                value={claudeKey}
                onChange={(e) => setClaudeKey(e.target.value)}
              />
            </label>
            <label>
              Modelo Claude
              <input
                value={settings.claude_model}
                onChange={(e) => setSettings({ ...settings, claude_model: e.target.value })}
                placeholder="claude-sonnet-4-5-20250929"
              />
            </label>
          </div>
        </div>

        <div className="panel-section">
          <span className="section-label">Análise</span>
          <div className="form-grid">
            <label>
              Intervalo global (seg)
              <input
                type="number"
                min={5}
                value={settings.analysis_interval_sec}
                onChange={(e) =>
                  setSettings({ ...settings, analysis_interval_sec: Number(e.target.value) })
                }
              />
            </label>
            <label>
              Cooldown de alerta (min)
              <input
                type="number"
                min={0}
                value={settings.cooldown_minutes}
                onChange={(e) =>
                  setSettings({ ...settings, cooldown_minutes: Number(e.target.value) })
                }
              />
            </label>
            <label>
              Confiança mínima
              <input
                type="number"
                min={0}
                max={1}
                step={0.05}
                value={settings.confidence_threshold}
                onChange={(e) =>
                  setSettings({ ...settings, confidence_threshold: Number(e.target.value) })
                }
              />
            </label>
          </div>
        </div>

        <div className="panel-section">
          <span className="section-label">Regras globais (fallback)</span>
          <p className="muted" style={{ margin: '0 0 0.75rem' }}>
            Preferência: use Ambientes por câmera. Estes toggles só entram se o perfil não cobrir.
          </p>
          <div className="rules-grid">
            <label className={`rule-card${settings.rule_sem_touca ? ' is-on' : ''}`}>
              <div className="rule-card-top">
                <input
                  type="checkbox"
                  checked={settings.rule_sem_touca}
                  onChange={(e) => setSettings({ ...settings, rule_sem_touca: e.target.checked })}
                />
                <div className="rule-card-copy">
                  <strong>Sem touca</strong>
                  <span>Fallback global</span>
                </div>
              </div>
            </label>
            <label className={`rule-card${settings.rule_fardamento ? ' is-on' : ''}`}>
              <div className="rule-card-top">
                <input
                  type="checkbox"
                  checked={settings.rule_fardamento}
                  onChange={(e) => setSettings({ ...settings, rule_fardamento: e.target.checked })}
                />
                <div className="rule-card-copy">
                  <strong>Fardamento</strong>
                  <span>Fallback global</span>
                </div>
              </div>
            </label>
            <label className={`rule-card${settings.rule_sem_epi ? ' is-on' : ''}`}>
              <div className="rule-card-top">
                <input
                  type="checkbox"
                  checked={settings.rule_sem_epi}
                  onChange={(e) => setSettings({ ...settings, rule_sem_epi: e.target.checked })}
                />
                <div className="rule-card-copy">
                  <strong>EPI</strong>
                  <span>Fallback global</span>
                </div>
              </div>
            </label>
          </div>
        </div>

        <div className="panel-section">
          <span className="section-label">Prompt base</span>
          <label>
            Use {'{{RULES}}'} para injetar as regras ativas
            <textarea
              className="tall"
              value={settings.base_prompt}
              onChange={(e) => setSettings({ ...settings, base_prompt: e.target.value })}
            />
          </label>
        </div>

        {msg ? <p className="flash ok">{msg}</p> : null}
        {error ? <p className="flash error">{error}</p> : null}

        <div className="form-actions">
          <button type="submit" disabled={saving}>
            {saving ? 'Salvando…' : 'Salvar configurações'}
          </button>
          <button type="button" className="secondary" onClick={testAi} disabled={testing}>
            {testing ? 'Testando IA…' : 'Testar conexão da IA'}
          </button>
        </div>
      </form>
    </div>
  )
}
