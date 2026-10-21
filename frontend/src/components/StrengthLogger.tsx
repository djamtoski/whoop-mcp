import { Copy, Dumbbell, Plus, Trash2, X } from 'lucide-react'
import { useMemo, useState } from 'react'
import { strengthRequest } from '@/api'
import { type Block, type Draft, type DraftSet, draftFromSession, emptyDraft, toDraftSets, todayIso } from '@/lib/strengthDraft'
import type { Exercise, StrengthSession, WhoopStrengthSession } from '@/types'
import { Card } from './ui'

const shortDate = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
const time = (iso: string | null) => (iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '')
const input = 'tabular w-full rounded-lg border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-[13px] text-[var(--ink)] outline-none focus:border-[var(--ink-muted)]'

export function StrengthLogger({ draft, setDraft, exercises, sessions, whoop, onSaved }: {
  draft: Draft; setDraft: (d: Draft) => void; exercises: Exercise[]; sessions: StrengthSession[]
  whoop: WhoopStrengthSession[]; onSaved: () => void
}) {
  const [pick, setPick] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const byId = useMemo(() => new Map(exercises.map((e) => [e.id, e])), [exercises])
  const last = sessions.find((s) => s.id !== draft.id)

  // WHOOP strength workouts within a day of the chosen date, plus the one already linked.
  const near = whoop.filter((w) => Math.abs(Date.parse(w.date) - Date.parse(draft.date)) <= 86400000 || w.id === draft.whoop_workout_id)

  const lastSetsFor = (exId: number) => {
    for (const s of sessions) {
      if (s.id === draft.id) continue
      const sets = s.sets.filter((x) => x.exercise_id === exId && !x.warmup)
      if (sets.length) return { date: s.date, sets }
    }
    return null
  }

  const update = (fn: (blocks: Block[]) => Block[]) => setDraft({ ...draft, blocks: fn(draft.blocks.map((b) => ({ ...b, sets: [...b.sets] }))) })

  const addExercise = (exId: number) => {
    if (!exId || draft.blocks.some((b) => b.exercise_id === exId)) return
    const prev = lastSetsFor(exId)
    update((bs) => [...bs, { exercise_id: exId, sets: prev ? toDraftSets(prev.sets) : [{ reps: '8', weight_kg: '0', rpe: '', warmup: false }] }])
    setPick('')
  }

  const save = async () => {
    setError(null)
    const sets = draft.blocks.flatMap((b) => b.sets.map((s) => ({
      exercise_id: b.exercise_id, reps: Number(s.reps), weight_kg: Number(s.weight_kg || 0),
      rpe: s.rpe === '' ? null : Number(s.rpe), warmup: s.warmup,
    })))
    if (!sets.length) return setError('Add at least one exercise.')
    setBusy(true)
    try {
      const body = { date: draft.date, sets, notes: draft.notes, whoop_workout_id: draft.whoop_workout_id || null }
      await (draft.id ? strengthRequest('PUT', `sessions/${draft.id}`, body) : strengthRequest('POST', 'sessions', body))
      setDraft(emptyDraft())
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusy(false)
    }
  }

  const unused = exercises.filter((e) => !draft.blocks.some((b) => b.exercise_id === e.id))

  return (
    <Card title={draft.id ? 'Edit session' : 'Log a session'} subtitle="Sets, reps and kg · linked to the WHOOP workout for strain and heart rate" icon={<Dumbbell className="size-4.5" />}
      action={draft.id || draft.blocks.length
        ? <button onClick={() => setDraft(emptyDraft())} className="flex items-center gap-1 rounded-full border border-[var(--border)] px-2.5 py-1 text-[12px] text-[var(--ink-2)]"><X className="size-3.5" />Clear</button>
        : last && <button onClick={() => setDraft({ ...draftFromSession(last, false), date: draft.date, whoop_workout_id: draft.whoop_workout_id })} className="flex items-center gap-1 rounded-full border border-[var(--border)] px-2.5 py-1 text-[12px] text-[var(--ink-2)]"><Copy className="size-3.5" />Repeat {shortDate(last.date)}</button>}>
      <div className="flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[150px_1fr]">
          <label className="flex flex-col gap-1 text-[11.5px] text-[var(--ink-muted)]">Date
            <input type="date" value={draft.date} max={todayIso()} onChange={(e) => setDraft({ ...draft, date: e.target.value })} className={input} />
          </label>
          <label className="flex flex-col gap-1 text-[11.5px] text-[var(--ink-muted)]">WHOOP workout
            <select value={draft.whoop_workout_id} onChange={(e) => setDraft({ ...draft, whoop_workout_id: e.target.value })} className={input}>
              <option value="">Not linked</option>
              {near.map((w) => (
                <option key={w.id} value={w.id}>
                  {shortDate(w.date)} {time(w.start)} · {Math.round(w.duration_min ?? 0)} min · strain {w.strain ?? '—'}{w.logged && w.id !== draft.whoop_workout_id ? ' · already logged' : ''}
                </option>
              ))}
            </select>
          </label>
        </div>

        {draft.blocks.map((b, bi) => {
          const ex = byId.get(b.exercise_id)
          const prev = lastSetsFor(b.exercise_id)
          return (
            <div key={b.exercise_id} className="rounded-xl bg-[var(--surface-2)] p-3">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div>
                  <div className="text-[14px] font-medium text-[var(--ink)]">{ex?.name}</div>
                  <div className="text-[11.5px] text-[var(--ink-muted)]">
                    {prev ? `Last ${shortDate(prev.date)}: ${prev.sets.map((s) => `${s.reps}×${s.weight_kg}`).join(', ')} kg` : 'First time logged'}
                    {ex?.bodyweight && ' · kg = added load'}
                  </div>
                </div>
                <button aria-label={`Remove ${ex?.name}`} onClick={() => update((bs) => bs.filter((_, i) => i !== bi))} className="p-1 text-[var(--ink-muted)] hover:text-[var(--critical)]"><Trash2 className="size-4" /></button>
              </div>
              <div className="grid grid-cols-[24px_1fr_1fr_1fr_44px_24px] items-center gap-1.5 text-[11px] text-[var(--ink-muted)]">
                <span>#</span><span>Reps</span><span>kg</span><span>RPE</span><span>Warm</span><span />
                {b.sets.map((s, si) => {
                  const set = (patch: Partial<DraftSet>) => update((bs) => { bs[bi].sets[si] = { ...bs[bi].sets[si], ...patch }; return bs })
                  return [
                    <span key={`n${si}`} className="tabular text-[12px] text-[var(--ink-2)]">{si + 1}</span>,
                    <input key={`r${si}`} aria-label="Reps" inputMode="numeric" value={s.reps} onChange={(e) => set({ reps: e.target.value })} className={input} />,
                    <input key={`k${si}`} aria-label="Weight kg" inputMode="decimal" value={s.weight_kg} onChange={(e) => set({ weight_kg: e.target.value })} className={input} />,
                    <input key={`p${si}`} aria-label="RPE" inputMode="decimal" placeholder="—" value={s.rpe} onChange={(e) => set({ rpe: e.target.value })} className={input} />,
                    <input key={`w${si}`} aria-label="Warm-up set" type="checkbox" checked={s.warmup} onChange={(e) => set({ warmup: e.target.checked })} className="mx-auto size-4 accent-[var(--strength)]" />,
                    <button key={`x${si}`} aria-label="Remove set" onClick={() => update((bs) => { bs[bi].sets.splice(si, 1); return bs.filter((x) => x.sets.length) })} className="text-[var(--ink-muted)] hover:text-[var(--critical)]"><X className="size-3.5" /></button>,
                  ]
                })}
              </div>
              <button onClick={() => update((bs) => { const l = bs[bi].sets.at(-1); bs[bi].sets.push(l ? { ...l, warmup: false } : { reps: '8', weight_kg: '0', rpe: '', warmup: false }); return bs })}
                className="mt-2 flex items-center gap-1 text-[12px] text-[var(--strain)]"><Plus className="size-3.5" />Add set</button>
            </div>
          )
        })}

        <div className="flex gap-2">
          <select value={pick} onChange={(e) => addExercise(Number(e.target.value))} className={input} aria-label="Add exercise">
            <option value="">+ Add exercise…</option>
            {['lower', 'upper', 'core'].map((r) => (
              <optgroup key={r} label={r[0].toUpperCase() + r.slice(1)}>
                {unused.filter((e) => e.region === r).map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
              </optgroup>
            ))}
          </select>
        </div>

        <textarea placeholder="Notes (optional)" value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} rows={2} className={input} />

        {error && <p role="alert" className="text-[12.5px] text-[var(--critical)]">{error}</p>}
        <button onClick={save} disabled={busy || !draft.blocks.length}
          className="rounded-full bg-[var(--ink)] px-4 py-2 text-[13px] font-medium text-[var(--surface)] disabled:opacity-40">
          {busy ? 'Saving…' : draft.id ? 'Save changes' : 'Save session'}
        </button>
      </div>
    </Card>
  )
}
