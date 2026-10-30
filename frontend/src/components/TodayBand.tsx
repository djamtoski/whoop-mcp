import { Bike, CheckCircle2, Dumbbell, Footprints, Waves } from 'lucide-react'
import { motion } from 'motion/react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { usePlan } from '@/api'
import { sportName } from '@/lib/sports'
import type { Insight, PlanSession, Summary, TrainingDiscipline, Zone } from '@/types'
import { deviationTone, signed, toneColor, zoneColor } from './ui'

const SPORT:Record<TrainingDiscipline, { label: string; color: string; icon: typeof Waves }> = {
  swim: { label: 'Swim', color: 'var(--swim)', icon: Waves },
  bike: { label: 'Bike', color: 'var(--bike)', icon: Bike },
  run: { label: 'Run', color: 'var(--run)', icon: Footprints },
  strength: { label: 'Strength', color: 'var(--strength)', icon: Dumbbell },
}

const VERDICT: Record<Zone, { headline: string; advice: string }> = {
  green: { headline: 'Ready to train', advice: 'Quality sessions are on today.' },
  yellow: { headline: 'Train easy', advice: 'Keep it in zone 2 and save intensity for a green day.' },
  red: { headline: 'Recovery day', advice: 'Walk, mobility and sleep. Skip anything hard.' },
}

function Stat({ label, value, note, color }: { label: string; value: string; note?: string | null; color?: string }) {
  return (
    <div className="min-w-0">
      <div className="text-[12.5px] text-[var(--ink-muted)]">{label}</div>
      <div className="font-display tabular text-[22px] leading-tight font-semibold text-[var(--ink)]">{value}</div>
      {note && <div className="tabular text-[12px] leading-snug" style={{ color: color ?? 'var(--ink-2)' }}>{note}</div>}
    </div>
  )
}

function Verdict({ data }: { data: Summary }) {
  const rec = data.recovery
  const zone = rec.readiness_zone ?? null
  const color = zone ? zoneColor[zone] : 'var(--ink-muted)'
  const b = data.trends.baselines_28d
  const hrvDev = rec.hrv_rmssd_ms != null && b.hrv ? (100 * (rec.hrv_rmssd_ms - b.hrv)) / b.hrv : null
  const rhrDev = rec.resting_hr != null && b.rhr != null ? rec.resting_hr - b.rhr : null
  const today = data.strain.days[0]
  const target = rec.target_strain ?? today?.target_strain
  const sleep = data.sleep.sleep

  return (
    <div className="flex min-w-0 flex-col gap-4">
      <div className="flex items-end gap-4">
        <div className="font-display tabular text-[84px] leading-[0.85] font-bold" style={{ color }}>
          {rec.recovery_score ?? '—'}<span className="text-[36px]">%</span>
        </div>
        <div className="min-w-0 pb-1">
          <div className="font-display text-[28px] leading-none font-semibold text-[var(--ink)]">{zone ? VERDICT[zone].headline : 'Awaiting recovery'}</div>
          <p className="mt-1.5 text-[14px] text-[var(--ink-2)]">{zone ? VERDICT[zone].advice : rec.message}</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4 lg:grid-cols-2 2xl:grid-cols-4">
        <Stat label="HRV" value={rec.hrv_rmssd_ms != null ? `${rec.hrv_rmssd_ms.toFixed(0)} ms` : '—'}
          note={hrvDev != null ? `${signed(hrvDev, 0, '%')} vs 28-day` : null} color={toneColor[deviationTone(hrvDev, 5, 'up')]} />
        <Stat label="Resting HR" value={rec.resting_hr != null ? `${rec.resting_hr} bpm` : '—'}
          note={rhrDev != null ? `${signed(rhrDev, 0)} vs 28-day` : null} color={toneColor[deviationTone(rhrDev, 2, 'down')]} />
        <Stat label="Sleep" value={sleep?.performance_pct != null ? `${sleep.performance_pct}%` : '—'}
          note={sleep?.hours_asleep != null ? `${sleep.hours_asleep.toFixed(1)} h slept, ${sleep.hours_needed?.toFixed(1) ?? '—'} h needed` : null} />
        <Stat label="Strain so far" value={today?.day_strain?.toFixed(1) ?? '—'}
          note={target ? `target ${target.low}–${target.high}` : null} />
      </div>
    </div>
  )
}

