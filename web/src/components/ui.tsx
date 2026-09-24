import React from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  Cpu,
  History,
  Inbox,
  XCircle,
} from 'lucide-react'

/* ------------------------------------------------------------------ */
/* Tool header: serif title, blurb, oversized Indic glyph watermark    */
/* ------------------------------------------------------------------ */
export const ToolHeader: React.FC<{
  icon: React.ReactNode
  title: string
  blurb: string
  glyph: string
  right?: React.ReactNode
  tileClass: string
}> = ({ icon, title, blurb, glyph, right, tileClass }) => (
  <div className="panel relative overflow-hidden px-5 py-4 sm:px-6">
    <span
      aria-hidden
      className="glyph-mark absolute -right-2 -top-7 text-[104px] sm:text-[120px]"
    >
      {glyph}
    </span>
    <div className="relative flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-3.5">
        <div className={`rounded-xl border p-2.5 ${tileClass}`}>{icon}</div>
        <div>
          <h2 className="font-display text-xl font-semibold tracking-tight text-parchment-100">
            {title}
          </h2>
          <p className="mt-0.5 max-w-xl text-[13px] leading-snug text-parchment-400">
            {blurb}
          </p>
        </div>
      </div>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  </div>
)

/* ------------------------------------------------------------------ */
/* Engine availability pill                                            */
/* ------------------------------------------------------------------ */
export const StatusPill: React.FC<{ available: boolean; label?: string }> = ({
  available,
  label,
}) =>
  available ? (
    <span className="pill-ready">
      <CheckCircle2 className="h-3 w-3" /> {label ?? 'Ready'}
    </span>
  ) : (
    <span className="pill-idle">
      <XCircle className="h-3 w-3" /> {label ?? 'Needs setup'}
    </span>
  )

/* ------------------------------------------------------------------ */
/* Error callout                                                       */
/* ------------------------------------------------------------------ */
export const ErrorBox: React.FC<{ message: string }> = ({ message }) => (
  <div className="flex items-start gap-2.5 rounded-xl border border-clay-500/40 bg-clay-500/10 p-3 text-xs leading-relaxed text-clay-300">
    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
    <span>{message}</span>
  </div>
)

/* ------------------------------------------------------------------ */
/* Empty state                                                         */
/* ------------------------------------------------------------------ */
export const EmptyState: React.FC<{
  icon: React.ReactNode
  title: string
  hint: string
}> = ({ icon, title, hint }) => (
  <div className="flex h-48 flex-col items-center justify-center text-center">
    <div className="mb-3 rounded-2xl border border-ink-700/70 bg-ink-900 p-3 text-parchment-500">
      {icon}
    </div>
    <span className="text-sm font-semibold text-parchment-300">{title}</span>
    <span className="mt-1 text-xs text-parchment-500">{hint}</span>
  </div>
)

/* ------------------------------------------------------------------ */
/* Metadata chip row                                                   */
/* ------------------------------------------------------------------ */
export interface MetaItem {
  label: string
  value: string
  tone?: 'live' | 'hit'
}

export const MetaBar: React.FC<{ items: MetaItem[] }> = ({ items }) => (
  <div className="flex flex-wrap items-center gap-2 border-t divider pt-3">
    {items.map((item) => (
      <span
        key={`${item.label}-${item.value}`}
        title={item.label}
        className={`meta-chip ${
          item.tone === 'hit'
            ? '!border-moss-500/40 !bg-moss-500/10 !text-moss-300'
            : ''
        }`}
      >
        {item.tone === 'hit' ? (
          <>✓ {item.value}</>
        ) : (
          <>
            <span className="text-parchment-500">{item.label}: </span>
            {item.value}
          </>
        )}
      </span>
    ))}
  </div>
)

