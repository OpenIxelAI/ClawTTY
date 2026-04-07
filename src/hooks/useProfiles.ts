import { useEffect, useState } from 'react'
import { Profile } from '@/lib/types'
import { sidecar } from '@/lib/sidecar'

export function useProfiles() {
  const [profiles, setProfiles] = useState<Profile[]>([])
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    setLoading(true)
    try {
      const data = await sidecar.call<Profile[]>('profiles.list')
      setProfiles(data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  return { profiles, setProfiles, refresh, loading }
}
