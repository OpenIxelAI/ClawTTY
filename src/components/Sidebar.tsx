import { Plus, Gear, Pulse, Circle, MagnifyingGlass } from '@phosphor-icons/react'
import { Profile } from '@/lib/types'
import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'

interface Props {
  profiles: Profile[]
  onOpenProfile: (p: Profile) => void
  onNewProfile: () => void
  onStatus: () => void
  onSettings: () => void
}

const agentColor: Record<string, string> = {
  openclaw: 'text-ix-gold',
  hermes: 'text-ix-purple',
  custom: 'text-yellow-400'
}

export default function Sidebar({ profiles, onOpenProfile, onNewProfile, onStatus, onSettings }: Props) {
  const [q, setQ] = useState('')
  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase()
    if (!s) return profiles
    return profiles.filter((p) => [p.name, p.host, p.user, p.ws_url, p.agent].join(' ').toLowerCase().includes(s))
  }, [profiles, q])

  return (
    <aside className="w-[260px] h-full bg-ix-surface border-r border-ix-surface2 flex flex-col">
      <div className="px-4 py-4 border-b border-ix-surface2">
        <div className="text-lg font-semibold">ClawTTY</div>
        <div className="text-xs text-ix-dim">v4 Tauri Rewrite</div>
      </div>
      <div className="p-3 space-y-2">
        <button onClick={onNewProfile} className="w-full rounded-ix bg-ix-accent text-ix-bg py-2 text-sm font-semibold flex items-center justify-center gap-2">
          <Plus size={16} /> Add Profile
        </button>
        <label className="flex items-center gap-2 rounded-ix bg-ix-surface2 px-2.5 py-2 text-xs">
          <MagnifyingGlass size={14} className="text-ix-dim" />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search profiles"
            className="bg-transparent outline-none w-full text-ix-text placeholder:text-ix-dim"
          />
        </label>
      </div>
      <div className="flex-1 overflow-auto px-3 pb-3 space-y-2">
        {filtered.map((p) => (
          <motion.button
            key={p.id}
            whileHover={{ scale: 1.01 }}
            onClick={() => onOpenProfile(p)}
            className="w-full text-left bg-ix-surface2 rounded-ix px-3 py-2 border border-transparent hover:border-ix-accent/40"
          >
            <div className="flex items-center justify-between">
              <div className="font-medium text-sm">{p.name}</div>
              <div className={`text-xs font-semibold ${agentColor[p.agent] ?? 'text-ix-dim'}`}>{p.agent}</div>
            </div>
            <div className="text-xs text-ix-dim">{p.connection_type === 'websocket' ? p.ws_url : `${p.user}@${p.host}`}</div>
            <div className="mt-1 flex items-center gap-1 text-xs text-ix-dim">
              <Circle size={8} weight="fill" className="text-ix-green pulse-online rounded-full" />
              online
            </div>
          </motion.button>
        ))}
        {!filtered.length && <div className="text-xs text-center text-ix-dim py-6">No profiles</div>}
      </div>
      <div className="p-3 border-t border-ix-surface2 flex gap-2">
        <button onClick={onStatus} className="flex-1 rounded-ix bg-ix-surface2 py-2 text-sm flex items-center justify-center gap-2">
          <Pulse size={16} /> Status
        </button>
        <button onClick={onSettings} className="rounded-ix bg-ix-surface2 px-3 py-2">
          <Gear size={16} />
        </button>
      </div>
    </aside>
  )
}
