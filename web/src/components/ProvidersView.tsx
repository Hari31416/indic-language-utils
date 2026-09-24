import React, { useState } from 'react'
import {
  ArrowUpRight,
  CheckCircle2,
  Cpu,
  KeyRound,
  Keyboard,
  Languages,
  Layers,
  Mic,
  Search,
  Volume2,
  XCircle,
} from 'lucide-react'
import type { LanguageItem, ProviderInfo, ProvidersResponse } from '../types'
import { StatusPill, ToolHeader } from './ui'

interface ProvidersViewProps {
  languages: LanguageItem[]
  providersData: ProvidersResponse | null
  onOpenApiKeysModal: () => void
  onOpenTool?: (tool: 'translate' | 'transliterate' | 'detect' | 'stt' | 'tts') => void
}

type ToolId = 'translate' | 'transliterate' | 'detect' | 'stt' | 'tts'

const GROUPS: Array<{
  key: keyof ProvidersResponse
  title: string
  icon: React.ReactNode
  tile: string
  tool: ToolId
}> = [
  {
    key: 'translation',
    title: 'Translation',
    icon: <Cpu className="h-4 w-4" />,
    tile: 'border-marigold-500/30 bg-marigold-500/10 text-marigold-300',
    tool: 'translate',
  },
  {
    key: 'transliteration',
    title: 'Transliteration',
    icon: <Keyboard className="h-4 w-4" />,
    tile: 'border-peacock-500/30 bg-peacock-500/10 text-peacock-300',
    tool: 'transliterate',
  },
  {
    key: 'detection',
    title: 'Detection',
    icon: <Languages className="h-4 w-4" />,
    tile: 'border-orchid-500/30 bg-orchid-500/10 text-orchid-300',
    tool: 'detect',
  },
  {
    key: 'speech_to_text',
    title: 'Speech to Text',
    icon: <Mic className="h-4 w-4" />,
    tile: 'border-clay-500/30 bg-clay-500/10 text-clay-300',
    tool: 'stt',
  },
  {
    key: 'text_to_speech',
    title: 'Text to Speech',
    icon: <Volume2 className="h-4 w-4" />,
    tile: 'border-rosewood-500/30 bg-rosewood-500/10 text-rosewood-300',
    tool: 'tts',
  },
]

type Availability = 'all' | 'ready' | 'setup'

