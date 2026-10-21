import { Activity, AlertTriangle } from 'lucide-react'
import type { HistoryAnalytics, LoadWeek, TrainingDiscipline } from '@/types'
import { Card, Tip } from './ui'

const DISCIPLINES: { id: TrainingDiscipline; label: string; color: string }[] = [
  { id: 'swim', label: 'Swim', color: 'var(--swim)' },
  { id: 'bike', label: 'Bike', color: 'var(--bike)' },
  { id: 'run', label: 'Run', color: 'var(--run)' },
  { id: 'strength', label: 'Strength', color: 'var(--strength)' },
]
// Two weeks without a discipline counts as a lapse.
const GAP_DAYS = 14

const shortDate = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

export function LoadCard({ load, weeks }: { load: HistoryAnalytics['load']; weeks: LoadWeek[] }) {
  const max = Math.max(1, ...weeks.map((w) => w.total_hours))
  const recent = weeks.slice(-4)
  const recentAvg = recent.reduce((a, w) => a + w.total_hours, 0) / (recent.length || 1)
  const avg = weeks.reduce((a, w) => a + w.total_hours, 0) / (weeks.length || 1)

  return (
    <Card title="Training load & consistency" subtitle={`Weekly hours by sport · last 4 weeks ${recentAvg.toFixed(1)} h/wk vs ${avg.toFixed(1)} h/wk in range`} icon={<Activity className="size-4.5" />}>
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {DISCIPLINES.map((d) => {
            const s = load.last_session[d.id]
            const lapsed = s.days == null || s.days > GAP_DAYS
            return (
              <div key={d.id} className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
                <div className="flex items-center gap-1.5 text-[11.5px] font-medium tracking-wide text-[var(--ink-muted)] uppercase">
                  <span className="size-2 rounded-full" style={{ background: d.color }} />{d.label}
                </div>
                <div className="tabular mt-0.5 flex items-center gap-1.5 text-[18px] font-semibold text-[var(--ink)]">
                  {s.days == null ? '—' : `${s.days} d`}
                  {lapsed && <AlertTriangle className="size-4" style={{ color: 'var(--serious)' }} aria-label="lapsed" />}
                </div>
                <div className="truncate text-[11.5px] text-[var(--ink-2)]">{s.date ? `since last · ${shortDate(s.date)}` : 'never logged'}</div>
              </div>
            )
          })}
        </div>

        <div>
          <div className="flex h-40 items-end gap-[2px]">
            {weeks.map((w) => (
              <Tip key={w.week} content={
                <div className="tabular">
                  <div className="font-medium">Week of {shortDate(w.week)} · {w.total_hours.toFixed(1)} h · {w.sessions} sessions</div>
                  {DISCIPLINES.map((d) => w.hours[d.id] > 0 && <div key={d.id}>{d.label}: {w.hours[d.id].toFixed(1)} h</div>)}
                  {w.avg_strain != null && <div>Avg day strain {w.avg_strain}</div>}
                </div>
              }>
                <div className="flex h-full min-w-0 flex-1 flex-col justify-end">
                  {DISCIPLINES.slice().reverse().map((d) => w.hours[d.id] > 0 && (
                    <div key={d.id} style={{ height: `${(w.hours[d.id] / max) * 100}%`, background: d.color }} />
                  ))}
                </div>
              </Tip>
            ))}
          </div>
          <div className="mt-1 flex justify-between text-[11px] text-[var(--ink-muted)]">
            <span>{weeks[0] && shortDate(weeks[0].week)}</span>
            <span>peak {max.toFixed(1)} h</span>
            <span>{weeks.length > 0 && shortDate(weeks[weeks.length - 1].week)}</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-3 text-[11.5px] text-[var(--ink-2)]">
            {DISCIPLINES.map((d) => <span key={d.id} className="flex items-center gap-1"><span className="size-2 rounded-[2px]" style={{ background: d.color }} />{d.label}</span>)}
          </div>
        </div>
      </div>
    </Card>
  )
}
