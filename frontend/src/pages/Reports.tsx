import { useEffect, useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../api'
import type { ParameterItem, ReportChatMessage } from '../api'

const SUGGESTIONS = [
  'Quantos alertas tivemos nas últimas 24h e quais foram os mais comuns?',
  'Alguém ficou muito tempo no celular hoje?',
  'Qual câmera teve mais tempo de espera na recepção ou corredor?',
  'Liste os parâmetros configuráveis do sistema.',
]

export default function ReportsPage() {
  const [messages, setMessages] = useState<ReportChatMessage[]>([])
  const [params, setParams] = useState<ParameterItem[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showParams, setShowParams] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  async function load() {
    const [chat, catalog] = await Promise.all([
      api<ReportChatMessage[]>('/api/reports/chat'),
      api<ParameterItem[]>('/api/reports/parameters'),
    ])
    setMessages(chat)
    setParams(catalog)
  }

  useEffect(() => {
    load().catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  async function send(text: string) {
    const msg = text.trim()
    if (!msg || loading) return
    setError('')
    setLoading(true)
    setInput('')
    setMessages((prev) => [
      ...prev,
      {
        id: Date.now(),
        role: 'user',
        content: msg,
        created_at: new Date().toISOString(),
      },
    ])
    try {
      const res = await api<{ reply: string; messages: ReportChatMessage[] }>(
        '/api/reports/chat',
        { method: 'POST', body: JSON.stringify({ message: msg }) },
      )
      setMessages(res.messages)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao consultar a IA')
      await load().catch(() => undefined)
    } finally {
      setLoading(false)
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    await send(input)
  }

  async function clearChat() {
    if (!confirm('Limpar histórico do chat?')) return
    await api('/api/reports/chat', { method: 'DELETE' })
    setMessages([])
  }

  return (
    <div className="page">
      <div className="page-header">
        <div className="page-header-text">
          <h1 className="page-title">Relatórios</h1>
          <p className="page-sub">
            Pergunte à IA sobre alertas, celular, espera e o que as câmeras viram nas últimas 24h.
          </p>
        </div>
        <div className="page-actions">
          <button type="button" className="secondary" onClick={() => setShowParams((v) => !v)}>
            {showParams ? 'Ocultar parâmetros' : 'Parâmetros'}
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => clearChat().catch((e) => setError(e.message))}
          >
            Limpar chat
          </button>
        </div>
      </div>

      <div className={`reports-layout${showParams ? ' with-params' : ''}`}>
        {showParams ? (
          <aside className="panel params-panel">
            <div className="panel-head">
              <h2 className="section-title">Parâmetros</h2>
            </div>
            <div className="params-list">
              {params.map((p) => (
                <div key={p.key} className="param-item">
                  <strong>{p.label}</strong>
                  <code>{p.key}</code>
                  <p>{p.description}</p>
                  <span className="muted" style={{ fontSize: '0.78rem' }}>
                    {p.where} · {p.default}
                  </span>
                </div>
              ))}
            </div>
          </aside>
        ) : null}

        <div className="panel chat-panel">
          <div className="chat-messages">
            {messages.length === 0 && !loading ? (
              <div className="chat-empty">
                <p>Nenhuma pergunta ainda. Exemplos:</p>
                <div className="suggest-list">
                  {SUGGESTIONS.map((s) => (
                    <button key={s} type="button" className="suggest-chip" onClick={() => send(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
            {messages.map((m) => (
              <div key={m.id} className={`chat-bubble ${m.role}`}>
                <div className="chat-role">{m.role === 'user' ? 'Você' : 'IA'}</div>
                <div className="chat-content">{m.content}</div>
              </div>
            ))}
            {loading ? (
              <div className="chat-bubble assistant">
                <div className="chat-role">IA</div>
                <div className="chat-content muted">Analisando dados das câmeras…</div>
              </div>
            ) : null}
            <div ref={bottomRef} />
          </div>

          <form className="chat-compose" onSubmit={onSubmit}>
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ex.: Quanto tempo as pessoas esperaram na recepção hoje?"
              rows={2}
              disabled={loading}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault()
                  void send(input)
                }
              }}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              Enviar
            </button>
          </form>
          {error ? <p className="flash error" style={{ margin: '0 1rem 1rem' }}>{error}</p> : null}
        </div>
      </div>
    </div>
  )
}
