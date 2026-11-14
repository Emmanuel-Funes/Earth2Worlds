import assert from 'node:assert/strict'
import { test } from 'node:test'
import { buildApp } from '../src/app.js'
import type { GeoJSONPolygon } from '../src/contracts.js'
import { submitQuery } from '../../frontend/src/api.js'

const secret = 'test-only-rotaterra-key'
const polygon: GeoJSONPolygon = {
  type: 'Polygon',
  coordinates: [
    [
      [-65.3, -33.7],
      [-65.295, -33.7],
      [-65.295, -33.705],
      [-65.3, -33.7],
    ],
  ],
}

const query = {
  itemId: 'ndvi',
  geometry: polygon,
  period: { from: '2026-01-01', to: '2026-01-15' },
}

function rotaterraObservation(
  overrides: Partial<Record<string, unknown>> = {},
) {
  return {
    lote_id: 'ephemeral',
    fecha: '2026-01-01',
    variable: 'ndvi',
    valor: 0.42,
    unidad: 'índice (-1 a 1)',
    fuente: 'HLS',
    resolucion_m: 30,
    calidad: 'buena',
    nota: 'Nota técnica sintética para pruebas.',
    ...overrides,
  }
}

function rotaterraPayload(
  observations: unknown[] = [rotaterraObservation()],
): Record<string, unknown> {
  return {
    fuente_usada: 'HLS',
    observaciones: observations,
    intentos: [
      {
        satelite: 'HLS',
        resultado: 'ok',
        filas: observations.length,
        mensaje: '',
      },
    ],
  }
}

function mockFetch(
  status: number,
  body: unknown,
  onRequest?: (input: RequestInfo | URL, init?: RequestInit) => void,
): typeof fetch {
  return async (input, init) => {
    onRequest?.(input, init)
    return new Response(JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

async function withApp(
  fetchImpl: typeof fetch,
  run: (app: ReturnType<typeof buildApp>) => Promise<void>,
) {
  const app = buildApp({
    apiUrl: 'https://rotaterra.invalid/consulta',
    apiKey: secret,
    fetchImpl,
  })

  try {
    await run(app)
  } finally {
    await app.close()
  }
}

test('adapta NDVI al contrato externo y usa un lote UUID efímero', async () => {
  let upstreamUrl: string | URL | RequestInfo | undefined
  let upstreamInit: RequestInit | undefined

  await withApp(
    mockFetch(200, rotaterraPayload(), (input, init) => {
      upstreamUrl = input
      upstreamInit = init
    }),
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        headers: { origin: 'https://earth2worlds-frontend.onrender.com' },
        payload: query,
      })

      assert.equal(response.statusCode, 200)
      assert.equal(
        response.headers['access-control-allow-origin'],
        'https://earth2worlds-frontend.onrender.com',
      )
      assert.equal(String(upstreamUrl), 'https://rotaterra.invalid/consulta')
      assert.equal(upstreamInit?.method, 'POST')
      assert.equal(
        new Headers(upstreamInit?.headers).get('X-API-Key'),
        secret,
      )
      assert.equal(
        new Headers(upstreamInit?.headers).get('Content-Type'),
        'application/json',
      )

      const sentBody = JSON.parse(String(upstreamInit?.body)) as {
        satelite: string
        lote_id: string
        poligono: GeoJSONPolygon
        desde: string
        hasta: string
      }
      assert.equal(sentBody.satelite, 'HLS')
      assert.match(
        sentBody.lote_id,
        /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
      )
      assert.deepEqual(sentBody.poligono, polygon)
      assert.equal(sentBody.desde, query.period.from)
      assert.equal(sentBody.hasta, query.period.to)

      const result = response.json()
      assert.equal(result.itemId, 'ndvi')
      assert.equal(result.observations[0].variable, 'ndvi')
      assert.equal(result.observations[0].value, 0.42)
      assert.equal(result.observations[0].resolutionM, 30)
      assert.equal(
        result.observations[0].technicalNote,
        'Nota técnica sintética para pruebas.',
      )
      assert.equal(JSON.stringify(result).includes(secret), false)
    },
  )
})

