import { useCallback, useEffect, useRef, useState } from 'react'

/** Load data on mount / when deps change. Ignores responses from stale calls. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const call = useRef(0)

  const load = useCallback(() => {
    const id = ++call.current
    setLoading(true)
    setError(null)
    fn()
      .then((d) => {
        if (id === call.current) setData(d)
      })
      .catch((e: unknown) => {
        if (id === call.current) setError(e instanceof Error ? e.message : 'Something went wrong')
      })
      .finally(() => {
        if (id === call.current) setLoading(false)
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    load()
  }, [load])

  return { data, error, loading, reload: load, setData }
}
