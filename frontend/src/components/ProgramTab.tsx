import { Bike, Calculator, CheckCircle2, ChevronLeft, ChevronRight, Dumbbell, Flag, Footprints, Moon, Settings2, Trophy, Waves } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { useProgram } from '@/api'
import { fmtKg, pct1rm, roundTo, e1rm as estimate } from '@/lib/load'
import { setPrefill } from '@/lib/strengthDraft'
import type { ProgramExercise, ProgramResponse, ProgramSettings, ProgramSport, ProgramWeek, ProgramWorkout } from '@/types'
import { Card, zoneColor } from './ui'

const SPORT: Record<ProgramSport, { label: string; color: string; icon: typeof Waves }> = {
  swim: { label: 'Swim', color: 'var(--swim)', icon: Waves },
  bike: { label: 'Bike', color: 'var(--bike)', icon: Bike },
  run: { label: 'Run', color: 'var(--run)', icon: Footprints },
  strength: { label: 'Strength', color: 'var(--strength)', icon: Dumbbell },
  rest: { label: 'Rest', color: 'var(--other)', icon: Moon },
  race: { label: 'Race', color: 'var(--good)', icon: Trophy },
}
// One hue ramp for the season's phases, light to dark as the race gets closer.
const PHASE_SHADE: Record<string, number> = { base1: 35, base2: 52, build: 70, peak: 90, taper: 58, race: 100 }
const phaseColor = (key: string) => (key === 'race' ? 'var(--good)' : `color-mix(in srgb, var(--strain) ${PHASE_SHADE[key] ?? 40}%, var(--surface-2))`)

const weekdayFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short' })
const rangeFmt = new Intl.DateTimeFormat(undefined, { day: 'numeric', month: 'short' })
const longFmt = new Intl.DateTimeFormat(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
const at = (iso: string) => new Date(iso + 'T12:00:00')
const fmtMin = (m: number) => (m >= 60 ? `${Math.floor(m / 60)} h${m % 60 ? ` ${String(m % 60).padStart(2, '0')}` : ''}` : `${m} min`)
const input = 'tabular w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-[14px] text-[var(--ink)] outline-none focus-visible:border-[var(--ink-muted)]'

function loadText(e: ProgramExercise) {
  if (!e.load) return null
  if (e.load.per === 'added') return e.load.note === 'bodyweight' ? 'bodyweight' : `+${fmtKg(e.load.kg)}`
  return e.load.per === 'hand' ? `${fmtKg(e.load.kg)} per hand` : fmtKg(e.load.kg)
}

function sessionDraft(date: string, w: ProgramWorkout) {
  const blocks = (w.exercises ?? [])
    .filter((e) => e.exercise_id != null && ['main', 'accessory', 'core'].includes(e.kind))
    .map((e) => ({
      exercise_id: e.exercise_id as number,
      sets: Array.from({ length: e.sets }, () => ({
        reps: String(e.reps_n ?? (parseInt(e.reps, 10) || '')), weight_kg: e.load ? String(e.load.kg) : '', rpe: e.rpe != null ? String(e.rpe) : '', warmup: false,
      })),
    }))
  return { date, whoop_workout_id: '', notes: `${w.name} (week program)`, blocks }
}

// --------------------------------------------------------------------------- season header

function Timeline({ data, selected, onPick }: { data: ProgramResponse; selected: number; onPick: (n: number) => void }) {
  const { weeks, phases } = data.program
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-9 items-stretch gap-[2px]" role="list" aria-label="Season weeks">
        {weeks.map((w) => {
          const current = w.weekNumber === data.current_week
          const isSelected = w.weekNumber === selected
          return (
            <button key={w.weekNumber} role="listitem" onClick={() => onPick(w.weekNumber)}
              aria-label={`Week ${w.weekNumber}, ${w.phase}${w.isRecoveryWeek ? ', recovery week' : ''}${current ? ', this week' : ''}`}
              aria-pressed={isSelected}
              className="relative min-w-0 flex-1 rounded-[3px] focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none"
              style={{ background: w.tuneup ? 'var(--strain)' : phaseColor(w.phaseKey), opacity: w.isRecoveryWeek ? 0.45 : 1, outline: isSelected ? '2px solid var(--ink)' : undefined, outlineOffset: 1 }}>
              {current && <span className="absolute -bottom-2.5 left-1/2 size-1.5 -translate-x-1/2 rounded-full bg-[var(--strain)]" aria-hidden />}
            </button>
          )
        })}
      </div>
      <div className="mt-1.5 flex gap-[2px] text-[12px] text-[var(--ink-muted)]">
        {phases.map((ph) => (
          <span key={ph.key} className="min-w-0 truncate" style={{ flex: ph.endWeek - ph.startWeek + 1 }}>{ph.name}</span>
        ))}
      </div>
    </div>
  )
}

