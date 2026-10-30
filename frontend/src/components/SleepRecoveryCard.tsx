import { Moon } from 'lucide-react'
import { useState } from 'react'
import type { HistoryAnalytics } from '@/types'
import { Card } from './ui'

const zoneColor = (r: number) => (r >= 67 ? 'var(--good)' : r >= 34 ? 'var(--warning)' : 'var(--critical)')
const shortDate = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
const bucketLabel = (b: { low: number; high: number | null }) => (b.low === 0 ? `< ${b.high} h` : b.high == null ? `≥ ${b.low} h` : `${b.low}–${b.high} h`)

export function SleepRecoveryCard({ data, from }: { data: HistoryAnalytics['sleep_recovery']; from: string }) {
  const [hover, setHover] = useState<number | null>(null)
  const points = data.points.filter((p) => p.date >= from)
  const W = 520, H = 220, padL = 32, padR = 8, padT = 8, padB = 24
  const xMin = 4, xMax = 11
  const x = (h: number) => padL + ((Math.min(xMax, Math.max(xMin, h)) - xMin) / (xMax - xMin)) * (W - padL - padR)
  const y = (r: number) => padT + (1 - r / 100) * (H - padT - padB)
  const bestBucket = Math.max(...data.buckets.map((b) => b.avg_recovery ?? 0))
  const hp = hover != null ? points[hover] : null

  return (
    <Card title="Sleep vs recovery" subtitle={data.target_h != null ? `Your recovery levels off from about ${data.target_h} h of sleep` : 'Not enough nights yet'} icon={<Moon className="size-4.5" />}>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-[3fr_2fr]">
        <div className="relative">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full" onMouseLeave={() => setHover(null)}>
            {[0, 34, 67, 100].map((t) => (
              <g key={t}>
                <line x1={padL} x2={W - padR} y1={y(t)} y2={y(t)} stroke="var(--grid)" />
                <text x={padL - 6} y={y(t) + 4} textAnchor="end" fontSize={11} fill="var(--ink-muted)">{t}</text>
              </g>
            ))}
            {[4, 5, 6, 7, 8, 9, 10, 11].map((h) => (
              <text key={h} x={x(h)} y={H - 6} textAnchor="middle" fontSize={11} fill="var(--ink-muted)">{h}h</text>
            ))}
            {data.target_h != null && (
              <g>
                <line x1={x(data.target_h)} x2={x(data.target_h)} y1={padT} y2={H - padB} stroke="var(--ink)" strokeDasharray="4 4" />
                <text x={x(data.target_h) + 4} y={padT + 10} fontSize={11} fill="var(--ink-2)">target {data.target_h} h</text>
              </g>
            )}
            {points.map((p, i) => (
              <circle key={p.date} cx={x(p.sleep_h)} cy={y(p.recovery)} r={hover === i ? 5 : 3} fill={zoneColor(p.recovery)} opacity={0.75}
                onMouseEnter={() => setHover(i)} />
            ))}
          </svg>
          {hp && (
            <div className="tabular pointer-events-none absolute top-0 right-0 rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1.5 text-[12px] text-[var(--ink)] shadow-lg">
              {shortDate(hp.date)} · {hp.sleep_h.toFixed(1)} h asleep → {hp.recovery}% recovery
            </div>
          )}
          <p className="mt-1 text-[11.5px] text-[var(--ink-muted)]">Each dot is one night in range · correlation r = {data.correlation ?? '—'}</p>
        </div>

        <div className="flex flex-col gap-2">
          <div className="text-[12.5px] font-medium text-[var(--ink-muted)]">Average recovery by sleep · whole history</div>
          {data.buckets.map((b) => (
            <div key={b.low} className="grid grid-cols-[64px_1fr_40px] items-center gap-2 text-[12.5px]">
              <span className="text-[var(--ink-2)]">{bucketLabel(b)}</span>
              <div className="h-3 rounded-[4px] bg-[var(--surface-2)]">
                {b.avg_recovery != null && (
                  <div className="h-full rounded-[4px]" style={{ width: `${b.avg_recovery}%`, background: zoneColor(b.avg_recovery), opacity: b.avg_recovery === bestBucket ? 1 : 0.7 }} />
                )}
              </div>
              <span className="tabular text-right text-[var(--ink)]">{b.avg_recovery?.toFixed(0) ?? '—'}%</span>
              <span />
              <span className="-mt-1 text-[11px] text-[var(--ink-muted)]">{b.nights} nights</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  )
}
