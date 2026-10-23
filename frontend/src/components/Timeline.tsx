export interface ProgressEvent {
  label: string
  detail: string
  tone: 'negative' | 'positive' | 'neutral' | 'current'
  date: string
}

export function Timeline({ events }: { events: ProgressEvent[] }) {
  return (
    <div className="timeline">
      {events.map((event, index) => (
        <div className="timeline-item" key={`${event.label}-${index}`}>
          <div className={`timeline-dot ${event.tone}`} />
          <div>
            <div className="timeline-label">{event.label}</div>
            <div className="timeline-detail">{event.detail}</div>
            {event.date ? <div className="timeline-date">{event.date}</div> : null}
          </div>
        </div>
      ))}
    </div>
  )
}
