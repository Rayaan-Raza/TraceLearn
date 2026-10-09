import { problemStatusLabel, statusLabel, type ProblemStatus, type UiStatus } from '../lib/labels'

export function StatusBadge({ status }: { status: UiStatus | ProblemStatus | 'correct' | 'incorrect' }) {
  const label =
    status === 'correct'
      ? 'Correct'
      : status === 'incorrect'
        ? 'Incorrect'
        : status === 'persistent' || status === 'improving' || status === 'isolated' || status === 'none' || status === 'review'
          ? statusLabel(status)
          : problemStatusLabel(status)
  return <span className={`badge ${status}`}>{label}</span>
}
