import { Command, Child } from '@tauri-apps/plugin-shell'
import { dirname, resolveResource } from '@tauri-apps/api/path'

type Pending = { resolve: (v: unknown) => void; reject: (e: Error) => void }

class SidecarClient {
  private child: Child | null = null
  private requestId = 0
  private pending = new Map<number, Pending>()
  private buffer = ''
  private sidecarCwd: string | undefined
  private static readonly CALL_TIMEOUT_MS = 15000

  private async resolveSidecarCwd(): Promise<string | undefined> {
    if (this.sidecarCwd !== undefined) return this.sidecarCwd
    try {
      const sidecarPath = await resolveResource('python/sidecar.py')
      const pythonDir = await dirname(sidecarPath)
      this.sidecarCwd = await dirname(pythonDir)
      return this.sidecarCwd
    } catch {
      this.sidecarCwd = undefined
      return undefined
    }
  }

  async start() {
    if (this.child) return
    const cwd = await this.resolveSidecarCwd()
    const cmd = Command.create('python3', ['python/sidecar.py'], cwd ? { cwd } : undefined)
    cmd.stdout.on('data', (line) => this.onStdout(line))
    cmd.stderr.on('data', (line) => console.error('[sidecar]', line))
    cmd.on('close', (payload) => {
      const err = new Error(`Sidecar exited (code=${payload.code}, signal=${payload.signal})`)
      for (const [id, pending] of this.pending.entries()) {
        this.pending.delete(id)
        pending.reject(err)
      }
      this.child = null
    })
    this.child = await cmd.spawn()
  }

  private onStdout(chunk: string) {
    this.buffer += chunk
    const lines = this.buffer.split('\n')
    this.buffer = lines.pop() ?? ''
    for (const line of lines) {
      const raw = line.trim()
      if (!raw) continue
      try {
        const msg = JSON.parse(raw)
        const pending = this.pending.get(msg.id)
        if (!pending) continue
        this.pending.delete(msg.id)
        if (msg.ok) pending.resolve(msg.result)
        else pending.reject(new Error(msg.error || 'sidecar error'))
      } catch {
        // ignore malformed lines
      }
    }
  }

  async call<T = any>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    await this.start()
    if (!this.child) throw new Error('Sidecar unavailable')
    const id = ++this.requestId
    const payload = JSON.stringify({ id, method, params }) + '\n'
    const p = new Promise<T>((resolve, reject) => {
      this.pending.set(id, { resolve: (v) => resolve(v as T), reject })
    })
    await this.child.write(payload)
    return await new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id)
        reject(new Error(`Sidecar call timed out: ${method}`))
      }, SidecarClient.CALL_TIMEOUT_MS)
      p.then(
        (value) => {
          clearTimeout(timer)
          resolve(value)
        },
        (err) => {
          clearTimeout(timer)
          reject(err)
        }
      )
    })
  }
}

export const sidecar = new SidecarClient()
