import { Bike, Calculator, CalendarRange, CheckCircle2, Dumbbell, Flag, Footprints, Moon, Settings2, Trophy, Waves, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
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

const dayFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric' })
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

function Timeline({ data, onPick }: { data: ProgramResponse; onPick: (n: number) => void }) {
  const { weeks, phases } = data.program
  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-9 items-stretch gap-[2px]" role="list" aria-label="Season weeks">
        {weeks.map((w) => {
          const current = w.weekNumber === data.current_week
          return (
            <button key={w.weekNumber} role="listitem" onClick={() => onPick(w.weekNumber)}
              aria-label={`Week ${w.weekNumber}, ${w.phase}${w.isRecoveryWeek ? ', recovery week' : ''}`}
              aria-current={current ? 'true' : undefined}
              className="relative min-w-0 flex-1 rounded-[3px] focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none"
              style={{ background: phaseColor(w.phaseKey), opacity: w.isRecoveryWeek ? 0.45 : 1, outline: current ? '2px solid var(--ink)' : undefined, outlineOffset: 1 }} />
          )
        })}
      </div>
      <div className="flex gap-[2px] text-[12px] text-[var(--ink-muted)]">
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
      </div>
      {error && <p role="alert" className="text-[13px] text-[var(--critical)]">{error}</p>}
      <button onClick={save} disabled={saving} className="self-start rounded-full bg-[var(--ink)] px-4 py-1.5 text-[14px] font-medium text-[var(--surface)] disabled:opacity-60">{saving ? 'Saving…' : 'Save program settings'}</button>
    </div>
  )
}

