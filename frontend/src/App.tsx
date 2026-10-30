import * as Tooltip from '@radix-ui/react-tooltip'
import { Moon, RefreshCw, Sun } from 'lucide-react'
import { MotionConfig } from 'motion/react'
import { useEffect, useState } from 'react'
import { isDemo, useInsights, useSummary } from './api'
import { CoachFeed } from './components/CoachFeed'
import { History } from './components/History'
import { PlanTab } from './components/PlanTab'
import { StrengthTab } from './components/StrengthTab'
import { RecoveryGauge } from './components/RecoveryGauge'
import { SleepCard } from './components/SleepCard'
import { StrainDial } from './components/StrainDial'
import { TodayBand } from './components/TodayBand'
import { TrendsCard } from './components/TrendsCard'
import { WorkoutLog } from './components/WorkoutLog'
import { LabeledProgressIndicator } from './components/watermelon/labeled-progress-indicator'
import { longDate } from './lib/sports'

const TABS = ['today', 'plan', 'strength', 'history'] as const
type Tab = (typeof TABS)[number]

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

function tabFromHash(): Tab {
  return TABS.find((t) => `#${t}` === window.location.hash) ?? 'today'
}

export default function App() {
  const { state, reload } = useSummary()
  const { items, live } = useInsights()
  const [theme, setTheme] = useTheme()
  const [tab, setTabState] = useState<Tab>(tabFromHash)
  const setTab = (t: Tab) => {
    setTabState(t)
    window.history.replaceState(null, '', t === 'today' ? window.location.pathname + window.location.search : `#${t}`)
  }
  // A typed or linked #plan / #strength / #history switches tabs; #coach (a link within Today) keeps Today.
  useEffect(() => {
    const onHash = () => setTabState(tabFromHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  return (
    <MotionConfig reducedMotion="user">
    <Tooltip.Provider>
      <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6 lg:py-8">
        <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 text-[13px] text-[var(--ink-muted)]">
              WHOOP triathlon dashboard
              {(isDemo || (state.status === 'ready' && state.data.demo)) && (
                <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[11px]">demo data</span>
              )}
            </p>
            <h1 className="font-display text-[34px] leading-tight font-bold text-[var(--ink)]">{state.status === 'ready' ? longDate(new Date(state.data.generated_at)) : 'Today'}</h1>
          </div>
          <div className="flex items-center gap-2">
            {state.status === 'ready' && (
              <span className="text-[12.5px] text-[var(--ink-muted)]">
                Updated {new Date(state.data.generated_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              </span>
            )}
            <button onClick={reload} aria-label="Refresh" className="rounded-full border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--ink-2)] hover:text-[var(--ink)] focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none">
              <RefreshCw className="size-4" aria-hidden />
            </button>
            <button onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme" className="rounded-full border border-[var(--border)] bg-[var(--surface)] p-2 text-[var(--ink-2)] hover:text-[var(--ink)] focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none">
              {theme === 'dark' ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
            </button>
          </div>
        </header>

        <nav className="mb-5 flex gap-1">
          {TABS.map((t) => (
            <button key={t} onClick={() => setTab(t)} aria-current={tab === t ? 'page' : undefined} className={`rounded-full border px-4 py-1.5 text-[14px] font-medium capitalize focus-visible:ring-2 focus-visible:ring-[var(--strain)] focus-visible:outline-none ${tab === t ? 'border-[var(--ink-muted)] bg-[var(--surface-2)] text-[var(--ink)]' : 'border-[var(--border)] text-[var(--ink-2)] hover:text-[var(--ink)]'}`}>{t}</button>
          ))}
        </nav>

        {tab === 'history' && <History />}
        {tab === 'strength' && <StrengthTab />}
        {tab === 'plan' && <PlanTab />}

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
          <div className="flex flex-col gap-4">
          <TodayBand data={state.data} latest={items[0]} />
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-12">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:col-span-8">
              <RecoveryGauge rec={state.data.recovery} series={state.data.trends.series} baselines28={state.data.trends.baselines_28d} />
              <StrainDial today={state.data.strain.days[0]} days={state.data.strain.days} rec={state.data.recovery} />
              <SleepCard report={state.data.sleep} />
              <TrendsCard trends={state.data.trends} />
              <div className="md:col-span-2"><WorkoutLog days={state.data.workout_days ?? state.data.strain.days} /></div>
            </div>
            <div className="xl:col-span-4">
              <div id="coach" className="scroll-mt-6 xl:sticky xl:top-6"><CoachFeed items={items} live={live} /></div>
            </div>
          </div>
          </div>
        )}
      </div>
    </Tooltip.Provider>
    </MotionConfig>
  )
}
