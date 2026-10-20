import * as Tooltip from '@radix-ui/react-tooltip'
import { Moon, RefreshCw, Sun } from 'lucide-react'
import { useEffect, useState } from 'react'
import { isDemo, useInsights, useSummary } from './api'
import { CoachFeed } from './components/CoachFeed'
import { History } from './components/History'
import { RecoveryGauge } from './components/RecoveryGauge'
import { SleepCard } from './components/SleepCard'
import { StrainDial } from './components/StrainDial'
import { TrendsCard } from './components/TrendsCard'
import { WorkoutLog } from './components/WorkoutLog'
import { LabeledProgressIndicator } from './components/watermelon/labeled-progress-indicator'

function useTheme() {
  const initial = (() => {
    try {
      const saved = localStorage.getItem('theme')
      if (saved === 'light' || saved === 'dark') return saved
    } catch { /* storage unavailable */ }
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  })()
  const [theme, setTheme] = useState<'light' | 'dark'>(initial)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    try { localStorage.setItem('theme', theme) } catch { /* ignore */ }
  }, [theme])
  return [theme, setTheme] as const
}

export default function App() {
  const { state, reload } = useSummary()
  const { items, live } = useInsights()
  const [theme, setTheme] = useTheme()
  const [tab, setTab] = useState<'today' | 'history'>(() => (window.location.hash === '#history' ? 'history' : 'today'))

  return (
    <Tooltip.Provider>
      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:py-8">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="size-2.5 rounded-full bg-[var(--good)]" />
              <span className="text-[12px] font-semibold tracking-[0.18em] text-[var(--ink-muted)] uppercase">WHOOP · Triathlon</span>
              {(isDemo || (state.status === 'ready' && state.data.demo)) && (
                <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[11px] text-[var(--ink-muted)]">demo data</span>
              )}
            </div>
            <h1 className="mt-1 text-[26px] font-semibold tracking-tight text-[var(--ink)]">Readiness Dashboard</h1>
          </div>
          <div className="flex items-center gap-2">
            {state.status === 'ready' && (
              <span className="text-[12px] text-[var(--ink-muted)]">
                Updated {new Date(state.data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            <button onClick={reload} aria-label="Refresh" className="rounded-full border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--ink-2)] hover:text-[var(--ink)]">
              <RefreshCw className="size-4" />
            </button>
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme" className="rounded-full border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--ink-2)] hover:text-[var(--ink)]">
              {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
            </button>
          </div>
        </header>

        <nav className="mb-5 flex gap-1">
          {(['today', 'history'] as const).map((t) => (
            <button key={t} onClick={() => setTab(t)} className={`rounded-full border px-4 py-1.5 text-[13px] font-medium capitalize ${tab === t ? 'border-[var(--ink-muted)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)] hover:text-[var(--ink)]'}`}>{t}</button>
          ))}
        </nav>

        {tab === 'history' && <History />}

        {tab === 'today' && state.status === 'loading' && (
          <div className="flex min-h-[50vh] items-center justify-center">
            <LabeledProgressIndicator labels={['Syncing recovery', 'Reading sleep', 'Tallying strain', 'Computing trends']} progress="70%" intervalMs={1100} />
          </div>
        )}

        {tab === 'today' && state.status === 'error' && (
          <div className="mx-auto mt-10 max-w-lg rounded-[20px] border border-[var(--border)] bg-[var(--surface)] p-6 text-center">
            <h2 className="text-lg font-semibold text-[var(--ink)]">
              {state.kind === 'not_logged_in' ? 'Connect your WHOOP' : state.kind === 'network' ? 'Dashboard server unreachable' : 'WHOOP API error'}
            </h2>
            <p className="mt-2 text-sm text-[var(--ink-2)]">
              {state.kind === 'not_logged_in'
                ? <>Stop this server, run <code className="rounded bg-[var(--surface-2)] px-1.5 py-0.5">python -m whoop_mcp login</code>, then start it again.</>
                : state.detail}
            </p>
            <a href="/?demo=1" className="mt-4 inline-block text-sm text-[var(--strain)] underline underline-offset-4">Preview with demo data</a>
          </div>
        )}

        {tab === 'today' && state.status === 'ready' && (
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:col-span-8">
              <RecoveryGauge rec={state.data.recovery} series={state.data.trends.series} hrvBaseline28={state.data.trends.baselines_28d.hrv} />
              <StrainDial today={state.data.strain.days[0]} days={state.data.strain.days} rec={state.data.recovery} />
              <SleepCard report={state.data.sleep} />
              <TrendsCard trends={state.data.trends} />
              <div className="md:col-span-2"><WorkoutLog days={state.data.workout_days ?? state.data.strain.days} /></div>
            </div>
            <div className="xl:col-span-4">
              <div className="xl:sticky xl:top-6"><CoachFeed items={items} live={live} /></div>
            </div>
          </div>
        )}
      </div>
    </Tooltip.Provider>
  )
}
