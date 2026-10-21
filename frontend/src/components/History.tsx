import { BarChart3 } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useHistory } from '@/api'
import type { HistoryDay, HistoryWorkout } from '@/types'
import { CalendarHeatmap } from './CalendarHeatmap'
import { LineChart } from './LineChart'
import { LoadCard } from './LoadCard'
import { RunZonesCard } from './RunZonesCard'
import { SleepRecoveryCard } from './SleepRecoveryCard'
import { Card } from './ui'

type Range = 30 | 90 | 180 | 0
const RANGES: [Range, string][] = [[30, '30d'], [90, '90d'], [180, '6m'], [0, 'All']]

const mean = (xs: (number | null | undefined)[]) => {
  const v = xs.filter((x): x is number => x != null)
  return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null
}
const fmt = (n: number | null | undefined, d = 0) => (n == null ? '—' : n.toFixed(d))
const shortDate = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })

function rolling(values: (number | null)[], w = 7) {
  return values.map((_, i) => mean(values.slice(Math.max(0, i - w + 1), i + 1)))
}

function Stat({ label, value, unit, sub }: { label: string; value: string; unit?: string; sub?: string }) {
  return (
    <div className="min-w-0 rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
      <div className="truncate text-[11.5px] font-medium tracking-wide text-[var(--ink-muted)] uppercase">{label}</div>
      <div className="tabular text-[20px] font-semibold text-[var(--ink)]">{value}<span className="ml-1 text-[12px] font-normal text-[var(--ink-muted)]">{unit}</span></div>
      {sub && <div className="truncate text-[11.5px] text-[var(--ink-2)]">{sub}</div>}
    </div>
  )
}

const DISC_COLOR: Record<string, string> = { swim: 'var(--swim)', bike: 'var(--bike)', run: 'var(--run)', strength: 'var(--strength)' }

