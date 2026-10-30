import { Flame } from 'lucide-react'
import type { Recovery, StrainDay } from '@/types'
import { ArcGauge, Card, StatusPill, Tip, dayLabel } from './ui'

export function StrainDial({ today, days, rec }: { today: StrainDay | undefined; days: StrainDay[]; rec: Recovery }) {
  const target = rec.target_strain ?? today?.target_strain ?? null
  const strain = today?.day_strain ?? null
  const status = strain == null || !target ? null
    : strain < target.low ? { zone: 'yellow' as const, text: `${(target.low - strain).toFixed(1)} to target` }
    : strain <= target.high ? { zone: 'green' as const, text: 'In target band' }
    : { zone: 'red' as const, text: `${(strain - target.high).toFixed(1)} over target` }
  const week = [...days].reverse()
  const max = 21
  return (
    <Card
      title="Strain vs Recovery"
      subtitle={today?.in_progress ? 'Today · cycle in progress' : today?.date}
      icon={<Flame className="size-4.5" />}
      action={status && <StatusPill zone={status.zone}>{status.text}</StatusPill>}
    >
      <div className="flex flex-col items-center gap-4">
        <ArcGauge
          value={strain}
          max={max}
          color="var(--strain)"
          band={target ? { low: target.low, high: target.high, color: 'var(--strain-band)' } : undefined}
          label={`Day strain ${strain ?? 'n/a'} of 21`}
        >
          <div className="font-display tabular text-[52px] leading-none font-bold text-[var(--ink)]">{strain?.toFixed(1) ?? '—'}</div>
          <div className="mt-1 text-[12px] text-[var(--ink-muted)]">day strain / 21</div>
        </ArcGauge>
        {target && (
          <div className="w-full rounded-xl bg-[var(--surface-2)] px-3 py-2.5 text-[13px] text-[var(--ink-2)]">
            <div className="mb-0.5 flex items-center gap-2 text-[12.5px] font-medium text-[var(--ink-muted)]">
              <span className="inline-block h-2 w-4 rounded-sm" style={{ background: 'var(--strain-band)' }} /> Target {target.low}–{target.high}
              <Tip content="Estimated from today’s recovery. WHOOP’s in-app Strain Coach target isn’t in the API.">
                <span className="cursor-help">(estimate)</span>
              </Tip>
            </div>
            {target.guidance}
          </div>
        )}
        <div className="w-full">
          <div className="mb-1.5 flex items-center justify-between text-[12.5px] text-[var(--ink-muted)]">
            <span>Day strain, last 7 days</span>
            {target && <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-3 rounded-[2px]" style={{ background: 'var(--strain-band)', opacity: 0.45 }} />today’s target</span>}
          </div>
          <div className="relative h-28">
            {target && (
              <div className="absolute inset-x-0 rounded-[3px]" aria-hidden
                style={{ bottom: `calc(${(target.low / max) * 100}% * 0.78 + 18px)`, height: `calc(${((target.high - target.low) / max) * 100}% * 0.78)`, background: 'var(--strain-band)', opacity: 0.3 }} />
            )}
            <div className="relative flex h-full items-end gap-[2px]">
              {week.map((d) => {
                const v = d.day_strain ?? 0
                return (
                  <Tip key={d.date} content={
                    <span className="tabular">{dayLabel(d.date)} · strain {d.day_strain ?? '—'} · recovery {d.recovery_score ?? '—'}%{d.workouts.length ? ` · ${d.workouts.length} workout${d.workouts.length > 1 ? 's' : ''}` : ''}</span>
                  }>
                    <div className="flex h-full flex-1 flex-col items-center justify-end gap-1">
                      <div className="flex h-[78%] w-full flex-col items-center justify-end">
                        <span className="tabular mb-0.5 text-[11.5px] text-[var(--ink-2)]">{d.day_strain != null ? d.day_strain.toFixed(1) : ''}</span>
                        <div
                          className="w-full max-w-7 rounded-t-[4px]"
                          style={{ height: `${(v / max) * 100}%`, background: 'var(--strain)', opacity: d.in_progress ? 0.55 : 1 }}
                        />
                      </div>
                      <span className="h-[14px] text-[11.5px] leading-[14px] text-[var(--ink-muted)]">{dayLabel(d.date).slice(0, 2)}</span>
                    </div>
                  </Tip>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </Card>
  )
}
