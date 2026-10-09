import type { ChartPoint } from '../lib/labels'

export function BarChart({
  title,
  subtitle,
  points,
  valueSuffix = '',
  axisNote = 'X: state · Y: attempt count',
  embedded = false,
}: {
  title: string
  subtitle?: string
  points: ChartPoint[]
  valueSuffix?: string
  axisNote?: string
  embedded?: boolean
}) {
  const max = Math.max(...points.map((p) => p.count), 1)
  const columns = Math.min(Math.max(points.length, 2), 5)

  return (
    <section className={embedded ? 'chart-embed' : 'card'}>
      <div className="card-label">{title}</div>
      {subtitle ? <p style={{ marginBottom: '0.85rem' }}>{subtitle}</p> : null}
      <div
        className="chart vertical-chart"
        style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
      >
        {points.map((point) => {
          const height =
            point.count === 0 ? 6 : Math.max((point.count / max) * 120, 14)
          return (
            <div className="vbar" key={point.label}>
              <div className="vbar-value">
                {point.count}
                {valueSuffix}
              </div>
              <div className="vbar-track">
                <div
                  className={`vbar-fill ${point.tone ?? ''}${point.count === 0 ? ' zero' : ''}`}
                  style={{ height: `${height}px` }}
                />
              </div>
              <div className="vbar-label">{point.label}</div>
            </div>
          )
        })}
      </div>
      <div className="chart-axis-note">{axisNote}</div>
    </section>
  )
}

export function TimelineChart({
  title,
  subtitle,
  points,
}: {
  title: string
  subtitle?: string
  points: ChartPoint[]
}) {
  const max = Math.max(...points.map((p) => p.count), 1)

  return (
    <section className="card">
      <div className="card-label">{title}</div>
      {subtitle ? <p style={{ marginBottom: '0.85rem' }}>{subtitle}</p> : null}
      <div className="chart">
        {points.map((point) => {
          const width =
            point.count === 0 ? 0 : Math.max((point.count / max) * 100, 12)
          return (
            <div className="chart-row" key={point.label}>
              <div className="chart-label">{point.label}</div>
              <div className="chart-bar-track">
                <div
                  className={`chart-bar${point.count === 0 ? ' zero' : ''}`}
                  style={{ width: `${width}%` }}
                />
              </div>
              <div className="chart-count">{point.count}</div>
            </div>
          )
        })}
      </div>
      <div className="chart-axis-note">
        X: date · Y: cumulative related mistakes
      </div>
    </section>
  )
}
