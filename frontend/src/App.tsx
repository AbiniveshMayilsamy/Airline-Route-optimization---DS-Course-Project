import { useState, useEffect } from 'react'
import GlobeView from './components/Globe'
import Dashboard from './components/Dashboard'
import AirportPanel from './components/AirportPanel'
import FlightPanel from './components/FlightPanel'
import ErrorBoundary from './components/ErrorBoundary'
import { fetchAirports, fetchOptimizedRoutes, runOptimize, OptimizedRoute, Airport } from './api/client'
import { useLiveFlights } from './api/useFlights'

export default function App() {
  const [airports, setAirports]           = useState<Airport[]>([])
  const [routes, setRoutes]               = useState<OptimizedRoute[]>([])
  const [hub, setHub]                     = useState('DEL')
  const [season, setSeason]               = useState('winter')
  const [loading, setLoading]             = useState(false)
  const [selectedIata, setSelectedIata]   = useState<string|null>(null)
  const [selectedIcao, setSelectedIcao]   = useState<string|null>(null)
  const [showRoutes, setShowRoutes]       = useState(true)
  const [showFlights, setShowFlights]     = useState(true)
  const [showAllAirports, setShowAllAirports] = useState(false)
  const [backendError, setBackendError]   = useState(false)

  const { flights, count, connected } = useLiveFlights()

  useEffect(() => {
    fetchAirports().then(setAirports).catch(() => setBackendError(true))
    fetchOptimizedRoutes().then(setRoutes).catch(() => setBackendError(true))
  }, [])

  const handleOptimize = async () => {
    setLoading(true)
    try {
      const result = await runOptimize({ hub_iata: hub, season: season as 'winter'|'summer', max_routes: 20, fleet_size: 15 })
      setRoutes(result)
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }

  const selectedFlight = selectedIcao ? flights.find(f => f.icao24 === selectedIcao) ?? null : null

  return (
    <div className="flex h-screen overflow-hidden font-sans" style={{ background: '#000010', color: '#f1f5f9' }}>
      {backendError && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 9999,
          background: '#7c2d12', color: '#fed7aa', padding: '8px 16px',
          fontSize: 13, fontFamily: 'Trebuchet MS, sans-serif',
          display: 'flex', alignItems: 'center', gap: 10
        }}>
          <span>⚠️</span>
          <strong>Backend API offline</strong> — Globe and data panels will be empty. Start Docker Desktop or the backend server to connect.
          <button onClick={() => setBackendError(false)} style={{ marginLeft: 'auto', background: 'none', border: 'none', color: '#fed7aa', cursor: 'pointer', fontSize: 16 }}>×</button>
        </div>
      )}
      <div className="flex-1 relative">
        <ErrorBoundary>
          <GlobeView
          routes={routes} airports={airports} hub={hub} flights={flights}
          onAirportClick={(iata) => { setSelectedIata(iata); setSelectedIcao(null) }}
          onFlightClick={(f)    => { setSelectedIcao(f.icao24); setSelectedIata(null) }}
          selectedIata={selectedIata} selectedIcao={selectedIcao}
            showRoutes={showRoutes} showFlights={showFlights} showAllAirports={showAllAirports}
          />
        </ErrorBoundary>

        {selectedIata && (
          <AirportPanel iata={selectedIata} onClose={() => setSelectedIata(null)} />
        )}

        {selectedFlight && (
          <FlightPanel flight={selectedFlight} onClose={() => setSelectedIcao(null)} />
        )}

        {/* Live badge */}
        {!selectedIata && !selectedFlight && (
          <div className="absolute top-4 left-4 flex items-center gap-2 bg-white rounded-none px-3 py-1.5 border border-slate-300 shadow-sm backdrop-blur">
            <span className={`w-2 h-2 rounded-none ${connected?'bg-emerald-500 animate-pulse':'bg-red-500'}`}/>
            <span className={`text-xs font-mono font-semibold ${connected?'text-emerald-700':'text-red-600'}`}>
              {connected ? `${count.toLocaleString()} flights live` : 'connecting…'}
            </span>
          </div>
        )}
      </div>

      <Dashboard
        routes={routes} flights={flights} hub={hub} season={season}
        onHubChange={(h) => { setHub(h); setSelectedIata(null) }}
        onSeasonChange={setSeason}
        onOptimize={handleOptimize} loading={loading}
        showRoutes={showRoutes} showFlights={showFlights} showAllAirports={showAllAirports}
        onToggleRoutes={() => setShowRoutes(v=>!v)}
        onToggleFlights={() => setShowFlights(v=>!v)}
        onToggleAllAirports={() => setShowAllAirports(v=>!v)}
        liveCount={count} connected={connected}
      />
    </div>
  )
}
