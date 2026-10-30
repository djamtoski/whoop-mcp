import { Activity, Bike, Dumbbell, Flower2, Footprints, Timer, Waves } from 'lucide-react'
import { useMemo, useState } from 'react'
import { ActivitiesCard } from '@/components/watermelon/activities-card'
import { ContinuousTabs } from '@/components/watermelon/continuous-tabs'
import { mergeSplitSessions, sportName } from '@/lib/sports'
import type { Discipline, StrainDay, Workout } from '@/types'
import { Card, Tip, dayLabel } from './ui'

const META: Record<Discipline, { label: string; color: string; icon: typeof Waves }> = {
  swim: { label: 'Swim', color: 'var(--swim)', icon: Waves },
  bike: { label: 'Bike', color: 'var(--bike)', icon: Bike },
  run: { label: 'Run', color: 'var(--run)', icon: Footprints },
  tri: { label: 'Tri', color: 'var(--other)', icon: Timer },
  strength: { label: 'Strength', color: 'var(--strength)', icon: Dumbbell },
  recovery: { label: 'Recovery', color: 'var(--other)', icon: Flower2 },
  other: { label: 'Other', color: 'var(--other)', icon: Activity },
}
const TRI: Discipline[] = ['swim', 'bike', 'run', 'strength']
const RANGES = [[7, '7d'], [14, '14d'], [28, '28d']] as const
const ZONES = ['z1', 'z2', 'z3', 'z4', 'z5'] as const
// Sequential single-hue ramp for intensity (Z1 light → Z5 dark).
const ZONE_COLORS = ['#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#104281']

function ZoneBar({ w }: { w: Workout }) {
  const z = w.zone_minutes
  if (!z) return null
  const total = ZONES.reduce((a, k) => a + z[k], 0) || 1
  return (
    <div className="flex h-2 w-full gap-[2px]">
      {ZONES.map((k, i) => z[k] > 0 && (
        <Tip key={k} content={<span className="tabular">Zone {i + 1} · {z[k].toFixed(0)} min</span>}>
          <div className={i === 0 ? 'rounded-l-[3px]' : i === 4 ? 'rounded-r-[3px]' : ''}
               style={{ width: `${(z[k] / total) * 100}%`, background: ZONE_COLORS[i] }} />
        </Tip>
      ))}
    </div>
  )
}

function fmtDur(m: number | null) {
  if (m == null) return '—'
  return m >= 60 ? `${Math.floor(m / 60)}h ${String(Math.round(m % 60)).padStart(2, '0')}m` : `${Math.round(m)}m`
}

export function WorkoutLog({ days }: { days: StrainDay[] }) {
  const [tab, setTab] = useState<'all' | Discipline>('all')
  const [range, setRange] = useState<7 | 14 | 28>(7)
  const [expanded, setExpanded] = useState(false)
  const all = useMemo(() => mergeSplitSessions(days.slice(0, range).flatMap((d) => d.workouts).sort((a, b) => (b.start ?? '').localeCompare(a.start ?? ''))), [days, range])
  const training = all.filter((w) => w.discipline !== 'recovery')
  const shown = tab === 'all' ? training : all.filter((w) => w.discipline === tab)

  const totals = TRI.map((d) => {
    const ws = all.filter((w) => w.discipline === d)
    return { d, n: ws.length, min: ws.reduce((a, w) => a + (w.duration_min ?? 0), 0), km: ws.reduce((a, w) => a + (w.distance_km ?? 0), 0) }
  })
  const maxMin = Math.max(1, ...totals.map((t) => t.min))

  return (
    <Card title="Workouts" subtitle={`${training.length} sessions in the last ${range} days`} icon={<Timer className="size-4.5" />}
      action={
        <div className="flex gap-1">
          {RANGES.map(([r, l]) => (
            <button key={l} onClick={() => setRange(r)} className={`rounded-full border px-2.5 py-1 text-[12px] ${range === r ? 'border-[var(--ink-muted)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)]'}`}>{l}</button>
          ))}
        </div>
      }>
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {totals.map(({ d, n, min, km }) => {
            const M = META[d]
            return (
              <div key={d} className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
                <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-[var(--ink-muted)]">
                  <span className="size-2 rounded-full" style={{ background: M.color }} />{M.label}
                </div>
                <div className="font-display tabular mt-0.5 text-[22px] leading-tight font-semibold text-[var(--ink)]">{fmtDur(min)}</div>
                <div className="tabular text-[12px] text-[var(--ink-2)]">{n} {n === 1 ? 'session' : 'sessions'}{km > 0 ? ` · ${km.toFixed(1)} km` : ''}</div>
                <div className="mt-2 h-1.5 w-full rounded-full bg-[var(--surface)]">
                  <div className="h-full rounded-full" style={{ width: `${(min / maxMin) * 100}%`, background: M.color }} />
                </div>
              </div>
            )
          })}
        </div>

        <div className="flex justify-center overflow-x-auto">
          <ContinuousTabs
            tabs={[{ id: 'all', label: 'All' }, { id: 'swim', label: 'Swim' }, { id: 'bike', label: 'Bike' }, { id: 'run', label: 'Run' }, { id: 'strength', label: 'Strength' }]}
            defaultActiveId="all"
            onChange={(id) => setTab(id as typeof tab)}
          />
        </div>

        {shown.length === 0 ? (
          <p className="py-6 text-center text-sm text-[var(--ink-muted)]">No {tab === 'all' ? '' : META[tab as Discipline].label.toLowerCase() + ' '}sessions in the last {range} days.</p>
        ) : (
          <>
            <ActivitiesCard
              key={tab}
              defaultOpen
              headerIcon={(() => { const I = tab === 'all' ? Activity : META[tab as Discipline].icon; return <I className="size-6 text-[var(--ink-2)]" /> })()}
              title={tab === 'all' ? 'All sessions' : `${META[tab as Discipline].label} sessions`}
              subtitle={`${shown.length} logged`}
              activities={shown.slice(0, expanded ? 60 : 8).map((w) => {
                const M = META[w.discipline]
                const I = M.icon
                return {
                  icon: <I className="size-5" style={{ color: M.color }} />,
                  title: `${sportName(w.sport)}, ${fmtDur(w.duration_min)}`,
                  desc: [
                    w.distance_km && `${w.distance_km.toFixed(1)} km`,
                    w.avg_hr && `HR ${w.avg_hr} avg, ${w.max_hr} max`,
                    w.strain != null && `strain ${w.strain}`,
                    (w.parts ?? 1) > 1 && `${w.parts} recordings joined`,
                  ].filter(Boolean).join(' · '),
                  time: dayLabel(w.date),
                }
              })}
            />
            {shown.length > 8 && (
              <button onClick={() => setExpanded(!expanded)} className="self-center text-sm text-[var(--strain)] underline underline-offset-4">{expanded ? 'Show fewer' : `Show all ${Math.min(shown.length, 60)}`}</button>
            )}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between text-[11.5px] text-[var(--ink-muted)]">
                <span>Heart rate zones</span>
                <span className="flex gap-2">
                  {ZONES.map((z, i) => <span key={z} className="flex items-center gap-1"><span className="size-2 rounded-[2px]" style={{ background: ZONE_COLORS[i] }} />Z{i + 1}</span>)}
                </span>
              </div>
              {shown.slice(0, 5).map((w) => (
                <div key={w.id} className="grid grid-cols-[88px_1fr] items-center gap-3">
                  <span className="truncate text-[12px] text-[var(--ink-2)]">{dayLabel(w.date)} · {META[w.discipline].label}</span>
                  <ZoneBar w={w} />
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </Card>
  )
}
