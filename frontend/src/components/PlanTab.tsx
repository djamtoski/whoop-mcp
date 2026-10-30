import { Bike, CalendarCheck, CheckCircle2, Dumbbell, Flag, Footprints, Settings2, Waves } from 'lucide-react'
import { useState } from 'react'
import { usePlan } from '@/api'
import type { PlanSession, PlanSettings, TrainingDiscipline } from '@/types'
import { Card } from './ui'

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const SPORT: Record<TrainingDiscipline, { label: string; color: string; icon: typeof Waves }> = {
  swim: { label: 'Swim', color: 'var(--swim)', icon: Waves },
  bike: { label: 'Bike', color: 'var(--bike)', icon: Bike },
  run: { label: 'Run', color: 'var(--run)', icon: Footprints },
  strength: { label: 'Strength', color: 'var(--strength)', icon: Dumbbell },
}
const ZONE = { green: 'var(--good)', yellow: 'var(--warning)', red: 'var(--critical)' } as const
const fmtMin = (m: number) => (m >= 60 ? `${Math.floor(m / 60)}h${m % 60 ? ` ${String(m % 60).padStart(2, '0')}` : ''}` : `${m}m`)
const dayLabel = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
const input = 'rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-[13px] text-[var(--ink)] outline-none focus:border-[var(--ink-muted)]'

function SessionCard({ s, isToday }: { s: PlanSession; isToday: boolean }) {
  const M = SPORT[s.sport]
  const I = M.icon
  const adj = isToday ? s.adjustment : null
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-2)] p-2.5" style={{ borderLeft: `3px solid ${M.color}` }}>
      <div className="flex items-center justify-between gap-1">
        <span className="flex items-center gap-1.5 text-[12.5px] font-medium text-[var(--ink)]"><I className="size-3.5" style={{ color: M.color }} />{M.label} · {s.kind}</span>
        {s.done && <CheckCircle2 className="size-4 shrink-0" style={{ color: 'var(--good)' }} aria-label="done" />}
      </div>
      <div className="tabular mt-0.5 text-[12px] text-[var(--ink-2)]">{fmtMin(s.minutes)} · {s.intensity}{s.hour != null ? ` · usually ${String(s.hour).padStart(2, '0')}:00` : ''}</div>
      <div className="mt-1 text-[11.5px] leading-snug text-[var(--ink-muted)]">{s.description}</div>
      {s.done && s.done_minutes != null && <div className="mt-1 text-[11.5px] text-[var(--good)]">Done · {Math.round(s.done_minutes)} min</div>}
      {adj && !s.done && (
        <div className="mt-1.5 flex items-start gap-1.5 rounded-lg bg-[var(--surface)] px-2 py-1 text-[11.5px] text-[var(--ink-2)]">
          <span className="mt-1 size-2 shrink-0 rounded-full" style={{ background: ZONE[adj.zone] }} />{adj.note}
        </div>
      )}
    </div>
  )
}