export const ProvidersView: React.FC<ProvidersViewProps> = ({
  languages,
  providersData,
  onOpenApiKeysModal,
  onOpenTool,
}) => {
  const [searchQuery, setSearchQuery] = useState('')
  const [scriptFilter, setScriptFilter] = useState('all')
  const [availability, setAvailability] = useState<Availability>('all')

  const all: ProviderInfo[] = providersData
    ? [
        ...providersData.translation,
        ...providersData.transliteration,
        ...providersData.detection,
        ...providersData.speech_to_text,
        ...providersData.text_to_speech,
      ]
    : []
  const readyCount = all.filter((p) => p.available).length

  const visible = (p: ProviderInfo) => {
    if (availability === 'ready' && !p.available) return false
    if (availability === 'setup' && p.available) return false
    return true
  }

  const scripts = Array.from(
    new Set(languages.map((l) => l.script).filter((s): s is string => !!s)),
  ).sort()

  const filteredLanguages = languages.filter(
    (lang) =>
      (scriptFilter === 'all' || lang.script === scriptFilter) &&
      (lang.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        lang.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (lang.script && lang.script.toLowerCase().includes(searchQuery.toLowerCase()))),
  )

  return (
    <div className="space-y-5">
      <ToolHeader
        icon={<Layers className="h-4 w-4" />}
        tileClass="border-moss-500/30 bg-moss-500/10 text-moss-300"
        title="Engines & Registry"
        blurb="Live adapter health, model capabilities, and the full registry of supported Indian languages."
        glyph="ऊ"
        right={
          <button type="button" onClick={onOpenApiKeysModal} className="btn-primary !py-2">
            <KeyRound className="h-4 w-4" /> Configure API keys
          </button>
        }
      />

      {/* Health overview */}
      <div className="panel flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <div className="flex items-center gap-4">
          <div className="font-display text-4xl font-semibold tracking-tight">
            {readyCount}
            <span className="text-xl text-parchment-500">/{all.length}</span>
          </div>
          <div>
            <p className="text-sm font-semibold text-parchment-100">engines ready</p>
            <p className="text-xs text-parchment-500">
              Unconfigured adapters need API keys or local models
            </p>
          </div>
        </div>
        <div className="h-2 flex-1 overflow-hidden rounded-full border border-ink-700 bg-ink-900">
          <div
            className="h-full rounded-full bg-gradient-to-r from-moss-500 via-peacock-400 to-marigold-400 transition-all duration-700"
            style={{ width: `${all.length === 0 ? 0 : Math.round((readyCount / all.length) * 100)}%` }}
          />
        </div>
        <div className="seg w-fit">
          {(['all', 'ready', 'setup'] as Availability[]).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setAvailability(f)}
              className={`seg-btn ${availability === f ? 'seg-btn-active' : ''}`}
            >
              {f === 'all' ? 'All' : f === 'ready' ? (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" /> Ready
                </>
              ) : (
                <>
                  <XCircle className="h-3.5 w-3.5" /> Needs setup
                </>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Engine groups */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        {GROUPS.map((group) => {
          const list = (providersData?.[group.key] ?? []).filter(visible)
          const total = providersData?.[group.key]?.length ?? 0
          return (
            <div key={group.key} className="panel flex flex-col p-5">
              <div className="flex items-center justify-between border-b divider pb-3">
                <div className="flex items-center gap-2">
                  <span className={`rounded-lg border p-1.5 ${group.tile}`}>{group.icon}</span>
                  <h3 className="text-[13px] font-bold tracking-wide text-parchment-100">
                    {group.title}
                  </h3>
                </div>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[11px] text-parchment-500">
                    {list.length}/{total}
                  </span>
                  {onOpenTool && (
                    <button
                      type="button"
                      onClick={() => onOpenTool(group.tool)}
                      title={`Open ${group.title} workbench`}
                      className="btn-ghost !px-2"
                    >
                      Open <ArrowUpRight className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
              <div className="mt-3 flex-1 space-y-2.5">
                {list.map((prov) => (
                  <div
                    key={prov.id}
                    className="panel-sunken flex items-start justify-between gap-3 p-3"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-xs font-semibold text-parchment-100">{prov.name}</span>
                        <span className="rounded bg-ink-700/70 px-1.5 py-0.5 font-mono text-[10px] text-parchment-400">
                          {prov.id}
                        </span>
                      </div>
                      <p className="mt-1 truncate font-mono text-[11px] text-parchment-500" title={prov.details}>
                        {prov.details}
                      </p>
                    </div>
                    <StatusPill available={prov.available} />
                  </div>
                ))}
                {list.length === 0 && (
                  <p className="rounded-xl border border-dashed border-ink-600 p-4 text-center text-xs text-parchment-600">
                    No engines match this filter.
                  </p>
                )}
              </div>
            </div>
          )
        })}
      </div>

      {/* Language registry */}
      <div className="panel space-y-4 p-5 sm:p-6">
        <div className="flex flex-col justify-between gap-3 border-b divider pb-4 lg:flex-row lg:items-center">
          <div>
            <h3 className="font-display text-lg font-semibold tracking-tight">
              Language & script registry
            </h3>
            <p className="mt-0.5 text-xs text-parchment-500">
              Eighth Schedule languages + English · {filteredLanguages.length} of{' '}
              {languages.length} shown · BCP-47 normalized
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Filter languages or scripts…"
                className="field !py-2 pl-9 text-xs sm:w-60"
              />
              <Search className="absolute left-3 top-3 h-3.5 w-3.5 text-parchment-500" />
            </div>
            {scripts.length > 0 && (
              <select
                value={scriptFilter}
                onChange={(e) => setScriptFilter(e.target.value)}
                className="field !py-2 text-xs sm:w-44"
                aria-label="Filter by script"
              >
                <option value="all">All scripts</option>
                {scripts.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {filteredLanguages.map((lang) => (
            <div
              key={lang.tag}
              className="panel-sunken group space-y-1.5 p-3 transition hover:border-marigold-500/40"
            >
              <div className="truncate font-display text-[15px] font-semibold tracking-tight text-parchment-100">
                {lang.name}
              </div>
              <div className="flex items-center justify-between font-mono text-[11px]">
                <span className="text-marigold-300">{lang.code}</span>
                {lang.script && <span className="text-parchment-500">{lang.script}</span>}
              </div>
              <div className="truncate font-mono text-[10px] text-parchment-600">{lang.tag}</div>
            </div>
          ))}
        </div>
        {filteredLanguages.length === 0 && (
          <p className="rounded-xl border border-dashed border-ink-600 p-6 text-center text-xs text-parchment-500">
            No languages match “{searchQuery}”.
          </p>
        )}
      </div>
    </div>
  )
}
export default ProvidersView