/* ------------------------------------------------------------------ */
/* Collapsible model-override drawer                                   */
/* ------------------------------------------------------------------ */
export const ModelDrawer: React.FC<{
  open: boolean
  title: string
  presets: string[]
  modelId: string
  onChange: (v: string) => void
  placeholder: string
}> = ({ open, title, presets, modelId, onChange, placeholder }) => {
  if (!open) return null
  return (
    <div className="drawer animate-fade-in">
      <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-center">
        <div className="flex items-center gap-2 text-xs font-semibold text-parchment-200">
          <Cpu className="h-4 w-4 text-marigold-300" />
          <span>{title}</span>
        </div>
        {presets.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] text-parchment-500">Presets:</span>
            {presets.map((preset) => (
              <button
                key={preset}
                type="button"
                onClick={() => onChange(preset)}
                className={`rounded-md px-2 py-0.5 font-mono text-[11px] transition ${
                  modelId === preset
                    ? 'bg-marigold-500 text-ink-950'
                    : 'bg-ink-700/70 text-parchment-300 hover:bg-ink-600'
                }`}
              >
                {preset}
              </button>
            ))}
          </div>
        )}
      </div>
      <input
        type="text"
        value={modelId}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="field field-mono !bg-ink-850"
      />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Labeled form field                                                  */
/* ------------------------------------------------------------------ */
export const Field: React.FC<{
  label: string
  action?: React.ReactNode
  children: React.ReactNode
}> = ({ label, action, children }) => (
  <div className="space-y-1.5">
    <div className="flex items-center justify-between">
      <label className="eyebrow">{label}</label>
      {action}
    </div>
    {children}
  </div>
)

/* ------------------------------------------------------------------ */
/* Recent-runs history strip (localStorage, additive)                 */
/* ------------------------------------------------------------------ */
export function HistoryStrip<T>({
  items,
  onRestore,
  onClear,
  renderLabel,
  renderSub,
}: {
  items: T[]
  onRestore: (item: T) => void
  onClear: () => void
  renderLabel: (item: T) => string
  renderSub: (item: T) => string
}) {
  if (items.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2 border-t divider pt-3 text-xs">
      <span className="flex items-center gap-1 font-semibold text-parchment-500">
        <History className="h-3.5 w-3.5" /> Recent:
      </span>
      {items.map((item, idx) => (
        <button
          // eslint-disable-next-line react/no-array-index-key
          key={idx}
          type="button"
          title={renderSub(item)}
          onClick={() => onRestore(item)}
          className="sample-btn max-w-[220px] truncate"
        >
          {renderLabel(item)}
        </button>
      ))}
      <button type="button" onClick={onClear} className="btn-quiet">
        Clear
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Definition-list style metadata table (STT / TTS result panels)      */
/* ------------------------------------------------------------------ */
export const MetaTable: React.FC<{ rows: Array<[string, string]> }> = ({
  rows,
}) => (
  <div className="space-y-2 border-t divider pt-4 text-xs">
    {rows.map(([k, v]) => (
      <div key={k} className="flex items-baseline justify-between gap-3">
        <span className="shrink-0 text-parchment-500">{k}</span>
        <span className="truncate text-right font-medium text-parchment-100">
          {v}
        </span>
      </div>
    ))}
  </div>
)

/* ------------------------------------------------------------------ */
/* Result panel shell (right-hand column on STT / TTS)                 */
/* ------------------------------------------------------------------ */
export const ResultPanel: React.FC<{
  title: string
  badge?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
}> = ({ title, badge, actions, children }) => (
  <div className="panel flex min-h-[380px] flex-col p-5 sm:p-6">
    <div className="flex items-center justify-between gap-2 border-b divider pb-3">
      <span className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.14em] text-parchment-300">
        {title}
        {badge}
      </span>
      {actions}
    </div>
    <div className="mt-4 flex flex-1 flex-col justify-between gap-4">
      {children}
    </div>
  </div>
)

export const EmptyInboxIcon: React.FC<{ className?: string }> = ({
  className,
}) => <Inbox className={className ?? 'h-10 w-10 opacity-40'} />
