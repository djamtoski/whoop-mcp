import type { Workout } from '@/types'

// WHOOP sport ids as people say them; anything else is title-cased from the id.
const NAMES: Record<string, string> = {
  running: 'Run', cycling: 'Ride', swimming: 'Swim', walking: 'Walk', hiking: 'Hike',
  weightlifting: 'Strength', weightlifting_msk: 'Strength', functional_fitness: 'Functional fitness',
  activity: 'Activity', meditation: 'Meditation', yoga: 'Yoga', triathlon: 'Triathlon',
}

export function sportName(sport: string) {
  if (NAMES[sport]) return NAMES[sport]
  const words = sport.replace(/_msk$/, '').replace(/[_-]+/g, ' ').trim()
  return words ? words[0].toUpperCase() + words.slice(1) : 'Workout'
}

const MERGE_GAP_MIN = 10

const endMs = (w: Workout) => new Date(w.start).getTime() + (w.duration_min ?? 0) * 60_000

/**
 * Join sessions WHOOP split in two (e.g. a swim paused at the wall): same sport, same day,
 * the second starting within 10 minutes of the first ending. Input and output are newest first.
 */
export function mergeSplitSessions(workouts: Workout[]): Workout[] {
  const out: Workout[] = []
  for (const w of [...workouts].reverse()) {
    const prev = out[out.length - 1]
    const gap = prev && w.start && prev.start ? (new Date(w.start).getTime() - endMs(prev)) / 60_000 : Infinity
    if (!prev || prev.sport !== w.sport || prev.date !== w.date || gap > MERGE_GAP_MIN || gap < -1) {
      out.push(w)
      continue
    }
    const a = prev.duration_min ?? 0, b = w.duration_min ?? 0
    const sum = (x: number | null, y: number | null) => (x == null && y == null ? null : (x ?? 0) + (y ?? 0))
    out[out.length - 1] = {
      ...prev,
      id: `${prev.id}+${w.id}`,
      duration_min: sum(prev.duration_min, w.duration_min),
      // Strain is not additive; the harder part is the closest single number.
      strain: Math.max(prev.strain ?? 0, w.strain ?? 0) || null,
      avg_hr: prev.avg_hr != null && w.avg_hr != null && a + b > 0 ? Math.round((prev.avg_hr * a + w.avg_hr * b) / (a + b)) : prev.avg_hr ?? w.avg_hr,
      max_hr: Math.max(prev.max_hr ?? 0, w.max_hr ?? 0) || null,
      kilojoules: sum(prev.kilojoules, w.kilojoules),
      distance_km: sum(prev.distance_km, w.distance_km),
      zone_minutes: prev.zone_minutes && w.zone_minutes
        ? Object.fromEntries(Object.entries(prev.zone_minutes).map(([k, v]) => [k, v + (w.zone_minutes?.[k as keyof typeof prev.zone_minutes] ?? 0)])) as Workout['zone_minutes']
        : prev.zone_minutes ?? w.zone_minutes,
      parts: (prev.parts ?? 1) + 1,
    }
  }
  return out.reverse()
}

const dateFmt = new Intl.DateTimeFormat(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
const shortFmt = new Intl.DateTimeFormat(undefined, { weekday: 'short', day: 'numeric', month: 'short' })

export const longDate = (d: Date) => dateFmt.format(d)
export const shortDate = (iso: string) => shortFmt.format(new Date(iso + 'T12:00:00'))