test('publica un catálogo funcional con sólo NDVI', async () => {
  const app = buildApp()
  try {
    const response = await app.inject({
      method: 'GET',
      url: '/api/v1/catalog',
      headers: { origin: 'https://earth2worlds-frontend.onrender.com' },
    })

    assert.equal(response.statusCode, 200)
    assert.equal(
      response.headers['access-control-allow-origin'],
      'https://earth2worlds-frontend.onrender.com',
    )
    assert.deepEqual(response.json(), {
      items: [
        {
          id: 'ndvi',
          name: 'NDVI',
          description: 'Estado de vegetación',
          representation: 'observations',
        },
      ],
    })
  } finally {
    await app.close()
  }
})

test('permite el origen local de desarrollo fuera de producción', async () => {
  const originalNodeEnv = process.env.NODE_ENV
  process.env.NODE_ENV = 'development'
  const app = buildApp()
  try {
    const response = await app.inject({
      method: 'GET',
      url: '/api/v1/catalog',
      headers: { origin: 'http://localhost:5173' },
    })

    assert.equal(response.statusCode, 200)
    assert.equal(
      response.headers['access-control-allow-origin'],
      'http://localhost:5173',
    )
  } finally {
    await app.close()
    if (originalNodeEnv === undefined) {
      delete process.env.NODE_ENV
    } else {
      process.env.NODE_ENV = originalNodeEnv
    }
  }
})

test('en producción sólo autoriza el origen del frontend publicado', async () => {
  const originalNodeEnv = process.env.NODE_ENV
  process.env.NODE_ENV = 'production'
  const app = buildApp()
  try {
    const response = await app.inject({
      method: 'GET',
      url: '/api/v1/catalog',
      headers: { origin: 'http://localhost:5173' },
    })

    assert.equal(response.statusCode, 200)
    assert.equal(response.headers['access-control-allow-origin'], undefined)
  } finally {
    await app.close()
    if (originalNodeEnv === undefined) {
      delete process.env.NODE_ENV
    } else {
      process.env.NODE_ENV = originalNodeEnv
    }
  }
})

test('no autoriza orígenes arbitrarios mediante CORS', async () => {
  const app = buildApp()
  try {
    const response = await app.inject({
      method: 'GET',
      url: '/api/v1/catalog',
      headers: { origin: 'https://example.invalid' },
    })

    assert.equal(response.statusCode, 200)
    assert.equal(response.headers['access-control-allow-origin'], undefined)
  } finally {
    await app.close()
  }
})

test('responde al preflight CORS de una consulta NDVI', async () => {
  const app = buildApp()
  try {
    const response = await app.inject({
      method: 'OPTIONS',
      url: '/api/v1/queries',
      headers: {
        origin: 'https://earth2worlds-frontend.onrender.com',
        'access-control-request-method': 'POST',
        'access-control-request-headers': 'content-type',
      },
    })

    assert.equal(response.statusCode, 204)
    assert.equal(
      response.headers['access-control-allow-origin'],
      'https://earth2worlds-frontend.onrender.com',
    )
    assert.match(
      String(response.headers['access-control-allow-methods']),
      /\bPOST\b/,
    )
    assert.match(
      String(response.headers['access-control-allow-headers']),
      /\bcontent-type\b/i,
    )
  } finally {
    await app.close()
  }
})

test('filtra NDMI de una respuesta HLS que contiene NDVI y NDMI', async () => {
  await withApp(
    mockFetch(
      200,
      rotaterraPayload([
        rotaterraObservation({ variable: 'ndmi', valor: -0.23 }),
        rotaterraObservation({ variable: 'ndvi', valor: 0.42 }),
      ]),
    ),
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        payload: query,
      })

      assert.equal(response.statusCode, 200)
      assert.deepEqual(
        response.json().observations.map(
          (observation: { variable: string }) => observation.variable,
        ),
        ['ndvi'],
      )
    },
  )
})

test('redacta la API key si el proveedor la devuelve en metadatos', async () => {
  const responseBody = rotaterraPayload([
    rotaterraObservation({
      fuente: `fuente-${secret}`,
      nota: `nota-${secret}`,
    }),
  ])
  responseBody.fuente_usada = `HLS-${secret}`
  responseBody.intentos = [
    {
      satelite: `satelite-${secret}`,
      resultado: 'ok',
      filas: 1,
      mensaje: '',
    },
  ]

  await withApp(mockFetch(200, responseBody), async (app) => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/queries',
      payload: query,
    })

    assert.equal(response.statusCode, 200)
    assert.equal(response.body.includes(secret), false)
    assert.equal(JSON.stringify(response.json()).includes('[redacted]'), true)
  })
})

