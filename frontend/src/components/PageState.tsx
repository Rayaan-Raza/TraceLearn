import { Link } from 'react-router-dom'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="page-state" role="status" aria-live="polite">
      <span className="spinner" aria-hidden /> {label}
    </div>
  )
}

export function ErrorState({ message, onRetry, back }: { message: string; onRetry?: () => void; back?: { to: string; label: string } }) {
  return (
    <section className="card error-card" role="alert">
      <div className="card-label">Something went wrong</div>
      <p style={{ margin: 0 }}>{message}</p>
      <div className="btn-row">
        {onRetry ? (
          <button type="button" className="btn btn-secondary" onClick={onRetry}>
            Try again
          </button>
        ) : null}
        {back ? (
          <Link className="btn btn-ghost" to={back.to}>
            {back.label}
          </Link>
        ) : null}
      </div>
    </section>
  )
}

export function NotFound({ title, body, back }: { title: string; body: string; back: { to: string; label: string } }) {
  return (
    <div className="stack">
      <header className="page-header">
        <h1>{title}</h1>
        <p>{body}</p>
      </header>
      <Link className="btn btn-primary" to={back.to} style={{ alignSelf: 'flex-start' }}>
        {back.label}
      </Link>
    </div>
  )
}
