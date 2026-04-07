import { motion, AnimatePresence } from 'framer-motion'
import { Profile, AgentType, ConnectionType } from '@/lib/types'
import { useState, useEffect } from 'react'

interface Props {
  open: boolean
  profile: Profile | null
  onClose: () => void
  onSave: (p: Profile) => Promise<void>
  onDelete: (id: string) => Promise<void>
  onSaveToken: (profileId: string, token: string) => Promise<void>
  onLoadToken: (profileId: string) => Promise<string | null>
}

const blank: Profile = {
  id: '',
  name: '',
  group: 'Default',
  connection_type: 'ssh',
  host: '',
  user: '',
  port: 22,
  identity_file: '',
  agent: 'openclaw',
  remote_command: 'openclaw tui',
  ws_url: '',
  notes: ''
}

export default function ProfileDrawer({ open, profile, onClose, onSave, onDelete, onSaveToken, onLoadToken }: Props) {
  const [form, setForm] = useState<Profile>(blank)
  const [token, setToken] = useState('')
  const [tokenState, setTokenState] = useState<'none' | 'saved'>('none')
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    const next = profile ?? { ...blank, id: crypto.randomUUID() }
    setForm(next)
    setToken('')
    setTokenState('none')
    setError(null)
    if (profile?.id) {
      void onLoadToken(profile.id).then((v) => {
        if (v) setTokenState('saved')
      })
    }
  }, [profile, onLoadToken])

  const parseConnectionType = (value: string): ConnectionType =>
    value === 'websocket' ? 'websocket' : 'ssh'

  const parseAgentType = (value: string): AgentType =>
    value === 'hermes' || value === 'custom' ? value : 'openclaw'

  const validateForm = (p: Profile): string | null => {
    if (!p.name.trim()) return 'Profile name is required.'
    if (p.connection_type === 'ssh') {
      if (!p.host.trim()) return 'SSH host is required.'
      if (!p.user.trim()) return 'SSH user is required.'
    } else {
      if (!p.ws_url.trim()) return 'WebSocket URL is required.'
      if (!/^wss?:\/\//i.test(p.ws_url.trim())) return 'WebSocket URL must start with ws:// or wss://.'
    }
    return null
  }

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div
            className="fixed right-0 top-0 h-full w-[420px] bg-ix-surface z-50 p-4 border-l border-ix-surface2 overflow-auto"
            initial={{ x: 420 }}
            animate={{ x: 0 }}
            exit={{ x: 420 }}
          >
            <h2 className="text-lg font-semibold mb-4">{profile ? 'Edit Profile' : 'New Profile'}</h2>
            {error ? (
              <div className="mb-3 rounded-ix bg-ix-red/20 border border-ix-red px-3 py-2 text-sm text-red-200">
                {error}
              </div>
            ) : null}
            <div className="space-y-3">
              {(['name', 'group', 'host', 'user', 'remote_command', 'ws_url'] as const).map((key) => (
                <input
                  key={key}
                  value={(form[key] as string) ?? ''}
                  onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                  placeholder={key}
                  className="w-full bg-ix-surface2 rounded-ix px-3 py-2 outline-none"
                />
              ))}
              <select className="w-full bg-ix-surface2 rounded-ix px-3 py-2" value={form.connection_type} onChange={(e) => setForm({ ...form, connection_type: parseConnectionType(e.target.value) })}>
                <option value="ssh">SSH</option>
                <option value="websocket">WebSocket</option>
              </select>
              <select className="w-full bg-ix-surface2 rounded-ix px-3 py-2" value={form.agent} onChange={(e) => setForm({ ...form, agent: parseAgentType(e.target.value) })}>
                <option value="openclaw">OpenClaw</option>
                <option value="hermes">Hermes</option>
                <option value="custom">Custom</option>
              </select>
              <input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder={tokenState === 'saved' ? 'API Token saved (••••••••)' : 'API Token (optional)'}
                type="password"
                className="w-full bg-ix-surface2 rounded-ix px-3 py-2 outline-none"
              />
            </div>
            <div className="mt-6 flex justify-between">
              {profile ? (
                <button className="px-3 py-2 rounded-ix bg-ix-red text-white" onClick={() => onDelete(form.id)}>Delete</button>
              ) : <span />}
              <div className="flex gap-2">
                <button className="px-3 py-2 rounded-ix bg-ix-surface2" onClick={onClose}>Cancel</button>
                <button
                  className="px-3 py-2 rounded-ix bg-ix-accent text-ix-bg font-semibold"
                  onClick={async () => {
                    const msg = validateForm(form)
                    if (msg) {
                      setError(msg)
                      return
                    }
                    setError(null)
                    await onSave(form)
                    if (token.trim()) {
                      await onSaveToken(form.id, token.trim())
                      setToken('')
                      setTokenState('saved')
                    }
                  }}
                >
                  Save
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
