import { CheckCircle2, Footprints, Info } from 'lucide-react'
import type { HistoryAnalytics } from '@/types'
import { Card, Tip } from './ui'

// Same Z1 light → Z5 dark ramp as the workout log.
const ZONE_COLORS = ['#9ec5f4', '#6da7ec', '#3987e5', '#256abf', '#104281']
const ZONE_RANGE = ['50–60', '60–70', '70–80', '80–90', '90–100']

const monthLabel = (m: string) => new Date(m + '-15T12:00:00').toLocaleDateString(undefined, { month: 'short', year: '2-digit' })

export function RunZonesCard({ zones, fromMonth }: { zones: HistoryAnalytics['run_zones']; fromMonth: string }) {
  const months = zones.months.filter((m) => m.month >= fromMonth)
  const target = zones.easy_target_pct
  const minutes = [0, 1, 2, 3, 4].map((i) => months.reduce((a, m) => a + m.minutes[i], 0))
  const total = minutes.reduce((a, b) => a + b, 0)
  const easy = total ? (100 * (minutes[0] + minutes[1])) / total : null
  const onTarget = easy != null && easy >= target

  return (
    <Card title="Run intensity" subtitle={`Time in HR zone (% of max HR) · ${months.reduce((a, m) => a + m.runs, 0)} runs in range`} icon={<Footprints className="size-4.5" />}>
      <div className="flex flex-col gap-4">
        <div className="flex items-start gap-3 rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
          {onTarget
            ? <CheckCircle2 className="mt-0.5 size-4 shrink-0" style={{ color: 'var(--good)' }} />
            : <Info className="mt-0.5 size-4 shrink-0" style={{ color: 'var(--serious)' }} />}
          <div className="text-[13px] text-[var(--ink-2)]">
            <span className="tabular text-[18px] font-semibold text-[var(--ink)]">{easy == null ? '—' : `${easy.toFixed(0)}%`}</span> easy (Z1–Z2) vs the {target}% target.{' '}
            {easy == null ? 'No run HR data in this range.' : onTarget ? 'Your easy running is where an endurance base needs it.' : `About ${(target - easy).toFixed(0)} points of Z3+ could move down to Z2.`}
          </div>
        </div>

        <div className="flex flex-col gap-1.5">
          {months.map((m) => (
            <div key={m.month} className="grid grid-cols-[52px_1fr_44px] items-center gap-2">
              <span className="text-[12px] text-[var(--ink-2)]">{monthLabel(m.month)}</span>
              <div className="relative flex h-3.5 w-full overflow-hidden rounded-[4px] bg-[var(--surface-2)]">
                {m.pct.map((p, i) => p > 0 && (
                  <Tip key={i} content={<span className="tabular">{monthLabel(m.month)} · Z{i + 1} ({ZONE_RANGE[i]}%) · {m.minutes[i].toFixed(0)} min · {p}%</span>}>
                    <div style={{ width: `${p}%`, background: ZONE_COLORS[i] }} />
                  </Tip>
                ))}
                <div className="pointer-events-none absolute inset-y-0 w-[2px] bg-[var(--ink)]" style={{ left: `${target}%` }} />
              </div>
              <span className="tabular text-right text-[12px] text-[var(--ink-2)]">{m.easy_pct?.toFixed(0)}%</span>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-3 text-[11.5px] text-[var(--ink-2)]">
          {ZONE_COLORS.map((c, i) => <span key={c} className="flex items-center gap-1"><span className="size-2 rounded-[2px]" style={{ background: c }} />Z{i + 1}</span>)}
          <span className="flex items-center gap-1"><span className="h-3 w-[2px] bg-[var(--ink)]" />{target}% easy target</span>
          <span className="ml-auto">right column: easy share</span>
        </div>
      </div>
    </Card>
  )
}
