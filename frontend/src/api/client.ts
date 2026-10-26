import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

export interface LiveFlight {
  icao24: string; callsign: string; country: string
  lon: number; lat: number; altitude: number; altitude_ft: number
  speed_kmh: number; speed_kts: number; heading: number
  vert_rate: number; on_ground: boolean
}

export interface OptimizedRoute {
  route_id: number; origin: string; dest: string
  origin_name: string; dest_name: string
  origin_city: string; dest_city: string
  distance_km: number; frequency: number
  profit_usd: number; fuel_cost_usd: number
  detour_km: number; wind_saving_usd: number; wind_label: string
  active_constraints: string[]
  aircraft_type: string; aircraft_seats: number
  aircraft_range_km: number; aircraft_engine: string; aircraft_category: string
  airlines: string[]; demand_pax: number; fare_usd: number; load_factor: number
}

export interface Airport {
  iata: string; name: string; city: string; country: string; lat: number; lon: number
}

export interface IntlRoute {
  id: number; origin: string; destination: string; distance_km: number
  base_demand: number; base_fare_usd: number
  origin_name: string; origin_city: string; origin_country: string
  origin_lat: number; origin_lon: number
  dest_name: string; dest_city: string; dest_country: string
  dest_lat: number; dest_lon: number
  hourly_demand: number[]; fuel_cost_usd: number; revenue_usd: number
}

export interface TrailPoint {
  lat: number; lon: number; altitude_m: number; heading: number; speed_ms: number; ts_epoch: number
}

export interface OptimizeRequest {
  hub_iata: string; season: 'winter'|'summer'; max_routes: number; fleet_size: number
}

export const fetchAirports            = (): Promise<Airport[]>        => api.get('/airports/').then(r => r.data)
export const fetchOptimizedRoutes     = (): Promise<OptimizedRoute[]> => api.get('/routes/optimized').then(r => r.data)
export const fetchInternationalRoutes = (iata: string): Promise<IntlRoute[]> => api.get(`/routes/international/${iata}`).then(r => r.data)
export const fetchFlightTrail         = (icao: string): Promise<TrailPoint[]> => api.get(`/flights/trail/${icao}`).then(r => r.data)
export const runOptimize              = (req: OptimizeRequest): Promise<OptimizedRoute[]> => api.post('/optimize/', req).then(r => r.data)
