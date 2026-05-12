import { Zap, Accessibility, Shield, Camera, CircleParking, Radio } from 'lucide-react'

const AMENITY_CONFIG = {
  'Electric Charging': { Icon: Zap,          color: '#facc15', label: 'EV Charging' },
  'Handicap Access':   { Icon: Accessibility, color: '#60a5fa', label: 'Accessible'  },
  'CCTV':              { Icon: Camera,        color: '#a78bfa', label: 'CCTV'        },
  '24h Security':      { Icon: Shield,        color: '#34d399', label: 'Security'    },
}

function getStatusStyle(status) {
  const s = String(status ?? 'Open')
  if (s === 'Full')        return { color: '#ef4444', bg: 'rgba(239,68,68,0.12)'   }
  if (s === 'Almost Full') return { color: '#f97316', bg: 'rgba(249,115,22,0.12)'  }
  if (s === 'Closed')      return { color: '#94a3b8', bg: 'rgba(148,163,184,0.12)' }
  return                          { color: '#22c55e', bg: 'rgba(34,197,94,0.12)'   }
}

function getOccupancyColor(pct) {
  if (pct > 80) return '#ef4444'
  if (pct >= 50) return '#facc15'
  return '#22c55e'
}

export default function ParkingInfoPanel({ poi }) {
  if (!poi) {
    return (
      <section
        className="w-80 rounded-xl border border-slate-700 bg-slate-900/90 p-4 shadow-lg backdrop-blur-sm"
        aria-label="Parking info"
      >
        <div className="flex flex-col items-center gap-2 py-4 text-center">
          <Radio size={28} className="animate-pulse text-sky-400" />
          <p className="text-sm font-semibold text-slate-200">Searching for V2X Parking…</p>
          <p className="text-xs text-slate-500">No facilities in range</p>
        </div>
      </section>
    )
  }

  const occupancy      = Math.max(0, Math.min(100, Number(poi.occupancy_percent) || 0))
  const status         = poi.status ?? 'Open'
  const parkingType    = poi.parking_type ?? null
  const amenities      = Array.isArray(poi.amenities) ? poi.amenities : []
  const totalSpots     = poi.total_spots != null ? Number(poi.total_spots) : null
  const availableSpots = poi.available_spots != null
    ? Number(poi.available_spots)
    : (totalSpots != null ? Math.round(totalSpots * (1 - occupancy / 100)) : null)

  const statusStyle = getStatusStyle(status)
  const barColor    = getOccupancyColor(occupancy)

  return (
    <section
      className="w-80 overflow-hidden rounded-xl border border-slate-700 bg-slate-900/90 shadow-lg backdrop-blur-sm"
      aria-label="Parking info"
    >
      {/* ── Header ── */}
      <div className="flex items-start gap-3 border-b border-slate-700/60 bg-slate-950/40 p-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
          style={{ background: 'rgba(34,197,94,0.12)', boxShadow: '0 0 12px rgba(34,197,94,0.2)' }}
        >
          <CircleParking size={22} color="#22c55e" strokeWidth={2.2} />
        </div>
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-sm font-bold leading-tight text-slate-100">
            {poi.name ?? 'Parking Facility'}
          </h2>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            {parkingType && (
              <span className="text-xs text-slate-400">{parkingType}</span>
            )}
            <span
              className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs font-semibold"
              style={{ color: statusStyle.color, background: statusStyle.bg }}
            >
              <span
                className="inline-block h-1.5 w-1.5 rounded-full"
                style={{ background: statusStyle.color }}
              />
              {status}
            </span>
          </div>
        </div>
      </div>

      {/* ── Occupancy ── */}
      <div className="border-b border-slate-700/60 px-3 py-2.5">
        <div className="mb-1.5 flex items-center justify-between">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">Availability</span>
          <span className="text-sm font-bold" style={{ color: barColor }}>
            {Math.round(occupancy)}% occupied
          </span>
        </div>
        <div className="h-2.5 overflow-hidden rounded-full bg-slate-700/60">
          <div
            className="h-full rounded-full transition-all duration-700"
            style={{ width: `${occupancy}%`, background: barColor }}
          />
        </div>
        <div className="mt-1.5 flex items-center justify-between text-xs text-slate-400">
          <span>
            <span className="font-mono font-bold text-slate-200">
              {availableSpots != null ? availableSpots : 'n/a'}
            </span>{' '}
            free
          </span>
          {totalSpots != null && <span>{totalSpots} total</span>}
        </div>
      </div>

      {/* ── Amenities ── */}
      {amenities.length > 0 && (
        <div className="px-3 py-2">
          <p className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Amenities</p>
          <div className="flex flex-wrap gap-1.5">
            {amenities.map((amenity) => {
              const config = AMENITY_CONFIG[amenity]
              if (!config) {
                return (
                  <span key={amenity} className="rounded bg-slate-800 px-1.5 py-0.5 text-xs text-slate-400">
                    {amenity}
                  </span>
                )
              }
              const { Icon, color, label } = config
              return (
                <span
                  key={amenity}
                  className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-xs"
                  style={{ color, background: 'rgba(15,23,42,0.6)', border: `1px solid ${color}30` }}
                >
                  <Icon size={11} strokeWidth={2.3} />
                  {label}
                </span>
              )
            })}
          </div>
        </div>
      )}
    </section>
  )
}
