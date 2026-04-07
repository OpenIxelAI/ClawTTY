import { X, TerminalWindow, Waves } from '@phosphor-icons/react'
import { SessionTab } from '@/lib/types'

interface Props {
  tabs: SessionTab[]
  active: string | null
  onSelect: (id: string) => void
  onClose: (id: string) => void
}

export default function TabBar({ tabs, active, onSelect, onClose }: Props) {
  return (
    <div className="h-12 border-b border-ix-surface2 bg-ix-surface px-2 flex items-end gap-1 overflow-x-auto">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          className={`min-w-[220px] h-10 rounded-t-ix px-3 text-sm flex items-center justify-between ${
            active === tab.id ? 'bg-ix-surface2 text-ix-text' : 'bg-transparent text-ix-dim hover:bg-ix-surface2/70'
          }`}
          onClick={() => onSelect(tab.id)}
        >
          <span className="flex items-center gap-2 truncate">
            {tab.type === 'ssh' ? <TerminalWindow size={14} /> : <Waves size={14} />}
            <span className="truncate">{tab.name}</span>
          </span>
          <X
            size={14}
            onClick={(e) => {
              e.stopPropagation()
              onClose(tab.id)
            }}
          />
        </button>
      ))}
    </div>
  )
}
