import { useEffect, useRef, useState } from 'react'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import type { GeoJSONPolygon } from '../api'
import { createBaseMap, type MapController } from './createBaseMap'
import './map.css'

interface MapViewProps {
  onTerrainSelected(geometry: GeoJSONPolygon | null): void
}

export function MapView({ onTerrainSelected }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const confirmationDialogRef = useRef<HTMLDialogElement>(null)
  const controllerRef = useRef<MapController | null>(null)
  const [isDrawing, setIsDrawing] = useState(false)
  const [hasSelectedTerrain, setHasSelectedTerrain] = useState(false)
  const [isConfirmingNewTerrain, setIsConfirmingNewTerrain] = useState(false)

  useEffect(() => {
    const container = containerRef.current

    if (!container) {
      throw new Error('El contenedor de Leaflet no está disponible.')
    }

    const controller = createBaseMap(container, {
      onDrawingChange: setIsDrawing,
      onTerrainSelected: (geoJSON) => {
        onTerrainSelected(
          geoJSON?.type === 'Feature' && geoJSON.geometry.type === 'Polygon'
            ? geoJSON.geometry
            : null,
        )
        setHasSelectedTerrain(geoJSON !== null)
      },
    })
    controllerRef.current = controller

    return () => {
      controllerRef.current = null
      controller.destroy()
    }
  }, [onTerrainSelected])

  useEffect(() => {
    const dialog = confirmationDialogRef.current
    if (!dialog) {
      return
    }

    if (isConfirmingNewTerrain && !dialog.open) {
      dialog.showModal()
    } else if (!isConfirmingNewTerrain && dialog.open) {
      dialog.close()
    }
  }, [isConfirmingNewTerrain])

  return (
    <div className="map-view">
      <div
        ref={containerRef}
        className="leaflet-map"
        aria-label="Mapa interactivo"
      />
      <div className="map-drawing-controls">
        {hasSelectedTerrain && (
          <span className="terrain-status" role="status">
            Terreno seleccionado
          </span>
        )}
        <button
          className="map-drawing-button"
          type="button"
          aria-pressed={isDrawing}
          onClick={() => {
            const controller = controllerRef.current
            if (!controller) {
              return
            }

            if (isDrawing) {
              controller.cancelDrawing()
            } else if (hasSelectedTerrain) {
              setIsConfirmingNewTerrain(true)
            } else {
              controller.startDrawing()
            }
          }}
        >
          {isDrawing
            ? 'Cancelar dibujo'
            : hasSelectedTerrain
              ? 'Nuevo terreno'
              : 'Dibujar terreno'}
        </button>
      </div>
      {isConfirmingNewTerrain && (
        <dialog
          ref={confirmationDialogRef}
          className="terrain-confirmation-dialog"
          aria-labelledby="terrain-confirmation-title"
          aria-describedby="terrain-confirmation-description"
          onCancel={() => setIsConfirmingNewTerrain(false)}
          onClose={() => setIsConfirmingNewTerrain(false)}
        >
          <h2 id="terrain-confirmation-title">Crear un nuevo terreno</h2>
          <p id="terrain-confirmation-description">
            El terreno actual se eliminará y comenzará el dibujo del nuevo. Si
            cancelas ese dibujo, no quedará un terreno seleccionado.
          </p>
          <div className="terrain-confirmation-actions">
            <button
              className="terrain-dialog-button"
              type="button"
              onClick={() => setIsConfirmingNewTerrain(false)}
            >
              Cancelar
            </button>
            <button
              className="terrain-dialog-button terrain-dialog-confirm"
              type="button"
              onClick={() => {
                const controller = controllerRef.current
                if (!controller) {
                  return
                }

                controller.startNewTerrain()
                setIsConfirmingNewTerrain(false)
              }}
            >
              Confirmar
            </button>
          </div>
        </dialog>
      )}
    </div>
  )
}
