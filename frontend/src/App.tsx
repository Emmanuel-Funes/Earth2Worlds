import './App.css'
import { useCallback, useEffect, useState, type FormEvent } from 'react'
import {
  ApiError,
  getCatalog,
  submitQuery,
  type CatalogItem,
  type GeoJSONPolygon,
  type QueryResult,
} from './api'
import { MapView } from './map/MapView'

function App() {
  const [catalog, setCatalog] = useState<CatalogItem[]>([])
  const [catalogError, setCatalogError] = useState<string | null>(null)
  const [itemId, setItemId] = useState('')
  const [geometry, setGeometry] = useState<GeoJSONPolygon | null>(null)
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [result, setResult] = useState<QueryResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoadingCatalog, setIsLoadingCatalog] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const handleTerrainSelected = useCallback(
    (selectedGeometry: GeoJSONPolygon | null) => {
      setGeometry(selectedGeometry)
      setResult(null)
      setError(null)
    },
    [],
  )

  useEffect(() => {
    let active = true
    getCatalog()
      .then((items) => {
        if (active) {
          setCatalog(items)
        }
      })
      .catch((cause: unknown) => {
        if (active) {
          setCatalogError(
            cause instanceof ApiError
              ? cause.message
              : 'No se pudo cargar el catálogo de datos.',
          )
        }
      })
      .finally(() => {
        if (active) {
          setIsLoadingCatalog(false)
        }
      })

    return () => {
      active = false
    }
  }, [])

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!geometry || !itemId || !from || !to || isSubmitting) {
      return
    }

    setIsSubmitting(true)
    setError(null)
    setResult(null)

    try {
      const response = await submitQuery({
        itemId,
        geometry,
        period: { from, to },
      })
      setResult(response)
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : 'No se pudo completar la consulta.',
      )
    } finally {
      setIsSubmitting(false)
    }
  }

  const canSubmit =
    !isSubmitting &&
    geometry !== null &&
    itemId !== '' &&
    from !== '' &&
    to !== ''

  return (
    <main className="app-shell">
      <header className="app-header">
        <div className="brand-mark" aria-hidden="true">
          E
        </div>
        <div>
          <p className="eyebrow">Earth2Worlds</p>
          <h1>Planificador de terrenos</h1>
        </div>
      </header>

      <section className="workspace" aria-labelledby="workspace-title">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">Espacio de trabajo</p>
            <h2 id="workspace-title">Mapa de terrenos</h2>
          </div>
          <span className="status-badge">Preparado para el mapa</span>
        </div>

        <div className="map-container">
          <MapView onTerrainSelected={handleTerrainSelected} />
        </div>
        <form className="query-panel" onSubmit={handleSubmit}>
          <h3>Consultar estado de vegetación</h3>
          {catalogError && (
            <p className="query-message query-error" role="alert">
              {catalogError}
            </p>
          )}
          <div className="query-fields">
            <label>
              Dato
              <select
                value={itemId}
                onChange={(event) => setItemId(event.target.value)}
                disabled={isLoadingCatalog || catalogError !== null}
                required
              >
                <option value="">
                  {isLoadingCatalog ? 'Cargando catálogo…' : 'Seleccionar dato'}
                </option>
                {catalog.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name} — {item.description}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Desde
              <input
                type="date"
                value={from}
                onChange={(event) => setFrom(event.target.value)}
                required
              />
            </label>
            <label>
              Hasta
              <input
                type="date"
                value={to}
                onChange={(event) => setTo(event.target.value)}
                min={from || undefined}
                required
              />
            </label>
            <button type="submit" disabled={!canSubmit}>
              {isSubmitting ? 'Consultando…' : 'Consultar'}
            </button>
          </div>
          <p className="query-hint" role="status">
            {isSubmitting
              ? 'La consulta está procesándose. Esto puede demorar.'
              : geometry
                ? 'Terreno seleccionado.'
                : 'Dibuja un polígono en el mapa para continuar.'}
          </p>
        </form>
        {error && (
          <p className="query-message query-error" role="alert">
            {error}
          </p>
        )}
        {result && (
          <section className="query-results" aria-labelledby="results-title">
            <h3 id="results-title">Resultados NDVI</h3>
            {result.observations.length === 0 ? (
              <p>No se encontraron observaciones NDVI para el período.</p>
            ) : (
              <ul className="observation-list">
                {result.observations.map((observation, index) => {
                  return (
                    <li key={`${observation.date}-${index}`}>
                      <time dateTime={observation.date}>
                        {observation.date}
                      </time>
                      <span>{formatObservationValue(observation)}</span>
                      <span className={`quality quality-${observation.quality}`}>
                        {observation.quality}
                        {observation.quality === 'dudosa' &&
                          observation.warning && (
                            <small>{observation.warning}</small>
                          )}
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </section>
        )}
      </section>
    </main>
  )
}

function formatObservationValue(
  observation: QueryResult['observations'][number],
): string {
  if (observation.value === null || observation.quality === 'descartada') {
    return 'Sin dato'
  }

  const value = new Intl.NumberFormat('es-AR', {
    maximumFractionDigits: 3,
  }).format(observation.value)
  return `${value} ${observation.unit}`
}

export default App