function SettingsForm({ settings, strengthDays, onSaved }: { settings: PlanSettings; strengthDays: number[]; onSaved: () => void }) {
  const [s, setS] = useState({ ...settings, strength_days: settings.strength_days ?? strengthDays })
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const save = async () => {
    setError(null)
    const r = await fetch('/api/plan/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...s, race_date: s.race_date || null }) })
    const body = await r.json().catch(() => ({}))
    if (!r.ok) return setError(typeof body.detail === 'string' ? body.detail : 'Invalid settings.')
    setSaved(true)
    onSaved()
  }
  const daySelect = (key: 'long_ride_day' | 'long_run_day' | 'rest_day', label: string) => (
    <label className="flex flex-col gap-1 text-[11.5px] text-[var(--ink-muted)]">{label}
      <select value={s[key]} onChange={(e) => { setSaved(false); setS({ ...s, [key]: Number(e.target.value) }) }} className={input}>
        {DAYS.map((d, i) => <option key={d} value={i}>{d}</option>)}
      </select>
    </label>
  )
  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <label className="col-span-2 flex flex-col gap-1 text-[11.5px] text-[var(--ink-muted)]">Race
          <input value={s.race_name} onChange={(e) => { setSaved(false); setS({ ...s, race_name: e.target.value }) }} className={input} />
        </label>
        <label className="flex flex-col gap-1 text-[11.5px] text-[var(--ink-muted)]">Race date
          <input type="date" value={s.race_date ?? ''} onChange={(e) => { setSaved(false); setS({ ...s, race_date: e.target.value || null }) }} className={input} />
        </label>
        <label className="flex flex-col gap-1 text-[11.5px] text-[var(--ink-muted)]">Hours / week
          <input type="number" min={3} max={25} step={0.5} value={s.weekly_hours} onChange={(e) => { setSaved(false); setS({ ...s, weekly_hours: Number(e.target.value) }) }} className={input} />
        </label>
        {daySelect('long_ride_day', 'Long ride')}
        {daySelect('long_run_day', 'Long run')}
        {daySelect('rest_day', 'Rest day')}
      </div>
      <div className="flex flex-col gap-1 text-[11.5px] text-[var(--ink-muted)]">Gym days (up to 3)
        <div className="flex flex-wrap gap-1">
          {DAYS.map((d, i) => {
            const on = s.strength_days.includes(i)
            return (
              <button key={d} aria-pressed={on} onClick={() => { setSaved(false); setS({ ...s, strength_days: on ? s.strength_days.filter((x) => x !== i) : [...s.strength_days, i].sort() }) }}
                className={`rounded-full border px-2.5 py-1 text-[12px] ${on ? 'border-[var(--strength)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)]'}`}>{d}</button>
            )
          })}
        </div>
      </div>
      {error && <p role="alert" className="text-[12.5px] text-[var(--critical)]">{error}</p>}
      <div className="flex items-center gap-3">
        <button onClick={save} className="rounded-full bg-[var(--ink)] px-4 py-1.5 text-[13px] font-medium text-[var(--surface)]">Save plan settings</button>
        {saved && <span className="text-[12px] text-[var(--good)]">Saved</span>}
      </div>
    </div>
  )
}