function SeasonHeader({ data, onPick, reload }: { data: ProgramResponse; onPick: (n: number) => void; reload: () => void }) {
  const [open, setOpen] = useState(false)
  const { meta, phases, zones } = data.program
  const cur = data.current_week
  const phase = phases.find((p) => cur != null && cur >= p.startWeek && cur <= p.endWeek)
  const weeksLeft = cur != null ? meta.totalWeeks - cur : meta.totalWeeks
  return (
    <Card title={meta.event} subtitle={`${longFmt.format(at(meta.eventDate))} · ${weeksLeft} weeks to go`} icon={<Flag className="size-4.5" />}
      action={<button onClick={() => setOpen(!open)} aria-expanded={open} className="flex items-center gap-1 rounded-full border border-[var(--border)] px-2.5 py-1 text-[13px] text-[var(--ink-2)] hover:text-[var(--ink)]"><Settings2 className="size-3.5" aria-hidden />{open ? 'Close' : 'Settings'}</button>}>
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
        <Timeline data={data} onPick={onPick} />
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

// --------------------------------------------------------------------------- calendar

function WorkoutChip({ w, onOpen }: { w: ProgramWorkout; onOpen: () => void }) {
  const M = SPORT[w.sport]
  const I = M.icon
  const mains = (w.exercises ?? []).filter((e) => e.kind === 'main')
  if (w.sport === 'rest') {
    return <button onClick={onOpen} className="rounded-xl border border-dashed border-[var(--border)] p-2.5 text-left text-[13px] text-[var(--ink-muted)] hover:text-[var(--ink-2)]">Rest · protocols</button>
  }
  return (
    <button onClick={onOpen} className="group flex flex-col gap-1 rounded-xl bg-[var(--surface-2)] p-2.5 text-left transition-colors hover:bg-[color-mix(in_srgb,var(--surface-2)_80%,var(--ink)_6%)] focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none"
      style={{ boxShadow: `inset 3px 0 0 ${M.color}` }}>
      <div className="flex items-center justify-between gap-1.5 pl-1">
        <span className="flex min-w-0 items-center gap-1.5 text-[13.5px] font-semibold text-[var(--ink)]"><I className="size-3.5 shrink-0" style={{ color: M.color }} aria-hidden /><span className="truncate">{w.name}</span></span>
        {w.completed && <CheckCircle2 className="size-4 shrink-0 text-[var(--good)]" aria-label="Done" />}
      </div>
      <div className="tabular pl-1 text-[12.5px] text-[var(--ink-muted)]">{w.slot} · {fmtMin(w.durationMinutes)}{w.primaryZone ? ` · ${w.primaryZone}` : ''}</div>
      {mains.length > 0 && (
        <ul className="pl-1 text-[12px] leading-snug text-[var(--ink-2)]">
          {mains.map((e) => <li key={e.name} className="truncate">{e.name} {e.sets}×{e.reps}{loadText(e) ? ` · ${loadText(e)}` : ''}</li>)}
        </ul>
      )}
      {w.adjustment && !w.completed && (
        <div className="mt-0.5 flex items-start gap-1.5 pl-1 text-[12px] text-[var(--ink-2)]"><span className="mt-1 size-2 shrink-0 rounded-full" style={{ background: zoneColor[w.adjustment.zone] }} aria-hidden />{w.adjustment.note}</div>
      )}
    </button>
  )
}

function WeekSection({ week, today, isCurrent, onOpen }: { week: ProgramWeek; today: string; isCurrent: boolean; onOpen: (day: string, w: ProgramWorkout) => void }) {
  const done = week.days.flatMap((d) => d.workouts).filter((w) => w.completed).reduce((a, w) => a + (w.doneMinutes ?? w.durationMinutes), 0)
  return (
    <section id={`week-${week.weekNumber}`} aria-label={`Week ${week.weekNumber}`} className="scroll-mt-16 rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-4"
      style={{ boxShadow: isCurrent ? 'inset 0 3px 0 var(--strain)' : undefined }}>
      <header className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <h3 className="font-display text-[20px] font-semibold text-[var(--ink)]">Week {week.weekNumber}</h3>
          <span className="flex items-center gap-1.5 text-[13px] text-[var(--ink-2)]"><span className="size-2.5 rounded-[3px]" style={{ background: phaseColor(week.phaseKey) }} aria-hidden />{week.phase}</span>
          <span className="text-[13px] text-[var(--ink-muted)]">{rangeFmt.format(at(week.startDate))} – {rangeFmt.format(at(week.endDate))}</span>
          {week.isRecoveryWeek && <span className="rounded-full bg-[var(--surface-2)] px-2 py-0.5 text-[12px] text-[var(--ink-2)]">Recovery week</span>}
          {isCurrent && <span className="rounded-full bg-[var(--strain)] px-2 py-0.5 text-[12px] font-medium text-white">This week</span>}
        </div>
        <span className="tabular text-[13px] text-[var(--ink-muted)]">{week.focus} · {week.summary.totalHours} h planned{done ? ` · ${fmtMin(Math.round(done))} done` : ''}</span>
      </header>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
        {week.days.map((d) => {
          const isToday = d.date === today
          return (
            <div key={d.date} className={`flex flex-col gap-1.5 rounded-xl p-1.5 ${isToday ? 'bg-[color-mix(in_srgb,var(--strain)_10%,transparent)] ring-1 ring-[var(--strain)]' : ''}`}>
              <div className="flex items-baseline justify-between px-1 text-[12.5px]">
                <span className={`font-semibold ${isToday ? 'text-[var(--ink)]' : 'text-[var(--ink-2)]'}`}>{dayFmt.format(at(d.date))}</span>
                {isToday && <span className="text-[var(--strain)]">Today</span>}
              </div>
              {d.workouts.map((w) => <WorkoutChip key={w.id} w={w} onOpen={() => onOpen(d.date, w)} />)}
            </div>
          )
        })}
      </div>
    </section>
  )
}

// --------------------------------------------------------------------------- workout detail

function WorkoutDetail({ date, w, data, onClose }: { date: string; w: ProgramWorkout; data: ProgramResponse; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  const M = SPORT[w.sport]
  const zones = w.sport === 'run' || w.sport === 'bike' ? data.program.zones[w.sport].hr : null
  const logIt = () => {
    setPrefill(sessionDraft(date, w))
    window.location.hash = '#strength'
  }
  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center bg-black/50 p-0 sm:items-center sm:p-6" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-labelledby="workout-title" onClick={(e) => e.stopPropagation()}
        className="max-h-[90vh] w-full max-w-2xl overflow-y-auto overscroll-contain rounded-t-[20px] border border-[var(--border)] bg-[var(--surface)] p-5 sm:rounded-[20px]"
        style={{ boxShadow: `inset 0 3px 0 ${M.color}` }}>
        <div className="mb-3 flex items-start justify-between gap-3">
          <div>
            <p className="text-[13px] text-[var(--ink-muted)]">{longFmt.format(at(date))} · {w.slot} · {M.label}</p>
            <h2 id="workout-title" className="font-display text-[26px] leading-tight font-bold text-[var(--ink)]">{w.name}</h2>
            <p className="tabular text-[14px] text-[var(--ink-2)]">{fmtMin(w.durationMinutes)}{w.primaryZone ? ` · ${w.primaryZone}` : ''}{w.distanceMeters ? ` · ${w.distanceMeters} m` : ''}{w.completed ? ' · done' : ''}</p>
          </div>
          <button ref={closeRef} onClick={onClose} aria-label="Close" className="rounded-full p-1.5 text-[var(--ink-muted)] hover:text-[var(--ink)] focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none"><X className="size-5" aria-hidden /></button>
        </div>
        {w.description && <p className="mb-3 text-[14.5px] text-[var(--ink-2)]">{w.description}</p>}
        {w.adjustment && <p className="mb-3 flex items-start gap-2 rounded-xl bg-[var(--surface-2)] px-3 py-2 text-[14px] text-[var(--ink)]"><span className="mt-1.5 size-2 shrink-0 rounded-full" style={{ background: zoneColor[w.adjustment.zone] }} aria-hidden />Today: {w.adjustment.note}</p>}

        {w.exercises ? (
          <>
            <div className="overflow-x-auto">
              <table className="tabular w-full min-w-[520px] text-left text-[13.5px]">
                <thead className="text-[12.5px] text-[var(--ink-muted)]"><tr><th className="py-1.5 font-medium">Exercise</th><th className="font-medium">Sets × reps</th><th className="font-medium">RPE</th><th className="font-medium">Load</th><th className="font-medium">Rest</th></tr></thead>
                <tbody>
                  {w.exercises.map((e, i) => (
                    <tr key={i} className="border-t border-[var(--border)] align-top">
                      <td className="py-2 pr-2">
                        <div className={`font-medium ${e.kind === 'main' ? 'text-[var(--ink)]' : 'text-[var(--ink-2)]'}`}>{e.name}</div>
                        <div className="text-[12.5px] leading-snug text-[var(--ink-muted)]">{e.notes}</div>
                      </td>
                      <td className="py-2 pr-2 whitespace-nowrap">{e.sets} × {e.reps}</td>
                      <td className="py-2 pr-2">{e.rpe ?? '—'}</td>
                      <td className="py-2 pr-2 whitespace-nowrap">{loadText(e) ?? (e.rpe && e.reps_n ? <span className="text-[var(--ink-muted)]">log to calibrate</span> : '—')}</td>
                      <td className="py-2 whitespace-nowrap text-[var(--ink-muted)]">{e.rest ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[12.5px] text-[var(--ink-muted)]">Loads come from your best logged sets of the last 8 weeks: weight × reps at RPE gives an estimated 1RM, and each prescription takes its share. If the bar moves faster or slower than the RPE, trust the RPE.</p>
            <button onClick={logIt} className="mt-3 rounded-full bg-[var(--ink)] px-4 py-2 text-[14px] font-medium text-[var(--surface)]">Log this session</button>
          </>
        ) : (
          <pre className="rounded-xl bg-[var(--surface-2)] p-3 font-sans text-[14px] leading-relaxed whitespace-pre-wrap text-[var(--ink)]">{w.humanReadable}</pre>
        )}
        {zones && (
          <p className="tabular mt-3 text-[13px] text-[var(--ink-muted)]">
            Your {w.sport} zones{zones.estimated ? ' (estimated)' : ''}: Z1 under {zones.zones[0].hrHigh} · Z2 {zones.zones[1].hrLow}–{zones.zones[1].hrHigh} · Z3 {zones.zones[2].hrLow}–{zones.zones[2].hrHigh} · Z4 {zones.zones[3].hrLow}–{zones.zones[3].hrHigh} bpm
          </p>
        )}
      </div>
    </div>
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
  const [open, setOpen] = useState<{ date: string; w: ProgramWorkout } | null>(null)
  const scrolled = useRef(false)
  const jump = (n: number) => document.getElementById(`week-${n}`)?.scrollIntoView({ block: 'start' })
  useEffect(() => {
    if (data?.current_week && !scrolled.current) {
      scrolled.current = true
      requestAnimationFrame(() => jump(data.current_week as number))
    }
  }, [data])
  const todays = useMemo(() => data?.program.weeks.flatMap((w) => w.days).find((d) => d.date === data.today), [data])

  if (error) return <div className="mx-auto mt-10 max-w-lg rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--ink-2)]">Couldn't load the program. {error}</div>
  if (!data) {
    return (
      <div className="flex flex-col gap-4" aria-busy="true" aria-label="Loading the program…">
        {[180, 420, 420].map((h, i) => <div key={i} className="animate-pulse rounded-[20px] bg-[var(--surface)] motion-reduce:animate-none" style={{ height: h }} />)}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-4">
      <SeasonHeader data={data} onPick={jump} reload={reload} />
      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_360px]">
        <div className="flex min-w-0 flex-col gap-3">
          <div className="sticky top-0 z-10 -mx-1 flex items-center justify-between gap-2 bg-[var(--page)]/90 px-1 py-2 backdrop-blur">
            <span className="flex items-center gap-2 text-[14px] text-[var(--ink-2)]"><CalendarRange className="size-4" aria-hidden />{data.program.meta.totalWeeks} weeks · tap a session for details</span>
            <div className="flex items-center gap-2">
              <label className="sr-only" htmlFor="week-jump">Jump to week</label>
              <select id="week-jump" value="" onChange={(e) => e.target.value && jump(Number(e.target.value))} className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-[13px] text-[var(--ink-2)]">
                <option value="">Jump to week…</option>
                {data.program.weeks.map((w) => <option key={w.weekNumber} value={w.weekNumber}>Week {w.weekNumber} · {w.phase} · {rangeFmt.format(at(w.startDate))}</option>)}
              </select>
              {data.current_week && <button onClick={() => jump(data.current_week as number)} className="rounded-full border border-[var(--border)] px-3 py-1 text-[13px] text-[var(--ink-2)] hover:text-[var(--ink)]">This week</button>}
            </div>
          </div>
          {data.program.weeks.map((w) => (
            <WeekSection key={w.weekNumber} week={w} today={data.today} isCurrent={w.weekNumber === data.current_week} onOpen={(date, wo) => setOpen({ date, w: wo })} />
          ))}
        </div>
        <aside className="flex flex-col gap-4 xl:sticky xl:top-4 xl:self-start">
          <Card title="Today" subtitle={longFmt.format(at(data.today))} icon={<CalendarRange className="size-4.5" />}>
            {todays ? (
              <div className="flex flex-col gap-2">
                {todays.workouts.map((w) => <WorkoutChip key={w.id} w={w} onOpen={() => setOpen({ date: todays.date, w })} />)}
                {data.recovery_today != null && <p className="text-[13px] text-[var(--ink-muted)]">Recovery {data.recovery_today}%: the coloured notes say how to adjust.</p>}
              </div>
            ) : <p className="text-[14px] text-[var(--ink-muted)]">The program starts {longFmt.format(at(data.program.meta.planStartDate))}.</p>}
          </Card>
          <LoadCalculator maxes={data.maxes} />
        </aside>
      </div>
      {open && <WorkoutDetail date={open.date} w={open.w} data={data} onClose={() => setOpen(null)} />}
    </div>
  )
}
