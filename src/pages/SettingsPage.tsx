export default function SettingsPage() {
  return (
    <div className="h-full bg-ix-bg p-6">
      <h1 className="text-xl font-semibold mb-4">Settings</h1>
      <div className="space-y-3">
        <div className="bg-ix-surface rounded-modal border border-ix-surface2 p-4 text-sm text-ix-dim">
          ClawTTY Tauri rewrite uses Inter + JetBrains Mono, xterm.js terminal sessions, and Python sidecar IPC over stdio.
        </div>
        <div className="bg-ix-surface rounded-modal border border-ix-surface2 p-4">
          <div className="text-sm font-semibold mb-1">Theme</div>
          <div className="text-xs text-ix-dim">IxelOS dark palette is active.</div>
        </div>
        <div className="bg-ix-surface rounded-modal border border-ix-surface2 p-4">
          <div className="text-sm font-semibold mb-1">Typography</div>
          <div className="text-xs text-ix-dim">UI: Inter · Terminal: JetBrains Mono.</div>
        </div>
      </div>
    </div>
  )
}
