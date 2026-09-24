import React, { useEffect, useState } from 'react'
import {
  Check,
  ExternalLink,
  Eye,
  EyeOff,
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

const SecretField: React.FC<{
  label: string
  value: string
  onChange: (v: string) => void
  placeholder: string
}> = ({ label, value, onChange, placeholder }) => {
  const [show, setShow] = useState(false)
  return (
    <div className="space-y-1.5">
      <label className="block text-xs font-medium text-parchment-400">{label}</label>
      <div className="relative">
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          autoComplete="off"
          spellCheck={false}
          className="field field-mono !pr-10"
        />
        <button
          type="button"
          onClick={() => setShow(!show)}
          title={show ? 'Hide key' : 'Reveal key'}
          className="absolute right-2.5 top-2.5 text-parchment-500 transition hover:text-parchment-200"
        >
          {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
    </div>
  )
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

  useEffect(() => {
    if (!isOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [isOpen, onClose])

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
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-black/75 p-4 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div className="relative flex max-h-[90vh] w-full max-w-xl animate-rise flex-col overflow-hidden rounded-2xl border border-ink-600 bg-ink-850 shadow-drawer">
        <div className="flex items-center justify-between border-b divider bg-ink-900/70 px-6 py-4">
          <div className="flex items-center gap-2.5">
            <div className="rounded-xl border border-marigold-500/30 bg-marigold-500/10 p-2 text-marigold-300">
              <KeyRound className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-display text-lg font-semibold tracking-tight">
                API keys & providers
              </h3>
              <p className="text-xs text-parchment-500">
                Stored only in your browser · sent securely with API calls
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1.5 text-parchment-500 transition hover:bg-ink-700 hover:text-parchment-100"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="space-y-5 overflow-y-auto p-6 text-sm">
          <div className="flex items-start gap-2.5 rounded-xl border border-peacock-500/25 bg-peacock-500/10 p-3 text-xs leading-relaxed text-peacock-200">
            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0" />
            <span>
              Keys entered here override server environment variables and persist across
              reloads via localStorage. Nothing ever leaves your machine except the API
              calls themselves.
            </span>
          </div>

          <div className="panel-sunken space-y-3.5 p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-semibold text-parchment-100">
                <Lock className="h-4 w-4 text-moss-300" />
                Sarvam AI
                {sarvamKey.trim() && (
                  <span className="pill-ready">Set</span>
                )}
              </div>
              <a
                href="https://dashboard.sarvam.ai"
                target="_blank"
                rel="noreferrer"
                className="link-accent"
              >
                Get API key <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <SecretField
              label="API subscription key (SARVAM_API_KEY)"
              value={sarvamKey}
              onChange={setSarvamKey}
              placeholder="e.g. 5d94…8c9"
            />
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-parchment-400">
                Custom endpoint URL (optional)
              </label>
              <input
                type="text"
                value={sarvamEndpoint}
                onChange={(e) => setSarvamEndpoint(e.target.value)}
                placeholder="https://api.sarvam.ai"
                spellCheck={false}
                className="field field-mono"
              />
            </div>
          </div>

          <div className="panel-sunken space-y-3.5 p-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-parchment-100">
                <Server className="h-4 w-4 shrink-0 text-peacock-300" />
                <span className="truncate">Bhashini (National Language Mission)</span>
                {bhashiniKey.trim() && (
                  <span className="pill-ready">Set</span>
                )}
              </div>
              <a
                href="https://bhashini.gov.in"
                target="_blank"
                rel="noreferrer"
                className="link-accent shrink-0"
              >
                Portal <ExternalLink className="h-3 w-3" />
              </a>
            </div>
            <SecretField
              label="Inference API key (BHASHINI_API_KEY)"
              value={bhashiniKey}
              onChange={setBhashiniKey}
              placeholder="e.g. ULCA pipeline API key"
            />
            <div className="space-y-1.5">
              <label className="block text-xs font-medium text-parchment-400">
                Pipeline / inference endpoint URL (optional)
              </label>
              <input
                type="text"
                value={bhashiniEndpoint}
                onChange={(e) => setBhashiniEndpoint(e.target.value)}
                placeholder="https://dhruva-api.bhashini.gov.in/services/inference/pipeline"
                spellCheck={false}
                className="field field-mono"
              />
            </div>
          </div>
        </div>

        <div className="flex items-center justify-between border-t divider bg-ink-900/70 px-6 py-4">
          <button
            type="button"
            onClick={handleClearAll}
            className="inline-flex items-center gap-1.5 rounded-lg border border-transparent px-3 py-1.5 text-xs font-medium text-clay-300 transition hover:border-clay-500/40 hover:bg-clay-500/10"
          >
            <Trash2 className="h-3.5 w-3.5" />
            Clear keys
          </button>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-xs font-medium text-parchment-400 transition hover:bg-ink-700 hover:text-parchment-100"
            >
              Cancel
            </button>
            <button type="button" onClick={handleSave} className="btn-primary !py-2">
              {savedNotice ? (
                <>
                  <Check className="h-3.5 w-3.5" /> Saved!
                </>
              ) : (
                <>
                  <RefreshCw className="h-3.5 w-3.5" /> Save & apply keys
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
