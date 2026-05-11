import { Pie, PieChart, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from 'recharts'

function toPercent(available, total) {
  if (!Number.isFinite(available) || !Number.isFinite(total) || total <= 0) {
    return 0
  }
  return Math.max(0, Math.min(100, (available / total) * 100))
}

export default function ParkingOccupancyGauge({ spacesAvailable, spacesTotal, history }) {
  const available = Number.isFinite(spacesAvailable) ? spacesAvailable : 0
  const total = Number.isFinite(spacesTotal) ? spacesTotal : 0
  const availablePercent = toPercent(available, total)

  const gaugeData = [
    { name: 'Available', value: availablePercent },
    { name: 'Used', value: 100 - availablePercent },
  ]

  const historyData = history.map((entry) => ({
    time: new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
    availablePercent: toPercent(entry.spacesAvailable, entry.spacesTotal),
  }))

  return (
    <section className="w-80 rounded-xl border border-slate-700 bg-slate-900/90 p-3 shadow-lg backdrop-blur-sm">
      <h2 className="text-sm font-semibold text-slate-100">Parking Occupancy Gauge</h2>
      <div className="mt-3 h-44">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={gaugeData}
              innerRadius={52}
              outerRadius={70}
              startAngle={210}
              endAngle={-30}
              dataKey="value"
              stroke="none"
            >
              <Cell fill="#22c55e" />
              <Cell fill="#ef4444" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="-mt-24 mb-12 text-center">
        <div className="text-3xl font-bold text-slate-100">{availablePercent.toFixed(0)}%</div>
        <div className="text-xs text-slate-300">Available</div>
        <div className="mt-1 text-xs text-slate-400">{available} / {total || 'n/a'} spaces</div>
      </div>
      <div className="h-28">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={historyData} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
            <CartesianGrid stroke="#334155" strokeDasharray="4 4" />
            <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 10 }} minTickGap={28} />
            <YAxis domain={[0, 100]} tick={{ fill: '#94a3b8', fontSize: 10 }} width={30} />
            <Tooltip
              contentStyle={{ background: '#0f172a', border: '1px solid #334155', color: '#e2e8f0' }}
              formatter={(value) => [`${Number(value).toFixed(0)}%`, 'Available']}
            />
            <Line type="monotone" dataKey="availablePercent" stroke="#22c55e" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
