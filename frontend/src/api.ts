import { useCallback, useEffect, useState } from 'react'
import type { Exercise, History, Insight, PlanResponse, StrengthSession, StrengthSummary, Summary } from './types'

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

const OUTDATED = 'The dashboard server is older than this page. Restart it (or reconnect the WHOOP MCP) to load this tab.'

/** GET JSON; a 404 or an HTML reply means the server predates this endpoint. */
async function getJson(url: string) {
  const r = await fetch(url)
  const json = (r.headers.get('content-type') ?? '').includes('application/json')
  if (r.status === 404 || !json) throw new Error(OUTDATED)
  if (!r.ok) throw new Error(`${url}: ${r.status}`)
  return r.json()
}

export interface StrengthData { summary: StrengthSummary; exercises: Exercise[]; sessions: StrengthSession[] }

export function useStrength() {
  const [data, setData] = useState<StrengthData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    try {
      const [summary, exercises, sessions] = await Promise.all(
        ['/api/strength/summary', '/api/strength/exercises', '/api/strength/sessions'].map(getJson),
      )
      setData({ summary, exercises, sessions })
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])
  useEffect(() => { load() }, [load])
  return { data, error, reload: load }
}

/** POST/PUT/DELETE against the strength API; throws the server's one-line detail on failure. */
export async function strengthRequest(method: 'POST' | 'PUT' | 'DELETE', path: string, body?: unknown) {
  const res = await fetch(`/api/strength/${path}`, {
    method, headers: body ? { 'Content-Type': 'application/json' } : undefined, body: body ? JSON.stringify(body) : undefined,
  })
  const json = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(json.detail ? (typeof json.detail === 'string' ? json.detail : 'Invalid input.') : res.statusText)
  return json
}

export function usePlan() {
  const [data, setData] = useState<PlanResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const load = useCallback(async () => {
    try {
      setData(await getJson('/api/plan'))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [])
  useEffect(() => { load() }, [load])
  return { data, error, reload: load }
}
