import { randomUUID } from 'node:crypto'
import type {
  GeoJSONPolygon,
  ObservationQuality,
  QueryObservation,
  QueryRequest,
  QueryResponse,
} from './contracts.js'

const DEFAULT_API_URL = 'https://rotaterra-api.onrender.com/consulta'
const ROTATERRA_TIMEOUT_MS = 240_000

interface RotaterraObservation {
  fecha: string
  variable: string
  valor: number | null
  unidad: string
  fuente: string
  resolucion_m: number | null
  calidad: ObservationQuality
  nota: string | null
}

interface RotaterraAttempt {
  satelite: string
  resultado: string
  filas: number
}

interface RotaterraResponse {
  fuente_usada: string
  observaciones: RotaterraObservation[]
  intentos: RotaterraAttempt[]
}

export class ProviderError extends Error {
  constructor(
    readonly statusCode: 502 | 503,
    readonly code: 'PROVIDER_QUERY_FAILED' | 'PROVIDER_UNAVAILABLE',
    message: string,
  ) {
    super(message)
    this.name = 'ProviderError'
  }
}

export interface RotaterraConfig {
  apiUrl?: string
  apiKey?: string
  fetchImpl?: typeof fetch
}

export function getDefaultRotaterraApiUrl(): string {
  return DEFAULT_API_URL
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === 'string'
}

function isStringOrNull(value: unknown): value is string | null {
  return typeof value === 'string' || value === null
}

function isFiniteNumberOrNull(value: unknown): value is number | null {
  return (typeof value === 'number' && Number.isFinite(value)) || value === null
}

