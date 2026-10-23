import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api } from '../api/client'
import type { Classroom } from '../api/types'

interface ClassState {
  classrooms: Classroom[]
  current: Classroom | null
  setCurrentId: (id: number) => void
  loading: boolean
  error: string | null
  refresh: () => Promise<void>
}

const ClassContext = createContext<ClassState | null>(null)
const KEY = 'tl_current_class'

function savedId(): number | null {
  try {
    const v = Number(localStorage.getItem(KEY))
    return Number.isInteger(v) && v > 0 ? v : null
  } catch {
    return null
  }
}

/** Classrooms the signed-in user owns (teacher) or belongs to (student). */
export function ClassProvider({ children }: { children: ReactNode }) {
  const [classrooms, setClassrooms] = useState<Classroom[]>([])
  const [currentId, setCurrent] = useState<number | null>(savedId)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      setClassrooms(await api.classrooms())
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not load classrooms')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const setCurrentId = useCallback((id: number) => {
    setCurrent(id)
    try {
      localStorage.setItem(KEY, String(id)) // only a UI preference, never a credential
    } catch {
      /* storage unavailable */
    }
  }, [])

  const current = classrooms.find((c) => c.id === currentId) ?? classrooms[0] ?? null
  const value = useMemo(
    () => ({ classrooms, current, setCurrentId, loading, error, refresh }),
    [classrooms, current, setCurrentId, loading, error, refresh],
  )
  return <ClassContext.Provider value={value}>{children}</ClassContext.Provider>
}

export function useClasses() {
  const ctx = useContext(ClassContext)
  if (!ctx) throw new Error('useClasses must be used within ClassProvider')
  return ctx
}
