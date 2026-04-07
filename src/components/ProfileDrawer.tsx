import { motion, AnimatePresence } from 'framer-motion'
import { Profile } from '@/lib/types'
import { useState, useEffect } from 'react'

interface Props {
  open: boolean
  profile: Profile | null
  onClose: () => void
  onSave: (p: Profile) => void
  onDelete: (id: string) => void
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
  useEffect(() => {
    const next = profile ?? { ...blank, id: crypto.randomUUID() }
    setForm(next)
    setToken('')
    setTokenState('none')
    if (profile?.id) {
      void onLoadToken(profile.id).then((v) => {
        if (v) setTokenState('saved')
      })
    }
  }, [profile, onLoadToken])

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
              <select className="w-full bg-ix-surface2 rounded-ix px-3 py-2" value={form.connection_type} onChange={(e) => setForm({ ...form, connection_type: e.target.value as any })}>
                <option value="ssh">SSH</option>
                <option value="websocket">WebSocket</option>
              </select>
              <select className="w-full bg-ix-surface2 rounded-ix px-3 py-2" value={form.agent} onChange={(e) => setForm({ ...form, agent: e.target.value as any })}>
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
                    onSave(form)
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