function isIsoDate(value: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false
  }

  const parsed = new Date(`${value}T00:00:00.000Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function safeProviderText(value: string, apiKey: string): string {
  return value.split(apiKey).join('[redacted]')
}

function isObservationQuality(value: unknown): value is ObservationQuality {
  return value === 'buena' || value === 'dudosa' || value === 'descartada'
}

function parseRotaterraResponse(value: unknown): RotaterraResponse {
  if (
    !isRecord(value) ||
    !isString(value.fuente_usada) ||
    !Array.isArray(value.observaciones) ||
    !Array.isArray(value.intentos)
  ) {
    throw new ProviderError(
      502,
      'PROVIDER_QUERY_FAILED',
      'El proveedor devolvió una respuesta no válida.',
    )
  }

  const observations = value.observaciones.map((entry): RotaterraObservation => {
    if (
      !isRecord(entry) ||
      !isString(entry.fecha) ||
      !isIsoDate(entry.fecha) ||
      !isString(entry.variable) ||
      !isFiniteNumberOrNull(entry.valor) ||
      !isString(entry.unidad) ||
      !isString(entry.fuente) ||
      !isFiniteNumberOrNull(entry.resolucion_m) ||
      !isObservationQuality(entry.calidad) ||
      !isStringOrNull(entry.nota)
    ) {
      throw new ProviderError(
        502,
        'PROVIDER_QUERY_FAILED',
        'El proveedor devolvió una observación no válida.',
      )
    }

    return {
      fecha: entry.fecha,
      variable: entry.variable,
      valor: entry.valor,
      unidad: entry.unidad,
      fuente: entry.fuente,
      resolucion_m: entry.resolucion_m,
      calidad: entry.calidad,
      nota: entry.nota,
    }
  })

  const attempts = value.intentos.map((entry): RotaterraAttempt => {
    if (
      !isRecord(entry) ||
      !isString(entry.satelite) ||
      !isString(entry.resultado) ||
      typeof entry.filas !== 'number' ||
      !Number.isInteger(entry.filas) ||
      entry.filas < 0
    ) {
      throw new ProviderError(
        502,
        'PROVIDER_QUERY_FAILED',
        'El proveedor devolvió metadatos de intentos no válidos.',
      )
    }

    return {
      satelite: entry.satelite,
      resultado: entry.resultado,
      filas: entry.filas,
    }
  })

  return {
    fuente_usada: value.fuente_usada,
    observaciones: observations,
    intentos: attempts,
  }
}

function normalizeObservation(
  observation: RotaterraObservation,
  apiKey: string,
): QueryObservation {
  return {
    variable: 'ndvi',
    date: observation.fecha,
    value: observation.valor,
    unit: safeProviderText(observation.unidad, apiKey),
    quality: observation.calidad,
    warning:
      observation.calidad === 'dudosa' ? 'Calidad dudosa' : null,
    provenance: {
      source: safeProviderText(observation.fuente, apiKey),
    },
    resolutionM: observation.resolucion_m,
    technicalNote:
      observation.nota === null
        ? null
        : safeProviderText(observation.nota, apiKey),
  }
}

function isTimeoutError(error: unknown): boolean {
  return (
    error instanceof Error &&
    (error.name === 'TimeoutError' || error.name === 'AbortError')
  )
}

function validateApiUrl(apiUrl: string, apiKey: string): URL {
  try {
    const url = new URL(apiUrl)
    const isLocalHttp =
      process.env.NODE_ENV !== 'production' &&
      url.protocol === 'http:' &&
      (url.hostname === '127.0.0.1' || url.hostname === 'localhost')
    if (
      (url.protocol !== 'https:' && !isLocalHttp) ||
      url.username !== '' ||
      url.password !== '' ||
      url.search !== '' ||
      url.hash !== '' ||
      url.toString().includes(apiKey)
    ) {
      throw new Error()
    }
    return url
  } catch {
    throw new ProviderError(
      503,
      'PROVIDER_UNAVAILABLE',
      'El servicio de datos no está disponible.',
    )
  }
}

export async function queryRotaterra(
  query: QueryRequest,
  config: RotaterraConfig,
): Promise<QueryResponse> {
  const apiKey = config.apiKey?.trim()
  if (!apiKey) {
    throw new ProviderError(
      503,
      'PROVIDER_UNAVAILABLE',
      'El servicio de datos no está configurado.',
    )
  }

  const apiUrl = validateApiUrl(config.apiUrl ?? DEFAULT_API_URL, apiKey)
  const fetchImpl = config.fetchImpl ?? globalThis.fetch
  const body = {
    satelite: 'HLS',
    lote_id: randomUUID(),
    poligono: query.geometry satisfies GeoJSONPolygon,
    desde: query.period.from,
    hasta: query.period.to,
  }

  const timeoutSignal = AbortSignal.timeout(ROTATERRA_TIMEOUT_MS)
  let response: Response
  try {
    response = await fetchImpl(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify(body),
      signal: timeoutSignal,
    })
  } catch (error) {
    const timedOut = isTimeoutError(error)
    throw new ProviderError(
      503,
      'PROVIDER_UNAVAILABLE',
      timedOut
        ? 'La consulta excedió el tiempo máximo disponible.'
        : 'El servicio de datos no está disponible.',
    )
  }

  if (response.status === 401 || response.status === 503) {
    throw new ProviderError(
      503,
      'PROVIDER_UNAVAILABLE',
      'El servicio de datos no está disponible.',
    )
  }

  if (response.status === 422) {
    throw new ProviderError(
      502,
      'PROVIDER_QUERY_FAILED',
      'El proveedor no pudo procesar la consulta enviada.',
    )
  }

  if (!response.ok) {
    throw new ProviderError(
      response.status === 502 ? 503 : 502,
      response.status === 502
        ? 'PROVIDER_UNAVAILABLE'
        : 'PROVIDER_QUERY_FAILED',
      'El servicio de datos no pudo completar la consulta.',
    )
  }

  let responseBody: unknown
  try {
    responseBody = await response.json()
  } catch (error) {
    if (isTimeoutError(error)) {
      throw new ProviderError(
        503,
        'PROVIDER_UNAVAILABLE',
        'La consulta excedió el tiempo máximo disponible.',
      )
    }
    throw new ProviderError(
      502,
      'PROVIDER_QUERY_FAILED',
      'El proveedor devolvió una respuesta no válida.',
    )
  }

  const rotaterra = parseRotaterraResponse(responseBody)
  const observations = rotaterra.observaciones
    .filter((observation) => observation.variable === 'ndvi')
    .map((observation) => normalizeObservation(observation, apiKey))
    .sort((left, right) => left.date.localeCompare(right.date))

  return {
    itemId: 'ndvi',
    period: query.period,
    observations,
    sourceUsed: safeProviderText(rotaterra.fuente_usada, apiKey),
    attempts: rotaterra.intentos.map((attempt) => ({
      satellite: safeProviderText(attempt.satelite, apiKey),
      result: safeProviderText(attempt.resultado, apiKey),
      rows: attempt.filas,
    })),
  }
}
