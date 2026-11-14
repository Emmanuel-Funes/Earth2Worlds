# Spec 044 · Memoria del suelo y menos pedidos a la vez al INTA

**Estado:** Hernán aprobó la idea ("Si porfavor, avanzar en eso"), después de la prueba del piloto · **Etapa:** pipeline satélite → API → app · **Completa:** spec 020 y spec 021 (GeoINTA)

## Objetivo

Que el INTA no nos corte la conexión cuando la app consulta varios lotes seguidos.

| Antes | Después |
|---|---|
| Cada consulta del suelo le hace al INTA decenas de pedidos, con hasta 5 a la vez | Como mucho 3 pedidos a la vez al INTA, sumando todas las consultas de la app |
| El mismo lote pedido dos veces se le vuelve a pedir entero al INTA | El suelo de un lote ya pedido sale de la memoria de la app durante 30 días |
| En la prueba del piloto, después del primer lote el INTA respondió "Connection reset" a GeoINTA y a SEPA, y el suelo salió del respaldo HWSD, que es mucho más grueso | Menos pedidos al INTA, así que es menos probable que nos corte |

## Fuente

GeoINTA, la misma de las specs 020 y 021. No se suma ninguna fuente nueva.

## Entrada

El polígono del lote, igual que hoy.

## Proceso

1. **Memoria del suelo.** El suelo no cambia de un día para el otro (cartas, Atlas, textura, pH, carbono y Mapa Nacional de Cultivos de campañas pasadas). Cuando una consulta trae **todo** el suelo sin errores, la app lo guarda en memoria con el polígono como llave (coordenadas redondeadas a 6 decimales, unos 10 cm).
   - Durante **30 días**, el mismo polígono sale de la memoria sin pedirle nada al INTA. Cada observación copia el `lote_id` del pedido nuevo y su `nota` aclara la fecha en que se le pidió al INTA.
   - Si la consulta tuvo algún error (un paso que el INTA no contestó, una campaña del Mapa Nacional de Cultivos que no llegó en 90 s), **no se guarda**, así la próxima consulta lo vuelve a intentar.
   - Se guardan como mucho **500 lotes**. Si se llena, sale el que se usó hace más tiempo.
   - Es memoria del proceso, no una base de datos (todavía no hay base). Cuando Render duerme o se reinicia, la memoria se vacía y el próximo pedido va al INTA.
2. **Menos pedidos a la vez.** Todos los pedidos HTTP de GeoINTA pasan por un límite común: **como mucho 3 a la vez**, sumando todas las consultas que esté atendiendo la app. Los demás esperan su turno. La lectura de GeoSEPA (GDAL) no entra en este límite, porque si se traba no tiene que trabar a las demás; ya tiene su tope de 90 s (spec 021).
3. Los tests sin internet no usan la memoria (pasan su propio cliente simulado), así cada test ve lo que simula.

## Salida

La misma lista de `Observacion` de siempre. Solo cambia la `nota` cuando el dato sale de la memoria: termina con "· guardado en memoria: el INTA lo entregó el AAAA-MM-DD".

## Reglas de calidad

- Nunca se guarda una respuesta incompleta: guardar un error lo repetiría 30 días.
- El valor y la calidad que salen de la memoria son exactamente los que entregó el INTA.
- SUPUESTO: 3 pedidos a la vez y 30 días. Se calibran con la prueba real del 1/11 (cuando GitHub Actions vuelva a tener minutos).

## Criterios de aceptación

- [x] Tests sin internet: el mismo lote pedido dos veces le pide al INTA una sola vez; otro `lote_id` con el mismo polígono sale de la memoria con su propio `lote_id`; una respuesta con un error no se guarda; pasados 30 días se vuelve a pedir; con más de 500 lotes sale el más viejo; nunca hay más de 3 pedidos HTTP a la vez.
- [ ] Prueba real (1/11/2026 o cuando haya minutos de Actions): las 3 parcelas del piloto seguidas, y después las mismas otra vez. La segunda vuelta no le pide nada al INTA y el suelo no cae al respaldo HWSD.
