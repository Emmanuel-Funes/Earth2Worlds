# Spec 045 · Copia del mapa del Catastro para cuando no contesta

**Estado:** Hernán aprobó la idea ("Si porfavor, avanzar en eso"), después de la prueba del piloto · **Etapa:** pipeline fuente → API → app · **Completa:** spec 025 (Catastro San Luis)

## Objetivo

Que la app pueda dar el polígono de una parcela rural aunque el servidor del Catastro de San Luis no conteste.

| Antes | Después |
|---|---|
| Si el Catastro no contesta, `/catastro-sl/parcela` y `/catastro-sl/parcelas-rurales` responden error 502 y el productor no puede elegir su lote | Si el Catastro no contesta, la app busca la parcela rural en una copia del mapa guardada en el repo y lo aclara en la `nota` |
| En la prueba del piloto, de 23:53 a 23:56 (hora de Argentina), el Catastro no contestó y la consulta se cortó: sin polígono no hay consulta | La consulta sigue con el polígono de la copia |

## Fuente

El mismo Catastro de San Luis de la spec 025: la capa `SanLuis:GIS_PARCELAS_RUR_VV`, bajada entera con `/catastro-sl/parcelas-rurales`. No se suma ninguna fuente nueva. Es el mismo arreglo que la copia de los rindes del Ministerio (spec 040).

## Entrada

La misma de la spec 025: `lat` y `lon`, `nomenclatura` o `partida`; o la zona del mapa (`oeste`, `sur`, `este`, `norte`), o nada para el mapa completo.

## Proceso

1. **La copia.** `rotaterra/fuentes/datos/catastro_sl_parcelas_rurales.geojson.gz` tiene las parcelas rurales en el mismo formato liviano que entrega `/catastro-sl/parcelas-rurales`: polígono EPSG:4326 con 6 decimales, nomenclatura, partida, número de parcela, plano de mensura y superficie registrada. Al lado, `catastro_sl_parcelas_rurales.json` dice la fecha de la copia y cuántas parcelas tiene.
   - La primera copia sale del mapa bajado el **14/11/2026**: 17.976 parcelas, 2,3 MB comprimidos.
   - Solo trae las **rurales**, que son las de los lotes agrícolas. Las suburbanas y urbanas siguen dependiendo del Catastro.
2. **Primero el Catastro.** Cada pedido va primero al Catastro, igual que hoy. La copia se usa **solo** cuando el Catastro no contesta o contesta algo ilegible.
3. **Parcela por punto.** Se buscan en la copia las parcelas cuyo rectángulo contiene el punto, y después las que lo contienen de verdad. Si son varias, se elige la más chica, igual que con el Catastro.
4. **Parcela por partida o nomenclatura.** Se busca el código exacto en la copia.
5. **Mapa completo.** Se entrega la copia tal cual. **Una zona del mapa:** se entregan las parcelas de la copia que tocan la zona, con el mismo tope de 5000.
6. **Cómo se avisa.** La `nota` arranca diciendo que el Catastro no contestó y que se usó la copia guardada en el repo, con su fecha. `fecha_consulta` es la fecha de la copia, no la de hoy. La calidad se calcula igual que con el Catastro (superficie, partes, polígono reparado).
7. **Si la copia no tiene la parcela** (por ejemplo, es suburbana o urbana, o el punto cae en un camino), se mantiene el error 502 con los dos motivos: que el Catastro no contestó y que la copia no la tiene. La copia no puede asegurar que una parcela no existe.
8. **La copia no queda en memoria.** Se lee del disco solo cuando hace falta y se suelta, para no ocupar memoria en Render (plan gratis, 512 MB). Leerla y buscar tarda menos de un segundo y ocupa unos 75 MB solo mientras dura el pedido (medido), y solo pasa cuando el Catastro está caído.
9. **Renovar la copia.** `actualizar_copia_catastro.py` baja el mapa completo del Catastro y reescribe la copia. Lo corre el workflow "Actualizar copia del Catastro", que se lanza a mano y guarda la copia en la rama desde la que se lanza.
   - Si el mapa nuevo trae menos del 90 % de las parcelas de la copia anterior, no la reemplaza: un mapa a medias sería peor que uno de hace unas semanas.

## Salida

La misma de la spec 025: `ParcelaCatastral` para una parcela y un GeoJSON `FeatureCollection` para el mapa. Cuando sale de la copia, la respuesta trae además la cabecera `X-Copia-Del-Catastro` con la fecha de la copia.

## Reglas de calidad

- Nunca se inventa una parcela. Si no está en la copia, es error, no "no hay parcela".
- La `nota` siempre dice que el dato salió de la copia y de qué fecha es.
- SUPUESTO: las parcelas rurales cambian poco (una subdivisión o una mensura nueva cada tanto), así que una copia de algunas semanas alcanza para no frenar al productor. Cuando el Catastro vuelve, se usa de nuevo el dato del día.

## Criterios de aceptación

- [x] Tests sin internet con el Catastro simulado caído (`ConnectTimeout`): la parcela por punto, por partida y por nomenclatura sale de la copia con la nota y la fecha de la copia; el mapa completo y una zona salen de la copia; una parcela que no está en la copia da 502 con los dos motivos; con el Catastro andando no se usa la copia.
- [x] Con la copia real: las 3 parcelas del piloto (partidas 01-90230, 06-924206 y 02-950571) salen de la copia por partida y por un punto adentro de cada una, con la nomenclatura y la superficie que dio el Catastro en la prueba del piloto (123,3, 456,1 y 196,5 ha), calidad buena, en 0,5 a 0,7 s cada búsqueda. Una zona de 0,3° × 0,3° cerca de Villa Mercedes trae 618 parcelas en 0,5 s.
- [ ] Prueba real (14/11/2026 o cuando haya minutos de Actions): correr "Actualizar copia del Catastro" y comprobar que la copia nueva tiene unas 18.000 parcelas.
