import { Profile, ProfileStatus } from '@/lib/types'
import { motion } from 'framer-motion'

interface Props {
  profiles: Profile[]
  status: Record<string, ProfileStatus>
  onRefresh: () => void
}

export default function StatusDashboardPage({ profiles, status, onRefresh }: Props) {
  return (
    <div className="h-full bg-ix-bg p-6 overflow-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-semibold">Agent Status Dashboard</h1>
        <button onClick={onRefresh} className="px-3 py-2 rounded-ix bg-ix-accent text-ix-bg font-semibold">Refresh All</button>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
        {profiles.map((p) => {
          const s = status[p.id] || { online: false }
          return (
            <motion.div
              key={p.id}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-ix-surface rounded-ix border border-ix-surface2 p-4"
            >
              <div className="flex justify-between">
                <div>
                  <div className="font-semibold">{p.name}</div>
                  <div className="text-sm text-ix-dim">{p.connection_type === 'websocket' ? p.ws_url : `${p.user}@${p.host}`}</div>
                </div>
                <div className={`text-sm font-semibold ${s.online ? 'text-ix-green' : 'text-ix-red'}`}>{s.online ? 'Online' : 'Offline'}</div>
              </div>
              <div className="text-xs text-ix-dim mt-2">Agent: {p.agent} · Last seen: {s.lastSeen ?? 'Never'}</div>
            </motion.div>
          )
        })}
      </div>
    </div>
  )
}
