import { AnimatePresence, motion } from 'framer-motion'
import { Profile } from '@/lib/types'
import { useMemo, useState } from 'react'

interface Props {
  open: boolean
  profiles: Profile[]
  onClose: () => void
  onSelect: (p: Profile) => void
}

export default function CommandPalette({ open, profiles, onClose, onSelect }: Props) {
  const [q, setQ] = useState('')
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return profiles
    return profiles.filter((p) => [p.name, p.host, p.user, p.ws_url, p.agent].join(' ').toLowerCase().includes(s))
  }, [q, profiles])

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div className="fixed inset-0 bg-black/55 z-[70]" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
          <motion.div
            className="fixed z-[80] left-1/2 top-24 -translate-x-1/2 w-[760px] rounded-modal bg-ix-surface border border-ix-surface2 shadow-2xl overflow-hidden"
            initial={{ opacity: 0, y: -18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.98 }}
          >
            <input
              autoFocus
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Type a profile name, host, or agent..."
              className="w-full bg-transparent px-4 py-3 border-b border-ix-surface2 outline-none text-sm"
            />
            <div className="max-h-[420px] overflow-auto p-2">
              {filtered.map((p) => (
                <button
                  key={p.id}
                  onClick={() => {
                    onSelect(p)
                    setQ('')
                  }}
                  className="w-full text-left rounded-ix px-3 py-2.5 hover:bg-ix-surface2"
                >
                  <div className="flex items-center justify-between">
                    <div className="font-medium text-sm">{p.name}</div>
                    <span className="text-xs text-ix-dim">{p.agent}</span>
                  </div>
                  <div className="text-xs text-ix-dim mt-0.5">{p.connection_type === 'websocket' ? p.ws_url : `${p.user}@${p.host}:${p.port}`}</div>
                </button>
              ))}
              {!filtered.length && <div className="px-3 py-6 text-sm text-ix-dim text-center">No matching profiles</div>}
            </div>
            <div className="border-t border-ix-surface2 px-4 py-2 text-xs text-ix-dim">Press Esc to close · Enter to connect</div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  )
}
