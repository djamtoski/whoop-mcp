import { Activity, HeartPulse, Pencil, Scale, Trash2, Trophy } from 'lucide-react'
import { useState } from 'react'
import { strengthRequest, useStrength } from '@/api'
import { type Draft, draftFromSession, emptyDraft } from '@/lib/strengthDraft'
import type { StrengthSummary } from '@/types'
import { LineChart } from './LineChart'
import { StrengthLogger } from './StrengthLogger'
import { Card, Tip } from './ui'

const shortDate = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
const fmt = (n: number | null | undefined, d = 0) => (n == null ? '—' : n.toFixed(d))
const MUSCLE_ORDER = ['quads', 'glutes', 'hamstrings', 'calves', 'chest', 'shoulders', 'triceps', 'back', 'biceps', 'core']
const ZONE = { green: 'var(--good)', yellow: 'var(--warning)', red: 'var(--critical)' } as const

function LiftsCard({ summary }: { summary: StrengthSummary }) {
  const [sel, setSel] = useState<number | null>(null)
  const lifts = summary.progress.filter((p) => p.pr_e1rm != null)
  const lift = lifts.find((p) => p.exercise_id === sel) ?? lifts[0]
  return (
    <Card title="Lift progress" subtitle="Estimated 1-rep max per session · ★ new PR" icon={<Trophy className="size-4.5" />}>
      {!lift ? <p className="text-sm text-[var(--ink-muted)]">Log a few sessions and your lifts show up here.</p> : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap gap-1">
            {lifts.map((p) => (
              <button key={p.exercise_id} onClick={() => setSel(p.exercise_id)}
                className={`rounded-full border px-2.5 py-1 text-[12px] ${p.exercise_id === lift.exercise_id ? 'border-[var(--ink-muted)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)]'}`}>{p.name}</button>
            ))}
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[['PR (e1RM)', `${fmt(lift.pr_e1rm, 1)} kg`, lift.pr_date ? shortDate(lift.pr_date) : ''],
              ['4-week change', lift.change_4w_pct == null ? '—' : `${lift.change_4w_pct > 0 ? '+' : ''}${lift.change_4w_pct}%`, 'vs 4+ weeks ago'],
              ['Sessions', String(lift.sessions), `last ${shortDate(lift.last_date)}`]].map(([l, v, s]) => (
              <div key={l} className="rounded-xl bg-[var(--surface-2)] px-3 py-2.5">
                <div className="text-[12.5px] font-medium text-[var(--ink-muted)]">{l}</div>
                <div className="tabular text-[18px] font-semibold text-[var(--ink)]">{v}</div>
                <div className="truncate text-[11.5px] text-[var(--ink-2)]">{s}</div>
              </div>
            ))}
          </div>
          {lift.points.length > 1
            ? <LineChart dates={lift.points.map((p) => p.date)} unit=" kg" lines={[{ label: 'e1RM', color: 'var(--strength)', values: lift.points.map((p) => p.e1rm), dots: true }]} />
            : <p className="text-[12.5px] text-[var(--ink-muted)]">One session so far; the chart starts with the second.</p>}
          <div className="flex flex-wrap gap-1.5 text-[12px] text-[var(--ink-2)]">
            {lift.points.slice(-8).reverse().map((p) => (
              <span key={p.session_id} className="tabular rounded-lg bg-[var(--surface-2)] px-2 py-1">
                {p.pr && '★ '}{shortDate(p.date)} · {p.top_set.reps}×{p.top_set.kg} kg · {p.sets} sets · {Math.round(p.volume_kg)} kg vol
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  )
}

function BalanceCard({ summary }: { summary: StrengthSummary }) {
  const weeks = summary.balance.weeks.slice(-4)
  const { low, high } = summary.balance.targets
  const avg = (f: (w: (typeof weeks)[number]) => number) => (weeks.length ? weeks.reduce((a, w) => a + f(w), 0) / weeks.length : 0)
  const muscles = MUSCLE_ORDER.map((m) => ({ m, sets: avg((w) => w.muscles[m] ?? 0) }))
  const max = Math.max(high + 4, ...muscles.map((x) => x.sets))
  const push = avg((w) => w.push), pull = avg((w) => w.pull)
  const lower = avg((w) => w.region.lower ?? 0), upper = avg((w) => w.region.upper ?? 0)
  return (
    <Card title="Muscle balance" subtitle={`Working sets per week, last ${weeks.length === 1 ? 'logged week' : `${weeks.length} logged weeks`} · band ${low}–${high}`} icon={<Scale className="size-4.5" />}>
      {!weeks.length ? <p className="text-sm text-[var(--ink-muted)]">No sessions logged yet.</p> : (
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            {muscles.map(({ m, sets }) => {
              const color = sets < low ? 'var(--serious)' : sets > high ? 'var(--warning)' : 'var(--good)'
              return (
                <div key={m} className="grid grid-cols-[84px_1fr_36px] items-center gap-2 text-[12.5px]">
                  <span className="capitalize text-[var(--ink-2)]">{m}</span>
                  <div className="relative h-3 rounded-[4px] bg-[var(--surface-2)]">
                    <div className="absolute inset-y-0 rounded-[4px] bg-[var(--good)] opacity-15" style={{ left: `${(low / max) * 100}%`, width: `${((high - low) / max) * 100}%` }} />
                    <div className="relative h-full rounded-[4px]" style={{ width: `${(sets / max) * 100}%`, background: color }} />
                  </div>
                  <span className="tabular text-right text-[var(--ink)]">{sets.toFixed(1)}</span>
                </div>
              )
            })}
          </div>
          <div className="grid grid-cols-2 gap-2 text-[12.5px] text-[var(--ink-2)]">
            <div className="rounded-xl bg-[var(--surface-2)] px-3 py-2"><span className="font-medium text-[var(--ink)]">Push : pull</span> {push.toFixed(1)} : {pull.toFixed(1)}
              <div className="text-[11.5px] text-[var(--ink-muted)]">{push + pull === 0 ? 'No upper-body pushing or pulling logged' : pull >= push ? 'Balanced or pull-heavy (good for shoulders and swim posture)' : 'More pushing than pulling: add a row or pull-up'}</div></div>
            <div className="rounded-xl bg-[var(--surface-2)] px-3 py-2"><span className="font-medium text-[var(--ink)]">Lower : upper</span> {lower.toFixed(1)} : {upper.toFixed(1)}
              <div className="text-[11.5px] text-[var(--ink-muted)]">Lower-body strength carries straight into bike and run</div></div>
          </div>
        </div>
      )}
    </Card>
  )
}

function RecoveryLinkCard({ summary }: { summary: StrengthSummary }) {
  const r = summary.recovery
  const zones = (['green', 'yellow', 'red'] as const).map((z) => ({ z, ...r.by_zone[z] }))
  return (
    <Card title="Lifting vs recovery" subtitle="How strong you are by morning recovery, and what lifting does to the next morning" icon={<HeartPulse className="size-4.5" />}>
      <div className="flex flex-col gap-2">
        {zones.map(({ z, sessions, avg_performance_pct }) => (
          <div key={z} className="grid grid-cols-[88px_1fr_64px] items-center gap-2 text-[12.5px]">
            <span className="flex items-center gap-1.5 text-[var(--ink-2)]"><span className="size-2 rounded-full" style={{ background: ZONE[z] }} />{z === 'green' ? '67%+' : z === 'yellow' ? '34–66%' : '< 34%'}</span>
            <Tip content={<span>{sessions} sessions</span>}>
              <div className="h-3 rounded-[4px] bg-[var(--surface-2)]">
                {avg_performance_pct != null && <div className="h-full rounded-[4px]" style={{ width: `${Math.min(100, Math.max(0, (avg_performance_pct - 80) * 4))}%`, background: ZONE[z] }} />}
              </div>
            </Tip>
            <span className="tabular text-right text-[var(--ink)]">{avg_performance_pct == null ? '—' : `${avg_performance_pct}%`}</span>
          </div>
        ))}
        <p className="text-[11.5px] text-[var(--ink-muted)]">Bar = average e1RM as % of each lift's previous best (80–105% scale).</p>
        <p className="text-[13px] text-[var(--ink-2)]">
          Next-morning recovery after lifting: <span className="tabular font-semibold text-[var(--ink)]">{r.avg_next_day_change == null ? '—' : `${r.avg_next_day_change > 0 ? '+' : ''}${r.avg_next_day_change} pts`}</span>
        </p>
      </div>
    </Card>
  )
}

export function StrengthTab() {
  const { data, error, reload } = useStrength()
  const [draft, setDraft] = useState<Draft>(emptyDraft())

  if (error) return <div className="mx-auto mt-10 max-w-lg rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-6 text-center text-sm text-[var(--ink-2)]">Couldn't load the strength log. {error}</div>
  if (!data) return <div className="py-20 text-center text-[var(--ink-2)]">Loading strength log…</div>
  const { summary, exercises, sessions } = data
  const unlogged = summary.whoop_sessions.filter((w) => !w.logged)

  const remove = async (id: number) => {
    if (!window.confirm('Delete this session and its sets?')) return
    await strengthRequest('DELETE', `sessions/${id}`)
    if (draft.id === id) setDraft(emptyDraft())
    reload()
  }

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
      <div className="flex flex-col gap-4 xl:col-span-5">
        <StrengthLogger draft={draft} setDraft={setDraft} exercises={exercises} sessions={sessions} whoop={summary.whoop_sessions} onSaved={reload} />

        <Card title="WHOOP strength workouts" subtitle={`${unlogged.length} without sets logged · newest first`} icon={<Activity className="size-4.5" />}>
          <div className="flex max-h-72 flex-col gap-1 overflow-y-auto">
            {summary.whoop_sessions.slice(0, 30).map((w) => (
              <div key={w.id} className="flex items-center justify-between gap-2 rounded-lg px-2 py-1.5 text-[12.5px] hover:bg-[var(--surface-2)]">
                <span className="tabular text-[var(--ink-2)]">{shortDate(w.date)} · {Math.round(w.duration_min ?? 0)} min · strain {w.strain ?? '—'} · avg {w.avg_hr ?? '—'} bpm</span>
                {w.logged
                  ? <span className="text-[11.5px] text-[var(--good)]">logged</span>
                  : <button onClick={() => setDraft({ ...emptyDraft(w.date, w.id), blocks: draft.id ? [] : draft.blocks })} className="text-[12px] text-[var(--strain)] underline underline-offset-4">Log sets</button>}
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="flex flex-col gap-4 xl:col-span-7">
        <LiftsCard summary={summary} />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BalanceCard summary={summary} />
          <RecoveryLinkCard summary={summary} />
        </div>
        <Card title="Logged sessions" subtitle={`${sessions.length} sessions`} icon={<Trophy className="size-4.5" />}>
          {!sessions.length ? <p className="text-sm text-[var(--ink-muted)]">Nothing logged yet. Start with today's workout, or pick a WHOOP workout on the left.</p> : (
            <div className="flex flex-col divide-y divide-[var(--border)]">
              {sessions.slice(0, 20).map((s) => {
                const names = [...new Set(s.sets.map((x) => x.exercise))]
                const working = s.sets.filter((x) => !x.warmup)
                return (
                  <div key={s.id} className="flex items-start justify-between gap-3 py-2">
                    <div className="min-w-0">
                      <div className="text-[13px] font-medium text-[var(--ink)]">{shortDate(s.date)} · {working.length} working sets{s.whoop_workout_id ? ' · WHOOP linked' : ''}</div>
                      <div className="truncate text-[12px] text-[var(--ink-2)]">{names.join(' · ')}</div>
                      {s.notes && <div className="truncate text-[11.5px] text-[var(--ink-muted)]">{s.notes}</div>}
                    </div>
                    <div className="flex shrink-0 gap-1">
                      <button aria-label="Edit session" onClick={() => setDraft(draftFromSession(s))} className="p-1.5 text-[var(--ink-muted)] hover:text-[var(--ink)]"><Pencil className="size-4" /></button>
                      <button aria-label="Delete session" onClick={() => remove(s.id)} className="p-1.5 text-[var(--ink-muted)] hover:text-[var(--critical)]"><Trash2 className="size-4" /></button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