function SessionRow({ s }: { s: PlanSession }) {
  const M = SPORT[s.sport]
  const I = M.icon
  return (
    <li className="flex gap-3 rounded-xl bg-[var(--surface-2)] py-2.5 pr-3 pl-3" style={{ boxShadow: `inset 3px 0 0 ${M.color}` }}>
      <I className="mt-0.5 size-4 shrink-0" style={{ color: M.color }} aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="truncate text-[14.5px] font-semibold text-[var(--ink)]">{M.label}, {s.kind}</span>
          {s.done
            ? <span className="flex shrink-0 items-center gap-1 text-[12.5px] text-[var(--good)]"><CheckCircle2 className="size-3.5" aria-hidden />Done{s.done_minutes != null ? `, ${Math.round(s.done_minutes)} min` : ''}</span>
            : <span className="tabular shrink-0 text-[12.5px] text-[var(--ink-muted)]">{s.minutes} min · {s.intensity}</span>}
        </div>
        {!s.done && <p className="mt-0.5 text-[13px] leading-snug text-[var(--ink-2)]">{s.adjustment?.note ?? s.description}</p>}
      </div>
    </li>
  )
}

function TodaySessions() {
  const { data, error } = usePlan()
  if (error) return <p className="text-[13px] text-[var(--ink-muted)]">Today’s plan didn’t load. {error}</p>
  if (!data) {
    return (
      <ul className="flex flex-col gap-2" aria-busy="true" aria-label="Loading today’s plan…">
        {[0, 1].map((i) => <li key={i} className="h-[62px] animate-pulse rounded-xl bg-[var(--surface-2)] motion-reduce:animate-none" />)}
      </ul>
    )
  }
  const day = data.week.days.find((d) => d.date === data.today)
  if (!day) return <p className="text-[13px] text-[var(--ink-muted)]">Today isn’t in this week’s plan.</p>
  return (
    <div className="flex flex-col gap-2">
      {day.rest
        ? <p className="rounded-xl bg-[var(--surface-2)] px-3 py-3 text-[14px] text-[var(--ink-2)]">Rest day. Walk, stretch, get to bed early.</p>
        : <ul className="flex flex-col gap-2">{day.sessions.map((s, i) => <SessionRow key={i} s={s} />)}</ul>}
      {!!day.extra?.length && (
        <p className="text-[12.5px] text-[var(--ink-muted)]">
          Also logged: {day.extra.map((x) => `${sportName(x.sport).toLowerCase()} ${Math.round(x.minutes ?? 0)} min`).join(', ')}
        </p>
      )}
    </div>
  )
}

function LatestNote({ item }: { item: Insight | undefined }) {
  if (!item) {
    return <p className="text-[13.5px] text-[var(--ink-muted)]">No coaching note yet. Ask Claude to look at today’s data.</p>
  }
  return (
    <div className="flex min-h-0 flex-col gap-2">
      <h3 className="text-[15px] leading-snug font-semibold text-[var(--ink)]">{item.title ?? 'Latest coaching note'}</h3>
      <div className="prose-coach line-clamp-6"><Markdown remarkPlugins={[remarkGfm]}>{item.markdown}</Markdown></div>
      <a href="#coach" className="self-start text-[13px] text-[var(--strain)] underline underline-offset-4 hover:text-[var(--ink)]">Read all notes</a>
    </div>
  )
}

/** The first thing on the page: how recovered you are, what to do about it, and Claude's latest read. */
export function TodayBand({ data, latest }: { data: Summary; latest: Insight | undefined }) {
  const zone = data.recovery.readiness_zone
  return (
    <motion.section
      aria-label="Today"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: 'spring', bounce: 0, duration: 0.5 }}
      className="grid grid-cols-1 gap-6 rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-5 lg:grid-cols-[1.25fr_1fr_1fr] lg:p-6"
      style={{ boxShadow: zone ? `inset 0 3px 0 ${zoneColor[zone]}` : undefined }}
    >
      <Verdict data={data} />
      <div className="flex min-w-0 flex-col gap-2 lg:border-l lg:border-[var(--border)] lg:pl-6">
        <h2 className="font-display text-[18px] font-semibold text-[var(--ink)]">Today’s plan</h2>
        <TodaySessions />
      </div>
      <div className="flex min-w-0 flex-col gap-2 lg:border-l lg:border-[var(--border)] lg:pl-6">
        <h2 className="font-display text-[18px] font-semibold text-[var(--ink)]">Coach</h2>
        <LatestNote item={latest} />
      </div>
    </motion.section>
  )
}
