import { useRef, useEffect, useMemo, useCallback, useState } from 'react'
import Globe, { GlobeMethods } from 'react-globe.gl'
import { OptimizedRoute, Airport, LiveFlight } from '../api/client'

interface Props {
  routes: OptimizedRoute[]; airports: Airport[]; hub: string; flights: LiveFlight[]
  onAirportClick: (iata: string) => void; onFlightClick: (f: LiveFlight) => void
  selectedIata: string | null; selectedIcao: string | null
  showRoutes: boolean; showFlights: boolean; showAllAirports: boolean
}

const arcColor = (r: OptimizedRoute): [string,string] => {
  if (r.profit_usd < 0)          return ['rgba(220,38,38,0)',  'rgba(220,38,38,0.95)']
  if (r.detour_km > 500)         return ['rgba(234,88,12,0)',  'rgba(234,88,12,0.95)']
  if (r.wind_saving_usd > 5000)  return ['rgba(22,163,74,0)',  'rgba(22,163,74,0.95)']
  return                                ['rgba(37,99,235,0)',  'rgba(37,99,235,0.85)']
}

function makeSelectedPlane(heading: number): HTMLElement {
  const el = document.createElement('div')
  el.style.cssText = `width:20px;height:20px;cursor:pointer;transform:rotate(${heading}deg);filter:drop-shadow(0 1px 3px rgba(0,0,0,0.35))`
  el.innerHTML = `<svg viewBox="0 0 24 24" fill="#ea580c"><path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/></svg>`
  return el
}