test('conserva varias fechas y devuelve las observaciones en orden cronológico', async () => {
  await withApp(
    mockFetch(
      200,
      rotaterraPayload([
        rotaterraObservation({ fecha: '2026-01-15', valor: 0.4 }),
        rotaterraObservation({ fecha: '2026-01-03', valor: 0.2 }),
      ]),
    ),
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        payload: query,
      })

      assert.deepEqual(
        response.json().observations.map(
          (observation: { date: string; value: number }) => [
            observation.date,
            observation.value,
          ],
        ),
        [
          ['2026-01-03', 0.2],
          ['2026-01-15', 0.4],
        ],
      )
    },
  )
})

test('una respuesta sin NDVI produce una lista vacía sin sustituir datos', async () => {
  await withApp(
    mockFetch(200, rotaterraPayload([rotaterraObservation({ variable: 'ndmi' })])),
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        payload: query,
      })

      assert.equal(response.statusCode, 200)
      assert.deepEqual(response.json().observations, [])
    },
  )
})

test('conserva calidad dudosa y no presenta descartados como valor', async () => {
  await withApp(
    mockFetch(
      200,
      rotaterraPayload([
        rotaterraObservation({
          fecha: '2026-01-02',
          calidad: 'dudosa',
          valor: 0.12,
        }),
        rotaterraObservation({
          fecha: '2026-01-03',
          calidad: 'descartada',
          valor: null,
        }),
      ]),
    ),
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        payload: query,
      })
      const observations = response.json().observations

      assert.equal(observations[0].quality, 'dudosa')
      assert.equal(observations[0].warning, 'Calidad dudosa')
      assert.equal(observations[0].value, 0.12)
      assert.equal(observations[1].quality, 'descartada')
      assert.equal(observations[1].value, null)
    },
  )
})

test('traduce una API key externa rechazada sin exponer credenciales', async () => {
  await withApp(mockFetch(401, { detail: secret }), async (app) => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/queries',
      payload: query,
    })

    assert.equal(response.statusCode, 503)
    assert.equal(response.json().error.code, 'PROVIDER_UNAVAILABLE')
    assert.equal(response.body.includes(secret), false)
  })
})

test('sin API key configurada no intenta contactar al proveedor', async () => {
  let calls = 0
  const app = buildApp({
    fetchImpl: async () => {
      calls += 1
      return new Response('{}', { status: 200 })
    },
  })

  try {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/queries',
      payload: query,
    })

    assert.equal(response.statusCode, 503)
    assert.equal(response.json().error.code, 'PROVIDER_UNAVAILABLE')
    assert.equal(calls, 0)
  } finally {
    await app.close()
  }
})

test('traduce el rechazo 422 del proveedor a un error propio seguro', async () => {
  await withApp(mockFetch(422, { detail: secret }), async (app) => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/queries',
      payload: query,
    })

    assert.equal(response.statusCode, 502)
    assert.equal(response.json().error.code, 'PROVIDER_QUERY_FAILED')
    assert.equal(response.body.includes(secret), false)
  })
})

test('traduce respuestas externas 502 y 503 a disponibilidad del proveedor', async () => {
  for (const status of [502, 503]) {
    await withApp(
      mockFetch(status, { detail: secret }),
      async (app) => {
        const response = await app.inject({
          method: 'POST',
          url: '/api/v1/queries',
          payload: query,
        })

        assert.equal(response.statusCode, 503)
        assert.equal(response.json().error.code, 'PROVIDER_UNAVAILABLE')
        assert.equal(response.body.includes(secret), false)
      },
    )
  }
})

test('traduce timeout y errores de conexión sin reintentar', async () => {
  let calls = 0
  let timeoutMs: number | undefined
  const originalTimeout = AbortSignal.timeout
  AbortSignal.timeout = (milliseconds) => {
    timeoutMs = milliseconds
    return originalTimeout(milliseconds)
  }
  const timeoutFetch: typeof fetch = async () => {
    calls += 1
    throw new DOMException('timed out', 'TimeoutError')
  }

  try {
    await withApp(timeoutFetch, async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        payload: query,
      })

      assert.equal(response.statusCode, 503)
      assert.equal(response.json().error.code, 'PROVIDER_UNAVAILABLE')
      assert.equal(calls, 1)
      assert.equal(timeoutMs, 240_000)
    })
  } finally {
    AbortSignal.timeout = originalTimeout
  }

  calls = 0
  const connectionFailure: typeof fetch = async () => {
    calls += 1
    throw new Error(`connection failed ${secret}`)
  }

  await withApp(connectionFailure, async (app) => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/queries',
      payload: query,
    })

    assert.equal(response.statusCode, 503)
    assert.equal(response.body.includes(secret), false)
    assert.equal(calls, 1)
  })
})

