import { buildApp } from './app.js'
import { getDefaultRotaterraApiUrl } from './rotaterra.js'

const port = Number(process.env.PORT ?? 3000)
const host = process.env.HOST ?? '127.0.0.1'

if (!Number.isInteger(port) || port < 1 || port > 65_535) {
  throw new Error('PORT debe ser un puerto TCP válido.')
}

const rotaterraApiKey = process.env.ROTATERRA_API_KEY
const app = buildApp({
  apiUrl: process.env.ROTATERRA_API_URL ?? getDefaultRotaterraApiUrl(),
  ...(rotaterraApiKey === undefined ? {} : { apiKey: rotaterraApiKey }),
})

await app.listen({ port, host })
