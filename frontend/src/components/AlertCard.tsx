import { useState } from 'react'
import { api, mediaUrl } from '../api'
import type { Alert } from '../api'

type Props = {
  alert: Alert
  onChange: (alert: Alert) => void
}

export default function AlertCard({ alert, onChange }: Props) {
  const [dislikeOpen, setDislikeOpen] = useState(false)
  const [comment, setComment] = useState(alert.feedback_comment || '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const imagePath = alert.favorite_path || alert.snapshot_path

  async function sendFeedback(value: 'tp' | 'fp', note?: string) {
    setBusy(true)
    setError('')
    try {
      const updated = await api<Alert>(`/api/alerts/${alert.id}/feedback`, {
        method: 'POST',
        body: JSON.stringify({ feedback: value, comment: note || null }),
      })
      onChange(updated)
      if (value === 'fp') setDislikeOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro no feedback')
    } finally {
      setBusy(false)
    }
  }

  async function toggleFavorite() {
    setBusy(true)
    setError('')
    try {
      const updated = await api<Alert>(`/api/alerts/${alert.id}/favorite`, {
        method: 'POST',
        body: JSON.stringify({ favorited: !alert.favorited }),
      })
      onChange(updated)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao favoritar')
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className="panel stack alert-card">
      {imagePath ? (
        <img src={mediaUrl(imagePath)} alt="Evidência" />
      ) : (
        <div className="preview" />
      )}
      <div>
        <strong>{alert.camera_name || `Câmera #${alert.camera_id}`}</strong>
        <div className="muted">{new Date(alert.created_at).toLocaleString('pt-BR')}</div>
      </div>
      <p style={{ margin: 0 }}>{alert.description}</p>
      <div className="row">
        {alert.violations.map((v) => (
          <span key={v} className="badge warn">
            {v}
          </span>
        ))}
        <span className="badge">{Math.round(alert.confidence * 100)}%</span>
        {alert.feedback === 'tp' ? <span className="badge online">acerto</span> : null}
        {alert.feedback === 'fp' ? <span className="badge offline">falso+</span> : null}
        {alert.favorited ? <span className="badge warn">★ favorito</span> : null}
      </div>

      <div className="row">
        <button
          type="button"
          className={alert.feedback === 'tp' ? '' : 'secondary'}
          disabled={busy}
          title="Like — alerta válido"
          onClick={() => sendFeedback('tp')}
        >
          👍 Like
        </button>
        <button
          type="button"
          className={alert.feedback === 'fp' || dislikeOpen ? '' : 'secondary'}
          disabled={busy}
          title="Dislike — falso positivo"
          onClick={() => setDislikeOpen((v) => !v)}
        >
          👎 Dislike
        </button>
        <button
          type="button"
          className={alert.favorited ? '' : 'secondary'}
          disabled={busy}
          title="Favoritar imagem"
          onClick={toggleFavorite}
        >
          {alert.favorited ? '★ Favorito' : '☆ Favoritar'}
        </button>
      </div>

      {dislikeOpen ? (
        <div className="stack">
          <label>
            O que a IA errou? (ajuda a melhorar)
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              placeholder="Ex.: era cliente, não colaborador; a pessoa estava de touca…"
            />
          </label>
          <div className="row">
            <button
              type="button"
              disabled={busy || comment.trim().length < 5}
              onClick={() => sendFeedback('fp', comment.trim())}
            >
              Enviar dislike
            </button>
            <button type="button" className="secondary" onClick={() => setDislikeOpen(false)}>
              Cancelar
            </button>
          </div>
        </div>
      ) : null}

      {alert.feedback === 'fp' && alert.feedback_comment && !dislikeOpen ? (
        <p className="muted" style={{ margin: 0 }}>
          Feedback: {alert.feedback_comment}
        </p>
      ) : null}
      {error ? <p className="error">{error}</p> : null}
    </article>
  )
}
