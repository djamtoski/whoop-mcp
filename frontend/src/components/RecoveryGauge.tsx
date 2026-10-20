import { HeartPulse } from 'lucide-react'
import type { Recovery, TrendPoint } from '@/types'
import { ArcGauge, Card, Metric, StatusPill, Tip, dayLabel, signed, zoneColor, zoneLabel } from './ui'

function HrvSpark({ series, baseline }: { series: TrendPoint[]; baseline: number | null }) {
  const pts = series.filter((p) => p.hrv != null)
  if (pts.length < 2) return null
  const w = 280, h = 64, pad = 6
  const vals = pts.map((p) => p.hrv as number).concat(baseline != null ? [baseline] : [])
  const lo = Math.min(...vals) * 0.92, hi = Math.max(...vals) * 1.05
  const x = (i: number) => pad + (i / (series.length - 1)) * (w - pad * 2)
  const y = (v: number) => h - pad - ((v - lo) / (hi - lo)) * (h - pad * 2)
  const idx = (d: string) => series.findIndex((s) => s.date === d)
  const line = pts.map((p, i) => `${i ? 'L' : 'M'} ${x(idx(p.date))} ${y(p.hrv as number)}`).join(' ')
  const last = pts[pts.length - 1]
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-[11.5px] text-[var(--ink-muted)]">
        <span>HRV · last 7 days</span>
        {baseline != null && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block h-px w-3 bg-[var(--ink-muted)]" /> 28-day baseline {baseline.toFixed(0)} ms
          </span>
        )}
      </div>
      <svg viewBox={`0 0 ${w} ${h}`} className="h-16 w-full overflow-visible" role="img" aria-label="HRV last 7 days">
        {baseline != null && <line x1={pad} x2={w - pad} y1={y(baseline)} y2={y(baseline)} stroke="var(--ink-muted)" strokeWidth={1} />}
        <path d={line} fill="none" stroke="var(--strain)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        {pts.map((p) => (
          <Tip key={p.date} content={<span className="tabular">{dayLabel(p.date)} · HRV {p.hrv?.toFixed(0)} ms · RHR {p.rhr ?? '—'}</span>}>
            <g className="cursor-default">
              <circle cx={x(idx(p.date))} cy={y(p.hrv as number)} r={11} fill="transparent" />
              <circle cx={x(idx(p.date))} cy={y(p.hrv as number)} r={p === last ? 4.5 : 3.5} fill="var(--strain)" stroke="var(--surface)" strokeWidth={2} />
            </g>
          </Tip>
        ))}
      </svg>
    </div>
  )
}

export function RecoveryGauge({ rec, series, hrvBaseline28 }: { rec: Recovery; series: TrendPoint[]; hrvBaseline28: number | null }) {
  const zone = rec.readiness_zone ?? null
  const color = zone ? zoneColor[zone] : 'var(--ink-muted)'
  return (
    <Card
      title="Recovery & Readiness"
      subtitle={rec.available ? `${rec.stale ? 'Yesterday · ' : ''}${rec.date}` : 'Awaiting today’s score'}
      icon={<HeartPulse className="size-4.5" />}
      action={zone && <StatusPill zone={zone}>{zoneLabel[zone]}</StatusPill>}
    >
      {!rec.available ? (
        <p className="text-sm text-[var(--ink-muted)]">{rec.message}</p>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col items-center gap-4">
            <ArcGauge value={rec.recovery_score} max={100} color={color} label={`Recovery ${rec.recovery_score}%`}>
              <div className="tabular text-[44px] leading-none font-semibold tracking-tight text-[var(--ink)]">
                {rec.recovery_score ?? '—'}<span className="text-[20px] text-[var(--ink-muted)]">%</span>
              </div>
              <div className="mt-1 text-[12px] text-[var(--ink-muted)]">recovery</div>
            </ArcGauge>
            <div className="grid w-full grid-cols-2 gap-2 sm:grid-cols-3">
              <Metric label="HRV" value={rec.hrv_rmssd_ms?.toFixed(0)} unit="ms"
                delta={rec.hrv_vs_baseline_pct != null ? `${signed(rec.hrv_vs_baseline_pct, 0, '%')} vs 7d` : undefined}
                hint={`7-day baseline ${rec.hrv_baseline_7d_ms?.toFixed(0) ?? '—'} ms`} />
              <Metric label="Resting HR" value={rec.resting_hr} unit="bpm"
                delta={rec.rhr_vs_baseline_bpm != null ? `${signed(rec.rhr_vs_baseline_bpm, 0)} bpm vs 7d` : undefined} />
              <Metric label="Stress (est.)" value={rec.stress_estimate?.score.toFixed(1)} unit="/ 3"
                delta={rec.stress_estimate?.level}
                hint="Derived from HRV & RHR deviation vs your 7-day baseline — not WHOOP's Stress Monitor." />
              <Metric label="SpO₂" value={rec.spo2_pct?.toFixed(1)} unit="%" />
              <Metric label="Skin temp" value={rec.skin_temp_c?.toFixed(1)} unit="°C"
                delta={rec.skin_temp_deviation_c != null ? `${signed(rec.skin_temp_deviation_c, 1, '°')} vs 7d` : undefined} />
              <Metric label="Resp. rate" value={rec.respiratory_rate?.toFixed(1)} unit="rpm"
                delta={rec.respiratory_rate_deviation != null ? `${signed(rec.respiratory_rate_deviation, 1)} vs 7d` : undefined} />
            </div>
          </div>
          <HrvSpark series={series} baseline={hrvBaseline28} />
          {rec.user_calibrating && <p className="text-[12px] text-[var(--ink-muted)]">WHOOP is still calibrating your baselines.</p>}
        </div>
      )}
    </Card>
  )
}
