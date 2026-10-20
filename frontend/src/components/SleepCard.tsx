import { Moon } from 'lucide-react'
import type { SleepReport } from '@/types'
import { Card, Metric, StatusPill, Tip, dayLabel, fmtH } from './ui'

const STAGES = [
  { key: 'deep_sws', label: 'Deep (SWS)', color: 'var(--stage-deep)' },
  { key: 'rem', label: 'REM', color: 'var(--stage-rem)' },
  { key: 'light', label: 'Light', color: 'var(--stage-light)' },
  { key: 'awake', label: 'Awake', color: 'var(--stage-awake)' },
] as const

export function SleepCard({ report }: { report: SleepReport }) {
  const s = report.sleep
  const debt = report.sleep_debt
  const rolling = debt.rolling_7d_h
  const debtZone = rolling == null ? null : rolling < 2 ? 'green' : rolling < 5 ? 'yellow' : 'red'
  const stages = s?.stages_h
  const total = stages ? STAGES.reduce((a, st) => a + (stages[st.key] ?? 0), 0) : 0
  const nights = [...debt.nights].reverse()
  const maxBal = Math.max(1, ...nights.map((n) => Math.abs(n.balance_h)))

  return (
    <Card
      title="Sleep & Debt"
      subtitle={s ? `Night ending ${report.date}` : 'No main sleep recorded yet'}
      icon={<Moon className="size-4.5" />}
      action={debtZone && <StatusPill zone={debtZone}>{rolling!.toFixed(1)} h debt · 7d</StatusPill>}
    >
      {!s ? (
        <p className="text-sm text-[var(--ink-muted)]">WHOOP hasn’t scored a sleep ending on this date.</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-2">
            <Metric label="Performance" value={s.performance_pct?.toFixed(0)} unit="%" />
            <Metric label="Efficiency" value={s.efficiency_pct?.toFixed(0)} unit="%" />
            <Metric label="Slept / need" value={`${fmtH(s.hours_asleep)}`} delta={`need ${fmtH(s.hours_needed)}`} />
            <Metric label="Awakenings" value={s.awakenings} delta={s.sleep_cycles != null ? `${s.sleep_cycles} cycles` : undefined} />
          </div>

          {stages && total > 0 && (
            <div>
              <div className="mb-1.5 text-[11.5px] text-[var(--ink-muted)]">Sleep stages · {fmtH(total)} in bed</div>
              <div className="flex h-3.5 w-full gap-[2px]">
                {STAGES.map((st, i) => {
                  const v = stages[st.key] ?? 0
                  if (!v) return null
                  return (
                    <Tip key={st.key} content={<span className="tabular">{st.label} · {fmtH(v)} · {((v / total) * 100).toFixed(0)}%</span>}>
                      <div
                        className={i === 0 ? 'rounded-l-[4px]' : i === STAGES.length - 1 ? 'rounded-r-[4px]' : ''}
                        style={{ width: `${(v / total) * 100}%`, background: st.color }}
                      />
                    </Tip>
                  )
                })}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                {STAGES.map((st) => (
                  <span key={st.key} className="tabular flex items-center gap-1.5 text-[12px] text-[var(--ink-2)]">
                    <span className="size-2.5 rounded-[3px]" style={{ background: st.color }} />
                    {st.label} <span className="text-[var(--ink-muted)]">{fmtH(stages[st.key])}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {nights.length > 0 && (
            <div>
              <div className="mb-1.5 flex justify-between text-[11.5px] text-[var(--ink-muted)]">
                <span>Nightly balance vs need</span>
                <span className="tabular">tonight’s shortfall {fmtH(debt.tonight_shortfall_h)}</span>
              </div>
              <div className="relative flex h-20 items-stretch gap-[2px]">
                <div className="absolute inset-x-0 top-1/2 h-px bg-[var(--grid)]" />
                {nights.map((n) => {
                  const hPct = (Math.abs(n.balance_h) / maxBal) * 50
                  const neg = n.balance_h < 0
                  return (
                    <Tip key={n.date} content={<span className="tabular">{dayLabel(n.date)} · slept {fmtH(n.asleep_h)} / need {fmtH(n.needed_h)} ({n.balance_h > 0 ? '+' : '−'}{fmtH(Math.abs(n.balance_h))})</span>}>
                      <div className="relative flex-1">
                        <div
                          className={`absolute left-1/2 w-full max-w-6 -translate-x-1/2 ${neg ? 'top-1/2 rounded-b-[4px]' : 'bottom-1/2 rounded-t-[4px]'}`}
                          style={{ height: `${hPct}%`, background: neg ? 'var(--serious)' : 'var(--stage-rem)' }}
                        />
                      </div>
                    </Tip>
                  )
                })}
              </div>
              <div className="mt-1 flex gap-[2px]">
                {nights.map((n) => <span key={n.date} className="flex-1 text-center text-[10.5px] text-[var(--ink-muted)]">{dayLabel(n.date).slice(0, 2)}</span>)}
              </div>
              <div className="mt-1.5 flex gap-4 text-[12px] text-[var(--ink-2)]">
                <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-[3px] bg-[var(--stage-rem)]" />Surplus</span>
                <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-[3px] bg-[var(--serious)]" />Shortfall</span>
                {debt.whoop_debt_component_h != null && <span className="ml-auto text-[var(--ink-muted)]">WHOOP debt in need: {fmtH(debt.whoop_debt_component_h)}</span>}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}