test('un timeout al leer el body se traduce como disponibilidad del proveedor', async () => {
  const fetchImpl: typeof fetch = async () => {
    const response = new Response('{}', { status: 200 })
    response.json = async () => {
      throw new DOMException('timed out reading body', 'AbortError')
    }
    return response
  }

  await withApp(fetchImpl, async (app) => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/queries',
      payload: query,
    })

    assert.equal(response.statusCode, 503)
    assert.equal(response.json().error.code, 'PROVIDER_UNAVAILABLE')
  })
})

test('no registra ni devuelve la API key en respuestas o consola', async () => {
  const logged: string[] = []
  const originalConsole = {
    error: console.error,
    log: console.log,
    warn: console.warn,
  }
  console.error = (...args: unknown[]) => logged.push(args.join(' '))
  console.log = (...args: unknown[]) => logged.push(args.join(' '))
  console.warn = (...args: unknown[]) => logged.push(args.join(' '))

  try {
    await withApp(
      async () => {
        throw new Error(`provider error ${secret}`)
      },
      async (app) => {
        const response = await app.inject({
          method: 'POST',
          url: '/api/v1/queries',
          payload: query,
        })

        assert.equal(response.body.includes(secret), false)
      },
    )
  } finally {
    console.error = originalConsole.error
    console.log = originalConsole.log
    console.warn = originalConsole.warn
  }

  assert.equal(logged.some((line) => line.includes(secret)), false)
})

test('la solicitud del navegador no envía la API key al backend', async () => {
  const originalFetch = globalThis.fetch
  let requestInit: RequestInit | undefined

  globalThis.fetch = async (_input, init) => {
    requestInit = init
    return new Response(
      JSON.stringify({
        itemId: 'ndvi',
        period: query.period,
        observations: [],
        sourceUsed: 'HLS',
        attempts: [],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    )
  }

  try {
    await submitQuery(query)
  } finally {
    globalThis.fetch = originalFetch
  }

  const headers = new Headers(requestInit?.headers)
  assert.equal(headers.has('X-API-Key'), false)
  assert.equal(String(requestInit?.body).includes(secret), false)
})

test('rechaza geometría y fechas inválidas antes de contactar al proveedor', async () => {
  let calls = 0
  const fetchImpl: typeof fetch = async () => {
    calls += 1
    return new Response('{}', { status: 200 })
  }

  await withApp(fetchImpl, async (app) => {
    const response = await app.inject({
      method: 'POST',
      url: '/api/v1/queries',
      payload: {
        ...query,
        period: { from: '2026-02-30', to: '2026-01-01' },
      },
    })

    assert.equal(response.statusCode, 422)
    assert.equal(response.json().error.code, 'INVALID_QUERY')
    assert.equal(calls, 0)
  })
})

test('un identificador ausente es una petición inválida', async () => {
  await withApp(
    mockFetch(200, rotaterraPayload()),
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        payload: { geometry: polygon, period: query.period },
      })

      assert.equal(response.statusCode, 422)
      assert.equal(response.json().error.code, 'INVALID_QUERY')
    },
  )
})

test('JSON sintácticamente inválido devuelve el error propio 422', async () => {
  await withApp(
    async () => {
      throw new Error('La petición inválida no debe contactar al proveedor.')
    },
    async (app) => {
      const response = await app.inject({
        method: 'POST',
        url: '/api/v1/queries',
        headers: { 'content-type': 'application/json' },
        payload: '{"itemId":',
      })

      assert.equal(response.statusCode, 422)
      assert.deepEqual(response.json(), {
        error: {
          code: 'INVALID_QUERY',
          message: 'La consulta no tiene un formato válido.',
        },
      })
      assert.equal(response.body.includes('Fastify'), false)
      assert.equal(response.body.includes('FST_ERR_CTP_INVALID_JSON'), false)
    },
  )
})
