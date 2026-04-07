import { Robot } from '@phosphor-icons/react'
import { motion } from 'framer-motion'

export default function EmptyState() {
  return (
    <div className="h-full flex items-center justify-center">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.28 }}
        className="text-center"
      >
        <div className="mx-auto mb-4 h-16 w-16 rounded-full bg-ix-surface2 flex items-center justify-center border border-ix-accent/40">
          <Robot size={30} className="text-ix-accent" />
        </div>
        <div className="text-4xl font-bold tracking-tight text-ix-accent">ClawTTY</div>
        <div className="mt-2 text-sm text-ix-dim">Connect to an agent to get started</div>
      </motion.div>
    </div>
  )
}
