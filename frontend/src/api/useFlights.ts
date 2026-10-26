import { useEffect, useRef, useState, useCallback } from 'react'
import { LiveFlight } from '../api/client'

const WS_URL = `ws://${window.location.host}/api/flights/ws`

export function useLiveFlights() {
  const [flights, setFlights]   = useState<LiveFlight[]>([])
  const [count, setCount]       = useState(0)
  const [connected, setConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  const connect = useCallback(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen  = () => setConnected(true)
    ws.onclose = () => {
      setConnected(false)
      setTimeout(connect, 3000) // auto-reconnect
    }
    ws.onerror = () => ws.close()
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        if (msg.type === 'snapshot') {
          setFlights(msg.flights)
          setCount(msg.count)
        }
      } catch {}
    }
  }, [])

  useEffect(() => {
    connect()
    return () => wsRef.current?.close()
  }, [connect])

  return { flights, count, connected }
}
