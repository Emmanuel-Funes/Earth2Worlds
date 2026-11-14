# Cómo se leyeron las planillas de la RECSO 2025/26 (soja)

Fuente: Informe RECSO 2025/26, Red de Evaluación de Cultivares de Soja (INTA EEA Marcos Juárez y ASA).
PDF de 456 páginas, publicado en https://www.recsoargentina.com/_files/ugd/7ecdbe_ba67e0407e0d49459c087bd8f2d861b4.pdf
SHA-256 del PDF usado: 9ef298ce4946286e330d82d9259f1059c7b4ab2e4139d28eebe56643f3091dd3 (89 MB, no se guarda en el repo).

Las planillas de cada ensayo están como imagen dentro del PDF, así que se leyeron con OCR (tesseract 5.3, idioma spa):

1. `pdfimages -j` saca las imágenes; `ocr_recso.py` lee encabezado, tabla de rindes (canal rojo, para no perder la fila resaltada del testigo) y el panel MEDIA/CV/LSD.
2. `ocr_alt.py` vuelve a leer, con otros umbrales, los ensayos donde el promedio no cerraba.
3. `ocr_cells.py` lee casillero por casillero el análisis de suelo (CO, NT, MO, pH, P, agua útil), fertilización, código, época, antecesor y fechas.
4. `parse3.py` arma los ensayos y las filas, une cada nombre leído con los 88 cultivares de los Cuadros 1 a 9 (`cuadros.json`, sacado del texto del PDF) y elige la lectura cuyo promedio coincide con la MEDIA impresa.
5. `final_recso.py` asigna grupo de madurez y subregión según el índice del informe y escribe los tres CSV de `semillas/datos/recso_soja_2025_26_*.csv`.

Controles que pasan los 351 ensayos (y que repite `tests/test_semillas.py`):
- el promedio de los rindes leídos está a menos de 2% de la MEDIA impresa (345 de 351 a menos de 0,5%);
- ningún cultivar aparece dos veces en el mismo ensayo y todos tienen nombre reconocido.

Correcciones a mano (5 lecturas de OCR ilegibles, verificadas mirando la imagen): '86540' = BG 540, 'GARGARSF' y parecidos = 64R64RSF, 'PSDAO2SCE' = P80A02SCE.
El índice del informe pone a Granville, Berrotarán, Gral. Cabrera, La Carlota y Hernando en "I-3" en los grupos IV corto y V corto; la planilla de cada ensayo dice II-3 y se usa II-3 (queda anotado en `nota_region`).
Las páginas 430 a 456 son los ensayos que el INTA dejó fuera del análisis conjunto (variación no aceptable, diseño o entrega tardía): se cargan pero marcados `en_analisis_conjunto = NO` y no entran en los promedios.
Los casilleros de suelo que el informe deja vacíos quedan vacíos.
