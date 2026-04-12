import { useState, useEffect, useRef } from 'react'

const POLL_INTERVAL_MS = 2000

export function useStatus() {
  const [status, setStatus]     = useState('idle')      // idle | running | done | error
  const [progress, setProgress] = useState(null)        // "2/10" or null
  const [total, setTotal]       = useState(null)        // total emails to process
  const [error, setError]       = useState(null)
  const intervalRef = useRef(null)

  async function fetchStatus() {
    try {
      const res  = await fetch('/api/status')
      const data = await res.json()
      setStatus(data.status)
      setProgress(data.progress ?? null)
      setTotal(data.total ?? null)
      setError(data.error ?? null)

      // Stop polling once the pipeline is no longer running
      if (data.status !== 'running') {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    } catch {
      setStatus('error')
      setError('Cannot reach Flask server.')
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
  }

  // Start polling — called externally after POST /run
  function startPolling() {
    fetchStatus()
    intervalRef.current = setInterval(fetchStatus, POLL_INTERVAL_MS)
  }

  // Initial fetch on mount to restore state after page reload
  useEffect(() => {
    fetchStatus()
    return () => clearInterval(intervalRef.current)
  }, [])

  return { status, progress, total, error, startPolling }
}