export default function GlobeView({ routes, airports, hub, flights, onAirportClick, onFlightClick, selectedIata, selectedIcao, showRoutes, showFlights, showAllAirports }: Props) {
  const globeRef = useRef<GlobeMethods|undefined>(undefined)
  const [dims, setDims] = useState({ w: window.innerWidth - 420, h: window.innerHeight })

  useEffect(() => {
    const fn = () => setDims({ w: window.innerWidth - 420, h: window.innerHeight })
    window.addEventListener('resize', fn); return () => window.removeEventListener('resize', fn)
  }, [])

  const airportMap = useMemo(() => Object.fromEntries(airports.map(a => [a.iata, a])), [airports])

  const arcsData = useMemo(() => {
    if (!showRoutes) return []
    return routes.filter(r => airportMap[r.origin] && airportMap[r.dest]).map(r => ({
      startLat: airportMap[r.origin].lat, startLng: airportMap[r.origin].lon,
      endLat:   airportMap[r.dest].lat,   endLng:   airportMap[r.dest].lon,
      color: arcColor(r), altitude: r.detour_km > 500 ? 0.35 : 0.2,
      stroke: 0.5, dashLen: 0.015, dashGap: 0.025,
      animTime: r.detour_km > 500 ? 5000 : 2800,
      label: `<div style="background:#ffffff;padding:10px 14px;border-radius:0px;font-size:12px;color:#0f172a;border:1px solid #cbd5e1;box-shadow:0 10px 15px -3px rgba(0,0,0,0.1),0 4px 6px -4px rgba(0,0,0,0.1);min-width:210px;font-family:'Trebuchet MS',sans-serif">
        <div style="font-weight:700;font-size:13px;color:#0f172a;margin-bottom:3px">${r.origin} → ${r.dest}</div>
        <div style="color:#64748b;font-size:11px;margin-bottom:8px">${r.origin_city||r.origin} → ${r.dest_city||r.dest}</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;font-size:11px">
          <span style="font-weight:600;color:#334155">${r.aircraft_type}</span><span style="color:#64748b;text-align:right">${r.distance_km?.toLocaleString()} km</span>
          <span style="color:#15803d;font-weight:600">Profit: $${(r.profit_usd/1000).toFixed(0)}k</span>
          <span style="color:#c2410c;font-weight:600;text-align:right">Fuel: $${(r.fuel_cost_usd/1000).toFixed(0)}k</span>
          <span style="color:#475569">${r.demand_pax} pax/day</span><span style="color:#475569;text-align:right">Fare: $${r.fare_usd}</span>
          ${r.detour_km>0?`<span style="color:#b45309;font-weight:600;grid-column:span 2">Detour: +${r.detour_km} km</span>`:''}
          ${r.wind_saving_usd>0?`<span style="color:#0369a1;font-weight:600;grid-column:span 2">Wind saving: $${(r.wind_saving_usd/1000).toFixed(1)}k</span>`:''}
        </div>
        <div style="margin-top:6px;padding-top:6px;border-top:1px solid #f1f5f9;color:#64748b;font-size:10px">${r.airlines?.join(' · ')}</div>
      </div>`,
      ...r
    }))
  }, [routes, airportMap, showRoutes])

  // Show airports from routes + optionally all airports
  const pointsData = useMemo(() => {
    const routeIatas = new Set([hub, ...routes.flatMap(r => [r.origin, r.dest])])
    const pts: {lat:number;lng:number;iata:string;label:string;color:string;radius:number}[] = []

    if (showAllAirports) {
      airports.slice(0, 3000).forEach(a => {
        pts.push({
          lat: a.lat, lng: a.lon, iata: a.iata,
          label: `<div style="background:#ffffff;padding:4px 8px;border-radius:0px;font-size:11px;font-weight:600;color:#0f172a;border:1px solid #cbd5e1;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);font-family:'Trebuchet MS',sans-serif">${a.iata} — ${a.city||a.name}</div>`,
          color: a.iata === selectedIata ? '#dc2626' : a.iata === hub ? '#ea580c' : routeIatas.has(a.iata) ? '#2563eb' : '#64748b',
          radius: a.iata === selectedIata ? 0.5 : a.iata === hub ? 0.45 : routeIatas.has(a.iata) ? 0.3 : 0.1,
        })
      })
    } else {
      routeIatas.forEach(iata => {
        const a = airportMap[iata]; if (!a) return
        pts.push({
          lat: a.lat, lng: a.lon, iata: a.iata,
          label: `<div style="background:#ffffff;padding:4px 8px;border-radius:0px;font-size:11px;font-weight:600;color:#0f172a;border:1px solid #cbd5e1;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);font-family:'Trebuchet MS',sans-serif">${a.iata} — ${a.city||a.name}</div>`,
          color: a.iata === selectedIata ? '#dc2626' : a.iata === hub ? '#ea580c' : '#2563eb',
          radius: a.iata === selectedIata ? 0.55 : a.iata === hub ? 0.5 : 0.25,
        })
      })
    }
    return pts
  }, [routes, airports, airportMap, hub, selectedIata, showAllAirports])

  // Flights as WebGL points (fast) — selected flight as single HTML element
  const flightPoints = useMemo(() => {
    if (!showFlights) return []
    return flights.map(f => ({
      lat: f.lat, lng: f.lon,
      color: f.icao24 === selectedIcao ? '#ea580c' : f.vert_rate > 0.5 ? '#16a34a' : '#2563eb',
      radius: f.icao24 === selectedIcao ? 0.18 : 0.08,
      flight: f,
      label: `<div style="background:#ffffff;padding:4px 8px;border-radius:0px;font-size:11px;font-weight:600;color:#0f172a;border:1px solid #cbd5e1;box-shadow:0 4px 6px -1px rgba(0,0,0,0.1);font-family:'Trebuchet MS',sans-serif">${f.callsign} · ${f.altitude_ft.toLocaleString()} ft · ${f.speed_kts} kts</div>`,
    }))
  }, [flights, showFlights, selectedIcao])

  const htmlData = useMemo(() => {
    if (!selectedIcao) return []
    const f = flights.find(f => f.icao24 === selectedIcao)
    if (!f) return []
    return [{ lat: f.lat, lng: f.lon, __html: makeSelectedPlane(f.heading), flight: f }]
  }, [flights, selectedIcao])

  const onPointClick  = useCallback((p: object) => {
    const pt = p as {iata?: string; flight?: LiveFlight}
    if (pt.flight) onFlightClick(pt.flight)
    else if (pt.iata) onAirportClick(pt.iata)
  }, [onAirportClick, onFlightClick])
  const onHtmlClick   = useCallback((m: object) => { const mt = m as {flight?:LiveFlight}; if (mt.flight) onFlightClick(mt.flight) }, [onFlightClick])

  useEffect(() => {
    if (globeRef.current && hub && airportMap[hub]) {
      const {lat,lon} = airportMap[hub]
      globeRef.current.pointOfView({lat, lng:lon, altitude:2.2}, 1200)
    }
  }, [hub, airportMap])

  useEffect(() => {
    if (globeRef.current && selectedIata && airportMap[selectedIata]) {
      const {lat,lon} = airportMap[selectedIata]
      globeRef.current.pointOfView({lat, lng:lon, altitude:1.5}, 800)
    }
  }, [selectedIata, airportMap])

  useEffect(() => {
    if (globeRef.current && selectedIcao) {
      const f = flights.find(f => f.icao24 === selectedIcao)
      if (f) globeRef.current.pointOfView({lat:f.lat, lng:f.lon, altitude:1.0}, 600)
    }
  }, [selectedIcao, flights])

  return (
    <Globe ref={globeRef}
      globeImageUrl="//unpkg.com/three-globe/example/img/earth-blue-marble.jpg"
      backgroundImageUrl="//unpkg.com/three-globe/example/img/night-sky.png"
      backgroundColor="#000010"
      arcsData={arcsData}
      arcStartLat="startLat" arcStartLng="startLng" arcEndLat="endLat" arcEndLng="endLng"
      arcColor="color" arcAltitude="altitude" arcStroke="stroke" arcLabel="label"
      arcDashLength="dashLen" arcDashGap="dashGap" arcDashAnimateTime="animTime"
      pointsData={[...pointsData, ...flightPoints]}
      pointLat="lat" pointLng="lng" pointColor="color" pointRadius="radius"
      pointLabel="label" pointAltitude={0.005} onPointClick={onPointClick}
      htmlElementsData={htmlData}
      htmlLat="lat" htmlLng="lng"
      htmlElement={(d: object) => (d as {__html:HTMLElement}).__html}
      {...{ onHtmlElementClick: onHtmlClick } as object}
      width={dims.w} height={dims.h}
    />
  )
}