export function PlanTab() {
  const { data, error, reload } = usePlan()
  const [showSettings, setShowSettings] = useState(false)
  if (error) return <div className="mx-auto mt-10 max-w-lg rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--ink-2)]">Couldn't load the plan. {error}</div>
  if (!data) return <div className="py-20 text-center text-[var(--ink-2)]">Building your week…</div>

  const { week, settings, habits } = data
  const done = (k: TrainingDiscipline) => week.days.reduce((a, d) => a + d.sessions.filter((s) => s.sport === k && s.done).reduce((b, s) => b + (s.done_minutes ?? s.minutes), 0), 0)
  const ph = week.phase

  return (
    <div className="flex flex-col gap-4">
      <Card title={settings.race_name} subtitle={settings.race_date ? `${dayLabel(settings.race_date)} · ${ph.weeks_to_race} weeks to go` : 'No race date yet'}
        icon={<Flag className="size-4.5" />}
        action={<button onClick={() => setShowSettings(!showSettings)} className="flex items-center gap-1 rounded-full border border-[var(--border)] px-2.5 py-1 text-[12px] text-[var(--ink-2)]"><Settings2 className="size-3.5" />{showSettings ? 'Close' : 'Settings'}</button>}>
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-2">
            <span className="rounded-full bg-[var(--surface-2)] px-2.5 py-1 text-[12px] font-semibold text-[var(--ink)] capitalize">{ph.name} phase</span>
            <span className="text-[13px] text-[var(--ink-2)]">{ph.focus}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {(Object.keys(SPORT) as TrainingDiscipline[]).map((k) => {
              const plannedMin = week.planned_minutes[k], doneMin = Math.round(done(k))
              return (
                <div key={k} className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
                  <div className="flex items-center gap-1.5 text-[12.5px] font-medium text-[var(--ink-muted)]"><span className="size-2 rounded-full" style={{ background: SPORT[k].color }} />{SPORT[k].label}</div>
                  <div className="tabular text-[17px] font-semibold text-[var(--ink)]">{fmtMin(doneMin)} <span className="text-[12px] font-normal text-[var(--ink-muted)]">/ {fmtMin(plannedMin)}</span></div>
                  <div className="mt-1.5 h-1.5 rounded-full bg-[var(--surface)]"><div className="h-full rounded-full" style={{ width: `${Math.min(100, plannedMin ? (100 * doneMin) / plannedMin : 0)}%`, background: SPORT[k].color }} /></div>
                </div>
              )
            })}
          </div>
          {data.recovery_today != null && (
            <p className="text-[12.5px] text-[var(--ink-2)]">Today's recovery <span className="tabular font-semibold text-[var(--ink)]">{data.recovery_today}%</span>: today's sessions show how to adjust.</p>
          )}
          {!data.live && <p className="text-[12px] text-[var(--ink-muted)]">Live WHOOP data unavailable: completed sessions and today's recovery may be missing.</p>}
          {showSettings && <SettingsForm settings={settings} strengthDays={week.strength_days} onSaved={reload} />}
        </div>
      </Card>

      <Card title="This week" subtitle={`${dayLabel(week.days[0].date)} – ${dayLabel(week.days[6].date)} · ticks come from your WHOOP workouts`} icon={<CalendarCheck className="size-4.5" />}>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-7">
          {week.days.map((d) => {
            const isToday = d.date === data.today
            return (
              <div key={d.date} className={`flex flex-col gap-2 rounded-xl p-2 ${isToday ? 'bg-[var(--surface-2)] ring-1 ring-[var(--ink-muted)]' : ''}`}>
                <div className="flex items-baseline justify-between px-0.5">
                  <span className="text-[13px] font-semibold text-[var(--ink)]">{d.weekday}{isToday && ' · today'}</span>
                  <span className="text-[11.5px] text-[var(--ink-muted)]">{dayLabel(d.date)}</span>
                </div>
                {d.rest
                  ? <div className="rounded-xl border border-dashed border-[var(--border)] p-3 text-center text-[12px] text-[var(--ink-muted)]">Rest · walk, mobility, sleep</div>
                  : d.sessions.map((s, i) => <SessionCard key={i} s={s} isToday={isToday} />)}
                {!!d.extra?.length && <div className="text-[11.5px] text-[var(--ink-muted)]">Also did: {d.extra.map((x) => `${x.sport} ${Math.round(x.minutes ?? 0)}m`).join(', ')}</div>}
              </div>
            )
          })}
        </div>
      </Card>

      <Card title="Your usual week" subtitle={`Sessions per week by weekday, last ${habits.weeks} training weeks · the plan places sessions on these days`} icon={<CalendarCheck className="size-4.5" />}>
        <div className="overflow-x-auto">
          <table className="tabular w-full min-w-[480px] text-center text-[12.5px]">
            <thead><tr><th className="py-1 text-left text-[12px] font-medium text-[var(--ink-muted)]">Sport</th>{DAYS.map((d) => <th key={d} className="py-1 text-[12px] font-medium text-[var(--ink-muted)]">{d}</th>)}<th className="py-1 text-[12px] font-medium text-[var(--ink-muted)]">Usual time</th></tr></thead>
            <tbody>
              {(Object.keys(SPORT) as TrainingDiscipline[]).map((k) => (
                <tr key={k} className="border-t border-[var(--border)]">
                  <td className="py-1.5 text-left text-[var(--ink-2)]">{SPORT[k].label}</td>
                  {habits.by_day.map((c, i) => {
                    const v = c[k] ?? 0
                    return <td key={i} className="py-1"><span className="inline-block min-w-9 rounded-md px-1.5 py-0.5" style={{ background: v ? `color-mix(in srgb, ${SPORT[k].color} ${Math.round(20 + 60 * Math.min(1, v))}%, transparent)` : 'transparent', color: v ? 'var(--ink)' : 'var(--ink-muted)' }}>{v ? v.toFixed(1) : '·'}</span></td>
                  })}
                  <td className="py-1.5 text-[var(--ink-2)]">{habits.hours[k] != null ? `${String(habits.hours[k]).padStart(2, '0')}:00` : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
