export type Zone = 'green' | 'yellow' | 'red'

export interface TargetStrain { low: number; high: number; guidance: string; derived: boolean }

export interface Recovery {
  date: string
  available: boolean
  stale?: boolean
  message?: string
  recovery_score?: number | null
  readiness_zone?: Zone | null
  user_calibrating?: boolean
  hrv_rmssd_ms?: number | null
  hrv_baseline_7d_ms?: number | null
  hrv_vs_baseline_pct?: number | null
  resting_hr?: number | null
  rhr_baseline_7d?: number | null
  rhr_vs_baseline_bpm?: number | null
  spo2_pct?: number | null
  skin_temp_c?: number | null
  skin_temp_deviation_c?: number | null
  respiratory_rate?: number | null
  respiratory_rate_deviation?: number | null
  stress_estimate?: { score: number; level: 'low' | 'medium' | 'high'; derived: boolean } | null
  target_strain?: TargetStrain | null
}

export interface SleepSummary {
  date: string
  performance_pct: number | null
  efficiency_pct: number | null
  consistency_pct: number | null
  respiratory_rate: number | null
  hours_in_bed: number | null
  hours_asleep: number | null
  hours_needed: number | null
  awakenings: number | null
  sleep_cycles: number | null
  stages_h: { deep_sws: number | null; rem: number | null; light: number | null; awake: number | null } | null
}

export interface SleepReport {
  date: string
  available: boolean
  sleep: SleepSummary | null
  naps: SleepSummary[]
  sleep_debt: {
    whoop_debt_component_h: number | null
    tonight_shortfall_h: number | null
    rolling_7d_h: number | null
    nights: { date: string; needed_h: number; asleep_h: number; balance_h: number }[]
  }
}

export type Discipline = 'swim' | 'bike' | 'run' | 'tri' | 'strength' | 'recovery' | 'other'

export interface Workout {
  id: string
  date: string
  start: string
  sport: string
  discipline: Discipline
  duration_min: number | null
  strain: number | null
  avg_hr: number | null
  max_hr: number | null
  kilojoules: number | null
  distance_km: number | null
  zone_minutes: Record<'z0' | 'z1' | 'z2' | 'z3' | 'z4' | 'z5', number> | null
}

export interface StrainDay {
  date: string
  day_strain: number | null
  in_progress: boolean | null
  kilojoules: number | null
  recovery_score: number | null
  target_strain: TargetStrain | null
  workouts: Workout[]
}

export interface TrendPoint {
  date: string
  recovery: number | null
  hrv: number | null
  rhr: number | null
  day_strain: number | null
  sleep_performance: number | null
  hours_asleep: number | null
  hours_needed: number | null
}

export interface Trends {
  series: TrendPoint[]
  averages_7d: Record<string, number | null>
  baselines_28d: { hrv: number | null; rhr: number | null; day_strain: number | null }
  hrv_trend: string | null
  rhr_trend: string | null
  acute_chronic_strain_ratio: number | null
  overtraining_flags: string[]
  status: 'ok' | 'watch' | 'caution'
}

export interface Summary {
  generated_at: string
  demo: boolean
  recovery: Recovery
  sleep: SleepReport
  workout_days?: StrainDay[]
  strain: { days: StrainDay[]; discipline_totals: Record<string, { sessions: number; minutes: number; kilojoules: number; distance_km: number }> }
  trends: Trends
}

export interface HistoryDay {
  date: string
  recovery?: number | null; hrv?: number | null; rhr?: number | null; spo2?: number | null; skin_temp?: number | null
  strain?: number | null; kj?: number | null; steps?: number | null
  sleep_h?: number | null; need_h?: number | null; sleep_perf?: number | null; efficiency?: number | null; consistency?: number | null
  resp?: number | null; deep_h?: number | null; rem_h?: number | null; light_h?: number | null; awake_h?: number | null
}

export interface HistoryWorkout {
  date: string; start: string; sport: string; discipline: string
  minutes: number | null; strain: number | null; avg_hr: number | null; max_hr: number | null
  kj: number | null; km: number | null; zones: number[]
}

export type TrainingDiscipline = 'swim' | 'bike' | 'run' | 'strength'

export interface LoadWeek {
  week: string; hours: Record<TrainingDiscipline, number>; sessions: number; total_hours: number; avg_strain: number | null
}

export interface HistoryAnalytics {
  load: { weeks: LoadWeek[]; last_session: Record<TrainingDiscipline, { date: string | null; days: number | null }>; as_of: string | null }
  run_zones: { discipline: string; easy_target_pct: number; overall: ZoneSummary; months: (ZoneSummary & { month: string })[] }
  sleep_recovery: {
    points: { date: string; sleep_h: number; recovery: number }[]
    buckets: { low: number; high: number | null; nights: number; avg_recovery: number | null }[]
    correlation: number | null
    target_h: number | null
  }
}

export interface ZoneSummary { runs: number; minutes: number[]; pct: number[]; easy_pct: number | null }

export type History =
  | { available: false }
  | {
      available: true
      exported_at: string | null
      counts: { cycles: number; recoveries: number; sleeps: number; workouts: number } | null
      body: Record<string, number> | null
      days: HistoryDay[]
      workouts: HistoryWorkout[]
      analytics?: HistoryAnalytics
      monthly: Record<string, number | string | null>[]
    }

export interface Insight { id: string; created_at: string; title: string | null; markdown: string }

export interface Exercise {
  id: number; name: string; pattern: string; muscles: string[]; push_pull: 'push' | 'pull' | 'none'
  region: 'upper' | 'lower' | 'core'; bodyweight: boolean
}

export interface StrengthSet { exercise_id: number; exercise?: string; reps: number; weight_kg: number; rpe: number | null; warmup: boolean }

export interface StrengthSession { id: number; date: string; whoop_workout_id: string | null; notes: string; created_at: string; sets: StrengthSet[] }

export interface LiftPoint {
  date: string; session_id: number; sets: number; reps: number; volume_kg: number
  e1rm: number | null; top_set: { kg: number; reps: number }; pr: boolean
}

export interface LiftProgress {
  exercise_id: number; name: string; pattern: string; muscles: string[]; sessions: number; last_date: string
  pr_e1rm: number | null; pr_date: string | null; change_4w_pct: number | null; points: LiftPoint[]
}

export interface BalanceWeek {
  week: string; sessions: number; sets: number; volume_kg: number
  muscles: Record<string, number>; push: number; pull: number; region: Record<string, number>
}

export interface WhoopStrengthSession {
  id: string; date: string; start: string | null; sport: string; duration_min: number | null
  strain: number | null; avg_hr: number | null; max_hr: number | null; logged: boolean
}

export interface StrengthSummary {
  sessions: number
  body_kg: number | null
  progress: LiftProgress[]
  balance: { targets: { low: number; high: number }; weeks: BalanceWeek[] }
  recovery: {
    sessions: { session_id: number; date: string; recovery: number | null; next_recovery: number | null; performance_pct: number | null }[]
    by_zone: Record<'green' | 'yellow' | 'red', { sessions: number; avg_performance_pct: number | null }>
    avg_next_day_change: number | null
  }
  whoop_sessions: WhoopStrengthSession[]
}
