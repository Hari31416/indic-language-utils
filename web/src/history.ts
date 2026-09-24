import { useState } from 'react'

/** Tiny localStorage-backed "recent runs" hook. Purely additive UX; no API impact. */
export function useLocalHistory<T>(key: string, limit = 6) {
  const [items, setItems] = useState<T[]>(() => {
    try {
      const raw = localStorage.getItem(key)
      if (!raw) return []
      const parsed: unknown = JSON.parse(raw)
      return Array.isArray(parsed) ? (parsed as T[]) : []
    } catch {
      return []
    }
  })

  const push = (item: T) => {
    setItems((prev) => {
      const next = [item, ...prev].slice(0, limit)
      try {
        localStorage.setItem(key, JSON.stringify(next))
      } catch {
        // storage full / unavailable — history is best-effort
      }
      return next
    })
  }

  const clear = () => {
    setItems([])
    try {
      localStorage.removeItem(key)
    } catch {
      // ignore
    }
  }

  return { items, push, clear }
}
