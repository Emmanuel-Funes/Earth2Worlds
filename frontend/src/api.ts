export interface GeoJSONPolygon {
  type: 'Polygon'
  coordinates: number[][][]
}

export interface CatalogItem {
  id: string
  name: string
  description: string
  representation: string
}

export interface QueryObservation {
  variable: 'ndvi'
  date: string
  value: number | null
  unit: string
  quality: 'buena' | 'dudosa' | 'descartada'
  warning: string | null
  provenance: {
    source: string
  }
  resolutionM: number | null
  technicalNote: string | null
}

export interface QueryResult {
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

export class ApiError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ApiError'
  }
}

const viteEnv = (
  import.meta as ImportMeta & {
    readonly env?: { readonly VITE_API_BASE_URL?: string }
  }
).env

const API_BASE_URL =
  typeof viteEnv === 'undefined' ? '' : (viteEnv.VITE_API_BASE_URL ?? '')

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init)
  } catch {
    throw new ApiError('No se pudo conectar con el servicio de consulta.')
  }

  let body: unknown
  try {
    body = await response.json()
  } catch {
    throw new ApiError('El servicio de consulta devolvió una respuesta no válida.')
  }

  if (!response.ok) {
    const message =
      typeof body === 'object' &&
      body !== null &&
      'error' in body &&
      typeof body.error === 'object' &&
      body.error !== null &&
      'message' in body.error &&
      typeof body.error.message === 'string'
        ? body.error.message
        : 'No se pudo completar la consulta.'
    throw new ApiError(message)
  }

  return body as T
}

export async function getCatalog(): Promise<CatalogItem[]> {
  const response = await request<{ items: CatalogItem[] }>('/api/v1/catalog')
  return response.items
}

export function submitQuery(input: {
  itemId: string
  geometry: GeoJSONPolygon
  period: { from: string; to: string }
}): Promise<QueryResult> {
  return request<QueryResult>('/api/v1/queries', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
}
