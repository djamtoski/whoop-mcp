import type { StrengthSession } from '@/types'

export interface DraftSet { reps: string; weight_kg: string; rpe: string; warmup: boolean }
export interface Block { exercise_id: number; sets: DraftSet[] }
export interface Draft { id?: number; date: string; whoop_workout_id: string; notes: string; blocks: Block[] }

export const todayIso = () => {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}
export const emptyDraft = (date = todayIso(), whoop = ''): Draft => ({ date, whoop_workout_id: whoop, notes: '', blocks: [] })

export const toDraftSets = (sets: StrengthSession['sets']): DraftSet[] =>
  sets.map((s) => ({ reps: String(s.reps), weight_kg: String(s.weight_kg), rpe: s.rpe == null ? '' : String(s.rpe), warmup: s.warmup }))

/** Group a saved session's sets back into exercise blocks, in the order they were done. */
export function draftFromSession(s: StrengthSession, keepId = true): Draft {
  const blocks: Block[] = []
  for (const set of s.sets) {
    let b = blocks.find((x) => x.exercise_id === set.exercise_id)
    if (!b) blocks.push((b = { exercise_id: set.exercise_id, sets: [] }))
    b.sets.push(...toDraftSets([set]))
  }
  return keepId
    ? { id: s.id, date: s.date, whoop_workout_id: s.whoop_workout_id ?? '', notes: s.notes, blocks }
    : { ...emptyDraft(), blocks }
}
