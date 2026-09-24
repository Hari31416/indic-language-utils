import React, { useState } from 'react'
import {
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
import type { LanguageItem, ProvidersResponse } from '../types'

interface ProvidersViewProps {
  languages: LanguageItem[]
  providersData: ProvidersResponse | null
  onOpenApiKeysModal: () => void
}

export const ProvidersView: React.FC<ProvidersViewProps> = ({
  languages,
  providersData,
  onOpenApiKeysModal,
}) => {
  const [searchQuery, setSearchQuery] = useState('')

  const filteredLanguages = languages.filter(
    (lang) =>
      lang.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      lang.code.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (lang.script && lang.script.toLowerCase().includes(searchQuery.toLowerCase()))
  )

  return (
    <div className="space-y-6">
      {/* Top Banner with Quick Action */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900/80 border border-slate-800/90 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-semibold text-slate-100">
              Engines, Models &amp; Language Registry
            </h2>
            <p className="text-xs text-slate-400">
              Review live adapter statuses, model capabilities, and supported Indian languages
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpenApiKeysModal}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-lg shadow-indigo-600/20 transition"
        >
          <KeyRound className="w-4 h-4" />
          Configure API Keys
        </button>
      </div>

      {/* Engine Status Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {/* Translation */}
        <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl space-y-3.5">
          <div className="flex items-center gap-2 pb-2.5 border-b border-slate-800">
            <Cpu className="w-4 h-4 text-indigo-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Translation Engines
            </h3>
          </div>
          <div className="space-y-2.5">
            {providersData?.translation.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-slate-100 text-xs">{prov.name}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-slate-400">
                      {prov.id}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 font-mono truncate">{prov.details}</p>
                </div>
                {prov.available ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 shrink-0">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60 shrink-0">
                    <XCircle className="w-3 h-3" /> Unconfigured
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Transliteration */}
        <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl space-y-3.5">
          <div className="flex items-center gap-2 pb-2.5 border-b border-slate-800">
            <Keyboard className="w-4 h-4 text-teal-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Transliteration Engines
            </h3>
          </div>
          <div className="space-y-2.5">
            {providersData?.transliteration.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-slate-100 text-xs">{prov.name}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-slate-400">
                      {prov.id}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 font-mono truncate">{prov.details}</p>
                </div>
                {prov.available ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 shrink-0">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60 shrink-0">
                    <XCircle className="w-3 h-3" /> Unconfigured
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Detection */}
        <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl space-y-3.5">
          <div className="flex items-center gap-2 pb-2.5 border-b border-slate-800">
            <Languages className="w-4 h-4 text-purple-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Detection Engines
            </h3>
          </div>
          <div className="space-y-2.5">
            {providersData?.detection.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-slate-100 text-xs">{prov.name}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-slate-400">
                      {prov.id}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 font-mono truncate">{prov.details}</p>
                </div>
                {prov.available ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 shrink-0">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60 shrink-0">
                    <XCircle className="w-3 h-3" /> Unconfigured
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Speech to Text */}
        <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl space-y-3.5">
          <div className="flex items-center gap-2 pb-2.5 border-b border-slate-800">
            <Mic className="w-4 h-4 text-amber-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Speech to Text (ASR)
            </h3>
          </div>
          <div className="space-y-2.5">
            {providersData?.speech_to_text.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex items-start justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-slate-100 text-xs">{prov.name}</span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-900 text-slate-400">
                      {prov.id}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 font-mono truncate">{prov.details}</p>
                </div>
                {prov.available ? (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 shrink-0">
                    <CheckCircle2 className="w-3 h-3" /> Ready
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60 shrink-0">
                    <XCircle className="w-3 h-3" /> Unconfigured
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Text to Speech */}
        <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 shadow-xl space-y-3.5 md:col-span-2">
          <div className="flex items-center gap-2 pb-2.5 border-b border-slate-800">
            <Volume2 className="w-4 h-4 text-violet-400" />
            <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-200">
              Text to Speech (TTS)
            </h3>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
            {providersData?.text_to_speech.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3 flex flex-col justify-between gap-2"
              >
                <div>
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="font-semibold text-slate-100 text-xs">{prov.name}</span>
                    {prov.available ? (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60 shrink-0">
                        Ready
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60 shrink-0">
                        Unconfigured
                      </span>
                    )}
                  </div>
                  <p className="text-[11px] text-slate-400 mt-1 font-mono">{prov.details}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Language Registry Explorer */}
      <div className="bg-slate-900/80 border border-slate-800/90 rounded-2xl p-5 sm:p-6 shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              Registered Indian Languages &amp; Scripts
            </h3>
            <p className="text-xs text-slate-400">
              Standard Eighth Schedule languages and English with full BCP-47 normalization
            </p>
          </div>

          <div className="relative w-full sm:w-64">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Filter languages or scripts..."
              className="w-full bg-slate-950 border border-slate-700/80 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2.5" />
          </div>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
          {filteredLanguages.map((lang) => (
            <div
              key={lang.tag}
              className="bg-slate-950/70 border border-slate-800/80 hover:border-slate-700 rounded-xl p-3 transition space-y-1"
            >
              <div className="text-xs font-semibold text-slate-200">{lang.name}</div>
              <div className="flex items-center justify-between text-[11px] font-mono text-slate-400">
                <span className="text-indigo-400">{lang.code}</span>
                {lang.script && <span>{lang.script}</span>}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
export default ProvidersView
