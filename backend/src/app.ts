import cors from '@fastify/cors'
import Fastify, { type FastifyInstance } from 'fastify'
import type { GeoJSONPolygon, QueryRequest } from './contracts.js'
import { ProviderError, queryRotaterra, type RotaterraConfig } from './rotaterra.js'

const catalog = {
  items: [
    {
      id: 'ndvi',
      name: 'NDVI',
      description: 'Estado de vegetación',
      representation: 'observations',
    },
  ],
}

interface ApiFailure {
  statusCode: number
  code: string
  message: string
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function isDate(value: unknown): value is string {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return false
  }

  const parsed = new Date(`${value}T00:00:00.000Z`)
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value
}

function isPosition(value: unknown): value is number[] {
  return (
    Array.isArray(value) &&
    value.length === 2 &&
    typeof value[0] === 'number' &&
    Number.isFinite(value[0]) &&
    value[0] >= -180 &&
    value[0] <= 180 &&
    typeof value[1] === 'number' &&
    Number.isFinite(value[1]) &&
    value[1] >= -90 &&
    value[1] <= 90
  )
}

function isClosedRing(value: unknown): value is number[][] {
  if (!Array.isArray(value) || value.length < 4 || !value.every(isPosition)) {
    return false
  }

  const first = value[0]
  const last = value[value.length - 1]
  return first?.[0] === last?.[0] && first?.[1] === last?.[1]
}

function isPolygon(value: unknown): value is GeoJSONPolygon {
  return (
    isRecord(value) &&
    value.type === 'Polygon' &&
    Array.isArray(value.coordinates) &&
    value.coordinates.length > 0 &&
    value.coordinates.every(isClosedRing)
  )
}

function parseQueryRequest(value: unknown):
  | { ok: true; query: QueryRequest }
  | { ok: false; error: ApiFailure } {
  if (!isRecord(value)) {
    return {
      ok: false,
      error: {
        statusCode: 422,
        code: 'INVALID_QUERY',
        message: 'La consulta no tiene un formato válido.',
      },
    }
  }

  if (typeof value.itemId !== 'string' || value.itemId.length === 0) {
    return {
      ok: false,
      error: {
        statusCode: 422,
        code: 'INVALID_QUERY',
        message: 'La consulta no tiene un formato válido.',
      },
    }
  }

  if (value.itemId !== 'ndvi') {
    return {
      ok: false,
      error: {
        statusCode: 404,
        code: 'ITEM_NOT_FOUND',
        message: 'El dato solicitado no está disponible.',
      },
    }
  }

  if (
    !isPolygon(value.geometry) ||
    !isRecord(value.period) ||
    !isDate(value.period.from) ||
    !isDate(value.period.to) ||
    value.period.from > value.period.to
  ) {
    return {
      ok: false,
      error: {
        statusCode: 422,
        code: 'INVALID_QUERY',
        message: 'La geometría o el período de la consulta no son válidos.',
      },
    }
  }

  return {
    ok: true,
    query: {
      itemId: 'ndvi',
      geometry: value.geometry,
      period: {
        from: value.period.from,
        to: value.period.to,
      },
    },
  }
}

export interface AppOptions extends RotaterraConfig {
  logger?: boolean
}

export function buildApp(options: AppOptions = {}): FastifyInstance {
  const app = Fastify({ logger: options.logger ?? false })
  const allowedOrigins =
    process.env.NODE_ENV === 'production'
      ? ['https://earth2worlds-frontend.onrender.com']
      : [
          'https://earth2worlds-frontend.onrender.com',
          'http://localhost:5173',
        ]

  app.register(cors, {
    origin: allowedOrigins,
    methods: ['GET', 'POST', 'OPTIONS'],
    allowedHeaders: ['Content-Type'],
  })

  app.setErrorHandler((error, _request, reply) => {
    if (
      isRecord(error) &&
      error.code === 'FST_ERR_CTP_INVALID_JSON_BODY'
    ) {
      return reply.status(422).send({
        error: {
          code: 'INVALID_QUERY',
          message: 'La consulta no tiene un formato válido.',
        },
      })
    }

    reply.status(500).send({
      error: {
        code: 'INTERNAL_ERROR',
        message: 'No se pudo completar la solicitud.',
      },
    })
  })

  app.get('/api/v1/catalog', async () => catalog)

  app.post<{ Body: unknown }>('/api/v1/queries', async (request, reply) => {
    const parsed = parseQueryRequest(request.body)
    if (!parsed.ok) {
      return reply.status(parsed.error.statusCode).send({
        error: {
          code: parsed.error.code,
          message: parsed.error.message,
        },
      })
    }

    try {
      return await queryRotaterra(parsed.query, options)
    } catch (error) {
      if (error instanceof ProviderError) {
        return reply.status(error.statusCode).send({
          error: {
            code: error.code,
            message: error.message,
          },
        })
      }

      return reply.status(500).send({
        error: {
          code: 'INTERNAL_ERROR',
          message: 'No se pudo completar la solicitud.',
        },
      })
    }
  })

  return app
}
