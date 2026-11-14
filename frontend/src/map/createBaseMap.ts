import * as L from 'leaflet'
import '@geoman-io/leaflet-geoman-free'

const mapsByContainer = new WeakMap<HTMLElement, L.Map>()

const terrainStyle: L.PathOptions = {
  color: '#2f6f4e',
  fillColor: '#75aa7a',
  fillOpacity: 0.25,
  weight: 3,
}

export type TerrainGeoJSON = ReturnType<L.Polygon['toGeoJSON']>

export interface MapController {
  startDrawing(): void
  startNewTerrain(): void
  cancelDrawing(): void
  destroy(): void
}

interface MapCallbacks {
  onDrawingChange(drawing: boolean): void
  onTerrainSelected(geoJSON: TerrainGeoJSON | null): void
}

export function createBaseMap(
  container: HTMLElement,
  callbacks: MapCallbacks,
): MapController {
  if (mapsByContainer.has(container)) {
    throw new Error('Ya existe una instancia de Leaflet para este contenedor.')
  }

  const map = L.map(container, {
    scrollWheelZoom: true,
    touchZoom: true,
    zoomControl: true,
  }).setView([-33.8, -66.1], 7)

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  }).addTo(map)

  let selectedTerrain: L.Polygon | null = null
  let drawing = false
  let disposed = false

  const handleDrawingStart = () => {
    if (!disposed) {
      drawing = true
      callbacks.onDrawingChange(true)
    }
  }

  const handleDrawingEnd = () => {
    if (!disposed) {
      drawing = false
      callbacks.onDrawingChange(false)
    }
  }

  const handleCreate: L.PM.CreateEventHandler = (event) => {
    if (event.shape !== 'Polygon' || !(event.layer instanceof L.Polygon)) {
      map.removeLayer(event.layer)
      return
    }

    if (selectedTerrain) {
      map.removeLayer(event.layer)
      return
    }

    const terrain = event.layer
    selectedTerrain = terrain
    terrain.setStyle(terrainStyle)
    callbacks.onTerrainSelected(terrain.toGeoJSON())
  }

  map.on('pm:drawstart', handleDrawingStart)
  map.on('pm:drawend', handleDrawingEnd)
  map.on('pm:create', handleCreate)

  mapsByContainer.set(container, map)

  const cleanup = () => {
    if (!disposed) {
      disposed = true
      map.off('pm:drawstart', handleDrawingStart)
      map.off('pm:drawend', handleDrawingEnd)
      map.off('pm:create', handleCreate)

      try {
        map.pm.disableDraw('Polygon')
      } finally {
        try {
          map.remove()
        } finally {
          mapsByContainer.delete(container)
        }
      }
    }
  }

  const startDrawing = () => {
    if (!disposed && !drawing) {
      map.pm.enableDraw('Polygon', {
        continueDrawing: false,
        pathOptions: terrainStyle,
        templineStyle: { color: terrainStyle.color, weight: terrainStyle.weight },
        hintlineStyle: {
          color: terrainStyle.color,
          dashArray: '5, 5',
          weight: 2,
        },
      })
    }
  }

  const startNewTerrain = () => {
    if (disposed || drawing) {
      return
    }

    if (selectedTerrain) {
      map.removeLayer(selectedTerrain)
      selectedTerrain = null
      callbacks.onTerrainSelected(null)
    }

    startDrawing()
  }

  const cancelDrawing = () => {
    if (!disposed && drawing) {
      map.pm.disableDraw('Polygon')
    }
  }

  return {
    startDrawing,
    startNewTerrain,
    cancelDrawing,
    destroy: cleanup,
  }
}
