/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'

const LDMContext = createContext(null)
const WS_URL = import.meta.env.VITE_LDM_WS_URL ?? 'ws://localhost:8000/ws/ldm'

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function newestByAge(items) {
  if (!Array.isArray(items) || items.length === 0) {
    return null
  }
  return [...items].sort(
    (left, right) => (toNumber(left.age_seconds) ?? Number.POSITIVE_INFINITY)
      - (toNumber(right.age_seconds) ?? Number.POSITIVE_INFINITY),
  )[0]
}

function buildEgoFeature(snapshot) {
  const latitude = toNumber(snapshot?.ego?.latitude)
  const longitude = toNumber(snapshot?.ego?.longitude)
  if (latitude === null || longitude === null) {
    return null
  }
  return {
    type: 'Feature',
    geometry: {
      type: 'Point',
      coordinates: [longitude, latitude],
    },
    properties: {
      type: 'ego',
      id: 'ego_ds7',
      heading: snapshot.ego?.heading ?? null,
      speed: snapshot.ego?.speed ?? null,
    },
  }
}

export function LDMProvider({ children }) {
  const [stations, setStations] = useState([])
  const [perceivedObjects, setPerceivedObjects] = useState([])
  const [pois, setPois] = useState([])
  const [egoFeature, setEgoFeature] = useState(null)
  const [latestPayloads, setLatestPayloads] = useState({
    ego: null,
    cam: null,
    cpm: null,
    poim: null,
    updatedAt: null,
  })
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
          const nextStations = Array.isArray(snapshot.stations) ? snapshot.stations : []
          const nextPerceivedObjects = Array.isArray(snapshot.perceived_objects) ? snapshot.perceived_objects : []
          const nextPois = Array.isArray(snapshot.pois) ? snapshot.pois : []
          setStations(nextStations)
          setPerceivedObjects(nextPerceivedObjects)
          setPois(nextPois)
          setEgoFeature(buildEgoFeature(snapshot))
          setLatestPayloads({
            ego: snapshot.ego ?? null,
            cam: newestByAge(nextStations),
            cpm: newestByAge(nextPerceivedObjects),
            poim: newestByAge(nextPois),
            updatedAt: Date.now(),
          })
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
    egoFeature,
    latestPayloads,
    status,
  }), [stations, perceivedObjects, pois, egoFeature, latestPayloads, status])

  return <LDMContext.Provider value={value}>{children}</LDMContext.Provider>
}

export function useLDM() {
  const context = useContext(LDMContext)
  if (!context) {
    throw new Error('useLDM must be used inside LDMProvider')
  }
  return context
}
