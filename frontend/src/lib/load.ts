/** Share of 1RM for `reps` at `rpe`: Epley with the reps left in reserve added (same maths as the server). */
export function pct1rm(reps: number, rpe: number) {
  if (reps === 1 && rpe >= 10) return 1
  return 1 / (1 + (reps + Math.max(0, 10 - rpe)) / 30)
}

export function e1rm(kg: number, reps: number, rpe: number) {
  if (!(kg > 0) || !(reps > 0) || reps > 12) return null
  return kg / pct1rm(reps, rpe)
}

export const roundTo = (kg: number, step: number) => Math.round(kg / step) * step

const kgFmt = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 })
export const fmtKg = (kg: number) => `${kgFmt.format(kg)} kg`
