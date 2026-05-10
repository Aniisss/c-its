/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'

const LDMContext = createContext(null)
const WS_URL = import.meta.env.VITE_LDM_WS_URL ?? 'ws://localhost:8000/ws/ldm'

export function LDMProvider({ children }) {
  const [stations, setStations] = useState([])
  const [perceivedObjects, setPerceivedObjects] = useState([])
  const [pois, setPois] = useState([])
  const [status, setStatus] = useState('connecting')
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)

  useEffect(() => {
    let disposed = false

    const connect = () => {
      setStatus('connecting')
      const ws = new WebSocket(WS_URL)
      wsRef.current = ws

      ws.onopen = () => {
        setStatus('live')
      }

      ws.onmessage = (event) => {
        try {
          const snapshot = JSON.parse(event.data)
          setStations(Array.isArray(snapshot.stations) ? snapshot.stations : [])
          setPerceivedObjects(Array.isArray(snapshot.perceived_objects) ? snapshot.perceived_objects : [])
          setPois(Array.isArray(snapshot.pois) ? snapshot.pois : [])
        } catch {
          // Ignore malformed payloads.
        }
      }

      ws.onerror = () => {
        ws.close()
      }

      ws.onclose = () => {
        setStatus('disconnected')
        if (!disposed) {
          reconnectRef.current = setTimeout(connect, 1500)
        }
      }
    }

    connect()

    return () => {
      disposed = true
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current)
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const value = useMemo(() => ({
    stations,
    perceivedObjects,
    pois,
    status,
  }), [stations, perceivedObjects, pois, status])

  return <LDMContext.Provider value={value}>{children}</LDMContext.Provider>
}

export function useLDM() {
  const context = useContext(LDMContext)
  if (!context) {
    throw new Error('useLDM must be used inside LDMProvider')
  }
  return context
}
