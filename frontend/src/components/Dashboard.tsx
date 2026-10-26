import { useState } from 'react'
import { OptimizedRoute, LiveFlight } from '../api/client'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

interface Props {
  routes: OptimizedRoute[]; flights: LiveFlight[]
  hub: string; season: string
  onSeasonChange:(s:string)=>void; onHubChange:(h:string)=>void
  onOptimize:()=>void; loading:boolean
  showRoutes:boolean; showFlights:boolean; showAllAirports:boolean
  onToggleRoutes:()=>void; onToggleFlights:()=>void; onToggleAllAirports:()=>void
  liveCount:number; connected:boolean
}

const HUBS = ['DEL','BOM','MAA','BLR','HYD','COK','CJB','LHR','CDG','FRA','AMS','ZRH','MUC','FCO','MAD','JFK','LAX','ORD','YYZ','MIA','DXB','DOH','AUH','IST','CAI','SIN','BKK','KUL','HKG','NRT','ICN','PEK','PVG','SYD','MEL','JNB','GRU','EZE']

export default function Dashboard({ routes, flights, hub, season, onSeasonChange, onHubChange, onOptimize, loading, showRoutes, showFlights, showAllAirports, onToggleRoutes, onToggleFlights, onToggleAllAirports, liveCount, connected }: Props) {
  const [tab, setTab] = useState<'live'|'routes'|'model'>('live')
  const [expandedRoute, setExpandedRoute] = useState<number|null>(null)

  const totalProfit  = routes.reduce((s,r)=>s+r.profit_usd,0)
  const totalFuel    = routes.reduce((s,r)=>s+r.fuel_cost_usd,0)
  const totalWind    = routes.reduce((s,r)=>s+r.wind_saving_usd,0)
  const detourRoutes = routes.filter(r=>r.detour_km>0)

  const byCountry = flights.reduce<Record<string,number>>((a,f)=>{ a[f.country]=(a[f.country]||0)+1; return a },{})
  const topCountries = Object.entries(byCountry).sort((a,b)=>b[1]-a[1]).slice(0,8)
  const maxC = topCountries[0]?.[1]||1

  const chartData = [...routes].sort((a,b)=>b.profit_usd-a.profit_usd).slice(0,8).map(r=>({
    name:`${r.origin}-${r.dest}`,
    profit:Math.round(r.profit_usd/1000),
    fuel:Math.round(r.fuel_cost_usd/1000),
    wind:Math.round(r.wind_saving_usd/1000),
  }))

  return (
    <div className="w-[420px] h-screen bg-white border-l border-slate-200 flex flex-col overflow-hidden shrink-0 font-sans">

      {/* Brand */}
      <div className="px-4 py-2.5 bg-white border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-none bg-orange-600 flex items-center justify-center text-white">
            <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
              <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>
            </svg>
          </div>
          <div>
            <span className="text-slate-900 font-bold text-sm">SkyOpt</span>
            <span className="text-slate-500 text-xs ml-1.5 font-medium">Route Intelligence</span>
          </div>
        </div>
        <div className="flex items-center gap-1.5">
          <span className={`w-2 h-2 rounded-none ${connected?'bg-emerald-500 animate-pulse':'bg-red-500'}`}/>
          <span className={`text-xs font-mono font-semibold ${connected?'text-emerald-700':'text-red-600'}`}>
            {connected?`${liveCount.toLocaleString()} live`:'reconnecting…'}
          </span>
        </div>
      </div>

      {/* Layer toggles */}
      <div className="grid grid-cols-3 gap-1 px-3 py-2 bg-slate-50 border-b border-slate-200">
        <Tog active={showFlights}     onClick={onToggleFlights}     label="Flights"  color="blue"/>
        <Tog active={showRoutes}      onClick={onToggleRoutes}      label="Routes"   color="orange"/>
        <Tog active={showAllAirports} onClick={onToggleAllAirports} label="Airports" color="green"/>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 bg-white shrink-0">
        {(['live','routes','model'] as const).map(t=>(
          <button key={t} onClick={()=>setTab(t)}
            className={`flex-1 py-2 text-xs font-semibold capitalize transition-colors rounded-none ${tab===t?'text-orange-600 border-b-2 border-orange-600 bg-orange-50/50':'text-slate-600 hover:text-slate-900 hover:bg-slate-50'}`}>
            {t==='live'?'Live':t==='routes'?'Optimize':'Model'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto">

        {/* ── LIVE TAB ── */}
        {tab==='live' && (
          <div className="p-3 space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <KPI label="Airborne" value={liveCount.toLocaleString()} color="text-blue-700"/>
              <KPI label="Countries" value={Object.keys(byCountry).length.toString()} color="text-purple-700"/>
              <KPI label="Source" value="ADS-B" color="text-emerald-700"/>
            </div>

            <div className="bg-white rounded-none p-3 border border-slate-200">
              <p className="text-slate-700 text-xs font-bold mb-2">TOP COUNTRIES BY AIRBORNE FLIGHTS</p>
              <div className="space-y-2">
                {topCountries.map(([country,n])=>(
                  <div key={country} className="flex items-center gap-2">
                    <span className="text-slate-800 text-xs w-32 truncate font-medium">{country}</span>
                    <div className="flex-1 bg-slate-100 rounded-none h-1.5">
                      <div className="bg-blue-600 h-1.5 rounded-none transition-all" style={{width:`${(n/maxC)*100}%`}}/>
                    </div>
                    <span className="text-slate-600 text-xs w-10 text-right font-mono font-medium">{n}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-none p-3 border border-slate-200 text-xs text-slate-700 space-y-1.5">
              <p className="text-slate-900 font-bold">HOW TO USE</p>
              <p>• Click any aircraft → live altitude, speed, heading</p>
              <p>• Click any airport dot → international routes</p>
              <p>• Go to Optimize tab → select hub → Run</p>
              <p>• Toggle Airports to see all 9,000+ airports</p>
            </div>
          </div>
        )}

        {/* ── ROUTES TAB ── */}
        {tab==='routes' && (
          <div className="p-3 space-y-3">
            {/* Controls */}
            <div className="flex gap-2">
              <select className="bg-white text-slate-900 rounded-none px-2 py-2 text-xs flex-1 border border-slate-300 font-medium"
                value={hub} onChange={e=>onHubChange(e.target.value)}>
                {HUBS.map(h=><option key={h}>{h}</option>)}
              </select>
              <select className="bg-white text-slate-900 rounded-none px-2 py-2 text-xs border border-slate-300 font-medium"
                value={season} onChange={e=>onSeasonChange(e.target.value)}>
                <option value="winter">Winter</option>
                <option value="summer">Summer</option>
              </select>
              <button onClick={onOptimize} disabled={loading}
                className="bg-orange-600 hover:bg-orange-700 disabled:opacity-40 text-white rounded-none px-4 py-2 text-xs font-bold transition-colors">
                {loading?'…':'RUN'}
              </button>
            </div>

            {routes.length>0 ? (
              <>
                {/* KPIs */}
                <div className="grid grid-cols-2 gap-2">
                  <KPI label="Total Profit"  value={`$${(totalProfit/1e6).toFixed(1)}M`}  color="text-emerald-700"/>
                  <KPI label="Fuel Cost"     value={`$${(totalFuel/1e6).toFixed(1)}M`}    color="text-orange-700"/>
                  <KPI label="Wind Savings"  value={`$${(totalWind/1e3).toFixed(0)}k`}    color="text-sky-700"/>
                  <KPI label="Detour Routes" value={`${detourRoutes.length}`}              color="text-amber-700"/>
                </div>

                {/* Legend */}
                <div className="bg-white rounded-none p-2.5 border border-slate-200">
                  <p className="text-slate-700 text-xs font-bold mb-1.5">ARC COLORS</p>
                  <div className="grid grid-cols-2 gap-1 text-xs">
                    {[['bg-emerald-500','Wind tailwind'],['bg-orange-500','Airspace detour'],['bg-red-500','Unprofitable'],['bg-blue-500','Normal route']].map(([cls,lbl])=>(
                      <div key={lbl} className="flex items-center gap-1.5 text-slate-700">
                        <span className={`w-2 h-2 rounded-none ${cls} shrink-0`}/>{lbl}
                      </div>
                    ))}
                  </div>
                </div>

                {/* Chart */}
                <div className="bg-white rounded-none p-3 border border-slate-200">
                  <p className="text-slate-700 text-xs font-bold mb-2">PROFIT / FUEL / WIND ($k)</p>
                  <ResponsiveContainer width="100%" height={140}>
                    <BarChart data={chartData} margin={{top:0,right:0,left:-25,bottom:0}}>
                      <XAxis dataKey="name" tick={{fontSize:8,fill:'#475569'}} interval={0} angle={-35} textAnchor="end" height={40}/>
                      <YAxis tick={{fontSize:8,fill:'#475569'}}/>
                      <Tooltip contentStyle={{background:'#ffffff',border:'1px solid #cbd5e1',color:'#0f172a',fontSize:10,borderRadius:0,boxShadow:'0 4px 6px -1px rgba(0,0,0,0.1)'}}/>
                      <Bar dataKey="profit" fill="#16a34a" name="Profit $k" radius={[0,0,0,0]}/>
                      <Bar dataKey="fuel"   fill="#ea580c" name="Fuel $k"   radius={[0,0,0,0]}/>
                      <Bar dataKey="wind"   fill="#2563eb" name="Wind $k"   radius={[0,0,0,0]}/>
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                {/* Route cards */}
                <div className="space-y-2">
                  {routes.map(r=>(
                    <div key={r.route_id}
                      className="bg-white border border-slate-200 rounded-none overflow-hidden cursor-pointer hover:border-slate-400 transition-all"
                      onClick={()=>setExpandedRoute(expandedRoute===r.route_id?null:r.route_id)}>
                      {/* Route header */}
                      <div className="px-3 py-2.5 flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-none shrink-0 ${r.profit_usd<0?'bg-red-500':r.detour_km>0?'bg-orange-500':r.wind_saving_usd>0?'bg-emerald-500':'bg-blue-500'}`}/>
                          <span className="text-slate-900 font-mono font-bold text-sm">{r.origin} → {r.dest}</span>
                          <span className="text-slate-500 text-xs">{r.distance_km?.toLocaleString()} km</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-bold ${r.profit_usd<0?'text-red-600':'text-emerald-700'}`}>
                            ${(r.profit_usd/1000).toFixed(0)}k
                          </span>
                          <span className="text-slate-400 text-xs">{expandedRoute===r.route_id?'▲':'▼'}</span>
                        </div>
                      </div>

                      {/* Expanded detail */}
                      {expandedRoute===r.route_id && (
                        <div className="px-3 pb-3 border-t border-slate-100 pt-2.5 space-y-2">
                          {/* Cities */}
                          <p className="text-slate-600 text-xs font-medium">{r.origin_city||r.origin} → {r.dest_city||r.dest}</p>

                          {/* Aircraft */}
                          <div className="bg-slate-50 border border-slate-200 rounded-none p-2.5">
                            <p className="text-slate-800 text-xs font-bold mb-1.5">AIRCRAFT</p>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                              <span className="text-slate-900 font-semibold">{r.aircraft_type}</span>
                              <span className="text-slate-600">{r.aircraft_category}</span>
                              <span className="text-slate-600">Seats: <span className="text-slate-900 font-medium">{r.aircraft_seats}</span></span>
                              <span className="text-slate-600">Range: <span className="text-slate-900 font-medium">{r.aircraft_range_km?.toLocaleString()} km</span></span>
                              <span className="text-slate-600 col-span-2">Engine: <span className="text-slate-900 font-medium">{r.aircraft_engine}</span></span>
                            </div>
                          </div>

                          {/* Airlines */}
                          <div className="bg-slate-50 border border-slate-200 rounded-none p-2.5">
                            <p className="text-slate-800 text-xs font-bold mb-1.5">AIRLINES</p>
                            <div className="flex flex-wrap gap-1.5">
                              {r.airlines?.map(a=>(
                                <span key={a} className="bg-white border border-slate-300 text-slate-800 text-xs px-2 py-0.5 rounded-none font-medium">{a}</span>
                              ))}
                            </div>
                          </div>

                          {/* Economics */}
                          <div className="bg-slate-50 border border-slate-200 rounded-none p-2.5">
                            <p className="text-slate-800 text-xs font-bold mb-1.5">ECONOMICS</p>
                            <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                              <span className="text-slate-600">Frequency</span><span className="text-slate-900 font-medium">{r.frequency}×/week</span>
                              <span className="text-slate-600">Demand</span><span className="text-slate-900 font-medium">{r.demand_pax} pax/day</span>
                              <span className="text-slate-600">Fare</span><span className="text-slate-900 font-medium">${r.fare_usd}</span>
                              <span className="text-slate-600">Load Factor</span>
                              <span className={`font-semibold ${r.load_factor>0.8?'text-emerald-700':r.load_factor>0.6?'text-amber-700':'text-red-600'}`}>
                                {(r.load_factor*100).toFixed(0)}%
                              </span>
                              <span className="text-slate-600">Fuel Cost</span><span className="text-orange-700 font-semibold">${(r.fuel_cost_usd/1000).toFixed(0)}k</span>
                              <span className="text-slate-600">Profit</span>
                              <span className={`font-semibold ${r.profit_usd<0?'text-red-600':'text-emerald-700'}`}>${(r.profit_usd/1000).toFixed(0)}k</span>
                            </div>
                          </div>

                          {/* Constraints */}
                          {r.detour_km>0 && (
                            <div className="bg-amber-50 border border-amber-300 rounded-none p-2.5">
                              <p className="text-amber-900 text-xs font-bold">AIRSPACE CONSTRAINT</p>
                              <p className="text-amber-800 text-xs mt-1">{r.active_constraints?.join(', ')}</p>
                              <p className="text-amber-700 text-xs">+{r.detour_km} km detour · extra fuel cost</p>
                            </div>
                          )}
                          {r.wind_saving_usd>0 && (
                            <div className="bg-sky-50 border border-sky-300 rounded-none p-2.5">
                              <p className="text-sky-900 text-xs font-bold">WIND ECONOMICS</p>
                              <p className="text-sky-800 text-xs mt-1">{r.wind_label?.replace(/_/g,' ')}</p>
                              <p className="text-sky-700 text-xs">Saving: ${(r.wind_saving_usd/1000).toFixed(1)}k/week</p>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <div className="text-center py-12 text-slate-500">
                <div className="w-12 h-12 mx-auto mb-3 rounded-none bg-slate-100 flex items-center justify-center text-slate-400">
                  <svg className="w-6 h-6 fill-current" viewBox="0 0 24 24">
                    <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>
                  </svg>
                </div>
                <p className="text-sm font-bold text-slate-800">Select a hub airport and click RUN</p>
                <p className="text-xs text-slate-500 mt-1 max-w-[280px] mx-auto">Optimizer uses OR-Tools CP-SAT with fuel economics, wind corridors and airspace constraints</p>
              </div>
            )}
          </div>
        )}

        {/* ── MODEL TAB ── */}
        {tab==='model' && (
          <div className="p-3 space-y-3">
            <div className="bg-white rounded-none p-3 border border-slate-200">
              <p className="text-slate-800 text-xs font-bold mb-2">PYTORCH DEMAND MODEL</p>
              <div className="space-y-1.5 text-xs text-slate-600">
                <Row k="Architecture" v="3-layer MLP + BatchNorm + Dropout"/>
                <Row k="Layers" v="128 → 64 → 32 → 1"/>
                <Row k="Loss" v="Huber Loss"/>
                <Row k="Optimizer" v="Adam + ReduceLROnPlateau"/>
                <Row k="Training data" v="150,000 routes"/>
                <Row k="Val MAE" v="~1.4 passengers"/>
                <Row k="Best val loss" v="0.0004"/>
              </div>
            </div>

            <div className="bg-white rounded-none p-3 border border-slate-200">
              <p className="text-slate-800 text-xs font-bold mb-2">ANOVA FEATURES (F-test)</p>
              <div className="space-y-1.5 text-xs text-slate-600">
                <Row k="log_distance" v="Route distance (log)"/>
                <Row k="size_origin" v="Airport size (large/med/small)"/>
                <Row k="continent" v="Origin/dest continent"/>
                <Row k="is_transatlantic" v="Crosses Atlantic?"/>
                <Row k="is_transpacific" v="Crosses Pacific?"/>
                <Row k="elevation" v="Airport elevation penalty"/>
                <Row k="is_international" v="Cross-border route?"/>
                <Row k="same_continent" v="Same continent?"/>
              </div>
            </div>

            <div className="bg-white rounded-none p-3 border border-slate-200">
              <p className="text-slate-800 text-xs font-bold mb-2">DATA SOURCES</p>
              <div className="space-y-1.5 text-xs text-slate-600">
                <Row k="Airports" v="OurAirports.com (9,228)"/>
                <Row k="Routes" v="OpenFlights (267,946)"/>
                <Row k="Live flights" v="OpenSky ADS-B (12k+)"/>
                <Row k="Optimization" v="Google OR-Tools CP-SAT"/>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function KPI({ label, value, color }: { label:string; value:string; color:string }) {
  return (
    <div className="bg-white rounded-none p-2.5 border border-slate-200">
      <p className="text-slate-500 text-xs font-medium mb-1">{label}</p>
      <p className={`font-bold text-sm ${color}`}>{value}</p>
    </div>
  )
}

function Tog({ active, onClick, label, color }: { active:boolean; onClick:()=>void; label:string; color:string }) {
  const activeClass = color==='blue'
    ? 'bg-blue-600 text-white border-blue-600'
    : color==='orange'
    ? 'bg-orange-600 text-white border-orange-600'
    : 'bg-emerald-600 text-white border-emerald-600'
  return (
    <button onClick={onClick}
      className={`rounded-none px-2 py-1.5 text-xs font-semibold transition-all border ${active?activeClass:'bg-white text-slate-700 border-slate-300 hover:bg-slate-100 hover:text-slate-900'}`}>
      {label}
    </button>
  )
}

function Row({ k, v }: { k:string; v:string }) {
  return (
    <div className="flex justify-between">
      <span className="text-slate-500">{k}</span>
      <span className="text-slate-800 font-medium text-right">{v}</span>
    </div>
  )
}
