import { CalendarDays } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { HistoryDay, HistoryWorkout } from '@/types'
import { Card } from './ui'

type Metric = 'recovery' | 'strain' | 'sleep_perf'
const METRICS: { id: Metric; label: string }[] = [
  { id: 'recovery', label: 'Recovery' },
  { id: 'strain', label: 'Strain' },
  { id: 'sleep_perf', label: 'Sleep' },
]
const TRAINING = new Set(['swim', 'bike', 'run', 'strength'])
const DISC_COLOR: Record<string, string> = { swim: 'var(--swim)', bike: 'var(--bike)', run: 'var(--run)', strength: 'var(--strength)' }
const DOW = ['Mon', '', 'Wed', '', 'Fri', '', 'Sun']
const CELL = 13, GAP = 3, LEFT = 30, TOP = 16

// Recovery and sleep use the readiness zone colours; strain is one hue whose opacity follows the 0–21 scale.
function cellFill(metric: Metric, v: number | null | undefined): { fill: string; opacity: number } {
  if (v == null) return { fill: 'var(--surface-2)', opacity: 1 }
  if (metric === 'strain') return { fill: 'var(--strain)', opacity: 0.15 + 0.85 * Math.min(1, v / 18) }
  const [hi, mid] = metric === 'recovery' ? [67, 34] : [85, 70]
  return { fill: v >= hi ? 'var(--good)' : v >= mid ? 'var(--warning)' : 'var(--critical)', opacity: 0.85 }
}

const iso = (d: Date) => d.toISOString().slice(0, 10)
const addDays = (s: string, n: number) => iso(new Date(Date.parse(s) + n * 86400000))
const longDate = (s: string) => new Date(s + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })

export function CalendarHeatmap({ days, workouts }: { days: HistoryDay[]; workouts: HistoryWorkout[] }) {
  const [metric, setMetric] = useState<Metric>('recovery')
  const [hover, setHover] = useState<string | null>(null)

  const { weeks, byDate, sessions, months } = useMemo(() => {
    const byDate = new Map(days.map((d) => [d.date, d]))
    const sessions = new Map<string, HistoryWorkout[]>()
    for (const w of workouts) if (TRAINING.has(w.discipline)) sessions.set(w.date, [...(sessions.get(w.date) ?? []), w])
    const all = [...byDate.keys(), ...sessions.keys()].sort()
    if (!all.length) return { weeks: [] as string[][], byDate, sessions, months: [] as { col: number; label: string }[] }
    // Columns start on the Monday on or before the first day (getUTCDay: 0 = Sunday).
    const first = all[0], last = all[all.length - 1]
    const start = addDays(first, -((new Date(first).getUTCDay() + 6) % 7))
    const weeks: string[][] = []
    for (let wk = start; wk <= last; wk = addDays(wk, 7)) weeks.push(Array.from({ length: 7 }, (_, i) => addDays(wk, i)))
    const months: { col: number; label: string }[] = []
    weeks.forEach((w, col) => {
      const firstOfMonth = w.find((d) => d.endsWith('-01'))
      if (col === 0 || firstOfMonth) {
        const d = firstOfMonth ?? w[0]
        months.push({ col, label: new Date(d + 'T12:00:00').toLocaleDateString(undefined, { month: 'short' }) })
      }
    })
    return { weeks, byDate, sessions, months }
  }, [days, workouts])

  const width = LEFT + weeks.length * (CELL + GAP)
  const height = TOP + 7 * (CELL + GAP)
  const hd = hover ? byDate.get(hover) : undefined
  const hs = hover ? sessions.get(hover) ?? [] : []
  const trainedDays = sessions.size

  return (
    <Card title="Calendar" subtitle={`Every day since ${days[0]?.date ?? '—'} · dot = training session · ${trainedDays} training days`} icon={<CalendarDays className="size-4.5" />}
      action={
        <div className="flex gap-1">
          {METRICS.map((m) => (
            <button key={m.id} onClick={() => setMetric(m.id)} className={`rounded-full border px-2.5 py-1 text-[12px] ${metric === m.id ? 'border-[var(--ink-muted)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)]'}`}>{m.label}</button>
          ))}
        </div>
      }>
      <div className="overflow-x-auto">
        <svg viewBox={`0 0 ${width} ${height}`} style={{ minWidth: Math.min(width, 640) }} className="w-full" onMouseLeave={() => setHover(null)}>
          {months.map((m) => <text key={m.col} x={LEFT + m.col * (CELL + GAP)} y={10} fontSize={10} fill="var(--ink-muted)">{m.label}</text>)}
          {DOW.map((l, i) => l && <text key={i} x={0} y={TOP + i * (CELL + GAP) + CELL - 3} fontSize={10} fill="var(--ink-muted)">{l}</text>)}
          {weeks.map((w, col) => w.map((d, row) => {
            const day = byDate.get(d)
            const { fill, opacity } = cellFill(metric, day?.[metric])
            const s = sessions.get(d)
            const cx = LEFT + col * (CELL + GAP), cy = TOP + row * (CELL + GAP)
            return (
              <g key={d} onMouseEnter={() => setHover(d)}>
                <rect x={cx} y={cy} width={CELL} height={CELL} rx={3} fill={fill} opacity={opacity}
                  stroke={hover === d ? 'var(--ink)' : 'none'} strokeWidth={1.5} />
                {s && <circle cx={cx + CELL / 2} cy={cy + CELL / 2} r={2.8} fill={s.length === 1 ? DISC_COLOR[s[0].discipline] : 'var(--ink)'} stroke="var(--surface)" strokeWidth={1.4} />}
              </g>
            )
          }))}
        </svg>
      </div>
      <div className="mt-2 min-h-[38px] text-[12.5px] text-[var(--ink-2)]">
        {hover ? (
          <div className="tabular">
            <span className="font-medium text-[var(--ink)]">{longDate(hover)}</span>
            {' · '}recovery {hd?.recovery ?? '—'}% · strain {hd?.strain ?? '—'} · sleep {hd?.sleep_h?.toFixed(1) ?? '—'} h ({hd?.sleep_perf ?? '—'}%) · HRV {hd?.hrv ?? '—'} ms
            <div>{hs.length ? hs.map((w) => `${w.sport.replace(/_/g, ' ')} ${Math.round(w.minutes ?? 0)} min`).join(' · ') : 'No training session'}</div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-3 text-[11.5px]">
            {metric === 'strain'
              ? <span>Lighter → darker = higher day strain (0–18+)</span>
              : (metric === 'recovery' ? ['≥ 67%', '34–66%', '< 34%'] : ['≥ 85%', '70–84%', '< 70%']).map((l, i) => (
                  <span key={l} className="flex items-center gap-1"><span className="size-2.5 rounded-[3px]" style={{ background: ['var(--good)', 'var(--warning)', 'var(--critical)'][i] }} />{l}</span>
                ))}
            {Object.entries(DISC_COLOR).map(([k, c]) => <span key={k} className="flex items-center gap-1 capitalize"><span className="size-2 rounded-full" style={{ background: c }} />{k}</span>)}
            <span className="flex items-center gap-1"><span className="size-2 rounded-full bg-[var(--ink)]" />2+ sessions</span>
          </div>
        )}
      </div>
    </Card>
  )
}
