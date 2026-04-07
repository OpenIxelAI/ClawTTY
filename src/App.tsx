import { useEffect, useMemo, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import Sidebar from '@/components/Sidebar'
import ProfileDrawer from '@/components/ProfileDrawer'
import CommandPalette from '@/components/CommandPalette'
import StatusDashboardPage from '@/pages/StatusDashboardPage'
import SettingsPage from '@/pages/SettingsPage'
import SessionsPage from '@/pages/SessionsPage'
import { useProfiles } from '@/hooks/useProfiles'
import { ChatMessage, Profile, SessionTab, ProfileStatus, AppView } from '@/lib/types'
import { sidecar } from '@/lib/sidecar'
import { save } from '@tauri-apps/plugin-dialog'
import { invoke } from '@tauri-apps/api/core'


export default function App() {
  const { profiles, refresh } = useProfiles()
  const [view, setView] = useState<AppView>('sessions')
  const [tabs, setTabs] = useState<SessionTab[]>([])
  const [activeTabId, setActiveTabId] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingProfile, setEditingProfile] = useState<Profile | null>(null)
  const [paletteOpen, setPaletteOpen] = useState(false)
  const [terminalBuffers, setTerminalBuffers] = useState<Record<string, string>>({})
  const [chatMessages, setChatMessages] = useState<Record<string, ChatMessage[]>>({})
  const [status, setStatus] = useState<Record<string, ProfileStatus>>({})

  const activeTab = useMemo(() => tabs.find((t) => t.id === activeTabId) ?? null, [tabs, activeTabId])

  const openProfile = async (profile: Profile) => {
    const id = crypto.randomUUID()
    setTabs((t) => [...t, { id, profileId: profile.id, name: profile.name, agent: profile.agent, type: profile.connection_type, createdAt: new Date().toISOString() }])
    setActiveTabId(id)
    setView('sessions')
    if (profile.connection_type === 'ssh') {
      const out = await sidecar.call<string>('session.ssh_open', { profileId: profile.id })
      setTerminalBuffers((b) => ({ ...b, [id]: out }))
    } else {
      const history = await sidecar.call<ChatMessage[]>('session.ws_open', { profileId: profile.id })
      setChatMessages((m) => ({ ...m, [id]: history }))
    }
  }

  const saveProfile = async (profile: Profile) => {
    await sidecar.call('profiles.save', { profile })
    setDrawerOpen(false)
    await refresh()
  }
  const deleteProfile = async (id: string) => {
    await sidecar.call('profiles.delete', { profileId: id })
    setDrawerOpen(false)
    await refresh()
  }

  const refreshStatus = async () => {
    const data = await sidecar.call<Record<string, ProfileStatus>>('status.refresh')
    setStatus(data)
  }

  const exportLog = async () => {
    if (!activeTab) return
    const text = activeTab.type === 'ssh' ? terminalBuffers[activeTab.id] ?? '' : (chatMessages[activeTab.id] ?? []).map((m) => `[${m.ts}] ${m.role.toUpperCase()}: ${m.text}`).join('\n')
    const path = await save({
      defaultPath: `clawtty-session-${activeTab.name} -${new Date().toISOString().replace(/[:.]/g, '-')}.txt`,
      filters: [{ name: 'Text', extensions: ['txt'] }]
    })
    if (path) await invoke('export_log', { path, content: text })
  }

  const saveToken = async (profileId: string, token: string) => {
    await invoke('save_token', { profileId, token })
  }

  const loadToken = async (profileId: string) => {
    return invoke<string | null>('load_token', { profileId })
  }

  const onSendChat = async (tab: SessionTab, text: string) => {
    const msg: ChatMessage = { role: 'user', text, ts: new Date().toLocaleTimeString() }
    setChatMessages((m) => ({ ...m, [tab.id]: [...(m[tab.id] ?? []), msg] }))
    const reply = await sidecar.call<ChatMessage>('session.ws_send', { profileId: tab.profileId, text })
    setChatMessages((m) => ({ ...m, [tab.id]: [...(m[tab.id] ?? []), reply] }))
  }

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletteOpen(true)
      }
      if (e.key === 'Escape') setPaletteOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  return (
    <div className="h-full w-full flex">
      <Sidebar
        profiles={profiles}
        onOpenProfile={openProfile}
        onNewProfile={() => {
          setEditingProfile(null)
          setDrawerOpen(true)
        }}
        onStatus={() => {
          setView('status')
          void refreshStatus()
        }}
        onSettings={() => setView('settings')}
      />

      <main className="flex-1 flex flex-col bg-ix-bg">
        {view === 'sessions' ? (
          <SessionsPage
            tabs={tabs}
            activeTabId={activeTabId}
            terminalBuffers={terminalBuffers}
            chatMessages={chatMessages}
            onSelectTab={setActiveTabId}
            onCloseTab={(id) => {
              setTabs((t) => t.filter((x) => x.id !== id))
              if (activeTabId === id) setActiveTabId(null)
            }}
            onSendChat={onSendChat}
            onExportLog={exportLog}
          />
        ) : (
          <AnimatePresence mode="wait">
            {view === 'status' ? (
              <motion.div key="status" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} className="h-full">
                <StatusDashboardPage profiles={profiles} status={status} onRefresh={refreshStatus} />
              </motion.div>
            ) : (
              <motion.div key="settings" initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }} className="h-full">
                <SettingsPage />
              </motion.div>
            )}
          </AnimatePresence>
        )}
      </main>

      <ProfileDrawer
        open={drawerOpen}
        profile={editingProfile}
        onClose={() => setDrawerOpen(false)}
        onSave={saveProfile}
        onDelete={deleteProfile}
        onSaveToken={saveToken}
        onLoadToken={loadToken}
      />
      <CommandPalette
        open={paletteOpen}
        profiles={profiles}
        onClose={() => setPaletteOpen(false)}
        onSelect={(p) => {
          setPaletteOpen(false)
          void openProfile(p)
        }}
      />
    </div>
  )
}
