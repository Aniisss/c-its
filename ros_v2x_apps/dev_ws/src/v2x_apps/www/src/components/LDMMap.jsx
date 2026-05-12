import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Car, CircleParking, RadioTower, UserRound, Wifi, WifiOff } from 'lucide-react'
import { renderToStaticMarkup } from 'react-dom/server'
import { useLDM } from '../context/LDMContext'

// Brussels fallback center used before first CAM station position is received.
const FALLBACK_CENTER = [50.85, 4.35]

function toNumber(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function stationTypeIcon(stationType) {
  if (stationType === 5) {
    return { Icon: Car, color: '#22d3ee' }
  }
  if (stationType === 15) {
    return { Icon: RadioTower, color: '#f59e0b' }
  }
  if (stationType === 1) {
    return { Icon: UserRound, color: '#a78bfa' }
  }
  return { Icon: Car, color: '#94a3b8' }
}

function occupancyColor(occupancyPercent) {
  if (occupancyPercent > 80) {
    return '#ef4444'
  }
  if (occupancyPercent >= 50) {
    return '#facc15'
  }
  return '#22c55e'
}

function createStationIcon(stationType, heading) {
  const { Icon, color } = stationTypeIcon(stationType)
  const rotation = toNumber(heading) ?? 0
  return L.divIcon({
    className: '',
    html: `<div style="width:30px;height:30px;border-radius:9999px;background:rgba(15,23,42,0.9);border:1px solid #334155;display:flex;align-items:center;justify-content:center;transform:rotate(${rotation}deg)">${renderToStaticMarkup(<Icon size={20} color={color} strokeWidth={2.2} />)}</div>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -14],
  })
}

function createParkingIcon(occupancyPercent) {
  const color = occupancyColor(occupancyPercent)
  return L.divIcon({
    className: '',
    html: `<div style="width:26px;height:26px;border-radius:9999px;background:rgba(15,23,42,0.9);border:1px solid #334155;display:flex;align-items:center;justify-content:center;box-shadow:0 0 0 1px rgba(15,23,42,0.3)">${renderToStaticMarkup(<CircleParking size={16} color={color} strokeWidth={2.3} />)}</div>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
    popupAnchor: [0, -10],
  })
}

function createEgoIcon(heading) {
  const rotation = toNumber(heading) ?? 0
  return L.divIcon({
    className: '',
    html: `<div style="width:36px;height:36px;border-radius:9999px;background:rgba(2,6,23,0.95);border:2px solid #f43f5e;display:flex;align-items:center;justify-content:center;transform:rotate(${rotation}deg);box-shadow:0 0 0 1px rgba(244,63,94,0.35)">${renderToStaticMarkup(<Car size={22} color="#fda4af" strokeWidth={2.3} />)}</div>`,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -16],
  })
}

function AutoCenter({ stations, egoFeature }) {
  const map = useMap()
  const hasCentered = useRef(false)
  const egoCoordinates = useMemo(() => {
    const longitude = toNumber(egoFeature?.geometry?.coordinates?.[0])
    const latitude = toNumber(egoFeature?.geometry?.coordinates?.[1])
    if (latitude === null || longitude === null) {
      return null
    }
    return [latitude, longitude]
  }, [egoFeature])
  const firstStation = useMemo(
    () => stations.find((station) => toNumber(station.latitude) !== null && toNumber(station.longitude) !== null),
    [stations],
  )

  useEffect(() => {
    if (hasCentered.current) {
      return
    }
    const anchor = egoCoordinates ?? (firstStation
      ? [Number(firstStation.latitude), Number(firstStation.longitude)]
      : null)
    if (!anchor) {
      return
    }
    map.setView(anchor, 16)
    hasCentered.current = true
  }, [egoCoordinates, firstStation, map])

  return null
}

function FollowEgoVehicle({ egoFeature, lockCamera }) {
  const map = useMap()
  const previousCoords = useRef(null)

  useEffect(() => {
    if (!lockCamera) {
      return
    }
    const longitude = toNumber(egoFeature?.geometry?.coordinates?.[0])
    const latitude = toNumber(egoFeature?.geometry?.coordinates?.[1])
    if (latitude === null || longitude === null) {
      return
    }

    const nextCoords = [latitude, longitude]
    if (!previousCoords.current) {
      map.setView(nextCoords, Math.max(map.getZoom(), 16))
      previousCoords.current = nextCoords
      return
    }
    map.panTo(nextCoords, { animate: true, duration: 0.6 })
    previousCoords.current = nextCoords
  }, [egoFeature, lockCamera, map])

  return null
}

function statusLabel(status) {
  if (status === 'live') {
    return 'Live'
  }
  if (status === 'connecting') {
    return 'Connecting'
  }
  return 'Disconnected'
}

