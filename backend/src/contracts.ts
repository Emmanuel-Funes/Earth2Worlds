export interface GeoJSONPolygon {
  type: 'Polygon'
  coordinates: number[][][]
}

export interface QueryRequest {
  itemId: string
  geometry: GeoJSONPolygon
  period: {
    from: string
    to: string
  }
}

export type ObservationQuality = 'buena' | 'dudosa' | 'descartada'

export interface QueryObservation {
  variable: 'ndvi'
  date: string
  value: number | null
  unit: string
  quality: ObservationQuality
  warning: string | null
  provenance: {
    source: string
  }
  resolutionM: number | null
  technicalNote: string | null
}

export interface QueryResponse {
  itemId: 'ndvi'
  period: {
    from: string
    to: string
  }
  observations: QueryObservation[]
  sourceUsed: string
  attempts: Array<{
    satellite: string
    result: string
    rows: number
  }>
}

export interface ApiErrorResponse {
  error: {
    code: string
    message: string
  }
}
