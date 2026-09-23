import React from 'react'
import {
  CheckCircle2,
  Cpu,
  Languages,
  Layers,
  Mic,
  Volume2,
  XCircle,
} from 'lucide-react'
import type { LanguageItem, ProvidersResponse } from '../types'

interface ProvidersViewProps {
  languages: LanguageItem[]
  providersData: ProvidersResponse | null
}

export const ProvidersView: React.FC<ProvidersViewProps> = ({
  languages,
  providersData,
}) => {
  return (
    <div className="space-y-6">
      {/* Engine Status Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Translation Providers */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-800">
            <Cpu className="w-5 h-5 text-indigo-400" />
            <h3 className="text-sm font-semibold text-slate-100">
              Translation Engines
            </h3>
          </div>

          <div className="space-y-3">
            {providersData?.translation.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/80 border border-slate-800 rounded-lg p-3.5 flex items-start justify-between gap-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100 text-sm">
                      {prov.name}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      [{prov.id}]
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 font-mono">
                    {prov.details}
                  </p>
                </div>

                <div>
                  {prov.available ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60">
                      <CheckCircle2 className="w-3 h-3" /> Ready
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60">
                      <XCircle className="w-3 h-3" /> Unconfigured
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Transliteration Providers */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-800">
            <Languages className="w-5 h-5 text-teal-400" />
            <h3 className="text-sm font-semibold text-slate-100">
              Transliteration Engines
            </h3>
          </div>

          <div className="space-y-3">
            {providersData?.transliteration.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/80 border border-slate-800 rounded-lg p-3.5 flex items-start justify-between gap-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100 text-sm">
                      {prov.name}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      [{prov.id}]
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 font-mono">
                    {prov.details}
                  </p>
                </div>

                <div>
                  {prov.available ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60">
                      <CheckCircle2 className="w-3 h-3" /> Ready
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60">
                      <XCircle className="w-3 h-3" /> Unconfigured
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detection Providers */}
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
          <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-800">
            <Layers className="w-5 h-5 text-purple-400" />
            <h3 className="text-sm font-semibold text-slate-100">
              Detection Engines
            </h3>
          </div>

          <div className="space-y-3">
            {providersData?.detection.map((prov) => (
              <div
                key={prov.id}
                className="bg-slate-950/80 border border-slate-800 rounded-lg p-3.5 flex items-start justify-between gap-3"
              >
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-slate-100 text-sm">
                      {prov.name}
                    </span>
                    <span className="text-xs font-mono text-slate-500">
                      [{prov.id}]
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 mt-1 font-mono">
                    {prov.details}
                  </p>
                </div>

                <div>
                  {prov.available ? (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-950/70 text-emerald-300 border border-emerald-800/60">
                      <CheckCircle2 className="w-3 h-3" /> Ready
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-950/70 text-amber-300 border border-amber-800/60">
                      <XCircle className="w-3 h-3" /> Unconfigured
                    </span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
        <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-800">
          <Mic className="w-5 h-5 text-indigo-400" />
          <h3 className="text-sm font-semibold text-slate-100">Speech to text engines</h3>
        </div>
        <div className="space-y-3">
          {providersData?.speech_to_text.map((prov) => (
            <div key={prov.id} className="bg-slate-950/80 border border-slate-800 rounded-lg p-3.5">
              <div className="flex justify-between gap-3 text-sm">
                <span className="font-semibold text-slate-100">{prov.name}</span>
                <span className={prov.available ? 'text-emerald-300' : 'text-amber-300'}>
                  {prov.available ? 'Ready' : 'Unconfigured'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 font-mono">{prov.details}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
        <div className="flex items-center gap-2 pb-3 mb-4 border-b border-slate-800">
          <Volume2 className="w-5 h-5 text-indigo-400" />
          <h3 className="text-sm font-semibold text-slate-100">Text to speech engines</h3>
        </div>
        <div className="space-y-3">
          {providersData?.text_to_speech.map((prov) => (
            <div key={prov.id} className="bg-slate-950/80 border border-slate-800 rounded-lg p-3.5">
              <div className="flex justify-between gap-3 text-sm">
                <span className="font-semibold text-slate-100">{prov.name}</span>
                <span className={prov.available ? 'text-emerald-300' : 'text-amber-300'}>
                  {prov.available ? 'Ready' : 'Unconfigured'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1 font-mono">{prov.details}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Language Registry Table */}
      <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 backdrop-blur-sm">
        <div className="flex justify-between items-center pb-3 mb-4 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-semibold text-slate-100">
              Registered Indian Languages &amp; Scripts
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Standard Eighth Schedule languages plus English normalized to BCP-47
            </p>
          </div>
          <span className="text-xs px-2.5 py-1 rounded bg-slate-800 text-slate-300 font-mono">
            {languages.length} Languages
          </span>
        </div>

        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
          {languages.map((lang) => (
            <div
              key={lang.tag}
              className="bg-slate-950/80 border border-slate-800/90 rounded-lg p-2.5 hover:border-slate-700 transition"
            >
              <div className="text-xs font-semibold text-slate-200">
                {lang.name}
              </div>
              <div className="text-[11px] font-mono text-indigo-400 mt-0.5">
                {lang.code}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