export default function LDMMap() {
  const {
    stations, perceivedObjects, pois, egoFeature, latestPayloads, status,
  } = useLDM()
  const [showCam, setShowCam] = useState(true)
  const [showCpm, setShowCpm] = useState(true)
  const [showPoim, setShowPoim] = useState(true)
  const [lockCamera, setLockCamera] = useState(true)

  const stationsById = useMemo(() => {
    return new Map(stations.map((station) => [String(station.station_id), station]))
  }, [stations])

  const activeStations = useMemo(() => {
    return [...stations].sort((left, right) => {
      const leftRssi = toNumber(left.rssi) ?? -Infinity
      const rightRssi = toNumber(right.rssi) ?? -Infinity
      if (leftRssi !== rightRssi) {
        return rightRssi - leftRssi
      }
      return (toNumber(left.age_seconds) ?? Infinity) - (toNumber(right.age_seconds) ?? Infinity)
    })
  }, [stations])

  return (
    <div className="relative h-screen w-screen bg-slate-950 text-slate-100">
      <MapContainer center={FALLBACK_CENTER} zoom={13} className="h-full w-full">
        <TileLayer
          attribution="&copy; OpenStreetMap contributors"
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <AutoCenter stations={stations} egoFeature={egoFeature} />
        <FollowEgoVehicle egoFeature={egoFeature} lockCamera={lockCamera} />

        {showCam && egoFeature && (
          <Marker
            position={[
              Number(egoFeature.geometry.coordinates[1]),
              Number(egoFeature.geometry.coordinates[0]),
            ]}
            icon={createEgoIcon(egoFeature.properties?.heading)}
          >
            <Popup>
              <div className="text-sm text-slate-900">
                <div><b>Vehicle:</b> DS7 (ego)</div>
                <div><b>Speed:</b> {egoFeature.properties?.speed ?? 'n/a'}</div>
                <div><b>Heading:</b> {egoFeature.properties?.heading ?? 'n/a'}</div>
              </div>
            </Popup>
          </Marker>
        )}

        {showCam && stations.map((station) => {
          const latitude = toNumber(station.latitude)
          const longitude = toNumber(station.longitude)
          if (latitude === null || longitude === null) {
            return null
          }

          return (
            <Marker
              key={station.id}
              position={[latitude, longitude]}
              icon={createStationIcon(station.station_type, station.heading)}
            >
              <Popup>
                <div className="text-sm text-slate-900">
                  <div><b>Station ID:</b> {station.station_id}</div>
                  <div><b>Speed:</b> {station.speed ?? 'n/a'}</div>
                  <div><b>RSSI:</b> {station.rssi ?? 'n/a'}</div>
                </div>
              </Popup>
            </Marker>
          )
        })}

        {showCpm && perceivedObjects.map((object) => {
          const latitude = toNumber(object.latitude)
          const longitude = toNumber(object.longitude)
          if (latitude === null || longitude === null) {
            return null
          }

          const sourceStation = stationsById.get(String(object.source_station_id))
          const sourceLatitude = toNumber(sourceStation?.latitude)
          const sourceLongitude = toNumber(sourceStation?.longitude)

          return (
            <Fragment key={object.id}>
              <CircleMarker
                center={[latitude, longitude]}
                radius={5}
                pathOptions={{
                  color: '#7dd3fc',
                  fillColor: '#7dd3fc',
                  fillOpacity: 0.35,
                  weight: 1,
                }}
              >
                <Popup>
                  <div className="text-sm text-slate-900">
                    <div><b>Object:</b> {object.object_id}</div>
                    <div><b>Source Station:</b> {object.source_station_id}</div>
                  </div>
                </Popup>
              </CircleMarker>
              {sourceLatitude !== null && sourceLongitude !== null && (
                <Polyline
                  positions={[
                    [sourceLatitude, sourceLongitude],
                    [latitude, longitude],
                  ]}
                  pathOptions={{
                    color: '#94a3b8',
                    dashArray: '4 8',
                    opacity: 0.45,
                    weight: 1,
                  }}
                />
              )}
            </Fragment>
          )
        })}

        {showPoim && pois.map((poi) => {
          const latitude = toNumber(poi.latitude)
          const longitude = toNumber(poi.longitude)
          if (latitude === null || longitude === null) {
            return null
          }

          const occupancy = toNumber(poi.occupancy_percent) ?? 0
          return (
            <Marker
              key={poi.id}
              position={[latitude, longitude]}
              icon={createParkingIcon(occupancy)}
            >
              <Popup>
                <div className="text-sm text-slate-900">
                  <div><b>{poi.name ?? 'Parking'}</b></div>
                  <div>Occupancy: {Math.round(occupancy)}%</div>
                </div>
              </Popup>
            </Marker>
          )
        })}
      </MapContainer>

      <div className="absolute left-4 top-4 z-[1000] w-56 rounded-xl border border-slate-700 bg-slate-900/90 p-3 shadow-lg backdrop-blur-sm">
        <div className="mb-2 text-sm font-semibold text-slate-100">Layers</div>
        <label className="mb-1 flex items-center gap-2 text-sm text-slate-200">
          <input type="checkbox" checked={showCam} onChange={(event) => setShowCam(event.target.checked)} /> CAM
        </label>
        <label className="mb-1 flex items-center gap-2 text-sm text-slate-200">
          <input type="checkbox" checked={showCpm} onChange={(event) => setShowCpm(event.target.checked)} /> CPM
        </label>
        <label className="mb-1 flex items-center gap-2 text-sm text-slate-200">
          <input type="checkbox" checked={showPoim} onChange={(event) => setShowPoim(event.target.checked)} /> POIM
        </label>
        <label className="flex items-center gap-2 text-sm text-slate-200">
          <input type="checkbox" checked={lockCamera} onChange={(event) => setLockCamera(event.target.checked)} /> Lock Camera to Vehicle
        </label>
      </div>

      <div className="absolute right-4 top-4 z-[1000] rounded-xl border border-slate-700 bg-slate-900/90 px-3 py-2 shadow-lg backdrop-blur-sm">
        <div className="flex items-center gap-2 text-sm">
          {status === 'live' ? <Wifi size={16} className="text-emerald-400" /> : <WifiOff size={16} className="text-red-400" />}
          <span className="text-slate-100">{statusLabel(status)}</span>
        </div>
      </div>

      <aside className="absolute bottom-4 right-4 z-[1000] max-h-80 w-80 overflow-y-auto rounded-xl border border-slate-700 bg-slate-900/90 p-3 shadow-lg backdrop-blur-sm">
        <div className="mb-2 text-sm font-semibold text-slate-100">Log View</div>
        <div className="mb-2 text-xs text-slate-400">
          Latest update: {latestPayloads.updatedAt ? new Date(latestPayloads.updatedAt).toLocaleTimeString() : 'n/a'}
        </div>
        <ul className="space-y-2 text-sm text-slate-200">
          <li className="rounded-md border border-rose-600/40 bg-slate-950/60 p-2">
            <div className="font-medium text-rose-200">EGO (DS7)</div>
            <div>Lat/Lon: {toNumber(latestPayloads.ego?.latitude)?.toFixed(6) ?? 'n/a'}, {toNumber(latestPayloads.ego?.longitude)?.toFixed(6) ?? 'n/a'}</div>
            <div>Speed: {latestPayloads.ego?.speed ?? 'n/a'}</div>
            <div>Heading: {latestPayloads.ego?.heading ?? 'n/a'}</div>
          </li>
          <li className="rounded-md border border-cyan-500/40 bg-slate-950/60 p-2">
            <div className="font-medium text-cyan-200">CAM (Station)</div>
            <div>Station ID: {latestPayloads.cam?.station_id ?? 'n/a'}</div>
            <div>RSSI: {latestPayloads.cam?.rssi ?? 'n/a'}</div>
            <div>Age: {toNumber(latestPayloads.cam?.age_seconds)?.toFixed(1) ?? 'n/a'} s</div>
          </li>
          <li className="rounded-md border border-sky-400/40 bg-slate-950/60 p-2">
            <div className="font-medium text-sky-200">CPM (Perceived Object)</div>
            <div>Object ID: {latestPayloads.cpm?.object_id ?? 'n/a'}</div>
            <div>Source: {latestPayloads.cpm?.source_station_id ?? 'n/a'}</div>
            <div>Age: {toNumber(latestPayloads.cpm?.age_seconds)?.toFixed(1) ?? 'n/a'} s</div>
          </li>
          <li className="rounded-md border border-emerald-500/40 bg-slate-950/60 p-2">
            <div className="font-medium text-emerald-200">POIM (Parking)</div>
            <div>Name: {latestPayloads.poim?.name ?? 'n/a'}</div>
            <div>Occupancy: {toNumber(latestPayloads.poim?.occupancy_percent)?.toFixed(0) ?? 'n/a'}%</div>
            <div>Age: {toNumber(latestPayloads.poim?.age_seconds)?.toFixed(1) ?? 'n/a'} s</div>
          </li>
          {activeStations.length > 0 && (
            <li className="rounded-md border border-slate-700 bg-slate-950/60 p-2 text-xs text-slate-300">
              Active CAM stations: {activeStations.length}
            </li>
          )}
        </ul>
      </aside>
    </div>
  )
}
