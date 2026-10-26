import { useEffect, useState } from 'react'
import { IntlRoute, fetchInternationalRoutes } from '../api/client'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

interface Props {
  iata: string
  onClose: () => void
}

const HOURS = Array.from({ length: 24 }, (_, i) => `${i}:00`)

export default function AirportPanel({ iata, onClose }: Props) {
  const [routes, setRoutes] = useState<IntlRoute[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<IntlRoute | null>(null)

  useEffect(() => {
    setLoading(true)
    setSelected(null)
    fetchInternationalRoutes(iata)
      .then(data => { setRoutes(data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [iata])

  const totalDemand = routes.reduce((s, r) => s + r.base_demand, 0)
  const totalRevenue = routes.reduce((s, r) => s + r.revenue_usd, 0)
  const totalFuel = routes.reduce((s, r) => s + r.fuel_cost_usd, 0)

  // Aggregate hourly demand across all routes
  const hourlyTotal = Array.from({ length: 24 }, (_, h) =>
    routes.reduce((s, r) => s + (r.hourly_demand[h] ?? 0), 0)
  )
  const hourlyChartData = HOURS.map((label, i) => ({ hour: label, demand: hourlyTotal[i] }))

  const selectedHourly = selected
    ? HOURS.map((label, i) => ({ hour: label, demand: selected.hourly_demand[i] ?? 0 }))
    : null

  return (
    <div className="absolute top-4 left-4 w-[360px] max-h-[calc(100vh-2rem)] bg-white border border-slate-300 rounded-none shadow-xl flex flex-col overflow-hidden z-50 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <div>
          <span className="text-orange-600 font-bold text-lg">{iata}</span>
          {routes[0] && (
            <span className="text-slate-500 text-xs ml-2 font-medium">
              {routes[0].origin === iata ? routes[0].origin_name : routes[0].dest_name}
            </span>
          )}
        </div>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-700 w-6 h-6 flex items-center justify-center rounded-none hover:bg-slate-100 transition-colors" aria-label="Close">
          <svg className="w-4 h-4 stroke-current" fill="none" viewBox="0 0 24 24" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {loading ? (
        <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">Loading routes…</div>
      ) : (
        <div className="flex-1 overflow-y-auto">
          {/* KPIs */}
          <div className="grid grid-cols-3 gap-2 p-3">
            <Stat label="Intl Routes" value={`${routes.length}`} color="text-blue-700" />
            <Stat label="Daily Pax" value={totalDemand.toLocaleString()} color="text-emerald-700" />
            <Stat label="Revenue" value={`$${(totalRevenue/1e6).toFixed(1)}M`} color="text-amber-700" />
          </div>

          {/* Hourly demand chart */}
          <div className="px-3 pb-2">
            <p className="text-xs text-slate-500 mb-1 font-medium">
              {selected ? `${selected.origin}→${selected.destination} hourly demand` : 'All routes — hourly demand today'}
            </p>
            <ResponsiveContainer width="100%" height={90}>
              <AreaChart data={selected ? selectedHourly! : hourlyChartData} margin={{ top: 0, right: 0, left: -30, bottom: 0 }}>
                <defs>
                  <linearGradient id="dg" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.35}/>
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="hour" tick={{ fontSize: 8, fill: '#64748b' }} interval={3}/>
                <YAxis tick={{ fontSize: 8, fill: '#64748b' }}/>
                <Tooltip contentStyle={{ background: '#ffffff', border: '1px solid #cbd5e1', color: '#0f172a', fontSize: 10, borderRadius: 0, boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}/>
                <Area type="monotone" dataKey="demand" stroke="#2563eb" fill="url(#dg)" strokeWidth={1.5}/>
              </AreaChart>
            </ResponsiveContainer>
          </div>

          {/* Route list */}
          <div className="px-3 pb-3">
            <p className="text-xs text-slate-500 mb-1 font-medium">International routes — click for details</p>
            <div className="space-y-1">
              {routes.map(r => {
                const other = r.origin === iata ? r.destination : r.origin
                const otherCity = r.origin === iata ? r.dest_city : r.origin_city
                const otherCountry = r.origin === iata ? r.dest_country : r.origin_country
                const isSelected = selected?.id === r.id
                return (
                  <button
                    key={r.id}
                    onClick={() => setSelected(isSelected ? null : r)}
                    className={`w-full text-left rounded-none px-2.5 py-2 text-xs transition-colors ${
                      isSelected ? 'bg-blue-50 border border-blue-400 shadow-xs' : 'bg-slate-50 hover:bg-slate-100 border border-slate-200'
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-mono font-bold text-slate-900">{iata} → {other}</span>
                      <span className="text-slate-500">{r.distance_km.toLocaleString()} km</span>
                    </div>
                    <div className="flex justify-between text-slate-600 mt-0.5">
                      <span>{otherCity}, {otherCountry}</span>
                      <span className="text-emerald-700 font-medium">{r.base_demand} pax/day · ${r.base_fare_usd}</span>
                    </div>
                    {isSelected && (
                      <div className="mt-1.5 grid grid-cols-2 gap-1 text-slate-700 pt-1 border-t border-blue-200">
                        <span>Fuel: <span className="text-orange-700 font-semibold">${r.fuel_cost_usd.toLocaleString()}</span></span>
                        <span>Revenue: <span className="text-emerald-700 font-semibold">${(r.revenue_usd/1000).toFixed(0)}k</span></span>
                      </div>
                    )}
                  </button>
                )
              })}
              {routes.length === 0 && (
                <p className="text-slate-500 text-xs text-center py-4">No international routes found for {iata}</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Stat({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-slate-50 border border-slate-200 rounded-none p-2 text-center shadow-none">
      <p className="text-slate-500 text-xs font-medium">{label}</p>
      <p className={`font-bold text-sm ${color}`}>{value}</p>
    </div>
  )
}
