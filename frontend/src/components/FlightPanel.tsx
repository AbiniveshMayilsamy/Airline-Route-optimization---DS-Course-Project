import { LiveFlight, TrailPoint, fetchFlightTrail } from '../api/client'
import { useEffect, useState } from 'react'

interface Props { flight: LiveFlight; onClose: () => void }

const dirs = ['N','NE','E','SE','S','SW','W','NW','N']
const dir  = (h: number) => dirs[Math.round(h/45)]
const climbLabel = (vr: number) => vr > 0.5 ? '↑ Climbing' : vr < -0.5 ? '↓ Descending' : '→ Level'
const climbColor = (vr: number) => vr > 0.5 ? 'text-emerald-700' : vr < -0.5 ? 'text-red-600' : 'text-slate-600'

export default function FlightPanel({ flight, onClose }: Props) {
  const [trail, setTrail] = useState<TrailPoint[]>([])
  useEffect(() => { fetchFlightTrail(flight.icao24).then(setTrail).catch(()=>{}) }, [flight.icao24])
  const fpm = Math.abs(Math.round(flight.vert_rate * 196.85))

  return (
    <div className="absolute bottom-4 left-1/2 -translate-x-1/2 w-[560px] bg-white border border-slate-300 rounded-none shadow-2xl z-50 overflow-hidden font-sans">
      <div className="flex items-center justify-between px-5 py-3 bg-slate-50 border-b border-slate-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-none bg-blue-100 border border-blue-200 flex items-center justify-center text-blue-600 shadow-none">
            <svg className="w-5 h-5 fill-current" viewBox="0 0 24 24">
              <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>
            </svg>
          </div>
          <div>
            <p className="text-slate-900 font-bold text-xl tracking-widest font-mono">{flight.callsign || flight.icao24.toUpperCase()}</p>
            <p className="text-slate-600 text-xs">{flight.country} · ICAO24: <span className="font-mono text-slate-800 font-semibold">{flight.icao24.toUpperCase()}</span></p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <div className="flex items-center gap-1.5 justify-end">
              <span className="w-2 h-2 rounded-none bg-emerald-500 animate-pulse"/>
              <span className="text-emerald-700 text-xs font-semibold">LIVE ADS-B</span>
            </div>
            <p className="text-slate-400 text-xs">OpenSky Network</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 w-7 h-7 flex items-center justify-center rounded-none hover:bg-slate-200 transition-colors" aria-label="Close">
            <svg className="w-4 h-4 stroke-current" fill="none" viewBox="0 0 24 24" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div className="grid grid-cols-4 divide-x divide-slate-200 border-b border-slate-200">
        <StatBox label="Altitude" main={`${flight.altitude_ft.toLocaleString()}`} unit="ft"
          sub={`${flight.altitude.toLocaleString()} m`} color="text-blue-700"/>
        <StatBox label="Speed" main={`${flight.speed_kts}`} unit="kts"
          sub={`${flight.speed_kmh} km/h`} color="text-emerald-700"/>
        <StatBox label="Heading" main={`${flight.heading}°`} unit={dir(flight.heading)}
          sub="True heading" color="text-amber-700"/>
        <StatBox label="Vert Rate" main={climbLabel(flight.vert_rate)} unit=""
          sub={`${fpm} fpm`} color={climbColor(flight.vert_rate)}/>
      </div>

      <div className="px-5 py-2.5 flex items-center justify-between bg-slate-50 text-xs text-slate-600">
        <div className="flex items-center gap-4">
          <span className="font-medium text-slate-700">{flight.lat.toFixed(4)}°, {flight.lon.toFixed(4)}°</span>
          <span className="text-slate-300">|</span>
          <span>{trail.length > 0 ? `${trail.length} trail pts` : 'Trail building…'}</span>
        </div>
        <span className="text-slate-400">15s refresh</span>
      </div>
    </div>
  )
}

function StatBox({ label, main, unit, sub, color }: { label:string; main:string; unit:string; sub:string; color:string }) {
  return (
    <div className="px-4 py-3 bg-white text-center">
      <p className="text-slate-500 text-xs font-medium mb-1">{label}</p>
      <p className={`font-bold text-sm ${color}`}>{main} <span className="text-slate-500 text-xs font-normal">{unit}</span></p>
      <p className="text-slate-400 text-xs mt-0.5">{sub}</p>
    </div>
  )
}
