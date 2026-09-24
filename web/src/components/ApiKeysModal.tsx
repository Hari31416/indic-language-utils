import React, { useState } from 'react'
import {
  Check,
  ExternalLink,
  KeyRound,
  Lock,
  RefreshCw,
  Server,
  ShieldCheck,
  Trash2,
  X,
} from 'lucide-react'
import { clearApiKeys, saveApiKeys } from '../storage'
import type { ApiKeysConfig } from '../types'

interface ApiKeysModalProps {
  isOpen: boolean
  onClose: () => void
  apiKeys: ApiKeysConfig
  onSave: (keys: ApiKeysConfig) => void
}

export const ApiKeysModal: React.FC<ApiKeysModalProps> = ({
  isOpen,
  onClose,
  apiKeys,
  onSave,
}) => {
  const [sarvamKey, setSarvamKey] = useState(apiKeys.sarvamApiKey)
  const [sarvamEndpoint, setSarvamEndpoint] = useState(apiKeys.sarvamEndpoint)
  const [bhashiniKey, setBhashiniKey] = useState(apiKeys.bhashiniApiKey)
  const [bhashiniEndpoint, setBhashiniEndpoint] = useState(apiKeys.bhashiniEndpoint)
  const [savedNotice, setSavedNotice] = useState(false)

  if (!isOpen) return null

  const handleSave = () => {
    const updated: ApiKeysConfig = {
      sarvamApiKey: sarvamKey.trim(),
      sarvamEndpoint: sarvamEndpoint.trim(),
      bhashiniApiKey: bhashiniKey.trim(),
      bhashiniEndpoint: bhashiniEndpoint.trim(),
    }
    saveApiKeys(updated)
    onSave(updated)
    setSavedNotice(true)
    setTimeout(() => {
      setSavedNotice(false)
      onClose()
    }, 800)
  }

  const handleClearAll = () => {
    clearApiKeys()
    setSarvamKey('')
    setSarvamEndpoint('')
    setBhashiniKey('')
    setBhashiniEndpoint('')
    const empty: ApiKeysConfig = {
      sarvamApiKey: '',
      sarvamEndpoint: '',
      bhashiniApiKey: '',
      bhashiniEndpoint: '',
    }
    onSave(empty)
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-xl bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-950/60">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <KeyRound className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-semibold text-slate-100">
                API Keys & Provider Configuration
              </h3>
              <p className="text-xs text-slate-400">
                Keys are stored locally in your browser and sent securely with API calls
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-6 text-sm text-slate-200">
          {/* Security Banner */}
          <div className="flex items-start gap-2.5 p-3 rounded-xl bg-indigo-950/40 border border-indigo-800/40 text-xs text-indigo-300">
            <ShieldCheck className="w-4 h-4 mt-0.5 shrink-0 text-indigo-400" />
            <span>
              API keys entered here override local environment variables and persist across
              browser reloads via localStorage.
            </span>
          </div>

          {/* Sarvam AI Section */}
          <div className="space-y-3 p-4 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-semibold text-slate-100 text-sm">
                <Lock className="w-4 h-4 text-emerald-400" />
                Sarvam AI
              </div>
              <a
                href="https://dashboard.sarvam.ai"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
              >
                Get API Key <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-slate-400">
                API Subscription Key (SARVAM_API_KEY)
              </label>
              <input
                type="password"
                value={sarvamKey}
                onChange={(e) => setSarvamKey(e.target.value)}
                placeholder="e.g. 5d94...8c9"
                className="w-full bg-slate-900 border border-slate-700/90 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-slate-400">
                Custom Endpoint URL (Optional)
              </label>
              <input
                type="text"
                value={sarvamEndpoint}
                onChange={(e) => setSarvamEndpoint(e.target.value)}
                placeholder="https://api.sarvam.ai"
                className="w-full bg-slate-900 border border-slate-700/90 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
              />
            </div>
          </div>

          {/* Bhashini Section */}
          <div className="space-y-3 p-4 rounded-xl bg-slate-950/60 border border-slate-800">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 font-semibold text-slate-100 text-sm">
                <Server className="w-4 h-4 text-cyan-400" />
                Bhashini (National Language Translation Mission)
              </div>
              <a
                href="https://bhashini.gov.in"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-xs text-indigo-400 hover:text-indigo-300"
              >
                Bhashini Portal <ExternalLink className="w-3 h-3" />
              </a>
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-slate-400">
                Inference API Key (BHASHINI_API_KEY)
              </label>
              <input
                type="password"
                value={bhashiniKey}
                onChange={(e) => setBhashiniKey(e.target.value)}
                placeholder="e.g. ULCA pipeline API Key"
                className="w-full bg-slate-900 border border-slate-700/90 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-slate-400">
                Pipeline / Inference Endpoint URL (Optional)
              </label>
              <input
                type="text"
                value={bhashiniEndpoint}
                onChange={(e) => setBhashiniEndpoint(e.target.value)}
                placeholder="https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
                className="w-full bg-slate-900 border border-slate-700/90 rounded-lg px-3 py-2 text-xs font-mono text-slate-100 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition"
              />
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-6 py-4 border-t border-slate-800 bg-slate-950/60">
          <button
            type="button"
            onClick={handleClearAll}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 border border-transparent hover:border-rose-900 transition"
          >
            <Trash2 className="w-3.5 h-3.5" />
            Clear Keys
          </button>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-xs font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleSave}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 text-white shadow-md shadow-indigo-600/20 transition"
            >
              {savedNotice ? (
                <>
                  <Check className="w-3.5 h-3.5 text-emerald-300" />
                  Saved!
                </>
              ) : (
                <>
                  <RefreshCw className="w-3.5 h-3.5" />
                  Save & Apply Keys
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
