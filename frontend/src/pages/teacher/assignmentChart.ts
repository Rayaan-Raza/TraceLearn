import type { SubmissionSummary } from '../../api/types'
import { isRealMisconception, misconceptionColor, misconceptionLabel, type ChartPoint } from '../../lib/labels'

/** X = misconception seen (or Correct), Y = attempt count. */
export function misconceptionPoints(subs: SubmissionSummary[]): ChartPoint[] {
  if (subs.length === 0) return [{ label: 'No attempts yet', count: 0, tone: 'isolated' }]
  const counts = new Map<string, { count: number; tone: string; mid: string | null }>()
  for (const s of subs) {
    const mid = s.passed ? null : (s.primary_misconception ?? null)
    const key = s.passed ? 'Correct' : isRealMisconception(mid) ? misconceptionLabel(mid) : 'Unclassified'
    const tone = s.passed ? 'none' : s.requires_teacher_review ? 'review' : key === 'Unclassified' ? 'isolated' : 'persistent'
    const prev = counts.get(key)
    counts.set(key, { count: (prev?.count ?? 0) + 1, tone, mid: prev?.mid ?? mid })
  }
  return [...counts.entries()].map(([label, v]) => ({
    label,
    count: v.count,
    tone: v.tone,
    color: v.mid ? misconceptionColor(v.mid) : undefined,
  }))
}
