import { Fragment, useEffect, useMemo, useRef, useState } from 'react'
import { CircleMarker, MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet'
import L from 'leaflet'
import { Car, CircleParking, RadioTower, UserRound } from 'lucide-react'
import { renderToStaticMarkup } from 'react-dom/server'
import { useLDM } from '../context/LDMContext'
import ParkingOccupancyGauge from './ParkingOccupancyGauge'

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

function AutoCenter({ referencePosition }) {
  const map = useMap()
  const hasCentered = useRef(false)

  useEffect(() => {
    if (!referencePosition || hasCentered.current) {
      return
    }

    const latitude = toNumber(referencePosition.latitude)
    const longitude = toNumber(referencePosition.longitude)
    if (latitude === null || longitude === null) {
      return
    }

    map.setView([latitude, longitude], 16)
    hasCentered.current = true
  }, [referencePosition, map])

  return null
}

export default function LDMMap() {
  const {
    stations,
    perceivedObjects,
    pois,
    status,
    poimMetrics,
    poimHistory,
    poimReferencePosition,
  } = useLDM()

  const [showCam, setShowCam] = useState(true)
  const [showCpm, setShowCpm] = useState(true)
  const [showPoim, setShowPoim] = useState(true)

  const stationsById = useMemo(() => new Map(stations.map((station) => [String(station.station_id), station])), [stations])

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

  const isConnected = status === 'live'

  return (
    <div className="relative h-screen w-screen bg-slate-950 text-slate-100">
      <MapContainer center={FALLBACK_CENTER} zoom={13} className="h-full w-full">
        <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <AutoCenter referencePosition={poimReferencePosition} />

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
        <label className="flex items-center gap-2 text-sm text-slate-200">
          <input type="checkbox" checked={showPoim} onChange={(event) => setShowPoim(event.target.checked)} /> POIM
        </label>
      </div>

      <div className="absolute right-4 top-4 z-[1000] rounded-xl border border-slate-700 bg-slate-900/90 px-3 py-2 shadow-lg backdrop-blur-sm">
        <div className="flex items-center gap-2 text-sm text-slate-100">
          <span className={`inline-flex h-3 w-3 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-red-400'} animate-pulse`} />
          <span>{isConnected ? 'Connected to ROS Backend' : 'Disconnected from ROS Backend'}</span>
        </div>
      </div>

      <aside className="absolute bottom-4 left-4 z-[1000]">
        <ParkingOccupancyGauge
          spacesAvailable={poimMetrics.spacesAvailable}
          spacesTotal={poimMetrics.spacesTotal}
          history={poimHistory}
        />
      </aside>

      <aside className="absolute bottom-4 right-4 z-[1000] max-h-80 w-80 overflow-y-auto rounded-xl border border-slate-700 bg-slate-900/90 p-3 shadow-lg backdrop-blur-sm">
        <div className="mb-2 text-sm font-semibold text-slate-100">Active Stations</div>
        <ul className="space-y-2 text-sm text-slate-200">
          {activeStations.length === 0 && <li className="text-slate-400">No active stations</li>}
          {activeStations.map((station) => (
            <li key={station.id} className="rounded-md border border-slate-700 bg-slate-950/60 p-2">
              <div className="font-medium text-slate-100">Station {station.station_id}</div>
              <div>RSSI: {station.rssi ?? 'n/a'}</div>
              <div>Age: {toNumber(station.age_seconds)?.toFixed(1) ?? 'n/a'} s</div>
            </li>
          ))}
        </ul>
      </aside>
    </div>
  )
}