function WorkoutTable({ workouts }: { workouts: HistoryWorkout[] }) {
  const [disc, setDisc] = useState('all')
  const [all, setAll] = useState(false)
  const discs = useMemo(() => ['all', ...Array.from(new Set(workouts.map((w) => w.discipline))).sort()], [workouts])
  const rows = workouts.filter((w) => disc === 'all' || w.discipline === disc)
  const shown = all ? rows : rows.slice(0, 40)
  return (
    <Card title="Workouts" subtitle={`${rows.length} sessions in range`} icon={<BarChart3 className="size-4.5" />}
      action={
        <div className="flex flex-wrap justify-end gap-1">
          {discs.map((d) => (
            <button key={d} onClick={() => setDisc(d)} className={`rounded-full border px-2.5 py-1 text-[12px] capitalize ${disc === d ? 'border-[var(--ink-muted)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)]'}`}>{d}</button>
          ))}
        </div>
      }>
      <div className="overflow-x-auto">
        <table className="tabular w-full text-left text-[12.5px] text-[var(--ink-2)]">
          <thead className="text-[11px] tracking-wide text-[var(--ink-muted)] uppercase">
            <tr>{['Date', 'Sport', 'Min', 'Strain', 'Avg HR', 'Max HR', 'kJ', 'km'].map((h) => <th key={h} className="px-2 py-1.5 font-medium">{h}</th>)}</tr>
          </thead>
          <tbody>
            {shown.map((w) => (
              <tr key={w.start} className="border-t border-[var(--border)]">
                <td className="px-2 py-1.5">{shortDate(w.date)}</td>
                <td className="px-2 py-1.5"><span className="mr-1.5 inline-block size-2 rounded-full" style={{ background: DISC_COLOR[w.discipline] ?? 'var(--other)' }} />{w.sport.replace(/_/g, ' ')}</td>
                <td className="px-2 py-1.5">{fmt(w.minutes)}</td><td className="px-2 py-1.5">{fmt(w.strain, 1)}</td>
                <td className="px-2 py-1.5">{fmt(w.avg_hr)}</td><td className="px-2 py-1.5">{fmt(w.max_hr)}</td>
                <td className="px-2 py-1.5">{fmt(w.kj)}</td><td className="px-2 py-1.5">{fmt(w.km, 1)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length > 40 && (
        <button onClick={() => setAll(!all)} className="mt-3 self-center text-sm text-[var(--strain)] underline underline-offset-4">{all ? 'Show fewer' : `Show all ${rows.length}`}</button>
      )}
    </Card>
  )
}

export function History() {
  const state = useHistory()
  const [range, setRange] = useState<Range>(90)

  if (state.status === 'loading') return <div className="py-20 text-center text-[var(--ink-2)]">Loading history…</div>
  if (state.status === 'error' || !state.data.available) {
    return (
      <div className="mx-auto mt-10 max-w-lg rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--ink-2)]">
        No history export found. Run <code className="rounded bg-[var(--surface-2)] px-1.5 py-0.5">python -m whoop_mcp export</code> and refresh.
      </div>
    )
  }

  const h = state.data
  // Ranges count back from the newest day in the export, not from today, so an older export still fills them.
  const latest = h.days[h.days.length - 1]?.date
  const cutoff = range && latest ? new Date(Date.parse(latest) - range * 86400000).toISOString().slice(0, 10) : ''
  const days: HistoryDay[] = h.days.filter((d) => d.date >= cutoff)
  const workouts = h.workouts.filter((w) => w.date >= cutoff)
  const dates = days.map((d) => d.date)
  const col = (k: keyof HistoryDay) => days.map((d) => (d[k] as number | null | undefined) ?? null)
  const rec = col('recovery')

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[12.5px] text-[var(--ink-muted)]">
          {h.days[0]?.date} → {h.days[h.days.length - 1]?.date} · {h.counts?.workouts} workouts · {h.counts?.sleeps} sleeps · export {h.exported_at ? new Date(h.exported_at).toLocaleDateString() : ''}
        </p>
        <div className="flex gap-1">
          {RANGES.map(([r, l]) => (
            <button key={l} onClick={() => setRange(r)} className={`rounded-full border px-3 py-1 text-[12.5px] ${range === r ? 'border-[var(--ink-muted)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)]'}`}>{l}</button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
        <Stat label="Recovery" value={fmt(mean(rec))} unit="%" sub={`${days.length} days`} />
        <Stat label="HRV" value={fmt(mean(col('hrv')))} unit="ms" />
        <Stat label="RHR" value={fmt(mean(col('rhr')))} unit="bpm" />
        <Stat label="Day strain" value={fmt(mean(col('strain')), 1)} />
        <Stat label="Sleep" value={fmt(mean(col('sleep_h')), 1)} unit="h" sub={`need ${fmt(mean(col('need_h')), 1)} h`} />
        <Stat label="Workouts" value={String(workouts.length)} sub={`${fmt(workouts.reduce((a, w) => a + (w.minutes ?? 0), 0) / 60, 1)} h total`} />
      </div>

      {/* An older dashboard process may serve this build without the analytics block. */}
      {h.analytics ? (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[3fr_2fr]">
            <LoadCard load={h.analytics.load} weeks={h.analytics.load.weeks.filter((w) => w.week >= cutoff)} />
            <RunZonesCard zones={h.analytics.run_zones} fromMonth={cutoff.slice(0, 7)} />
          </div>
          <SleepRecoveryCard data={h.analytics.sleep_recovery} from={cutoff} />
        </>
      ) : (
        <p className="rounded-xl border border-[var(--border)] px-4 py-3 text-[13px] text-[var(--ink-2)]">
          Training load, run intensity and sleep insights need a newer dashboard server. Restart it to load them.
        </p>
      )}

      <CalendarHeatmap days={h.days} workouts={h.workouts} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Recovery" subtitle="Daily score with 7-day average" icon={<BarChart3 className="size-4.5" />}>
          <LineChart dates={dates} min={0} max={100} unit="%" lines={[{ label: 'Recovery', color: 'var(--good)', values: rec, dots: true }, { label: '7d avg', color: 'var(--ink)', values: rolling(rec) }]} />
        </Card>
        <Card title="HRV & resting heart rate" subtitle="HRV (ms) and RHR (bpm), 7-day averages" icon={<BarChart3 className="size-4.5" />}>
          <LineChart dates={dates} lines={[{ label: 'HRV', color: 'var(--strain)', values: rolling(col('hrv')) }, { label: 'RHR', color: 'var(--bike)', values: rolling(col('rhr')) }]} />
        </Card>
        <Card title="Day strain" subtitle="Daily strain with 7-day average" icon={<BarChart3 className="size-4.5" />}>
          <LineChart dates={dates} min={0} max={21} lines={[{ label: 'Strain', color: 'var(--strain)', values: col('strain'), dots: true }, { label: '7d avg', color: 'var(--ink)', values: rolling(col('strain')) }]} />
        </Card>
        <Card title="Sleep" subtitle="Hours asleep vs hours needed, 7-day averages" icon={<BarChart3 className="size-4.5" />}>
          <LineChart dates={dates} unit=" h" lines={[{ label: 'Slept', color: 'var(--stage-rem)', values: rolling(col('sleep_h')) }, { label: 'Needed', color: 'var(--ink-muted)', values: rolling(col('need_h')), dashed: true }]} />
        </Card>
      </div>

      <Card title="Monthly summary" subtitle="Whole history by month" icon={<BarChart3 className="size-4.5" />}>
        <div className="overflow-x-auto">
          <table className="tabular w-full text-left text-[12.5px] text-[var(--ink-2)]">
            <thead className="text-[11px] tracking-wide text-[var(--ink-muted)] uppercase">
              <tr>{['Month', 'Recovery', 'HRV', 'RHR', 'Strain', 'Sleep h', 'Sleep %', 'Swim h', 'Bike h', 'Run h', 'Strength h'].map((c) => <th key={c} className="px-2 py-1.5 font-medium">{c}</th>)}</tr>
            </thead>
            <tbody>
              {h.monthly.map((m) => (
                <tr key={String(m.month)} className="border-t border-[var(--border)]">
                  <td className="px-2 py-1.5 text-[var(--ink)]">{String(m.month)}</td>
                  <td className="px-2 py-1.5">{fmt(m.avg_recovery as number | null)}%</td>
                  <td className="px-2 py-1.5">{fmt(m.avg_hrv_ms as number | null)}</td>
                  <td className="px-2 py-1.5">{fmt(m.avg_rhr as number | null)}</td>
                  <td className="px-2 py-1.5">{fmt(m.avg_day_strain as number | null, 1)}</td>
                  <td className="px-2 py-1.5">{fmt(m.avg_sleep_h as number | null, 1)}</td>
                  <td className="px-2 py-1.5">{fmt(m.avg_sleep_performance as number | null)}</td>
                  {['swim', 'bike', 'run', 'strength'].map((d) => <td key={d} className="px-2 py-1.5">{fmt(m[`training.${d}.hours`] as number | null, 1)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <WorkoutTable workouts={workouts} />
    </div>
  )
}
