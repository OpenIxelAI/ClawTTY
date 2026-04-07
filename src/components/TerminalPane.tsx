import { useEffect, useRef } from 'react'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'

interface Props {
  output: string
}

export default function TerminalPane({ output }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const terminalRef = useRef<Terminal | null>(null)
  const fitRef = useRef<FitAddon | null>(null)
  const lastRef = useRef('')

  useEffect(() => {
    if (!containerRef.current || terminalRef.current) return
    const term = new Terminal({
      fontFamily: 'JetBrains Mono',
      fontSize: 13,
      theme: {
        background: '#070b14',
        foreground: '#c8d8e8',
        cursor: '#7eb8d4'
      }
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(containerRef.current)
    fit.fit()
    terminalRef.current = term
    fitRef.current = fit
    const onResize = () => fit.fit()
    window.addEventListener('resize', onResize)
    return () => {
      window.removeEventListener('resize', onResize)
      term.dispose()
      terminalRef.current = null
      fitRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!terminalRef.current) return
    const prev = lastRef.current
    const append = output.startsWith(prev) ? output.slice(prev.length) : output
    if (append) terminalRef.current.write(append.replace(/\n/g, '\r\n'))
    lastRef.current = output
  }, [output])

  return <div ref={containerRef} className="w-full h-full bg-ix-bg" />
}
