import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { RunAnalyzeResponse, StudentOption } from '../types'

export type SessionContextValue = {
  students: StudentOption[]
  setStudents: (s: StudentOption[]) => void
  selectedStudentId: number | null
  setSelectedStudentId: (id: number | null) => void
  lastResult: RunAnalyzeResponse | null
  setLastResult: (r: RunAnalyzeResponse | null) => void
  loadingSession: boolean
  setLoadingSession: (v: boolean) => void
}

const SessionContext = createContext<SessionContextValue | null>(null)

export function SessionProvider({ children }: { children: ReactNode }) {
  const [students, setStudents] = useState<StudentOption[]>([])
  const [selectedStudentId, setSelectedStudentId] = useState<number | null>(null)
  const [lastResult, setLastResult] = useState<RunAnalyzeResponse | null>(null)
  const [loadingSession, setLoadingSession] = useState(false)

  const value = useMemo(
    () => ({
      students,
      setStudents,
      selectedStudentId,
      setSelectedStudentId,
      lastResult,
      setLastResult,
      loadingSession,
      setLoadingSession,
    }),
    [students, selectedStudentId, lastResult, loadingSession],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
