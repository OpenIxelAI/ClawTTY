import { ChatMessage, SessionTab } from '@/lib/types'
import TabBar from '@/components/TabBar'
import TerminalPane from '@/components/TerminalPane'
import ChatPane from '@/components/ChatPane'
import EmptyState from '@/components/EmptyState'

interface Props {
  tabs: SessionTab[]
  activeTabId: string | null
  terminalBuffers: Record<string, string>
  chatMessages: Record<string, ChatMessage[]>
  onSelectTab: (id: string) => void
  onCloseTab: (id: string) => void
  onSendChat: (tab: SessionTab, text: string) => Promise<void>
  onExportLog: () => Promise<void>
}

export default function SessionsPage({
  tabs,
  activeTabId,
  terminalBuffers,
  chatMessages,
  onSelectTab,
  onCloseTab,
  onSendChat,
  onExportLog
}: Props) {
  const active = tabs.find((t) => t.id === activeTabId) ?? null

  return (
    <>
      <TabBar tabs={tabs} active={activeTabId} onSelect={onSelectTab} onClose={onCloseTab} />
      <div className="flex-1">
        {active ? (
          <div className="h-full relative">
            <button
              className="absolute top-3 right-3 z-20 px-3 py-1.5 text-xs rounded-ix bg-ix-surface2 border border-ix-surface2 hover:border-ix-accent/40"
              onClick={() => void onExportLog()}
            >
              Export Log
            </button>
            {active.type === 'ssh' ? (
              <TerminalPane output={terminalBuffers[active.id] ?? ''} />
            ) : (
              <ChatPane
                messages={chatMessages[active.id] ?? []}
                onSend={(text) => {
                  void onSendChat(active, text)
                }}
              />
            )}
          </div>
        ) : (
          <EmptyState />
        )}
      </div>
    </>
  )
}
