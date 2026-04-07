import { useState } from 'react'
import { ChatMessage } from '@/lib/types'
import { PaperPlaneTilt } from '@phosphor-icons/react'

interface Props {
  messages: ChatMessage[]
  onSend: (text: string) => void
}

export default function ChatPane({ messages, onSend }: Props) {
  const [input, setInput] = useState('')
  return (
    <div className="h-full flex flex-col bg-ix-bg">
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {messages.map((m, i) => (
          <div key={`${m.ts}-${i}`} className={`max-w-[70%] rounded-ix p-3 ${m.role === 'user' ? 'ml-auto bg-ix-accent text-ix-bg' : 'bg-ix-surface2'}`}>
            <div className="text-xs opacity-70 mb-1">{m.role} · {m.ts}</div>
            <div className="text-sm whitespace-pre-wrap">{m.text}</div>
          </div>
        ))}
      </div>
      <div className="p-3 border-t border-ix-surface2 flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          className="flex-1 bg-ix-surface2 rounded-ix px-3 py-2 outline-none"
          placeholder="Send message…"
          onKeyDown={(e) => {
            if (e.key === 'Enter' && input.trim()) {
              onSend(input)
              setInput('')
            }
          }}
        />
        <button
          className="bg-ix-accent text-ix-bg px-3 rounded-ix"
          onClick={() => {
            if (!input.trim()) return
            onSend(input)
            setInput('')
          }}
        >
          <PaperPlaneTilt size={16} />
        </button>
      </div>
    </div>
  )
}
