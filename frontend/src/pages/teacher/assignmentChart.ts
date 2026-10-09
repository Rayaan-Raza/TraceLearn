import type { SubmissionSummary } from '../../api/types'
import { isRealMisconception, misconceptionLabel, type ChartPoint } from '../../lib/labels'

/** X = misconception seen (or Correct), Y = attempt count. */
export function misconceptionPoints(subs: SubmissionSummary[]): ChartPoint[] {
  if (subs.length === 0) return [{ label: 'No attempts yet', count: 0, tone: 'isolated' }]
  const counts = new Map<string, { count: number; tone: string }>()
  for (const s of subs) {
    const key = s.passed ? 'Correct' : isRealMisconception(s.primary_misconception) ? misconceptionLabel(s.primary_misconception) : 'Unclassified'
    const tone = s.passed ? 'none' : s.requires_teacher_review ? 'review' : key === 'Unclassified' ? 'isolated' : 'persistent'
    const prev = counts.get(key)
    counts.set(key, { count: (prev?.count ?? 0) + 1, tone })
  }
  return [...counts.entries()].map(([label, v]) => ({ label, ...v }))
}
