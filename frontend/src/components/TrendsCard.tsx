import { AlertTriangle, CheckCircle2, TrendingUp } from 'lucide-react'
import type { Trends } from '@/types'
import { Card, StatusPill, Tip, dayLabel, zoneColor } from './ui'

const statusZone = { ok: 'green', watch: 'yellow', caution: 'red' } as const
const statusText = { ok: 'Load balanced', watch: 'Watch load', caution: 'Overreach risk' }

export function TrendsCard({ trends }: { trends: Trends }) {
  const a = trends.averages_7d
  const zone = (r: number | null) => (r == null ? null : r >= 67 ? 'green' : r >= 34 ? 'yellow' : 'red')
  return (
    <Card
      title="7-Day Trends"
      subtitle="7-day averages vs 28-day baseline"
      icon={<TrendingUp className="size-4.5" />}
      action={<StatusPill zone={statusZone[trends.status]}>{statusText[trends.status]}</StatusPill>}
    >
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            ['Recovery', a.recovery?.toFixed(0), '% avg'],
            ['HRV', a.hrv?.toFixed(0), `ms · ${trends.hrv_trend ?? '—'}`],
            ['RHR', a.rhr?.toFixed(0), `bpm · ${trends.rhr_trend ?? '—'}`],
            ['ACWR', trends.acute_chronic_strain_ratio?.toFixed(2), 'acute:chronic'],
          ].map(([l, v, u]) => (
            <div key={l} className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
              <div className="text-[11.5px] font-medium tracking-wide text-[var(--ink-muted)] uppercase">{l}</div>
              <div className="tabular text-[18px] font-semibold text-[var(--ink)]">{v ?? '—'}</div>
              <div className="truncate text-[11.5px] text-[var(--ink-2)]">{u}</div>
            </div>
          ))}
        </div>

        <div>
          <div className="mb-1.5 text-[11.5px] text-[var(--ink-muted)]">Daily recovery</div>
          <div className="flex h-32 items-end gap-[2px]">
            {trends.series.map((p) => {
              const z = zone(p.recovery)
              return (
                <Tip key={p.date} content={<span className="tabular">{dayLabel(p.date)} · recovery {p.recovery ?? '—'}% · strain {p.day_strain ?? '—'} · sleep {p.sleep_performance ?? '—'}%</span>}>
                  <div className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                    <span className="tabular text-[10.5px] text-[var(--ink-2)]">{p.recovery ?? ''}</span>
                    <div className="w-full max-w-6 rounded-t-[4px]" style={{ height: `${(p.recovery ?? 0) * 0.7}%`, background: z ? zoneColor[z] : 'var(--surface-2)' }} />
                    <span className="text-[10.5px] text-[var(--ink-muted)]">{dayLabel(p.date).slice(0, 2)}</span>
                  </div>
                </Tip>
              )
            })}
          </div>
        </div>

        {trends.overtraining_flags.length ? (
          <ul className="flex flex-col gap-1.5">
            {trends.overtraining_flags.map((f) => (
              <li key={f} className="flex items-start gap-2 text-[13px] text-[var(--ink-2)]">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" style={{ color: 'var(--serious)' }} />{f}
              </li>
            ))}
          </ul>
        ) : (
          <p className="flex items-center gap-2 text-[13px] text-[var(--ink-2)]">
            <CheckCircle2 className="size-4" style={{ color: 'var(--good)' }} /> No overtraining flags this week.
          </p>
        )}
      </div>
    </Card>
  )
}
