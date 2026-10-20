import { Sparkles } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Insight } from '@/types'
import { Card } from './ui'

function ago(iso: string) {
  const s = (Date.now() - new Date(iso).getTime()) / 1000
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function CoachFeed({ items, live }: { items: Insight[]; live: boolean }) {
  return (
    <Card
      title="Live AI Coaching"
      subtitle="Pushed by Claude via update_dashboard_insights"
      icon={<Sparkles className="size-4.5" />}
      action={
        <span className="flex items-center gap-1.5 text-[12px] text-[var(--ink-muted)]">
          <span className="relative flex size-2">
            {live && <span className="absolute inline-flex size-full animate-ping rounded-full bg-[var(--good)] opacity-60" />}
            <span className="relative inline-flex size-2 rounded-full" style={{ background: live ? 'var(--good)' : 'var(--ink-muted)' }} />
          </span>
          {live ? 'Live' : 'Offline'}
        </span>
      }
      className="h-full"
    >
      {items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
          <Sparkles className="size-5 text-[var(--ink-muted)]" />
          <p className="text-sm text-[var(--ink-2)]">No coaching notes yet.</p>
          <p className="max-w-xs text-[12.5px] text-[var(--ink-muted)]">
            Ask Claude to analyse your WHOOP data and update the dashboard. New notes appear here instantly.
          </p>
        </div>
      ) : (
        <div className="flex max-h-[720px] flex-col gap-3 overflow-y-auto pr-1">
          <AnimatePresence initial={false}>
            {items.map((it, i) => (
              <motion.article
                key={it.id}
                layout
                initial={{ opacity: 0, y: -16, scale: 0.98, filter: 'blur(4px)' }}
                animate={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)' }}
                exit={{ opacity: 0 }}
                transition={{ type: 'spring', bounce: 0.15, duration: 0.6 }}
                className={`rounded-xl border p-4 ${i === 0 ? 'border-[var(--strain)]/40 bg-[var(--surface-2)]' : 'border-[var(--border)] bg-transparent'}`}
              >
                <div className="mb-2 flex items-center justify-between gap-2">
                  <h3 className="truncate text-[14px] font-semibold text-[var(--ink)]">{it.title ?? 'Coaching update'}</h3>
                  <time className="shrink-0 text-[11.5px] text-[var(--ink-muted)]" dateTime={it.created_at}>{ago(it.created_at)}</time>
                </div>
                {/* react-markdown does not render raw HTML by default — model output stays sanitized. */}
                <div className="prose-coach"><Markdown remarkPlugins={[remarkGfm]}>{it.markdown}</Markdown></div>
              </motion.article>
            ))}
          </AnimatePresence>
        </div>
      )}
    </Card>
  )
}