function SettingsForm({ settings, onSaved }: { settings: ProgramSettings; onSaved: () => void }) {
  const [s, setS] = useState(settings)
  const [error, setError] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const set = <K extends keyof ProgramSettings>(k: K, v: ProgramSettings[K]) => setS({ ...s, [k]: v })
  const save = async () => {
    setError(null)
    setSaving(true)
    try {
      const r = await fetch('/api/program/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(s) })
      const body = await r.json().catch(() => ({}))
      if (!r.ok) return setError(typeof body.detail === 'string' ? body.detail : 'Invalid settings.')
      onSaved()
    } finally {
      setSaving(false)
    }
  }
  const field = 'flex flex-col gap-1 text-[12.5px] text-[var(--ink-muted)]'
  return (
    <div className="flex flex-col gap-3 rounded-xl bg-[var(--surface-2)] p-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <label className={`${field} col-span-2`}>Race<input name="race_name" autoComplete="off" value={s.race_name} onChange={(e) => set('race_name', e.target.value)} className={input} /></label>
        <label className={field}>Race date<input name="race_date" type="date" value={s.race_date} onChange={(e) => set('race_date', e.target.value)} className={input} /></label>
        <label className={field}>Start (Monday)<input name="start_date" type="date" value={s.start_date} onChange={(e) => set('start_date', e.target.value)} className={input} /></label>
        <label className={field}>Base hours / week<input name="weekly_hours" type="number" inputMode="decimal" min={4} max={15} step={0.5} value={s.weekly_hours} onChange={(e) => set('weekly_hours', Number(e.target.value))} className={input} /></label>
        <label className={field}>Bike
          <select name="bike" value={s.bike} onChange={(e) => set('bike', e.target.value as ProgramSettings['bike'])} className={`${input} bg-[var(--surface)]`}>
            <option value="gym">Gym bike</option><option value="road">Road bike</option>
          </select>
        </label>
        <label className={field}>Run LTHR (bpm)<input name="run_lthr" type="number" inputMode="numeric" placeholder="from 30 min test…" value={s.run_lthr ?? ''} onChange={(e) => set('run_lthr', e.target.value ? Number(e.target.value) : null)} className={input} /></label>
        <label className={field}>Bike LTHR (bpm)<input name="bike_lthr" type="number" inputMode="numeric" placeholder="from 20 min test…" value={s.bike_lthr ?? ''} onChange={(e) => set('bike_lthr', e.target.value ? Number(e.target.value) : null)} className={input} /></label>
        <label className={field}>Swim CSS (per 100 m)<input name="css" autoComplete="off" placeholder="e.g. 1:55…" value={s.css ?? ''} onChange={(e) => set('css', e.target.value || null)} className={input} /></label>
        <label className={`${field} col-span-2`}>Tune-up half marathon<input name="tuneup_name" autoComplete="off" value={s.tuneup_name} onChange={(e) => set('tuneup_name', e.target.value)} className={input} /></label>
        <label className={field}>Half marathon date<input name="tuneup_date" type="date" value={s.tuneup_date ?? ''} onChange={(e) => set('tuneup_date', e.target.value || null)} className={input} /></label>
      </div>
      <p className="text-[12px] text-[var(--ink-muted)]">The 5 weeks up to the half marathon run-focused: 5 runs, 2 swims, no bike. Clear the date to go back to the triathlon plan.</p>
      {error && <p role="alert" className="text-[13px] text-[var(--critical)]">{error}</p>}
      <button onClick={save} disabled={saving} className="self-start rounded-full bg-[var(--ink)] px-4 py-1.5 text-[14px] font-medium text-[var(--surface)] disabled:opacity-60">{saving ? 'Saving…' : 'Save program settings'}</button>
    </div>
  )
}

function SeasonHeader({ data, selected, onPick, reload }: { data: ProgramResponse; selected: number; onPick: (n: number) => void; reload: () => void }) {
  const [open, setOpen] = useState(false)
  const { meta, phases, zones } = data.program
  const cur = data.current_week
  const phase = phases.find((p) => cur != null && cur >= p.startWeek && cur <= p.endWeek)
  const weeksLeft = cur != null ? meta.totalWeeks - cur : meta.totalWeeks
  return (
    <Card title={meta.event} subtitle={`Starts ${longFmt.format(at(meta.planStartDate))} · race ${longFmt.format(at(meta.eventDate))} · ${weeksLeft} weeks to go`} icon={<Flag className="size-4.5" />}
      action={<button onClick={() => setOpen(!open)} aria-expanded={open} className="flex items-center gap-1 rounded-full border border-[var(--border)] px-2.5 py-1 text-[13px] text-[var(--ink-2)] hover:text-[var(--ink)]"><Settings2 className="size-3.5" aria-hidden />{open ? 'Close' : 'Edit program'}</button>}>
      <div className="flex flex-col gap-4">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-2">
          <div>
            <div className="text-[12.5px] text-[var(--ink-muted)]">{cur ? 'Now' : 'Week 1 is tests and calibration'}</div>
            <div className="font-display text-[30px] leading-none font-bold text-[var(--ink)]">
              {cur ? <>Week {cur}<span className="text-[18px] font-semibold text-[var(--ink-muted)]"> of {meta.totalWeeks}</span></> : `Starts ${longFmt.format(at(meta.planStartDate))}`}
            </div>
          </div>
          {phase && <p className="max-w-xl text-[14px] text-[var(--ink-2)]"><span className="font-semibold text-[var(--ink)]">{phase.name}.</span> {phase.focus}</p>}
        </div>
        <Timeline data={data} selected={selected} onPick={onPick} />
        <div className="grid grid-cols-1 gap-2 text-[13px] sm:grid-cols-3">
          {([['run', 'Run'], ['bike', 'Bike']] as const).map(([k, label]) => {
            const z = zones[k].hr
            return (
              <div key={k} className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
                <div className="flex items-baseline justify-between"><span className="font-medium text-[var(--ink)]">{label} zones</span><span className="text-[12px] text-[var(--ink-muted)]">LTHR {z.lthr}{z.estimated ? ' (estimate)' : ''}</span></div>
                <div className="tabular mt-1 text-[12.5px] text-[var(--ink-2)]">Z2 {z.zones[1].hrLow}–{z.zones[1].hrHigh} · Z3 {z.zones[2].hrLow}–{z.zones[2].hrHigh} · Z4 {z.zones[3].hrLow}–{z.zones[3].hrHigh}</div>
              </div>
            )
          })}
          <div className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
            <div className="flex items-baseline justify-between"><span className="font-medium text-[var(--ink)]">Swim</span><span className="text-[12px] text-[var(--ink-muted)]">{zones.swim.css ? `CSS ${zones.swim.css}/100 m` : 'CSS not tested'}</span></div>
            <div className="tabular mt-1 text-[12.5px] text-[var(--ink-2)]">
              {zones.swim.zones ? `Z2 ${zones.swim.zones[1].pace} · CSS ${zones.swim.zones[3].pace}` : 'Do the week-1 CSS test, then enter it in settings.'}
            </div>
          </div>
        </div>
        {(zones.run.hr.estimated || zones.bike.hr.estimated || zones.swim.estimated) && (
          <p className="text-[13px] text-[var(--ink-muted)]">Zones are estimated from your max HR until you enter the week-1 test results in settings.</p>
        )}
        {open && <SettingsForm settings={data.settings} onSaved={() => { setOpen(false); reload() }} />}
      </div>
    </Card>
  )
}

// --------------------------------------------------------------------------- one week

function Parts({ text }: { text: string }) {
  return (
    <ol className="flex flex-col gap-1.5">
      {text.split('\n').map((line, i) => {
        const [time, ...rest] = line.split(' · ')
        return rest.length ? (
          <li key={i} className="grid grid-cols-[72px_1fr] gap-3 text-[14.5px] leading-snug">
            <span className="tabular text-[var(--ink-muted)]">{time}</span><span className="text-[var(--ink)]">{rest.join(' · ')}</span>
          </li>
        ) : <li key={i} className="text-[14.5px] text-[var(--ink)]">{line}</li>
      })}
    </ol>
  )
}

function ExerciseTable({ date, w }: { date: string; w: ProgramWorkout }) {
  const logIt = () => {
    setPrefill(sessionDraft(date, w))
    window.location.hash = '#strength'
  }
  return (
    <div className="flex flex-col gap-2">
      <div className="overflow-x-auto">
        <table className="tabular w-full min-w-[560px] text-left text-[14px]">
          <thead className="text-[12.5px] text-[var(--ink-muted)]"><tr><th className="py-1.5 font-medium">Exercise</th><th className="font-medium">Sets × reps</th><th className="font-medium">RPE</th><th className="font-medium">Load</th><th className="font-medium">Rest</th></tr></thead>
          <tbody>
            {(w.exercises ?? []).map((e, i) => (
              <tr key={i} className="border-t border-[var(--border)] align-top">
                <td className="py-2 pr-3">
                  <div className={`font-medium ${e.kind === 'main' ? 'text-[var(--ink)]' : 'text-[var(--ink-2)]'}`}>{e.name}</div>
                  <div className="text-[12.5px] leading-snug text-[var(--ink-muted)]">{e.notes}</div>
                </td>
                <td className="py-2 pr-3 whitespace-nowrap">{e.sets} × {e.reps}</td>
                <td className="py-2 pr-3">{e.rpe ?? '—'}</td>
                <td className="py-2 pr-3 whitespace-nowrap">{loadText(e) ?? (e.rpe && e.reps_n ? <span className="text-[var(--ink-muted)]">log to calibrate</span> : '—')}</td>
                <td className="py-2 whitespace-nowrap text-[var(--ink-muted)]">{e.rest ?? '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button onClick={logIt} className="rounded-full bg-[var(--ink)] px-4 py-1.5 text-[14px] font-medium text-[var(--surface)] focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none">Log this session</button>
        <span className="text-[12.5px] text-[var(--ink-muted)]">Loads come from your best logged sets of the last 8 weeks. If the bar moves faster or slower than the RPE, trust the RPE.</span>
      </div>
    </div>
  )
}

function WorkoutBlock({ date, w, data }: { date: string; w: ProgramWorkout; data: ProgramResponse }) {
  const M = SPORT[w.sport]
  const I = M.icon
  if (w.sport === 'rest') {
    return (
      <div className="flex items-start gap-3 rounded-xl border border-dashed border-[var(--border)] px-4 py-3 text-[14px] text-[var(--ink-2)]">
        <Moon className="mt-0.5 size-4 shrink-0 text-[var(--ink-muted)]" aria-hidden />
        <span><span className="font-medium text-[var(--ink)]">Rest day.</span> {w.description}</span>
      </div>
    )
  }
  const zones = w.sport === 'run' || w.sport === 'bike' ? data.program.zones[w.sport].hr : null
  return (
    <article className="flex flex-col gap-3 rounded-xl bg-[var(--surface-2)] p-4" style={{ boxShadow: `inset 3px 0 0 ${M.color}` }}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex min-w-0 items-start gap-2.5">
          <I className="mt-1 size-4.5 shrink-0" style={{ color: M.color }} aria-hidden />
          <div className="min-w-0">
            <h4 className="font-display text-[21px] leading-tight font-semibold text-[var(--ink)]">{w.name}</h4>
            <p className="tabular text-[13.5px] text-[var(--ink-muted)]">
              {w.slot === 'AM' ? 'Morning' : 'Evening'} · {fmtMin(w.durationMinutes)}{w.primaryZone ? ` · ${w.primaryZone}` : ''}{w.distanceMeters ? ` · ${w.distanceMeters} m` : ''}
            </p>
          </div>
        </div>
        {w.completed && <span className="flex items-center gap-1 text-[13px] text-[var(--good)]"><CheckCircle2 className="size-4" aria-hidden />Done{w.doneMinutes ? `, ${Math.round(w.doneMinutes)} min` : ''}</span>}
      </header>
      {w.description && <p className="text-[14px] text-[var(--ink-2)]">{w.description}</p>}
      {w.adjustment && !w.completed && (
        <p className="flex items-start gap-2 rounded-lg bg-[var(--surface)] px-3 py-2 text-[14px] text-[var(--ink)]">
          <span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: zoneColor[w.adjustment.zone] }} aria-hidden />Today: {w.adjustment.note}
        </p>
      )}
      {w.exercises ? <ExerciseTable date={date} w={w} /> : <Parts text={w.humanReadable} />}
      {zones && (
        <p className="tabular text-[12.5px] text-[var(--ink-muted)]">
          Your {w.sport} zones{zones.estimated ? ' (estimated)' : ''}: Z2 {zones.zones[1].hrLow}–{zones.zones[1].hrHigh} · Z3 {zones.zones[2].hrLow}–{zones.zones[2].hrHigh} · Z4 {zones.zones[3].hrLow}–{zones.zones[3].hrHigh} bpm
        </p>
      )}
    </article>
  )
}

function WeekNav({ week, total, current, weeks, onGo }: { week: ProgramWeek; total: number; current: number | null; weeks: ProgramWeek[]; onGo: (n: number) => void }) {
  const arrow = 'rounded-full border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--ink-2)] hover:text-[var(--ink)] disabled:opacity-35 focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none'
  return (
    <div className="sticky top-0 z-10 -mx-1 flex flex-wrap items-center justify-between gap-3 bg-[var(--page)]/90 px-1 py-2.5 backdrop-blur">
      <div className="flex items-center gap-2">
        <button onClick={() => onGo(week.weekNumber - 1)} disabled={week.weekNumber <= 1} aria-label="Previous week" className={arrow}><ChevronLeft className="size-5" aria-hidden /></button>
        <div className="min-w-0 px-1">
          <div className="font-display text-[26px] leading-none font-bold text-[var(--ink)]">Week {week.weekNumber}<span className="text-[16px] font-semibold text-[var(--ink-muted)]"> of {total}</span></div>
          <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[13px] text-[var(--ink-2)]">
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-[3px]" style={{ background: phaseColor(week.phaseKey) }} aria-hidden />{week.phase}</span>
            <span className="text-[var(--ink-muted)]">{rangeFmt.format(at(week.startDate))} – {rangeFmt.format(at(week.endDate))}</span>
            {week.weekNumber === current && <span className="rounded-full bg-[var(--strain)] px-2 py-0.5 text-[11.5px] font-medium text-white">This week</span>}
            {week.isRecoveryWeek && <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 text-[11.5px]">Recovery week</span>}
            {week.tuneup && <span className="rounded-full bg-[color-mix(in_srgb,var(--strain)_14%,transparent)] px-2 py-0.5 text-[11.5px] text-[var(--ink)]">Half marathon block</span>}
          </div>
        </div>
        <button onClick={() => onGo(week.weekNumber + 1)} disabled={week.weekNumber >= total} aria-label="Next week" className={arrow}><ChevronRight className="size-5" aria-hidden /></button>
      </div>
      <div className="flex items-center gap-2">
        {current && week.weekNumber !== current && (
          <button onClick={() => onGo(current)} className="rounded-full border border-[var(--border)] px-3 py-1.5 text-[13px] text-[var(--ink-2)] hover:text-[var(--ink)]">Back to this week</button>
        )}
        <label className="sr-only" htmlFor="week-jump">Jump to week</label>
        <select id="week-jump" value={week.weekNumber} onChange={(e) => onGo(Number(e.target.value))} className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1.5 text-[13px] text-[var(--ink-2)]">
          {weeks.map((w) => <option key={w.weekNumber} value={w.weekNumber}>Week {w.weekNumber} · {w.phase} · {rangeFmt.format(at(w.startDate))}</option>)}
        </select>
      </div>
    </div>
  )
}

function WeekSummary({ week, today, selected, onSelect }: { week: ProgramWeek; today: string; selected: number; onSelect: (i: number) => void }) {
  const done = week.days.flatMap((d) => d.workouts).filter((w) => w.completed).reduce((a, w) => a + (w.doneMinutes ?? w.durationMinutes), 0)
  const sports = (['swim', 'bike', 'run', 'strength'] as const).filter((k) => week.summary.bySport[k])
  return (
    <section aria-label="Week overview" className="flex flex-col gap-4 rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-[15px] text-[var(--ink)]"><span className="font-semibold">Focus:</span> {week.focus}</p>
        <p className="tabular text-[13.5px] text-[var(--ink-muted)]">{week.summary.totalHours} h planned{done ? ` · ${fmtMin(Math.round(done))} done` : ''}</p>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {sports.map((k) => {
          const b = week.summary.bySport[k]
          const I = SPORT[k].icon
          return (
            <div key={k} className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
              <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-[var(--ink-muted)]"><I className="size-3.5" style={{ color: SPORT[k].color }} aria-hidden />{SPORT[k].label}</div>
              <div className="font-display tabular text-[22px] leading-tight font-semibold text-[var(--ink)]">{fmtMin(Math.round(b.hours * 60))}</div>
              <div className="tabular text-[12px] text-[var(--ink-2)]">{b.sessions} {b.sessions === 1 ? 'session' : 'sessions'}</div>
            </div>
          )
        })}
      </div>
      <div role="tablist" aria-label="Days" className="grid grid-cols-7 gap-1">
        {week.days.map((d, i) => {
          const isToday = d.date === today
          const isSelected = i === selected
          const active = d.workouts.filter((w) => w.sport !== 'rest')
          return (
            <button key={d.date} role="tab" aria-selected={isSelected} aria-controls="day-panel" onClick={() => onSelect(i)}
              className={`flex flex-col items-center gap-1 rounded-xl px-1 py-2 text-center transition-colors focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none ${isSelected ? 'bg-[var(--ink)]' : isToday ? 'bg-[color-mix(in_srgb,var(--strain)_14%,transparent)] ring-1 ring-[var(--strain)]' : 'bg-[var(--surface-2)] hover:bg-[color-mix(in_srgb,var(--surface-2)_80%,var(--ink)_6%)]'}`}>
              <span className={`text-[12px] ${isSelected ? 'text-[var(--surface)]/70' : 'text-[var(--ink-muted)]'}`}>{isToday ? 'Today' : weekdayFmt.format(at(d.date))}</span>
              <span className={`font-display tabular text-[18px] leading-none font-semibold ${isSelected ? 'text-[var(--surface)]' : 'text-[var(--ink)]'}`}>{at(d.date).getDate()}</span>
              <span className="flex h-2 items-center gap-0.5" aria-label={active.map((w) => SPORT[w.sport].label).join(', ') || 'Rest'}>
                {active.length ? active.map((w) => <span key={w.id} className="size-1.5 rounded-full" style={{ background: w.completed ? 'var(--good)' : SPORT[w.sport].color }} />) : <span className={`text-[10px] ${isSelected ? 'text-[var(--surface)]/70' : 'text-[var(--ink-muted)]'}`}>rest</span>}
              </span>
            </button>
          )
        })}
      </div>
    </section>
  )
}

function DayPlan({ day, today, data }: { day: ProgramWeek['days'][number]; today: string; data: ProgramResponse }) {
  const isToday = day.date === today
  const minutes = day.workouts.reduce((a, w) => a + w.durationMinutes, 0)
  return (
    <section id="day-panel" role="tabpanel" aria-label={longFmt.format(at(day.date))} className="rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-4"
      style={{ boxShadow: isToday ? 'inset 0 3px 0 var(--strain)' : undefined }}>
      <header className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="font-display text-[20px] font-semibold text-[var(--ink)]">{longFmt.format(at(day.date))}{isToday && <span className="ml-2 align-middle text-[13px] font-medium text-[var(--strain)]">Today</span>}</h3>
        {minutes > 0 && <span className="tabular text-[13px] text-[var(--ink-muted)]">{fmtMin(minutes)}</span>}
      </header>
      <div className="flex flex-col gap-3">
        {day.workouts.map((w) => <WorkoutBlock key={w.id} date={day.date} w={w} data={data} />)}
      </div>
    </section>
  )
}

// --------------------------------------------------------------------------- calculator

const REPS = [1, 3, 5, 6, 8, 10]
const RPES = [6, 7, 8, 9, 10]

function LoadCalculator({ maxes }: { maxes: ProgramResponse['maxes'] }) {
  const [kg, setKg] = useState('80')
  const [reps, setReps] = useState('5')
  const [rpe, setRpe] = useState('8')
  const [picked, setPicked] = useState<string>('')
  const fromSet = estimate(Number(kg), Number(reps), Number(rpe))
  const max = picked && maxes[picked] ? maxes[picked].e1rm : fromSet
  const logged = Object.entries(maxes)
  return (
    <Card title="Load and 1RM calculator" subtitle="Weight × reps at RPE → estimated 1RM → loads" icon={<Calculator className="size-4.5" />}>
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-3 gap-2">
          <label className="flex flex-col gap-1 text-[12.5px] text-[var(--ink-muted)]">Weight (kg)<input name="calc_kg" type="number" inputMode="decimal" value={kg} onChange={(e) => { setKg(e.target.value); setPicked('') }} className={input} /></label>
          <label className="flex flex-col gap-1 text-[12.5px] text-[var(--ink-muted)]">Reps<input name="calc_reps" type="number" inputMode="numeric" min={1} max={12} value={reps} onChange={(e) => { setReps(e.target.value); setPicked('') }} className={input} /></label>
          <label className="flex flex-col gap-1 text-[12.5px] text-[var(--ink-muted)]">RPE
            <select name="calc_rpe" value={rpe} onChange={(e) => { setRpe(e.target.value); setPicked('') }} className={`${input} bg-[var(--surface)]`}>
              {[6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
        </div>
        {logged.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {logged.map(([name, m]) => (
              <button key={name} aria-pressed={picked === name} onClick={() => setPicked(picked === name ? '' : name)}
                className={`rounded-full border px-2.5 py-1 text-[12.5px] ${picked === name ? 'border-[var(--strength)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)]'}`}>
                {name} · {Math.round(m.e1rm)}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-baseline gap-2">
          <span className="text-[13px] text-[var(--ink-muted)]">Estimated 1RM{picked ? ` (${picked}, from ${maxes[picked].from})` : ''}</span>
          <span className="font-display tabular text-[30px] leading-none font-bold text-[var(--ink)]">{max ? fmtKg(roundTo(max, 0.5)) : '—'}</span>
        </div>
        {max && (
          <table className="tabular w-full text-center text-[13px]">
            <thead className="text-[12px] text-[var(--ink-muted)]"><tr><th className="py-1 text-left font-medium">Reps</th>{RPES.map((r) => <th key={r} className="font-medium">RPE {r}</th>)}</tr></thead>
            <tbody>
              {REPS.map((n) => (
                <tr key={n} className="border-t border-[var(--border)]">
                  <td className="py-1 text-left text-[var(--ink-2)]">{n}</td>
                  {RPES.map((r) => <td key={r} className="py-1 text-[var(--ink)]">{roundTo(max * pct1rm(n, r), 2.5)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <p className="text-[12.5px] text-[var(--ink-muted)]">RPE 8 means 2 reps left in the tank. Loads round to 2.5 kg.</p>
      </div>
    </Card>
  )
}

// --------------------------------------------------------------------------- tab

export function ProgramTab() {
  const { data, error, reload } = useProgram()
  const [picked, setPicked] = useState<number | null>(null)
  const [pickedDay, setPickedDay] = useState<number | null>(null)
  const navRef = useRef<HTMLDivElement>(null)
  const total = data?.program.weeks.length ?? 0
  const shown = picked ?? data?.current_week ?? 1
  const week = data?.program.weeks.find((w) => w.weekNumber === shown)
  // Without a pick: today in the current week, Monday in any other.
  const todayIdx = week ? week.days.findIndex((d) => d.date === data?.today) : -1
  const dayIdx = pickedDay ?? Math.max(0, todayIdx)

  const go = useCallback((n: number, day: number | null = null) => {
    if (n < 1 || n > total) return
    setPicked(n)
    setPickedDay(day)
    // Keep the week header in view when switching from further down the page.
    if (navRef.current && navRef.current.getBoundingClientRect().top < 0) navRef.current.scrollIntoView({ block: 'start' })
  }, [total])

  const stepDay = useCallback((delta: number) => {
    const next = dayIdx + delta
    if (next < 0) go(shown - 1, 6)
    else if (next > 6) go(shown + 1, 0)
    else setPickedDay(next)
  }, [dayIdx, go, shown])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target instanceof Element && e.target.closest('input, select, textarea')) || e.altKey || e.ctrlKey || e.metaKey) return
      if (e.key === 'ArrowLeft') stepDay(-1)
      if (e.key === 'ArrowRight') stepDay(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [stepDay])

  if (error) return <div className="mx-auto mt-10 max-w-lg rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--ink-2)]">Couldn't load the program. {error}</div>
  if (!data || !week) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading the program…">
        {[180, 120, 420].map((h, i) => <div key={i} className="animate-pulse rounded-[20px] bg-[var(--surface)] motion-reduce:animate-none" style={{ height: h }} />)}
      </div>
    )
  }

  const step = 'flex items-center gap-1 rounded-full border border-[var(--border)] px-3 py-1.5 text-[14px] text-[var(--ink-2)] hover:text-[var(--ink)] disabled:opacity-35'
  return (
    <div className="flex flex-col gap-4">
      <SeasonHeader data={data} selected={week.weekNumber} onPick={go} reload={reload} />
      <div ref={navRef}>
        <WeekNav week={week} total={total} current={data.current_week} weeks={data.program.weeks} onGo={go} />
      </div>
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <div className="flex min-w-0 flex-col gap-3">
          <WeekSummary week={week} today={data.today} selected={dayIdx} onSelect={setPickedDay} />
          <DayPlan day={week.days[dayIdx]} today={data.today} data={data} />
          <div className="flex justify-between gap-2 pt-1">
            <button onClick={() => stepDay(-1)} disabled={week.weekNumber <= 1 && dayIdx === 0} className={step}>
              <ChevronLeft className="size-4" aria-hidden />{dayIdx === 0 ? `Week ${week.weekNumber - 1}` : weekdayFmt.format(at(week.days[dayIdx - 1].date))}
            </button>
            <button onClick={() => stepDay(1)} disabled={week.weekNumber >= total && dayIdx === 6} className={step}>
              {dayIdx === 6 ? `Week ${week.weekNumber + 1}` : weekdayFmt.format(at(week.days[dayIdx + 1].date))}<ChevronRight className="size-4" aria-hidden />
            </button>
          </div>
        </div>
        <aside className="flex flex-col gap-4 xl:sticky xl:top-20 xl:self-start">
          <LoadCalculator maxes={data.maxes} />
        </aside>
      </div>
    </div>
  )
}
