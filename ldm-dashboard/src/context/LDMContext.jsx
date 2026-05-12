/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useEffect, useMemo, useRef, useState } from 'react'

const LDMContext = createContext(null)
const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/ldm'
const POIM_HISTORY_LIMIT = 30
const FEED_LIMIT = 50

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function normalizeCoordinate(value) {
  const numeric = toNumber(value)
  if (numeric === null) {
    return null
  }
  if (Math.abs(numeric) > 180) {
    return numeric / 1e7
  }
  return numeric
}

function extractReferencePosition(payload) {
  const reference = payload.referencePosition
    ?? payload.reference_position
    ?? payload.placeInfo?.position
    ?? payload.position

  if (!reference || typeof reference !== 'object') {
    return null
  }

  const latitude = normalizeCoordinate(reference.latitude ?? reference.lat)
  const longitude = normalizeCoordinate(reference.longitude ?? reference.lon ?? reference.lng)
  if (latitude === null || longitude === null) {
    return null
  }

  return { latitude, longitude }
}

function isPoimMessage(payload) {
  const messageType = String(
    payload.messageType
    ?? payload.message_type
    ?? payload.type
    ?? payload.payload?.messageType
    ?? payload.payload?.message_type
    ?? '',
  ).toUpperCase()

  if (messageType === 'POIM') {
    return true
  }

  return Boolean(
    payload.spacesAvailable
    ?? payload.spaces_available
    ?? payload.spacesTotal
    ?? payload.spaces_total,
  )
}

function parsePoim(payload) {
  const data = payload.payload && typeof payload.payload === 'object' ? payload.payload : payload

  const spacesAvailable = toNumber(
    data.spacesAvailable
      ?? data.spaces_available
      ?? data.availableSpaces
      ?? data.available_spaces,
  )

  const spacesTotal = toNumber(
    data.spacesTotal
      ?? data.spaces_total
      ?? data.totalSpaces
      ?? data.total_spaces
      ?? data.parkingTotal,
  )

  const referencePosition = extractReferencePosition(data)

  return {
    spacesAvailable,
    spacesTotal,
    referencePosition,
  }
}

export function LDMProvider({ children }) {
  const [stations, setStations] = useState([])
  const [perceivedObjects, setPerceivedObjects] = useState([])
  const [pois, setPois] = useState([])
  const [ego, setEgo] = useState(null)
  const [status, setStatus] = useState('connecting')
  const [poimMetrics, setPoimMetrics] = useState({
    spacesAvailable: null,
    spacesTotal: null,
  })
  const [poimHistory, setPoimHistory] = useState([])
  const [poimReferencePosition, setPoimReferencePosition] = useState(null)
  const [messageFeed, setMessageFeed] = useState([])
  const wsRef = useRef(null)
  const reconnectRef = useRef(null)
  const poimMetricsRef = useRef(poimMetrics)
  const poimReferencePositionRef = useRef(poimReferencePosition)

  useEffect(() => {
    poimMetricsRef.current = poimMetrics
  }, [poimMetrics])

  useEffect(() => {
    poimReferencePositionRef.current = poimReferencePosition
  }, [poimReferencePosition])

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
          const payload = JSON.parse(event.data)

          if (payload && typeof payload === 'object' && isPoimMessage(payload)) {
            const parsedPoim = parsePoim(payload)

            setPoimMetrics((previous) => ({
              spacesAvailable: parsedPoim.spacesAvailable ?? previous.spacesAvailable,
              spacesTotal: parsedPoim.spacesTotal ?? previous.spacesTotal,
            }))

            if (parsedPoim.spacesAvailable !== null && parsedPoim.spacesTotal !== null && parsedPoim.spacesTotal > 0) {
              setPoimHistory((history) => {
                const next = [...history, {
                  timestamp: Date.now(),
                  spacesAvailable: parsedPoim.spacesAvailable,
                  spacesTotal: parsedPoim.spacesTotal,
                }]
                return next.slice(-POIM_HISTORY_LIMIT)
              })
            }

            if (parsedPoim.referencePosition && poimReferencePositionRef.current === null) {
              setPoimReferencePosition(parsedPoim.referencePosition)
            }

            if (parsedPoim.referencePosition) {
              const available = parsedPoim.spacesAvailable ?? poimMetricsRef.current.spacesAvailable
              const total = parsedPoim.spacesTotal ?? poimMetricsRef.current.spacesTotal
              const occupancyPercent = total && total > 0
                ? ((total - (available ?? 0)) / total) * 100
                : 0

              setPois([{
                id: 'poim-reference',
                name: 'POIM Reference',
                latitude: parsedPoim.referencePosition.latitude,
                longitude: parsedPoim.referencePosition.longitude,
                occupancy_percent: Math.max(0, Math.min(100, occupancyPercent)),
              }])
            }

            addFeedEntry('POIM', 'ref', parsedPoim)
            return
          }

          // Snapshot message from /ws/ldm endpoint
          if (Array.isArray(payload.stations)) {
            setStations(payload.stations)
            setPerceivedObjects(Array.isArray(payload.perceived_objects) ? payload.perceived_objects : [])
            setPois(Array.isArray(payload.pois) ? payload.pois : [])

            if (payload.ego && typeof payload.ego === 'object') {
              setEgo(payload.ego)
            }

            const objCount = Array.isArray(payload.perceived_objects) ? payload.perceived_objects.length : 0
            const poiCount = Array.isArray(payload.pois) ? payload.pois.length : 0
            payload.stations.forEach((station) => {
              addFeedEntry('CAM', station.station_id, station)
            })
            if (objCount > 0) {
              const cpmGroups = {}
              payload.perceived_objects.forEach((obj) => {
                const sid = String(obj.source_station_id ?? 'unknown')
                if (!cpmGroups[sid]) cpmGroups[sid] = []
                cpmGroups[sid].push(obj)
              })
              Object.entries(cpmGroups).forEach(([sid, objects]) => {
                addFeedEntry('CPM', sid, { source_station_id: sid, objects })
              })
            }
            if (poiCount > 0) {
              addFeedEntry('POIM', 'ref', payload.pois)
            }
          }
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

    function addFeedEntry(type, stationId, payload) {
      const key = `${type}-${stationId}`
      setMessageFeed((feed) => {
        const now = Date.now()
        const idx = feed.findIndex((e) => e.key === key)
        if (idx !== -1) {
          const updated = [...feed]
          updated[idx] = { ...updated[idx], timestamp: now, payload }
          return updated
        }
        const next = [{ key, type, stationId, timestamp: now, payload }, ...feed]
        return next.slice(0, FEED_LIMIT)
      })
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
    ego,
    status,
    poimMetrics,
    poimHistory,
    poimReferencePosition,
    messageFeed,
  }), [stations, perceivedObjects, pois, ego, status, poimMetrics, poimHistory, poimReferencePosition, messageFeed])

  return <LDMContext.Provider value={value}>{children}</LDMContext.Provider>
}

export function useLDM() {
  const context = useContext(LDMContext)
  if (!context) {
    throw new Error('useLDM must be used inside LDMProvider')
  }
  return context
}
