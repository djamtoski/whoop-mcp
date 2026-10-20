import { useCallback, useEffect, useState } from 'react'
import type { History, Insight, Summary } from './types'

type HistoryState = { status: 'loading' } | { status: 'error' } | { status: 'ready'; data: History }

export function useHistory(): HistoryState & { data: History } {
  const [state, setState] = useState<HistoryState>({ status: 'loading' })
  useEffect(() => {
    fetch('/api/history').then((r) => r.json()).then((data) => setState({ status: 'ready', data })).catch(() => setState({ status: 'error' }))
  }, [])
  return { ...state, data: (state as { data?: History }).data ?? { available: false } }
}

export const isDemo = new URLSearchParams(window.location.search).has('demo')

type SummaryState =
  | { status: 'loading' }
  | { status: 'ready'; data: Summary }
  | { status: 'error'; kind: 'not_logged_in' | 'whoop_error' | 'network'; detail: string }

const REFRESH_MS = 5 * 60_000

export function useSummary() {
  const [state, setState] = useState<SummaryState>({ status: 'loading' })

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/summary${isDemo ? '?demo=1' : ''}`)
      const body = await res.json()
      if (!res.ok) {
        setState({ status: 'error', kind: body.error ?? 'whoop_error', detail: body.detail ?? res.statusText })
      } else {
        setState({ status: 'ready', data: body })
      }
    } catch (e) {
      setState({ status: 'error', kind: 'network', detail: String(e) })
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, REFRESH_MS)
    return () => clearInterval(t)
  }, [load])

  return { state, reload: load }
}

export function useInsights() {
  const [items, setItems] = useState<Insight[]>([])
  const [live, setLive] = useState(false)

  useEffect(() => {
    fetch('/api/insights').then((r) => r.json()).then(setItems).catch(() => {})
    const es = new EventSource('/api/events')
    es.addEventListener('insights', (e) => {
      setItems(JSON.parse((e as MessageEvent).data))
      setLive(true)
    })
    es.onopen = () => setLive(true)
    es.onerror = () => setLive(false)
    return () => es.close()
  }, [])

  return { items, live }
}
