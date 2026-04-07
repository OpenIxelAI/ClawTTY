export type AgentType = 'openclaw' | 'hermes' | 'custom'
export type ConnectionType = 'ssh' | 'websocket'

export interface Profile {
  id: string
  name: string
  group: string
  connection_type: ConnectionType
  host: string
  user: string
  port: number
  identity_file: string
  agent: AgentType
  remote_command: string
  ws_url: string
  notes: string
}

export interface SessionTab {
  id: string
  profileId: string
  name: string
  agent: AgentType
  type: ConnectionType
  createdAt: string
}

export interface ChatMessage {
  role: 'user' | 'agent' | 'system'
  text: string
  ts: string
}

export interface ProfileStatus {
  online: boolean
  lastSeen?: string
}

export type AppView = 'sessions' | 'status' | 'settings'
