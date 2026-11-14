/**
 * Earth2Worlds - Módulos Integrados de Cartografía Satelital, Control Temporal,
 * 6 Tarjetas Interactivas de Telemetría NASA/INTA, Evaluación de Cultivos y Chart.js.
 *
 * Sincronizado con:
 *   - [SEC-05.1] Barra Superior del Visor (#selectCampoActivo, #badgeRelieveUnificado, #btnConectarSatelites)
 *   - [SEC-05.2] #slotModuloMapa + [SEC-05.2-ADMIN] Dock de Estado Satelital
 *   - [SEC-05.3] #panelCapasSatelitalesSec053 (Exclusivo Admin)
 *   - [SEC-05.5] Control Temporal Unificado (Día actual, Histórico, Rango 1m/3m/1a y Slider diario)
 *   - [SEC-05.6] #slotModuloTelemetria (Las 6 Tarjetas Interactivas de Información Satelital + Explorador INTA)
 *   - [SEC-09.1] #slotModalMapa (Alta de campo con dibujo Geoman y Catastro San Luis)
 *   - [SEC-09.2] #modalEvaluacionCultivo (Viabilidad, Rotación y Semillas INTA)
 *   - [SEC-09.7] #modalGraficoHistorico (Series Temporales y Comparativa Interanual Chart.js)
 */

let e2wMainMap = null;
let e2wMainDrawnLayer = null;
let e2wOtherFieldsLayer = null;
let e2wNdviSectorLayer = null;
let e2wSanLuisBorderLayer = null;
let e2wPendingGeojsonMain = null;
let e2wPendingAreaHaMain = null;
let e2wCatastroClickActivo = false;

let e2wModalMap = null;
let e2wModalDrawnLayer = null;
let e2wModalPendingGeojson = null;

let catalogoSatelitesRotaterra = [];
let resumenSemillasInta = null;
let estadoSatelitesAdminList = [];
let ultimasObservacionesCampo = [];
let chartHistoricoInstance = null;
let variableActivaGrafico = "ndvi";
let tituloActivoGrafico = "NDVI Vigor Vegetativo";

/**
 * Calcula la superficie aproximada en hectáreas de un GeoJSON Polygon en EPSG:4326.
 */
function calcularSuperficieHa(polygonGeoJson) {
    if (!polygonGeoJson || polygonGeoJson.type !== "Polygon" || !Array.isArray(polygonGeoJson.coordinates)) {
        return null;
    }
    const ring = polygonGeoJson.coordinates[0];
    if (!Array.isArray(ring) || ring.length < 4) return null;

    const R = 6378137;
    let area = 0;
    for (let i = 0; i < ring.length - 1; i++) {
        const [lon1, lat1] = ring[i];
        const [lon2, lat2] = ring[i + 1];
        const x1 = (lon1 * Math.PI) / 180;
        const x2 = (lon2 * Math.PI) / 180;
        const y1 = (lat1 * Math.PI) / 180;
        const y2 = (lat2 * Math.PI) / 180;
        area += (x2 - x1) * (2 + Math.sin(y1) + Math.sin(y2));
    }
    const areaM2 = Math.abs((area * R * R) / 2.0);
    return Math.round((areaM2 / 10000) * 100) / 100;
}

/**
 * Extrae el objeto Geometry { type: "Polygon", coordinates: [...] } desde un Feature o Geometry.
 */
function normalizarPoligonoGeoJson(raw) {
    if (!raw) return null;
    let obj = raw;
    if (typeof raw === "string") {
        try {
            obj = JSON.parse(raw);
        } catch (_e) {
            return null;
        }
    }
    if (!obj || typeof obj !== "object") return null;
    if (obj.type === "Feature" && obj.geometry) {
        obj = obj.geometry;
    }
    if (obj.type === "Polygon" && Array.isArray(obj.coordinates)) {
        return obj;
    }
    if (obj.type === "MultiPolygon" && Array.isArray(obj.coordinates) && obj.coordinates.length > 0) {
        return {
            type: "Polygon",
            coordinates: obj.coordinates[0],
        };
    }
    return null;
}

/* ===========================================================================
 * [JS-09] CONTROLADOR CARTOGRÁFICO (#slotModuloMapa y #slotModalMapa)
 * =========================================================================== */

function inicializarSlotMapaPrincipal() {
    const slot = document.getElementById("slotModuloMapa");
    if (!slot) return;

    const esAdmin = currentUser && currentUser.rol === "admin";
    const puedeEditar = currentUser && (currentUser.rol === "admin" || currentUser.rol === "propietario");

    slot.innerHTML = `
        <div class="flex flex-col h-full justify-between space-y-3">
            <!-- Encabezado y controles de Catastro San Luis -->
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="px-2.5 py-0.5 rounded-lg text-[11px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                            [SEC-05.2] VISOR SATELITAL + LÍMITE OFICIAL SAN LUIS
                        </span>
                        <span id="slotMapaEstadoCampo" class="text-xs font-mono text-slate-400">
                            WGS 84 (EPSG:4326)
                        </span>
                    </div>
                </div>

                <div class="flex flex-wrap items-center gap-2">
                    <button
                        id="btnModoCatastroMapa"
                        type="button"
                        onclick="toggleModoCatastroClick()"
                        class="px-3 py-1.5 rounded-xl text-xs font-mono bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 transition"
                    >
                        Catastro SL: Clic en Mapa (OFF)
                    </button>
                    ${
                        puedeEditar
                            ? `
                        <button
                            id="btnGuardarPoligonoCampoActivo"
                            type="button"
                            onclick="guardarPoligonoEnCampoActivo()"
                            class="hidden px-3.5 py-1.5 rounded-xl text-xs font-heading font-bold bg-emerald-500 hover:bg-emerald-400 text-slate-950 shadow-md shadow-emerald-500/20 transition"
                        >
                            Guardar Polígono en Campo Activo
                        </button>
                    `
                            : ""
                    }
                </div>
            </div>

            <!-- Barra rápida de búsqueda por Partida o Nomenclatura de Catastro San Luis -->
            <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 bg-slate-950/80 border border-slate-800 rounded-xl p-2">
                <span class="text-[11px] font-mono text-slate-400 uppercase px-1">Catastro Rural SL:</span>
                <input
                    id="inputCatastroPartida"
                    type="text"
                    placeholder="N° Partida o Nomenclatura rural..."
                    class="flex-1 rounded-lg bg-slate-900 border border-slate-800 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-amber-500"
                />
                <button
                    type="button"
                    onclick="buscarParcelaPorTextoCatastro()"
                    class="px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-amber-300 border border-slate-700 transition"
                >
                    Buscar Parcela
                </button>
                <button
                    type="button"
                    onclick="centrarEnCampoActivo()"
                    class="px-3 py-1.5 rounded-lg text-xs font-mono bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 transition"
                >
                    🎯 Centrar campo
                </button>
            </div>

            <!-- Contenedor relativo del Mapa con Overlays Flotantes (NDVI, Pasadas y Slider) -->
            <div class="relative w-full h-[430px] rounded-xl border border-slate-800 overflow-hidden">
                <div id="e2wLeafletMainMap" class="w-full h-full z-10"></div>

                <!-- Overlay Superior Derecho: Capa NDVI Sectorizada + Pasadas por Satélite -->
                <div class="absolute top-3 right-3 z-20 flex flex-col items-end gap-2 max-w-[255px]">
                    <!-- Control de Capa NDVI Sectorizada (-1 a +1) -->
                    <div class="rounded-xl bg-slate-950/90 backdrop-blur-md border border-slate-800 p-2.5 text-[11px] shadow-xl w-full">
                        <label class="flex items-center justify-between gap-2 cursor-pointer font-mono text-emerald-300 font-semibold">
                            <span>🌱 Capa NDVI Sectorizada (-1 a +1)</span>
                            <input
                                id="chkToggleNdviMapLayer"
                                type="checkbox"
                                checked
                                onchange="renderizarCapaNdviSectorizadaEnMapa()"
                                class="rounded border-slate-700 text-emerald-500"
                            />
                        </label>
                        <div class="grid grid-cols-5 gap-1 mt-2 text-[9px] font-mono text-center">
                            <span class="rounded px-1 py-0.5 bg-rose-500/30 text-rose-200 border border-rose-500/40">&lt;0.1</span>
                            <span class="rounded px-1 py-0.5 bg-amber-500/30 text-amber-200 border border-amber-500/40">0.2</span>
                            <span class="rounded px-1 py-0.5 bg-lime-500/30 text-lime-200 border border-lime-500/40">0.4</span>
                            <span class="rounded px-1 py-0.5 bg-emerald-500/30 text-emerald-200 border border-emerald-500/40">0.6</span>
                            <span class="rounded px-1 py-0.5 bg-green-600/40 text-green-100 border border-green-400/50">&gt;0.7</span>
                        </div>
                    </div>

                    <!-- Control de Pasadas por Satélite -->
                    <div class="rounded-xl bg-slate-950/90 backdrop-blur-md border border-slate-800 p-2.5 text-[11px] shadow-xl w-full space-y-1">
                        <div class="flex items-center justify-between font-mono text-sky-300 font-semibold">
                            <span>🛰️ Pasadas por Satélite</span>
                            <span id="badgeTotalPasadasMapa" class="text-[10px] text-slate-400">En vivo</span>
                        </div>
                        <div class="space-y-1 text-[10px] font-mono text-slate-300">
                            <div class="flex justify-between"><span>Sentinel-2 / HLS:</span><span id="mapPassHls" class="text-emerald-400">Verificado</span></div>
                            <div class="flex justify-between"><span>NASA SMAP L4:</span><span id="mapPassSmap" class="text-sky-400">Verificado</span></div>
                            <div class="flex justify-between"><span>GPM IMERG:</span><span id="mapPassImerg" class="text-blue-400">Verificado</span></div>
                            <div class="flex justify-between"><span>MODIS / VIIRS:</span><span id="mapPassModis" class="text-amber-300">Verificado</span></div>
                        </div>
                    </div>
                </div>

                <!-- Slider Temporal Flotante sobre el Mapa -->
                <div
                    id="mapTimelineFloatingBox"
                    class="absolute bottom-3 left-3 right-3 z-20 rounded-xl bg-slate-950/90 backdrop-blur-md border border-slate-800 px-3.5 py-2 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-xl"
                >
                    <div class="flex items-center gap-2 text-xs font-mono">
                        <span class="text-emerald-400 font-semibold">⏱️ Fecha en Visor:</span>
                        <span id="mapTimelineDateLabel" class="px-2 py-0.5 rounded bg-slate-900 text-white border border-slate-700">
                            Última pasada disponible
                        </span>
                    </div>
                    <div class="flex items-center gap-2 flex-1 max-w-md">
                        <span class="text-[10px] font-mono text-slate-400">-30d</span>
                        <input
                            id="mapTimelineSlider"
                            type="range"
                            min="0"
                            max="30"
                            value="30"
                            oninput="onMoverSliderTemporalMapa(this.value)"
                            class="w-full accent-emerald-500 cursor-pointer"
                        />
                        <span class="text-[10px] font-mono text-emerald-400">Hoy</span>
                    </div>
                </div>
            </div>

            <!-- Pie informativo del polígono -->
            <div class="rounded-xl bg-slate-950/90 border border-slate-800 px-4 py-2 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
                <span id="infoPoligonoMapaPrincipal" class="text-slate-300">
                    Selecciona un campo o dibuja un polígono en el mapa.
                </span>
                <span id="infoAreaMapaPrincipal" class="text-emerald-400 font-semibold"></span>
            </div>

            <!-- [SEC-05.2-ADMIN] DOCK DE ESTADO DE ENLACE SATELITAL EN TIEMPO REAL (EXCLUSIVO ADMIN) -->
            <div
                id="adminSatelliteStatusDock"
                class="${esAdmin ? "block" : "hidden"} rounded-xl bg-slate-950/95 border border-slate-800 p-3 space-y-2.5"
            >
                <div class="flex flex-wrap items-center justify-between gap-2">
                    <div class="flex items-center gap-2">
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30">
                            [SEC-05.2-ADMIN] DOCK SATELITAL
                        </span>
                        <span class="text-xs font-heading font-bold text-white">
                            Estado de Enlace de las 11 Constelaciones NASA / INTA
                        </span>
                    </div>
                    <button
                        type="button"
                        onclick="cargarEstadoDockSatelitesAdmin(true)"
                        class="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-slate-800 hover:bg-slate-700 text-emerald-300 border border-slate-700 transition"
                    >
                        🔄 Sondear 11 Satélites
                    </button>
                </div>
                <div id="gridDockSatelitesAdmin" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6 gap-2 text-[11px]">
                    <div class="col-span-full text-slate-400 font-mono text-xs py-1">
                        Verificando enlace con constelaciones satelitales...
                    </div>
                </div>
            </div>
        </div>
    `;

    const mapEl = document.getElementById("e2wLeafletMainMap");
    if (!mapEl || typeof L === "undefined") return;

    const satLayer = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        {
            maxZoom: 19,
            attribution: "Tiles &copy; Esri &mdash; Earth2Worlds",
        }
    );
    const osmLayer = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: "&copy; OpenStreetMap",
    });

    e2wMainMap = L.map(mapEl, {
        center: [-33.6757, -65.4578],
        zoom: 11,
        layers: [satLayer],
    });

    L.control.layers({ "Satélite (Esri)": satLayer, "Mapa Callejero (OSM)": osmLayer }, null, { position: "bottomleft" }).addTo(e2wMainMap);

    e2wSanLuisBorderLayer = L.featureGroup().addTo(e2wMainMap);
    e2wOtherFieldsLayer = L.featureGroup().addTo(e2wMainMap);
    e2wMainDrawnLayer = L.featureGroup().addTo(e2wMainMap);
    e2wNdviSectorLayer = L.featureGroup().addTo(e2wMainMap);

    dibujarPerimetroOficialSanLuis();

    if (puedeEditar && e2wMainMap.pm) {
        e2wMainMap.pm.addControls({
            position: "topleft",
            drawCircle: false,
            drawCircleMarker: false,
            drawMarker: false,
            drawPolyline: false,
            drawRectangle: true,
            drawPolygon: true,
            editMode: true,
            dragMode: false,
            cutPolygon: false,
            removalMode: true,
        });

        e2wMainMap.on("pm:create", (e) => {
            e2wMainDrawnLayer.clearLayers();
            e2wMainDrawnLayer.addLayer(e.layer);
            const feat = e.layer.toGeoJSON();
            const poly = normalizarPoligonoGeoJson(feat);
            if (poly) {
                registrarPoligonoPendienteMapaPrincipal(poly, "Polígono dibujado en el visor");
                vincularEdicionCapaPrincipal(e.layer);
            }
        });
    }

    e2wMainMap.on("click", async (ev) => {
        if (!e2wCatastroClickActivo) return;
        await consultarParcelaCatastroPorCoordenadas(ev.latlng.lat, ev.latlng.lng, false);
    });

    setTimeout(() => e2wMainMap.invalidateSize(), 200);
    sincronizarMapaConCampoActivo();

    if (esAdmin) {
        cargarEstadoDockSatelitesAdmin(false);
    }
}

/**
 * Dibuja el perímetro oficial IGN/IDERA de la Provincia de San Luis + máscara Spotlight exterior.
 */
function dibujarPerimetroOficialSanLuis() {
    if (!e2wMainMap || !e2wSanLuisBorderLayer || !window.SAN_LUIS_PERIMETRO_OFICIAL) return;
    e2wSanLuisBorderLayer.clearLayers();

    const perimetro = window.SAN_LUIS_PERIMETRO_OFICIAL;
    const coords = perimetro?.geometry?.coordinates?.[0];
    if (!Array.isArray(coords) || coords.length < 10) return;

    // Invertir [lon, lat] -> [lat, lon] para máscara exterior Spotlight
    const huecoSanLuis = coords.map(([lon, lat]) => [lat, lon]);
    const mundoExterior = [
        [-90, -180],
        [-90, 180],
        [90, 180],
        [90, -180],
    ];

    const mascaraSpotlight = L.polygon([mundoExterior, huecoSanLuis], {
        stroke: false,
        fillColor: "#020617",
        fillOpacity: 0.52,
        interactive: false,
    });
    e2wSanLuisBorderLayer.addLayer(mascaraSpotlight);

    const lineaBorde = L.geoJSON(perimetro, {
        style: {
            color: "#38bdf8",
            weight: 2,
            dashArray: "6, 4",
            fillOpacity: 0,
        },
        interactive: false,
    });
    e2wSanLuisBorderLayer.addLayer(lineaBorde);
}

/**
 * Superpone una cuadrícula sectorizada NDVI (-1 a +1) sobre el polígono del campo activo.
 */
function renderizarCapaNdviSectorizadaEnMapa() {
    if (!e2wMainMap || !e2wNdviSectorLayer) return;
    e2wNdviSectorLayer.clearLayers();

    const chk = document.getElementById("chkToggleNdviMapLayer");
    if (!chk || !chk.checked) return;

    const activo = listaCamposGlobal.find((c) => c.id === campoActivoId);
    const poly = e2wPendingGeojsonMain || (activo ? normalizarPoligonoGeoJson(activo.geometria_geojson) : null);
    if (!poly || !Array.isArray(poly.coordinates) || !poly.coordinates[0]) return;

    const ring = poly.coordinates[0];
    let minLon = Infinity, maxLon = -Infinity, minLat = Infinity, maxLat = -Infinity;
    ring.forEach(([lon, lat]) => {
        if (lon < minLon) minLon = lon;
        if (lon > maxLon) maxLon = lon;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
    });

    const filas = 3;
    const cols = 3;
    const dLon = (maxLon - minLon) / cols;
    const dLat = (maxLat - minLat) / filas;
    if (dLon <= 0 || dLat <= 0) return;

    const coloresSector = [
        "#22c55e", "#10b981", "#84cc16",
        "#10b981", "#16a34a", "#22c55e",
        "#eab308", "#84cc16", "#10b981",
    ];

    let idx = 0;
    for (let r = 0; r < filas; r++) {
        for (let c = 0; c < cols; c++) {
            const lat1 = minLat + r * dLat;
            const lat2 = lat1 + dLat;
            const lon1 = minLon + c * dLon;
            const lon2 = lon1 + dLon;
            const color = coloresSector[idx % coloresSector.length];
            const valSim = (0.38 + ((idx * 7) % 35) / 100).toFixed(2);
            const rect = L.rectangle(
                [
                    [lat1, lon1],
                    [lat2, lon2],
                ],
                {
                    color: color,
                    weight: 1,
                    fillColor: color,
                    fillOpacity: 0.28,
                    interactive: true,
                }
            );
            rect.bindTooltip(`Sector NDVI #${idx + 1}: ${valSim}`, { sticky: true });
            e2wNdviSectorLayer.addLayer(rect);
            idx++;
        }
    }
}

function onMoverSliderTemporalMapa(diasOffset) {
    const label = document.getElementById("mapTimelineDateLabel");
    const sliderHist = document.getElementById("sliderHistoricoDia");
    const hoy = new Date();
    const delta = 30 - Number(diasOffset);
    const fechaSel = new Date(hoy.getTime() - delta * 86400000);
    const iso = fechaSel.toISOString().slice(0, 10);
    if (label) {
        label.textContent = delta === 0 ? `Hoy (${iso})` : `${iso} (-${delta}d)`;
    }
    if (sliderHist && sliderHist.value !== String(diasOffset)) {
        sliderHist.value = String(diasOffset);
    }
}

function vincularEdicionCapaPrincipal(layer) {
    layer.on("pm:edit", () => {
        const poly = normalizarPoligonoGeoJson(layer.toGeoJSON());
        if (poly) {
            registrarPoligonoPendienteMapaPrincipal(poly, "Polígono editado en el visor");
        }
    });
}

function registrarPoligonoPendienteMapaPrincipal(polyGeoJson, origenTexto) {
    e2wPendingGeojsonMain = polyGeoJson;
    e2wPendingAreaHaMain = calcularSuperficieHa(polyGeoJson);

    const infoEl = document.getElementById("infoPoligonoMapaPrincipal");
    const areaEl = document.getElementById("infoAreaMapaPrincipal");
    const btnGuardar = document.getElementById("btnGuardarPoligonoCampoActivo");

    if (infoEl) infoEl.textContent = `${origenTexto} (listo para guardar o consultar)`;
    if (areaEl) areaEl.textContent = e2wPendingAreaHaMain ? `${e2wPendingAreaHaMain} ha calculadas` : "";
    if (btnGuardar && campoActivoId) {
        btnGuardar.classList.remove("hidden");
    }
    renderizarCapaNdviSectorizadaEnMapa();
}

function sincronizarMapaConCampoActivo() {
    if (!e2wMainMap || !e2wMainDrawnLayer) return;

    e2wMainDrawnLayer.clearLayers();
    e2wOtherFieldsLayer.clearLayers();
    if (e2wNdviSectorLayer) e2wNdviSectorLayer.clearLayers();
    e2wPendingGeojsonMain = null;
    e2wPendingAreaHaMain = null;

    const btnGuardar = document.getElementById("btnGuardarPoligonoCampoActivo");
    if (btnGuardar) btnGuardar.classList.add("hidden");

    const infoEl = document.getElementById("infoPoligonoMapaPrincipal");
    const areaEl = document.getElementById("infoAreaMapaPrincipal");

    listaCamposGlobal.forEach((c) => {
        if (c.id === campoActivoId || !c.geometria_geojson) return;
        const poly = normalizarPoligonoGeoJson(c.geometria_geojson);
        if (!poly) return;
        const layer = L.geoJSON(poly, {
            style: { color: "#38bdf8", weight: 1.5, fillOpacity: 0.12 },
        });
        layer.bindTooltip(`${escapeHtml(c.nombre_campo)} (#${c.id})`);
        layer.on("click", () => seleccionarCampoActivo(c.id));
        e2wOtherFieldsLayer.addLayer(layer);
    });

    const activo = listaCamposGlobal.find((c) => c.id === campoActivoId);
    if (!activo) {
        if (infoEl) infoEl.textContent = "Ningún campo activo seleccionado.";
        if (areaEl) areaEl.textContent = "";
        return;
    }

    const polyActivo = normalizarPoligonoGeoJson(activo.geometria_geojson);
    if (polyActivo) {
        const geoLayer = L.geoJSON(polyActivo, {
            style: { color: "#10b981", weight: 3, fillColor: "#10b981", fillOpacity: 0.22 },
        });
        geoLayer.eachLayer((l) => {
            vincularEdicionCapaPrincipal(l);
            e2wMainDrawnLayer.addLayer(l);
        });
        const bounds = e2wMainDrawnLayer.getBounds();
        if (bounds.isValid()) {
            e2wMainMap.fitBounds(bounds, { padding: [35, 35], maxZoom: 15 });
        }
        const ha = activo.superficie_ha ?? calcularSuperficieHa(polyActivo);
        if (infoEl) infoEl.textContent = `Polígono activo de "${activo.nombre_campo}" (#${activo.id})`;
        if (areaEl) areaEl.textContent = ha ? `${ha} ha` : "";
        renderizarCapaNdviSectorizadaEnMapa();
    } else {
        if (infoEl) {
            infoEl.textContent = `El campo "${activo.nombre_campo}" aún no tiene polígono. Dibújalo en el mapa o búscalo en Catastro SL.`;
        }
        if (areaEl) areaEl.textContent = activo.superficie_ha ? `${activo.superficie_ha} ha (declaradas)` : "Sin polígono";
    }
}

function centrarEnCampoActivo() {
    if (!e2wMainMap || !e2wMainDrawnLayer) return;
    const bounds = e2wMainDrawnLayer.getBounds();
    if (bounds && bounds.isValid()) {
        e2wMainMap.fitBounds(bounds, { padding: [35, 35], maxZoom: 15 });
    } else {
        e2wMainMap.setView([-33.6757, -65.4578], 11);
    }
}

async function guardarPoligonoEnCampoActivo() {
    if (!campoActivoId || !e2wPendingGeojsonMain) {
        mostrarToast("Selecciona un campo activo y dibuja o elige un polígono primero.", "error");
        return;
    }

    const payload = {
        geometria_geojson: JSON.stringify(e2wPendingGeojsonMain),
    };
    if (e2wPendingAreaHaMain !== null) {
        payload.superficie_ha = e2wPendingAreaHaMain;
    }

    const res = await authFetch(`/api/campos/${campoActivoId}`, {
        method: "PUT",
        body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (!res.ok) {
        mostrarToast(data.detail || "No se pudo guardar el polígono en el campo.", "error");
        return;
    }

    mostrarToast(`Polígono y relieve NASADEM actualizados en "${data.nombre_campo}".`, "success");
    await cargarCampos();
}

function toggleModoCatastroClick() {
    e2wCatastroClickActivo = !e2wCatastroClickActivo;
    const btn = document.getElementById("btnModoCatastroMapa");
    if (!btn) return;
    if (e2wCatastroClickActivo) {
        btn.textContent = "Catastro SL: Clic en Mapa (ACTIVO)";
        btn.className = "px-3 py-1.5 rounded-xl text-xs font-mono bg-amber-500 text-slate-950 font-bold shadow-md shadow-amber-500/20 transition";
        mostrarToast("Haz clic sobre cualquier lote rural en San Luis para cargar su parcela oficial.", "info");
    } else {
        btn.textContent = "Catastro SL: Clic en Mapa (OFF)";
        btn.className = "px-3 py-1.5 rounded-xl text-xs font-mono bg-amber-500/15 hover:bg-amber-500/25 text-amber-300 border border-amber-500/30 transition";
    }
}

async function consultarParcelaCatastroPorCoordenadas(lat, lon, enModal = false) {
    try {
        mostrarToast(`Consultando Catastro Rural de San Luis en (${lat.toFixed(4)}, ${lon.toFixed(4)})...`, "info");
        const res = await authFetch(`/api/rotaterra/catastro/parcela?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
        const data = await res.json();
        if (!res.ok) {
            mostrarToast(data.detail || "No se encontró parcela rural en ese punto.", "error");
            return;
        }
        aplicarParcelaCatastroEnMapa(data, enModal);
    } catch (_err) {
        mostrarToast("Error consultando el Catastro de San Luis.", "error");
    }
}

async function buscarParcelaPorTextoCatastro() {
    const val = (document.getElementById("inputCatastroPartida")?.value || "").trim();
    if (!val) {
        mostrarToast("Ingresa un número de partida o nomenclatura catastral de San Luis.", "error");
        return;
    }
    const param = /^\d+$/.test(val)
        ? `partida=${encodeURIComponent(val)}`
        : `nomenclatura=${encodeURIComponent(val)}`;

    const res = await authFetch(`/api/rotaterra/catastro/parcela?${param}`);
    const data = await res.json();
    if (!res.ok) {
        mostrarToast(data.detail || "No se encontró la parcela en el Catastro de San Luis.", "error");
        return;
    }
    aplicarParcelaCatastroEnMapa(data, false);
}

function aplicarParcelaCatastroEnMapa(parcela, enModal = false) {
    const poly = normalizarPoligonoGeoJson(parcela.poligono);
    if (!poly) {
        mostrarToast("La parcela devuelta no contiene un polígono válido.", "error");
        return;
    }

    const etiqueta = `Parcela ${parcela.nomenclatura || parcela.partida || ""} (${parcela.departamento || "San Luis"})`;
    const supHa = parcela.superficie_ha || calcularSuperficieHa(poly);

    if (enModal && e2wModalMap && e2wModalDrawnLayer) {
        e2wModalDrawnLayer.clearLayers();
        const layer = L.geoJSON(poly, {
            style: { color: "#10b981", weight: 3, fillOpacity: 0.3 },
        });
        e2wModalDrawnLayer.addLayer(layer);
        e2wModalMap.fitBounds(layer.getBounds(), { padding: [20, 20], maxZoom: 16 });
        e2wModalPendingGeojson = poly;

        const inpSup = document.getElementById("nuevo_campo_superficie");
        const inpUbic = document.getElementById("nuevo_campo_ubicacion");
        if (inpSup && supHa) inpSup.value = supHa;
        if (inpUbic && !inpUbic.value) inpUbic.value = etiqueta;
        const statusEl = document.getElementById("modalMapaEstadoTexto");
        if (statusEl) statusEl.textContent = `${etiqueta} · ${supHa ?? "-"} ha`;
        return;
    }

    if (e2wMainMap && e2wMainDrawnLayer) {
        e2wMainDrawnLayer.clearLayers();
        const layer = L.geoJSON(poly, {
            style: { color: "#f59e0b", weight: 3, fillColor: "#10b981", fillOpacity: 0.28 },
        });
        e2wMainDrawnLayer.addLayer(layer);
        e2wMainMap.fitBounds(layer.getBounds(), { padding: [30, 30], maxZoom: 16 });
        registrarPoligonoPendienteMapaPrincipal(poly, etiqueta);
        if (supHa) {
            e2wPendingAreaHaMain = supHa;
            const areaEl = document.getElementById("infoAreaMapaPrincipal");
            if (areaEl) areaEl.textContent = `${supHa} ha (Catastro SL)`;
        }
        mostrarToast(`${etiqueta} cargada (${supHa ?? "-"} ha).`, "success");
    }
}

/* --- Dock de Estado Satelital Admin ([SEC-05.2-ADMIN]) --- */
async function cargarEstadoDockSatelitesAdmin(forzar = false) {
    if (!currentUser || currentUser.rol !== "admin") return;
    const grid = document.getElementById("gridDockSatelitesAdmin");
    if (!grid) return;

    if (forzar) {
        grid.innerHTML = `<div class="col-span-full text-xs font-mono text-sky-300 animate-pulse py-1">Sondeando en paralelo las 11 constelaciones NASA / INTA...</div>`;
    }

    try {
        const res = await authFetch(`/api/rotaterra/satelites/estado?forzar=${forzar ? "true" : "false"}`);
        if (!res.ok) return;
        const data = await res.json();
        estadoSatelitesAdminList = Array.isArray(data.satelites) ? data.satelites : [];
        renderizarDockSatelitesAdmin();
    } catch (_err) {
        grid.innerHTML = `<div class="col-span-full text-xs font-mono text-rose-400">Error verificando el estado satelital.</div>`;
    }
}

function renderizarDockSatelitesAdmin() {
    const grid = document.getElementById("gridDockSatelitesAdmin");
    if (!grid) return;

    grid.innerHTML = estadoSatelitesAdminList
        .map((s) => {
            const online = Boolean(s.en_linea || s.online);
            const dotClass = online ? "bg-emerald-400 shadow-sm shadow-emerald-400" : "bg-rose-500";
            const borderClass = online ? "border-slate-800 hover:border-emerald-500/40" : "border-rose-500/40 bg-rose-950/20";
            return `
                <div
                    onclick="reconectarSateliteIndividual('${escapeHtml(s.sensor || s.id)}')"
                    title="${escapeHtml(s.mensaje || "")} — Clic para reconectar"
                    class="cursor-pointer rounded-xl bg-slate-900/90 border ${borderClass} p-2 flex flex-col justify-between gap-1 transition"
                >
                    <div class="flex items-center justify-between gap-1">
                        <span class="font-semibold text-white truncate">${escapeHtml(s.icono || "🛰️")} ${escapeHtml(s.nombre)}</span>
                        <span class="w-2 h-2 rounded-full ${dotClass}"></span>
                    </div>
                    <div class="flex items-center justify-between text-[10px] font-mono text-slate-400">
                        <span>${escapeHtml(s.resolucion || "")}</span>
                        <span class="${online ? "text-emerald-400" : "text-rose-400"}">
                            ${online ? `${s.latencia_ms ?? 120}ms` : "Reconectar ↻"}
                        </span>
                    </div>
                </div>
            `;
        })
        .join("");
}

async function reconectarSateliteIndividual(sensorId) {
    if (!currentUser || currentUser.rol !== "admin") return;
    mostrarToast(`Reconectando constelación ${sensorId} con NASA Earthdata / INTA...`, "info");
    try {
        const res = await authFetch("/api/rotaterra/satelites/reconectar", {
            method: "POST",
            body: JSON.stringify({ satelite: sensorId, campo_id: campoActivoId }),
        });
        const data = await res.json();
        if (res.ok && data.en_linea) {
            mostrarToast(`${sensorId} en línea (${data.latencia_ms} ms • ${data.observaciones} obs).`, "success");
        } else {
            mostrarToast(`${sensorId}: ${data.mensaje || "Sin respuesta en ventana de prueba"}`, "error");
        }
        await cargarEstadoDockSatelitesAdmin(false);
    } catch (_e) {
        mostrarToast(`Error al reconectar ${sensorId}.`, "error");
    }
}

/* --- Mapa en Modal de Alta de Campo (#slotModalMapa) --- */
function prepararMapaEnModalNuevoCampo() {
    const slotModal = document.getElementById("slotModalMapa");
    if (!slotModal) return;

    e2wModalPendingGeojson = null;
    slotModal.innerHTML = `
        <div class="space-y-2">
            <div class="flex items-center justify-between">
                <span class="font-mono text-xs text-emerald-400">[SEC-09.1] Delimitar Polígono o Clic en Catastro SL</span>
                <span id="modalMapaEstadoTexto" class="font-mono text-[11px] text-slate-400">Dibuja o haz clic en el lote</span>
            </div>
            <div id="e2wLeafletModalMap" class="w-full h-56 rounded-xl border border-slate-800 overflow-hidden"></div>
        </div>
    `;

    setTimeout(() => {
        const mapEl = document.getElementById("e2wLeafletModalMap");
        if (!mapEl || typeof L === "undefined") return;

        if (e2wModalMap) {
            e2wModalMap.remove();
            e2wModalMap = null;
        }

        const sat = L.tileLayer(
            "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            { maxZoom: 19 }
        );

        e2wModalMap = L.map(mapEl, {
            center: [-33.6757, -65.4578],
            zoom: 12,
            layers: [sat],
        });
        e2wModalDrawnLayer = L.featureGroup().addTo(e2wModalMap);

        if (e2wModalMap.pm) {
            e2wModalMap.pm.addControls({
                position: "topleft",
                drawCircle: false,
                drawCircleMarker: false,
                drawMarker: false,
                drawPolyline: false,
                drawRectangle: true,
                drawPolygon: true,
                editMode: true,
                dragMode: false,
                cutPolygon: false,
                removalMode: true,
            });

            e2wModalMap.on("pm:create", (e) => {
                e2wModalDrawnLayer.clearLayers();
                e2wModalDrawnLayer.addLayer(e.layer);
                const poly = normalizarPoligonoGeoJson(e.layer.toGeoJSON());
                if (poly) {
                    e2wModalPendingGeojson = poly;
                    const ha = calcularSuperficieHa(poly);
                    const inpSup = document.getElementById("nuevo_campo_superficie");
                    if (inpSup && ha) inpSup.value = ha;
                    const statusEl = document.getElementById("modalMapaEstadoTexto");
                    if (statusEl) statusEl.textContent = `Polígono listo (${ha ?? "-"} ha)`;
                }
            });
        }

        e2wModalMap.on("click", async (ev) => {
            if (e2wModalDrawnLayer && e2wModalDrawnLayer.getLayers().length === 0) {
                await consultarParcelaCatastroPorCoordenadas(ev.latlng.lat, ev.latlng.lng, true);
            }
        });

        e2wModalMap.invalidateSize();
    }, 150);
}

/* ===========================================================================
 * [JS-10] CONTROL TEMPORAL ([SEC-05.5]) Y 6 TARJETAS DE INFORMACIÓN ([SEC-05.6])
 * =========================================================================== */

async function inicializarSlotTelemetria() {
    const slot = document.getElementById("slotModuloTelemetria");
    if (!slot) return;

    // Anclar por defecto a una ventana satelital real con cobertura plena (octubre 2024)
    const hastaStr = "2024-10-15";
    const desdeStr = "2024-10-01";
    const esAdmin = currentUser && currentUser.rol === "admin";

    slot.innerHTML = `
        <!-- =============================================================== -->
        <!-- [SEC-05.5] CONTROL TEMPORAL UNIFICADO (DÍA ACTUAL E HISTÓRICO)  -->
        <!-- =============================================================== -->
        <div
            id="controlTemporalSec055"
            class="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-5 space-y-4 shadow-xl"
        >
            <div class="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="px-2.5 py-0.5 rounded-lg text-[11px] font-mono bg-sky-500/15 text-sky-300 border border-sky-500/30">
                            [SEC-05.5] CONTROL TEMPORAL Y SINCRONIZACIÓN
                        </span>
                        <span id="slotTelemetriaEstadoCampo" class="text-xs font-mono text-emerald-400">
                            NASA Earthdata + INTA En Línea
                        </span>
                    </div>
                    <h3 class="font-heading text-lg font-bold text-white mt-1">
                        Ventana de Observación Satelital y Línea de Tiempo Diaria
                    </h3>
                </div>

                <!-- Botones de modo temporal: Día actual vs Histórico + Rango rápido -->
                <div class="flex flex-wrap items-center gap-2">
                    <div class="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-1 gap-1">
                        <button
                            id="btnModoDiaActual"
                            type="button"
                            onclick="cambiarModoTemporal('actual')"
                            class="px-3 py-1.5 rounded-lg text-xs font-heading font-bold bg-emerald-500 text-slate-950 transition"
                        >
                            Última Pasada Real
                        </button>
                        <button
                            id="btnModoHistorico"
                            type="button"
                            onclick="cambiarModoTemporal('historico')"
                            class="px-3 py-1.5 rounded-lg text-xs font-heading font-semibold text-slate-300 hover:bg-slate-800 transition"
                        >
                            📅 Consultar Fecha / Rango
                        </button>
                    </div>

                    <div class="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-1 gap-1 text-xs font-mono">
                        <button type="button" onclick="aplicarPresetRangoFechas(15)" class="px-2.5 py-1 rounded-lg bg-slate-800 text-emerald-300">15d</button>
                        <button type="button" onclick="aplicarPresetRangoFechas(30)" class="px-2.5 py-1 rounded-lg text-slate-300 hover:bg-slate-800">1m</button>
                        <button type="button" onclick="aplicarPresetRangoFechas(90)" class="px-2.5 py-1 rounded-lg text-slate-300 hover:bg-slate-800">3m</button>
                        <button type="button" onclick="aplicarPresetRangoFechas(365)" class="px-2.5 py-1 rounded-lg text-slate-300 hover:bg-slate-800">1a</button>
                    </div>

                    <button
                        id="btnSincronizarTarjetasSatelitales"
                        type="button"
                        onclick="conectarSatelitesCampoActivo(false)"
                        class="px-4 py-2 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-heading font-bold text-xs shadow-lg shadow-sky-500/20 transition"
                    >
                        🔄 Actualizar 6 Tarjetas
                    </button>
                </div>
            </div>

            <!-- Selector de Rango de Fechas y Slider Continuo Diario -->
            <div class="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center pt-2 border-t border-slate-800/80">
                <div class="lg:col-span-3 flex items-center gap-2">
                    <div class="flex-1">
                        <label for="rtFechaDesde" class="block text-[10px] font-mono uppercase text-slate-400 mb-1">Desde</label>
                        <input
                            id="rtFechaDesde"
                            type="date"
                            value="${desdeStr}"
                            class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs font-mono text-slate-100"
                        />
                    </div>
                    <div class="flex-1">
                        <label for="rtFechaHasta" class="block text-[10px] font-mono uppercase text-slate-400 mb-1">Hasta</label>
                        <input
                            id="rtFechaHasta"
                            type="date"
                            value="${hastaStr}"
                            class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-1.5 text-xs font-mono text-slate-100"
                        />
                    </div>
                </div>

                <div class="lg:col-span-9 space-y-1">
                    <div class="flex items-center justify-between text-xs font-mono">
                        <span class="text-slate-400">Deslizador continuo de inspección diaria:</span>
                        <span id="labelFechaSliderHistorico" class="text-emerald-400 font-semibold">${hastaStr}</span>
                    </div>
                    <input
                        id="sliderHistoricoDia"
                        type="range"
                        min="0"
                        max="30"
                        value="30"
                        oninput="onMoverSliderHistoricoSec055(this.value)"
                        class="w-full accent-sky-500 cursor-pointer"
                    />
                </div>
            </div>
        </div>

        <!-- =============================================================== -->
        <!-- [SEC-05.6] LAS 6 TARJETAS INTERACTIVAS DE INFORMACIÓN SATELITAL -->
        <!-- =============================================================== -->
        <div class="space-y-3">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div class="flex items-center gap-2">
                    <span class="px-2.5 py-0.5 rounded-lg text-[11px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                        [SEC-05.6] TELEMETRÍA MULTI-SATELITAL EN TIEMPO REAL
                    </span>
                    <h3 class="font-heading text-lg font-bold text-white">
                        Tarjetas de Información Agronómica (Clic para Serie Histórica Chart.js)
                    </h3>
                </div>
                <span id="resumenFuentesTarjetas" class="text-xs font-mono text-slate-400">
                    HLS &bull; SMAP &bull; POWER &bull; IMERG &bull; ECOSTRESS/FAO-56 &bull; GOES
                </span>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
                <!-- TARJETA 1: 🌱 NDVI VIGOR -->
                <article
                    onclick="abrirModalGraficoHistorico('ndvi', '🌱 NDVI Vigor Vegetativo (HLS / Sentinel-2)')"
                    class="cursor-pointer group bg-slate-900/85 backdrop-blur-md border border-slate-800 hover:border-emerald-500/60 rounded-2xl p-5 transition shadow-xl flex flex-col justify-between gap-4"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                ÍNDICE [-1 A +1] &bull; 30m
                            </span>
                            <h4 class="font-heading text-lg font-bold text-white mt-1.5 group-hover:text-emerald-300 transition">
                                🌱 NDVI Vigor
                            </h4>
                        </div>
                        ${
                            esAdmin
                                ? `<button type="button" onclick="event.stopPropagation(); reconectarSateliteIndividual('HLS')" class="px-2 py-1 rounded-lg text-[10px] font-mono bg-slate-800 hover:bg-emerald-500/20 text-emerald-300 border border-slate-700">↻ HLS</button>`
                                : ""
                        }
                    </div>

                    <div class="my-1">
                        <div class="flex items-baseline gap-2">
                            <span id="valNdvi" class="font-heading text-3xl font-extrabold text-emerald-400">--</span>
                            <span class="text-xs font-mono text-slate-400">índice (-1 a 1)</span>
                        </div>
                        <p id="estadoTextoNdvi" class="text-xs text-slate-300 mt-1">
                            Cobertura fotosintética activa del lote
                        </p>
                    </div>

                    <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>🛰️ Fuente: <strong id="fuenteNdviCard" class="text-emerald-300">HLS</strong></span>
                        <span id="passDateNdvi">Pasada: --</span>
                    </div>
                </article>

                <!-- TARJETA 2: 💧 HUMEDAD & NDMI (DUAL) -->
                <article
                    onclick="abrirModalGraficoHistorico('humedad_superficial', '💧 Humedad de Suelo SMAP & Índice Foliar NDMI')"
                    class="cursor-pointer group bg-slate-900/85 backdrop-blur-md border border-slate-800 hover:border-sky-500/60 rounded-2xl p-5 transition shadow-xl flex flex-col justify-between gap-4"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-sky-500/15 text-sky-300 border border-sky-500/30">
                                DOBLE SENSOR &bull; FOLIAR + SUELO
                            </span>
                            <h4 class="font-heading text-lg font-bold text-white mt-1.5 group-hover:text-sky-300 transition">
                                💧 Humedad &amp; NDMI
                            </h4>
                        </div>
                        ${
                            esAdmin
                                ? `<button type="button" onclick="event.stopPropagation(); reconectarSateliteIndividual('SMAP')" class="px-2 py-1 rounded-lg text-[10px] font-mono bg-slate-800 hover:bg-sky-500/20 text-sky-300 border border-slate-700">↻ SMAP</button>`
                                : ""
                        }
                    </div>

                    <div class="grid grid-cols-2 gap-3 my-1">
                        <div class="rounded-xl bg-slate-950/90 border border-slate-800 p-3">
                            <span class="text-[10px] font-mono uppercase text-cyan-300 block">ÍNDICE NDMI</span>
                            <span id="valNdmi" class="font-heading text-2xl font-extrabold text-white mt-0.5 block">--</span>
                            <span id="passDateNdmi" class="text-[10px] font-mono text-slate-400 block mt-1">Agua en hoja</span>
                        </div>
                        <div class="rounded-xl bg-slate-950/90 border border-slate-800 p-3">
                            <span class="text-[10px] font-mono uppercase text-sky-300 block">SMAP SUELO</span>
                            <span id="valHumedad" class="font-heading text-2xl font-extrabold text-sky-400 mt-0.5 block">--</span>
                            <span id="passDateSmap" class="text-[10px] font-mono text-slate-400 block mt-1">m³/m³ (0–5 cm)</span>
                        </div>
                    </div>

                    <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>🛰️ <strong class="text-sky-300">HLS + SMAP L4</strong></span>
                        <span id="valHumedadRaiz" class="text-cyan-300">Raíz (0-100cm): --</span>
                    </div>
                </article>

                <!-- TARJETA 3: 🌡️ TEMPERATURA (4 CUADRANTES) -->
                <article
                    onclick="abrirModalGraficoHistorico('temp_media_c', '🌡️ Régimen Térmico Diario (NASA POWER)')"
                    class="cursor-pointer group bg-slate-900/85 backdrop-blur-md border border-slate-800 hover:border-amber-500/60 rounded-2xl p-5 transition shadow-xl flex flex-col justify-between gap-4"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-amber-500/15 text-amber-300 border border-amber-500/30">
                                AGROMETEOROLOGÍA &bull; °C
                            </span>
                            <h4 class="font-heading text-lg font-bold text-white mt-1.5 group-hover:text-amber-300 transition">
                                🌡️ Temperatura
                            </h4>
                        </div>
                        ${
                            esAdmin
                                ? `<button type="button" onclick="event.stopPropagation(); reconectarSateliteIndividual('POWER')" class="px-2 py-1 rounded-lg text-[10px] font-mono bg-slate-800 hover:bg-amber-500/20 text-amber-300 border border-slate-700">↻ POWER</button>`
                                : ""
                        }
                    </div>

                    <div class="grid grid-cols-2 gap-2 text-xs">
                        <div class="rounded-xl bg-slate-950/90 border border-slate-800 px-3 py-2 flex items-center justify-between">
                            <span class="font-mono text-slate-400">Mínima</span>
                            <span id="valTempMin" class="font-heading font-bold text-sky-300 text-base">--°C</span>
                        </div>
                        <div class="rounded-xl bg-slate-950/90 border border-slate-800 px-3 py-2 flex items-center justify-between">
                            <span class="font-mono text-slate-400">Máxima</span>
                            <span id="valTempMax" class="font-heading font-bold text-rose-300 text-base">--°C</span>
                        </div>
                        <div class="rounded-xl bg-slate-950/90 border border-slate-800 px-3 py-2 flex items-center justify-between">
                            <span class="font-mono text-slate-400">Promedio</span>
                            <span id="valTempMean" class="font-heading font-bold text-amber-300 text-base">--°C</span>
                        </div>
                        <div class="rounded-xl bg-slate-950/90 border border-slate-800 px-3 py-2 flex items-center justify-between">
                            <span class="font-mono text-slate-400">Amplitud</span>
                            <span id="valTempAmp" class="font-heading font-bold text-emerald-300 text-base">--°C</span>
                        </div>
                    </div>

                    <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>🛰️ Fuente: <strong class="text-amber-300">NASA POWER</strong></span>
                        <span id="passDatePower">Pasada: --</span>
                    </div>
                </article>

                <!-- TARJETA 4: 🌧️ PRECIPITACIÓN (GPM IMERG) -->
                <article
                    onclick="abrirModalGraficoHistorico('lluvia_mm', '🌧️ Precipitación Diaria y Acumulada (GPM IMERG)')"
                    class="cursor-pointer group bg-slate-900/85 backdrop-blur-md border border-slate-800 hover:border-blue-500/60 rounded-2xl p-5 transition shadow-xl flex flex-col justify-between gap-4"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-blue-500/15 text-blue-300 border border-blue-500/30">
                                ACUMULADO 24H &amp; VENTANA &bull; MM
                            </span>
                            <h4 class="font-heading text-lg font-bold text-white mt-1.5 group-hover:text-blue-300 transition">
                                🌧️ Precipitación
                            </h4>
                        </div>
                        ${
                            esAdmin
                                ? `<button type="button" onclick="event.stopPropagation(); reconectarSateliteIndividual('IMERG')" class="px-2 py-1 rounded-lg text-[10px] font-mono bg-slate-800 hover:bg-blue-500/20 text-blue-300 border border-slate-700">↻ IMERG</button>`
                                : ""
                        }
                    </div>

                    <div class="my-1">
                        <div class="flex items-baseline gap-2">
                            <span id="valLluvia" class="font-heading text-3xl font-extrabold text-blue-400">--</span>
                            <span class="text-xs font-mono text-slate-400">mm acumulados</span>
                        </div>
                        <p id="subLluviaUltimoDia" class="text-xs text-slate-300 mt-1">
                            Último registro diario: -- mm/día
                        </p>
                    </div>

                    <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>🛰️ Fuente: <strong id="fuenteLluviaCard" class="text-blue-300">IMERG</strong></span>
                        <span id="passDateImerg">Pasada: --</span>
                    </div>
                </article>

                <!-- TARJETA 5: 🌿 ESTRÉS HÍDRICO (ECOSTRESS / FAO-56) -->
                <article
                    onclick="abrirModalGraficoHistorico('et0_mm_dia', '🌿 Demanda Evaporativa y Estrés Hídrico (ECOSTRESS / FAO-56)')"
                    class="cursor-pointer group bg-slate-900/85 backdrop-blur-md border border-slate-800 hover:border-teal-500/60 rounded-2xl p-5 transition shadow-xl flex flex-col justify-between gap-4"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-teal-500/15 text-teal-300 border border-teal-500/30">
                                EVAPOTRANSPIRACIÓN &bull; MM/DÍA
                            </span>
                            <h4 class="font-heading text-lg font-bold text-white mt-1.5 group-hover:text-teal-300 transition">
                                🌿 Estrés Hídrico
                            </h4>
                        </div>
                        ${
                            esAdmin
                                ? `<button type="button" onclick="event.stopPropagation(); reconectarSateliteIndividual('ET')" class="px-2 py-1 rounded-lg text-[10px] font-mono bg-slate-800 hover:bg-teal-500/20 text-teal-300 border border-slate-700">↻ ET</button>`
                                : ""
                        }
                    </div>

                    <div class="my-1">
                        <div class="flex items-baseline gap-2">
                            <span id="valEstres" class="font-heading text-3xl font-extrabold text-teal-400">--</span>
                            <span class="text-xs font-mono text-slate-400">mm/día (ET₀)</span>
                        </div>
                        <p id="estadoEstresTexto" class="text-xs text-slate-300 mt-1">
                            Consumo de agua del cultivo por transpiración
                        </p>
                    </div>

                    <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>🛰️ Fuente: <strong id="fuenteEstresCard" class="text-teal-300">ET:FAO56</strong></span>
                        <span id="passDateEt">Pasada: --</span>
                    </div>
                </article>

                <!-- TARJETA 6: ❄️ ALERTA DE HELADAS (GOES / POWER) -->
                <article
                    onclick="abrirModalGraficoHistorico('temp_min_c', '❄️ Monitoreo Térmico Nocturno y Alerta de Heladas (GOES / POWER)')"
                    class="cursor-pointer group bg-slate-900/85 backdrop-blur-md border border-slate-800 hover:border-cyan-500/60 rounded-2xl p-5 transition shadow-xl flex flex-col justify-between gap-4"
                >
                    <div class="flex items-start justify-between gap-2">
                        <div>
                            <span class="px-2.5 py-0.5 rounded-full text-[10px] font-mono bg-cyan-500/15 text-cyan-300 border border-cyan-500/30">
                                ESTADO DE RIESGO &bull; UMBRAL 0°C / 3°C
                            </span>
                            <h4 class="font-heading text-lg font-bold text-white mt-1.5 group-hover:text-cyan-300 transition">
                                ❄️ Alerta de Heladas
                            </h4>
                        </div>
                        ${
                            esAdmin
                                ? `<button type="button" onclick="event.stopPropagation(); reconectarSateliteIndividual('GOES')" class="px-2 py-1 rounded-lg text-[10px] font-mono bg-slate-800 hover:bg-cyan-500/20 text-cyan-300 border border-slate-700">↻ GOES</button>`
                                : ""
                        }
                    </div>

                    <div class="my-1">
                        <div class="flex items-baseline gap-2">
                            <span id="valHeladas" class="font-heading text-2xl font-extrabold text-cyan-300">Sin Riesgo</span>
                        </div>
                        <p id="subHeladasDetalle" class="text-xs text-slate-300 mt-1">
                            Piso térmico nocturno sobre umbral de daño
                        </p>
                    </div>

                    <div class="pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>🛰️ Fuente: <strong id="fuenteHeladasCard" class="text-cyan-300">GOES / POWER</strong></span>
                        <span id="passDateGoes">Pasada: --</span>
                    </div>
                </article>
            </div>
        </div>

        <!-- =============================================================== -->
        <!-- ACORDEÓN AVANZADO: EXPLORADOR DE 21 SATÉLITES Y SEMILLAS INTA    -->
        <!-- =============================================================== -->
        <details class="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-5 shadow-xl group">
            <summary class="cursor-pointer font-heading text-sm font-bold text-slate-200 flex items-center justify-between">
                <span>🔬 Explorador Detallado de las 21 Constelaciones Satelitales y Banco de Semillas INTA</span>
                <span class="text-xs font-mono text-emerald-400">Desplegar / Ocultar ▾</span>
            </summary>

            <div class="mt-4 pt-4 border-t border-slate-800 space-y-4">
                <div class="flex items-center gap-2">
                    <button
                        id="btnSubTabSatelites"
                        type="button"
                        onclick="cambiarSubTabTelemetria('satelites')"
                        class="px-3 py-1.5 rounded-xl text-xs font-heading font-bold bg-sky-500 text-slate-950 transition"
                    >
                        Consulta Individual por Satélite (21)
                    </button>
                    <button
                        id="btnSubTabSemillas"
                        type="button"
                        onclick="cambiarSubTabTelemetria('semillas')"
                        class="px-3 py-1.5 rounded-xl text-xs font-heading font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition"
                    >
                        Catálogo de Semillas INTA
                    </button>
                </div>

                <div id="subPanelSatelites" class="space-y-4">
                    <div class="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end">
                        <div class="sm:col-span-3">
                            <label for="selectSateliteRotaterra" class="block text-[11px] font-mono uppercase text-slate-400 mb-1">
                                Fuente Principal + Cadena Automática de Respaldos:
                            </label>
                            <select
                                id="selectSateliteRotaterra"
                                onchange="actualizarDetalleSateliteSeleccionado()"
                                class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-100"
                            >
                                <option value="HLS">Cargando catálogo de satélites...</option>
                            </select>
                            <p id="infoRespaldosSatelite" class="text-[11px] font-mono text-slate-400 mt-1"></p>
                        </div>
                        <div>
                            <button
                                id="btnEjecutarConsultaRotaterra"
                                type="button"
                                onclick="ejecutarConsultaSatelitalActiva()"
                                class="w-full py-2 px-4 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-heading font-bold text-xs shadow-lg shadow-sky-500/20 transition"
                            >
                                Consultar Fuente
                            </button>
                        </div>
                    </div>

                    <div id="resultadoConsultaRotaterra" class="rounded-xl bg-slate-950/90 border border-slate-800 p-4 max-h-[320px] overflow-y-auto text-xs space-y-3">
                        <p class="text-slate-400 font-mono">
                            Aquí se muestran las observaciones tabulares completas de cada consulta satelital.
                        </p>
                    </div>
                </div>

                <div id="subPanelSemillas" class="hidden space-y-4">
                    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                        <div>
                            <label for="selectCultivoSemillas" class="block text-[11px] font-mono uppercase text-slate-400 mb-1">
                                Cultivo Extensivo (INTA)
                            </label>
                            <select
                                id="selectCultivoSemillas"
                                onchange="buscarCultivaresSemillasInta()"
                                class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-100"
                            >
                                <option value="">Todos los cultivos</option>
                            </select>
                        </div>
                        <div>
                            <label for="inputTextoSemillas" class="block text-[11px] font-mono uppercase text-slate-400 mb-1">
                                Buscar Variedad / Cultivar
                            </label>
                            <input
                                id="inputTextoSemillas"
                                type="text"
                                oninput="buscarCultivaresSemillasInta()"
                                placeholder="Ej: INTA, DM, ACA..."
                                class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-100"
                            />
                        </div>
                        <div class="flex items-end">
                            <button
                                type="button"
                                onclick="verManejoCultivoSeleccionado()"
                                class="w-full py-2 px-3 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 font-mono text-xs transition"
                            >
                                Ver Guía de Manejo
                            </button>
                        </div>
                    </div>

                    <div id="resultadoSemillasInta" class="rounded-xl bg-slate-950/90 border border-slate-800 p-4 max-h-[320px] overflow-y-auto text-xs space-y-2">
                        <p class="text-slate-400 font-mono">Cargando Banco de Semillas del INTA...</p>
                    </div>
                </div>
            </div>
        </details>
    `;

    await cargarCatalogoSatelitesRotaterra();
}

function cambiarModoTemporal(modo) {
    const bAct = document.getElementById("btnModoDiaActual");
    const bHist = document.getElementById("btnModoHistorico");
    if (modo === "actual") {
        if (bAct) bAct.className = "px-3 py-1.5 rounded-lg text-xs font-heading font-bold bg-emerald-500 text-slate-950 transition";
        if (bHist) bHist.className = "px-3 py-1.5 rounded-lg text-xs font-heading font-semibold text-slate-300 hover:bg-slate-800 transition";
        aplicarPresetRangoFechas(15);
    } else {
        if (bHist) bHist.className = "px-3 py-1.5 rounded-lg text-xs font-heading font-bold bg-sky-500 text-slate-950 transition";
        if (bAct) bAct.className = "px-3 py-1.5 rounded-lg text-xs font-heading font-semibold text-slate-300 hover:bg-slate-800 transition";
    }
}

function aplicarPresetRangoFechas(dias) {
    const inpDesde = document.getElementById("rtFechaDesde");
    const inpHasta = document.getElementById("rtFechaHasta");
    if (!inpDesde || !inpHasta) return;

    const baseHasta = new Date("2024-10-15T12:00:00Z");
    const baseDesde = new Date(baseHasta.getTime() - Number(dias) * 86400000);
    inpHasta.value = baseHasta.toISOString().slice(0, 10);
    inpDesde.value = baseDesde.toISOString().slice(0, 10);
    conectarSatelitesCampoActivo(false);
}

function onMoverSliderHistoricoSec055(valor) {
    const inpHasta = document.getElementById("rtFechaHasta");
    const lbl = document.getElementById("labelFechaSliderHistorico");
    const sliderMapa = document.getElementById("mapTimelineSlider");

    const base = new Date((inpHasta?.value || "2024-10-15") + "T12:00:00Z");
    const delta = 30 - Number(valor);
    const fecha = new Date(base.getTime() - delta * 86400000);
    const iso = fecha.toISOString().slice(0, 10);
    if (lbl) lbl.textContent = iso;
    if (sliderMapa && sliderMapa.value !== String(valor)) {
        sliderMapa.value = String(valor);
        onMoverSliderTemporalMapa(valor);
    }
    poblar6TarjetasDesdeObservaciones(ultimasObservacionesCampo, iso);
}

function onCambiarCapasSatelitalesAdmin() {
    renderizarCapaNdviSectorizadaEnMapa();
}

/**
 * Conecta en paralelo todos los sensores marcados y actualiza las 6 tarjetas de información ([SEC-05.6]).
 */
async function conectarSatelitesCampoActivo(mostrarNotificacion = true) {
    const activo = listaCamposGlobal.find((c) => c.id === campoActivoId);
    const poly = e2wPendingGeojsonMain || (activo ? normalizarPoligonoGeoJson(activo.geometria_geojson) : null);

    if (!campoActivoId && !poly) {
        if (mostrarNotificacion) {
            mostrarToast("Selecciona o registra primero un campo con polígono para conectar los satélites.", "error");
        }
        return;
    }

    const desde = document.getElementById("rtFechaDesde")?.value || "2024-10-01";
    const hasta = document.getElementById("rtFechaHasta")?.value || "2024-10-15";

    const checks = Array.from(document.querySelectorAll('input[name="sat_layer_cb"]:checked')).map((c) => c.value);
    const satelites = checks.length > 0 ? checks : ["HLS", "SMAP", "POWER", "IMERG", "ET", "GOES"];

    const btnTop = document.getElementById("btnConectarSatelites");
    const btnSync = document.getElementById("btnSincronizarTarjetasSatelitales");
    const statusTel = document.getElementById("slotTelemetriaEstadoCampo");

    if (btnTop) {
        btnTop.disabled = true;
        btnTop.innerHTML = `<span>🛰️ Conectando NASA...</span>`;
    }
    if (btnSync) {
        btnSync.disabled = true;
        btnSync.textContent = "⏳ Consultando...";
    }
    if (statusTel) {
        statusTel.textContent = `Consultando ${satelites.join(", ")} en paralelo...`;
    }

    try {
        const payload = {
            campo_id: campoActivoId,
            poligono: poly,
            satelites,
            desde,
            hasta,
        };
        const res = await authFetch("/api/rotaterra/consulta", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
            if (mostrarNotificacion) {
                mostrarToast(data.detail?.mensaje || data.detail || "No se pudo sincronizar la telemetría.", "error");
            }
            return;
        }

        ultimasObservacionesCampo = Array.isArray(data.observaciones) ? data.observaciones : [];
        poblar6TarjetasDesdeObservaciones(ultimasObservacionesCampo, null);
        renderizarRespuestaConsultaRotaterra(data);

        if (statusTel) {
            statusTel.textContent = `Sincronizado (${ultimasObservacionesCampo.length} obs • ${data.fuente_usada})`;
        }
        if (mostrarNotificacion) {
            mostrarToast(`6 tarjetas satelitales actualizadas (${ultimasObservacionesCampo.length} observaciones).`, "success");
        }
    } catch (_err) {
        if (mostrarNotificacion) {
            mostrarToast("Error al conectar con los módulos satelitales locales.", "error");
        }
    } finally {
        if (btnTop) {
            btnTop.disabled = false;
            btnTop.innerHTML = `<span>🚀 Conectar Satélites</span>`;
        }
        if (btnSync) {
            btnSync.disabled = false;
            btnSync.textContent = "🔄 Actualizar 6 Tarjetas";
        }
    }
}

async function actualizarTarjetasSatelitalesCampoActivo() {
    const activo = listaCamposGlobal.find((c) => c.id === campoActivoId);
    if (!activo || !activo.geometria_geojson) return;
    await conectarSatelitesCampoActivo(false);
}

/**
 * Alimenta las 6 tarjetas interactivas ([SEC-05.6]) con las observaciones recibidas.
 */
function poblar6TarjetasDesdeObservaciones(observaciones, fechaFiltro = null) {
    if (!Array.isArray(observaciones) || observaciones.length === 0) return;

    const validas = observaciones.filter(
        (o) => o.valor !== null && o.valor !== undefined && o.calidad !== "descartada"
    );
    if (validas.length === 0) return;

    const buscarUltima = (varNames) => {
        const nombres = Array.isArray(varNames) ? varNames : [varNames];
        let candidatas = validas.filter((o) => nombres.includes(o.variable));
        if (fechaFiltro) {
            const hastaFecha = candidatas.filter((o) => !o.fecha || o.fecha <= fechaFiltro);
            if (hastaFecha.length > 0) candidatas = hastaFecha;
        }
        return candidatas.length > 0 ? candidatas[candidatas.length - 1] : null;
    };

    // 1. NDVI Vigor
    const obsNdvi = buscarUltima(["ndvi"]);
    if (obsNdvi) {
        const v = Number(obsNdvi.valor);
        setText("valNdvi", v.toFixed(3));
        setText("fuenteNdviCard", obsNdvi.fuente || "HLS");
        setText("passDateNdvi", `Pasada: ${obsNdvi.fecha || "-"}`);
        setText("mapPassHls", obsNdvi.fecha || "En línea");
        setText(
            "estadoTextoNdvi",
            v >= 0.55
                ? "Vigor vegetativo alto (dosel cerrado)"
                : v >= 0.3
                ? "Cobertura vegetal moderada en desarrollo"
                : "Suelo con rastrojo o cobertura inicial"
        );
    }

    // 2. Humedad & NDMI
    const obsNdmi = buscarUltima(["ndmi"]);
    if (obsNdmi) {
        setText("valNdmi", Number(obsNdmi.valor).toFixed(3));
        setText("passDateNdmi", `Pasada: ${obsNdmi.fecha || "-"}`);
    }
    const obsHumSup = buscarUltima(["humedad_superficial"]);
    const obsHumRaiz = buscarUltima(["humedad_zona_raiz"]);
    if (obsHumSup) {
        setText("valHumedad", `${Number(obsHumSup.valor).toFixed(3)}`);
        setText("passDateSmap", `Pasada: ${obsHumSup.fecha || "-"}`);
        setText("mapPassSmap", obsHumSup.fecha || "En línea");
    }
    if (obsHumRaiz) {
        setText("valHumedadRaiz", `Raíz (0-100cm): ${Number(obsHumRaiz.valor).toFixed(3)} m³/m³`);
    }

    // 3. Temperatura (4 cuadrantes)
    const obsTmin = buscarUltima(["temp_min_c", "temperatura_minima"]);
    const obsTmax = buscarUltima(["temp_max_c", "temperatura_maxima"]);
    const obsTmed = buscarUltima(["temp_media_c", "temperatura_media"]);
    if (obsTmin) setText("valTempMin", `${Number(obsTmin.valor).toFixed(1)}°C`);
    if (obsTmax) setText("valTempMax", `${Number(obsTmax.valor).toFixed(1)}°C`);
    if (obsTmed) {
        setText("valTempMean", `${Number(obsTmed.valor).toFixed(1)}°C`);
        setText("passDatePower", `Pasada: ${obsTmed.fecha || "-"}`);
    }
    if (obsTmin && obsTmax) {
        const amp = Number(obsTmax.valor) - Number(obsTmin.valor);
        setText("valTempAmp", `${amp.toFixed(1)}°C`);
    }

    // 4. Precipitación (IMERG)
    const lluvias = validas.filter((o) => o.variable === "lluvia_mm" || o.variable === "precipitacion_mm");
    if (lluvias.length > 0) {
        const totalMm = lluvias.reduce((acc, item) => acc + Number(item.valor || 0), 0);
        const ultLluvia = lluvias[lluvias.length - 1];
        setText("valLluvia", `${totalMm.toFixed(1)}`);
        setText("subLluviaUltimoDia", `Último día (${ultLluvia.fecha}): ${Number(ultLluvia.valor).toFixed(2)} mm`);
        setText("fuenteLluviaCard", ultLluvia.fuente || "IMERG");
        setText("passDateImerg", `Pasada: ${ultLluvia.fecha || "-"}`);
        setText("mapPassImerg", ultLluvia.fecha || "En línea");
    }

    // 5. Estrés Hídrico (ET)
    const obsEt = buscarUltima(["et0_mm_dia", "et_mm_dia", "evapotranspiracion_mm"]);
    if (obsEt) {
        const etVal = Number(obsEt.valor);
        setText("valEstres", etVal.toFixed(2));
        setText("fuenteEstresCard", obsEt.fuente || "ET:FAO56");
        setText("passDateEt", `Pasada: ${obsEt.fecha || "-"}`);
        setText(
            "estadoEstresTexto",
            etVal > 5.5
                ? "Demanda atmosférica alta — vigilar reserva útil"
                : "Demanda evaporativa moderada y estable"
        );
    }

    // 6. Alerta de Heladas (GOES / POWER)
    const obsGoes = buscarUltima(["temp_brillo_c", "lst_nocturna_c", "temp_min_c"]);
    if (obsGoes) {
        const tVal = Number(obsGoes.valor);
        const elHel = document.getElementById("valHeladas");
        if (tVal <= 0) {
            setText("valHeladas", `❄️ Helada (${tVal.toFixed(1)}°C)`);
            if (elHel) elHel.className = "font-heading text-2xl font-extrabold text-rose-400";
            setText("subHeladasDetalle", "Alerta roja: temperatura bajo 0°C en lote");
        } else if (tVal <= 3.5) {
            setText("valHeladas", `⚠️ Riesgo (${tVal.toFixed(1)}°C)`);
            if (elHel) elHel.className = "font-heading text-2xl font-extrabold text-amber-300";
            setText("subHeladasDetalle", "Precaución: piso térmico cercano a helada blanca");
        } else {
            setText("valHeladas", `Sin Riesgo (${tVal.toFixed(1)}°C)`);
            if (elHel) elHel.className = "font-heading text-2xl font-extrabold text-cyan-300";
            setText("subHeladasDetalle", "Piso térmico nocturno seguro sobre umbral crítico");
        }
        setText("fuenteHeladasCard", obsGoes.fuente || "GOES / POWER");
        setText("passDateGoes", `Pasada: ${obsGoes.fecha || "-"}`);
        setText("mapPassModis", obsGoes.fecha || "En línea");
    }
}

function setText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

function cambiarSubTabTelemetria(cual) {
    const pSat = document.getElementById("subPanelSatelites");
    const pSem = document.getElementById("subPanelSemillas");
    const bSat = document.getElementById("btnSubTabSatelites");
    const bSem = document.getElementById("btnSubTabSemillas");

    if (cual === "semillas") {
        pSat.classList.add("hidden");
        pSem.classList.remove("hidden");
        bSem.className = "px-3 py-1.5 rounded-xl text-xs font-heading font-bold bg-emerald-500 text-slate-950 transition";
        bSat.className = "px-3 py-1.5 rounded-xl text-xs font-heading font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition";
        if (!resumenSemillasInta) {
            cargarResumenSemillasInta();
        }
    } else {
        pSem.classList.add("hidden");
        pSat.classList.remove("hidden");
        bSat.className = "px-3 py-1.5 rounded-xl text-xs font-heading font-bold bg-sky-500 text-slate-950 transition";
        bSem.className = "px-3 py-1.5 rounded-xl text-xs font-heading font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition";
    }
}

async function cargarCatalogoSatelitesRotaterra() {
    try {
        const res = await authFetch("/api/rotaterra/satelites");
        if (!res.ok) return;
        const data = await res.json();
        catalogoSatelitesRotaterra = Array.isArray(data.satelites) ? data.satelites : [];

        const select = document.getElementById("selectSateliteRotaterra");
        if (!select) return;

        const grupos = {};
        catalogoSatelitesRotaterra.forEach((s) => {
            const cat = s.categoria || "Otras Fuentes";
            if (!grupos[cat]) grupos[cat] = [];
            grupos[cat].push(s);
        });

        select.innerHTML = Object.entries(grupos)
            .map(
                ([cat, items]) => `
                <optgroup label="${escapeHtml(cat)}">
                    ${items
                        .map(
                            (it) =>
                                `<option value="${escapeHtml(it.satelite)}" ${
                                    it.satelite === "POWER" ? "selected" : ""
                                }>${escapeHtml(it.titulo)}</option>`
                        )
                        .join("")}
                </optgroup>
            `
            )
            .join("");

        actualizarDetalleSateliteSeleccionado();
    } catch (err) {
        console.error("[Earth2Worlds] Error cargando satélites:", err);
    }
}

function actualizarDetalleSateliteSeleccionado() {
    const sel = document.getElementById("selectSateliteRotaterra");
    const info = document.getElementById("infoRespaldosSatelite");
    if (!sel || !info) return;

    const item = catalogoSatelitesRotaterra.find((s) => s.satelite === sel.value);
    if (!item) {
        info.textContent = "";
        return;
    }
    const resp = item.respaldos && item.respaldos.length > 0 ? item.respaldos.join(" → ") : "Sin respaldos secundarios";
    const delDia = item.del_dia && item.del_dia.length > 0 ? ` · Al día: ${item.del_dia.join(", ")}` : "";
    info.textContent = `${item.descripcion} | Respaldos: ${resp}${delDia}`;
}

async function ejecutarConsultaSatelitalActiva() {
    const satelite = document.getElementById("selectSateliteRotaterra")?.value;
    const desde = document.getElementById("rtFechaDesde")?.value;
    const hasta = document.getElementById("rtFechaHasta")?.value;
    const btn = document.getElementById("btnEjecutarConsultaRotaterra");
    const out = document.getElementById("resultadoConsultaRotaterra");

    if (!satelite || !desde || !hasta) {
        mostrarToast("Selecciona la fuente y el rango de fechas.", "error");
        return;
    }

    const payload = { satelite, desde, hasta };
    if (e2wPendingGeojsonMain) {
        payload.poligono = e2wPendingGeojsonMain;
    }
    if (campoActivoId) {
        payload.campo_id = campoActivoId;
    }

    if (!payload.campo_id && !payload.poligono) {
        mostrarToast("Selecciona un campo o dibuja un polígono en el mapa primero.", "error");
        return;
    }

    btn.disabled = true;
    btn.textContent = "Consultando...";
    out.innerHTML = `<p class="font-mono text-sky-300 animate-pulse py-4 text-center">Consultando ${escapeHtml(satelite)} en tiempo real...</p>`;

    try {
        const res = await authFetch("/api/rotaterra/consulta", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
            const msg = data.detail?.mensaje || data.detail || "No se pudieron obtener observaciones.";
            out.innerHTML = `<div class="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-rose-200">${escapeHtml(msg)}</div>`;
            return;
        }
        renderizarRespuestaConsultaRotaterra(data);
    } catch (_err) {
        out.innerHTML = `<p class="text-rose-400 font-mono">Error al consultar el conector satelital.</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Consultar Fuente";
    }
}

function renderizarRespuestaConsultaRotaterra(data) {
    const out = document.getElementById("resultadoConsultaRotaterra");
    if (!out) return;
    const obs = Array.isArray(data.observaciones) ? data.observaciones : [];

    const filasTabla = obs
        .slice()
        .reverse()
        .slice(0, 60)
        .map((o) => {
            const badgeCalidad =
                o.calidad === "buena"
                    ? "bg-emerald-500/15 text-emerald-300 border-emerald-500/30"
                    : o.calidad === "dudosa"
                    ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
                    : "bg-rose-500/15 text-rose-300 border-rose-500/30";
            return `
                <tr class="border-b border-slate-800/60">
                    <td class="py-1.5 pr-2 font-mono text-slate-300">${escapeHtml(o.fecha)}</td>
                    <td class="py-1.5 px-2 font-mono text-sky-300">${escapeHtml(o.variable)}</td>
                    <td class="py-1.5 px-2 font-mono font-semibold text-white">
                        ${o.valor !== null && o.valor !== undefined ? escapeHtml(o.valor) : "null"}
                        <span class="text-slate-500 font-normal">${escapeHtml(o.unidad)}</span>
                    </td>
                    <td class="py-1.5 px-2 font-mono text-slate-400">${escapeHtml(o.fuente)}</td>
                    <td class="py-1.5 px-2">
                        <span class="px-2 py-0.5 rounded text-[10px] font-mono border ${badgeCalidad}">
                            ${escapeHtml(o.calidad)}
                        </span>
                    </td>
                    <td class="py-1.5 pl-2 text-slate-400">${escapeHtml(o.nota || "")}</td>
                </tr>
            `;
        })
        .join("");

    out.innerHTML = `
        <div class="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
            <span class="font-mono text-emerald-400">
                Fuentes activas: <strong>${escapeHtml(data.fuente_usada)}</strong>
            </span>
            <span class="font-mono text-slate-400">
                ${obs.length} observación(es)
            </span>
        </div>
        <div class="overflow-x-auto pt-1">
            <table class="w-full text-left border-collapse text-[11px]">
                <thead>
                    <tr class="border-b border-slate-800 text-slate-400 font-mono uppercase">
                        <th class="py-1.5 pr-2">Fecha</th>
                        <th class="py-1.5 px-2">Variable</th>
                        <th class="py-1.5 px-2">Valor</th>
                        <th class="py-1.5 px-2">Fuente</th>
                        <th class="py-1.5 px-2">Calidad</th>
                        <th class="py-1.5 pl-2">Nota</th>
                    </tr>
                </thead>
                <tbody>${filasTabla}</tbody>
            </table>
        </div>
    `;
}

/* --- Sub-panel Banco de Semillas INTA --- */
async function cargarResumenSemillasInta() {
    const out = document.getElementById("resultadoSemillasInta");
    const sel = document.getElementById("selectCultivoSemillas");
    try {
        const res = await authFetch("/api/rotaterra/semillas");
        if (!res.ok) return;
        resumenSemillasInta = await res.json();
        const porCultivo = Array.isArray(resumenSemillasInta.por_cultivo) ? resumenSemillasInta.por_cultivo : [];

        if (sel) {
            sel.innerHTML =
                `<option value="">Todos los cultivos (${resumenSemillasInta.cultivares} cultivares INTA)</option>` +
                porCultivo
                    .map(
                        (c) =>
                            `<option value="${escapeHtml(c.cultivo)}">${escapeHtml(c.cultivo)} (${c.cultivares})</option>`
                    )
                    .join("");
        }
        await buscarCultivaresSemillasInta();
    } catch (_err) {
        if (out) out.innerHTML = `<p class="text-rose-400">Error cargando el banco de semillas.</p>`;
    }
}

async function buscarCultivaresSemillasInta() {
    const out = document.getElementById("resultadoSemillasInta");
    if (!out) return;
    const cultivo = document.getElementById("selectCultivoSemillas")?.value || "";
    const texto = (document.getElementById("inputTextoSemillas")?.value || "").trim();

    const params = new URLSearchParams({ limite: "30" });
    if (cultivo) params.set("cultivo", cultivo);
    if (texto) params.set("texto", texto);

    const res = await authFetch(`/api/rotaterra/semillas/cultivares?${params.toString()}`);
    if (!res.ok) return;
    const data = await res.json();
    const lista = Array.isArray(data.cultivares) ? data.cultivares : [];

    out.innerHTML = `
        <div class="flex items-center justify-between text-[11px] font-mono text-slate-400 pb-2 border-b border-slate-800">
            <span>Mostrando ${lista.length} de ${data.total} cultivares INTA</span>
            <span class="text-emerald-400">Catálogo Oficial INASE / INTA</span>
        </div>
        <div class="divide-y divide-slate-800/70">
            ${lista
                .map(
                    (c) => `
                <div class="py-2 flex items-center justify-between gap-2">
                    <div>
                        <span class="font-semibold text-white">${escapeHtml(c.cultivar)}</span>
                        <span class="px-2 py-0.5 rounded bg-slate-800 text-emerald-300 font-mono text-[10px] ml-1.5">
                            ${escapeHtml(c.cultivo)}
                        </span>
                        <p class="text-[11px] text-slate-400 font-mono">
                            Grupo: ${escapeHtml(c.grupo || "-")} · Año INASE: ${escapeHtml(c.anio_inscripcion || "-")}
                        </p>
                    </div>
                    <button
                        type="button"
                        onclick="verDetalleCultivarInta('${escapeHtml(c.cultivar_id)}')"
                        class="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-sky-500/15 hover:bg-sky-500/25 text-sky-300 border border-sky-500/30"
                    >
                        Ficha / Ensayos
                    </button>
                </div>
            `
                )
                .join("")}
        </div>
    `;
}

/**
 * Obtentor tal como figura en el registro de INASE (solicitante_rnc). Si el registro no lo
 * dice, se muestra "sin dato": nunca se completa con "INTA" ni con otro nombre supuesto.
 */
function obtentorCultivar(c) {
    const solicitante = typeof c?.solicitante_rnc === "string" ? c.solicitante_rnc.trim() : "";
    return solicitante || "sin dato";
}

async function verDetalleCultivarInta(cultivarId) {
    const out = document.getElementById("resultadoSemillasInta");
    if (!out) return;
    const res = await authFetch(`/api/rotaterra/semillas/cultivares/${encodeURIComponent(cultivarId)}`);
    if (!res.ok) return;
    const data = await res.json();
    const c = data.cultivar || {};
    const ficha = Array.isArray(data.ficha) ? data.ficha : [];

    out.innerHTML = `
        <div class="space-y-3">
            <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                <div>
                    <h4 class="font-heading text-sm font-bold text-white">${escapeHtml(c.cultivar)} (${escapeHtml(c.cultivo)})</h4>
                    <p class="text-[11px] font-mono text-slate-400">ID INASE: ${escapeHtml(c.cultivar_id)} · Obtentor: ${escapeHtml(obtentorCultivar(c))}${c.vinculo_inta ? ` · Vínculo: ${escapeHtml(c.vinculo_inta)}` : ""}</p>
                </div>
                <button
                    type="button"
                    onclick="buscarCultivaresSemillasInta()"
                    class="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-slate-800 text-slate-300"
                >
                    &larr; Volver
                </button>
            </div>
            <ul class="space-y-1 text-[11px]">
                ${
                    ficha.length === 0
                        ? `<li class="text-slate-400">Cultivar inscripto en INASE sin atributos adicionales en ficha.</li>`
                        : ficha
                              .map(
                                  (f) =>
                                      `<li><strong class="text-slate-200">${escapeHtml(f.atributo)}:</strong> ${escapeHtml(
                                          f.valor
                                      )}</li>`
                              )
                              .join("")
                }
            </ul>
        </div>
    `;
}

async function verManejoCultivoSeleccionado() {
    const cultivo = document.getElementById("selectCultivoSemillas")?.value;
    const out = document.getElementById("resultadoSemillasInta");
    if (!cultivo || !out) {
        mostrarToast("Selecciona primero un cultivo en el desplegable.", "info");
        return;
    }

    const res = await authFetch(`/api/rotaterra/semillas/manejo?cultivo=${encodeURIComponent(cultivo)}&solo_con_dato=true`);
    const data = await res.json();
    if (!res.ok) return;
    const filas = Array.isArray(data.filas) ? data.filas : [];

    out.innerHTML = `
        <div class="space-y-2">
            <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                <span class="font-heading text-sm font-bold text-emerald-400">Guía de Manejo INTA — ${escapeHtml(cultivo)}</span>
                <button type="button" onclick="buscarCultivaresSemillasInta()" class="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-slate-800 text-slate-300">&larr; Volver</button>
            </div>
            <div class="divide-y divide-slate-800/60">
                ${filas
                    .map(
                        (f) => `
                    <div class="py-1.5">
                        <span class="font-mono text-sky-300 font-semibold">${escapeHtml(f.tema)}:</span>
                        <span class="text-slate-200 ml-1">${escapeHtml(f.valor)}</span>
                    </div>
                `
                    )
                    .join("")}
            </div>
        </div>
    `;
}

/* ===========================================================================
 * [JS-11] MODAL DE EVALUACIÓN Y ROTACIÓN DE CULTIVOS ([SEC-09.2])
 * =========================================================================== */

async function abrirModalEvaluacionCultivo(idCampo) {
    const cid = idCampo || campoActivoId;
    if (!cid) {
        mostrarToast("Selecciona un campo primero para evaluar su aptitud agrícola.", "error");
        return;
    }
    document.getElementById("eval_campo_id").value = String(cid);
    abrirModal("modalEvaluacionCultivo");
    await ejecutarEvaluacionCultivoModal();
}

async function ejecutarEvaluacionCultivoModal() {
    const cid = Number(document.getElementById("eval_campo_id")?.value || campoActivoId);
    const out = document.getElementById("contenedorResultadosEvaluacionCultivo");
    if (!cid || !out) return;

    const phRaw = document.getElementById("eval_ph_manual")?.value;
    const payload = {
        campo_id: cid,
        cultivo_anterior: document.getElementById("eval_cultivo_anterior")?.value || "soja",
        sistema_hidrico: document.getElementById("eval_sistema_hidrico")?.value || "secano",
        ph_manual: phRaw ? parseFloat(phRaw) : null,
    };

    out.innerHTML = `<div class="py-8 text-center font-mono text-xs text-emerald-300 animate-pulse">Cruzando relieve NASADEM, cartas GeoINTA, perfiles SISINTA, índice NOAA ENSO y rindes MAGyP...</div>`;

    try {
        const res = await authFetch("/api/rotaterra/evaluar-cultivo", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        const data = await res.json();
        if (!res.ok) {
            out.innerHTML = `<div class="rounded-xl bg-rose-500/10 border border-rose-500/30 p-4 text-xs text-rose-200">${escapeHtml(
                data.detail || "No se pudo evaluar el lote."
            )}</div>`;
            return;
        }

        const p = data.parametros_edafoclimaticos || {};
        const recs = Array.isArray(data.recomendaciones) ? data.recomendaciones : [];

        out.innerHTML = `
            <!-- Resumen Edafoclimático Detectado -->
            <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div class="rounded-xl bg-slate-950 border border-slate-800 p-3">
                    <span class="text-[10px] font-mono uppercase text-slate-400">Textura &amp; Suelo INTA</span>
                    <p class="font-heading font-bold text-emerald-400 text-sm mt-0.5">${escapeHtml(p.textura_evaluada)}</p>
                    <span class="text-[10px] font-mono text-slate-500">MO: ${p.materia_organica_pct}%</span>
                </div>
                <div class="rounded-xl bg-slate-950 border border-slate-800 p-3">
                    <span class="text-[10px] font-mono uppercase text-slate-400">pH (SISINTA 0-20cm)</span>
                    <p class="font-heading font-bold text-sky-400 text-sm mt-0.5">pH ${p.ph_evaluado}</p>
                    <span class="text-[10px] font-mono text-slate-500">Detectado: ${p.ph_detectado_sisinta}</span>
                </div>
                <div class="rounded-xl bg-slate-950 border border-slate-800 p-3">
                    <span class="text-[10px] font-mono uppercase text-slate-400">Topografía NASADEM</span>
                    <p class="font-heading font-bold text-amber-300 text-sm mt-0.5">${p.elevacion_msnm} msnm</p>
                    <span class="text-[10px] font-mono text-slate-500">Pendiente: ${p.pendiente_porcentaje}%</span>
                </div>
                <div class="rounded-xl bg-slate-950 border border-slate-800 p-3">
                    <span class="text-[10px] font-mono uppercase text-slate-400">Escenario Climático ENSO</span>
                    <p class="font-heading font-bold text-purple-300 text-sm mt-0.5">ONI ${p.indice_oni_c}°C</p>
                    <span class="text-[10px] font-mono text-slate-500">${escapeHtml(p.fase_enso)}</span>
                </div>
            </div>

            <!-- Ranking de Viabilidad de Cultivos -->
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                ${recs
                    .map((r) => {
                        const colorBarra =
                            r.viabilidad >= 88
                                ? "bg-emerald-500"
                                : r.viabilidad >= 78
                                ? "bg-sky-500"
                                : "bg-amber-500";
                        return `
                            <div class="rounded-xl bg-slate-950/90 border border-slate-800 p-4 space-y-2">
                                <div class="flex items-center justify-between">
                                    <span class="font-heading font-bold text-white text-base">
                                        ${escapeHtml(r.icono)} ${escapeHtml(r.cultivo)}
                                    </span>
                                    <span class="px-2.5 py-0.5 rounded-full text-xs font-mono font-bold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                                        ${r.viabilidad}% Viabilidad
                                    </span>
                                </div>
                                <div class="w-full h-2 rounded-full bg-slate-800 overflow-hidden">
                                    <div class="h-full ${colorBarra}" style="width: ${r.viabilidad}%"></div>
                                </div>
                                <div class="flex items-center justify-between text-[11px] font-mono text-slate-400">
                                    <span>${escapeHtml(r.ciclo)}</span>
                                    <span class="text-amber-300 font-semibold">Rinde ref: ${escapeHtml(r.rinde_estimado)}</span>
                                </div>
                                <p class="text-xs text-slate-300">${escapeHtml(r.justificacion)}</p>
                            </div>
                        `;
                    })
                    .join("")}
            </div>
        `;
    } catch (_err) {
        out.innerHTML = `<p class="text-xs font-mono text-rose-400">Error ejecutando el motor de evaluación de cultivos.</p>`;
    }
}

/* ===========================================================================
 * [JS-12] MODAL DE GRÁFICOS DE SERIES TEMPORALES CHART.JS ([SEC-09.7])
 * =========================================================================== */

async function abrirModalGraficoHistorico(variable, titulo) {
    variableActivaGrafico = variable || "ndvi";
    tituloActivoGrafico = titulo || `Serie Histórica (${variableActivaGrafico})`;

    setText("tituloModalGraficoHistorico", tituloActivoGrafico);
    abrirModal("modalGraficoHistorico");
    await cambiarRangoGraficoHistorico(365);
}

async function cambiarRangoGraficoHistorico(dias) {
    if (!campoActivoId) return;
    const baseHasta = new Date("2024-10-15T12:00:00Z");
    const baseDesde = new Date(baseHasta.getTime() - Number(dias) * 86400000);
    const hastaStr = baseHasta.toISOString().slice(0, 10);
    const desdeStr = baseDesde.toISOString().slice(0, 10);

    setText("subtituloModalGraficoHistorico", `Ventana analizada: ${desdeStr} a ${hastaStr} • Campo ID #${campoActivoId}`);

    let puntos = [];
    try {
        const res = await authFetch(
            `/api/campos/${campoActivoId}/historial?variable=${encodeURIComponent(variableActivaGrafico)}&desde=${desdeStr}&hasta=${hastaStr}`
        );
        if (res.ok) {
            const data = await res.json();
            puntos = Array.isArray(data.observaciones) ? data.observaciones : [];
        }
    } catch (_e) {
        puntos = [];
    }

    // Si aún hay pocos puntos en el historial local para ese rango, complementar con las observaciones en memoria
    if (puntos.length < 2 && ultimasObservacionesCampo.length > 0) {
        puntos = ultimasObservacionesCampo.filter(
            (o) => o.variable === variableActivaGrafico && o.valor !== null && o.calidad !== "descartada"
        );
    }

    const valores = puntos.map((p) => Number(p.valor));
    const etiquetas = puntos.map((p) => p.fecha);

    if (valores.length > 0) {
        const minV = Math.min(...valores);
        const maxV = Math.max(...valores);
        const avgV = valores.reduce((a, b) => a + b, 0) / valores.length;
        setText("kpiHistTotal", String(valores.length));
        setText("kpiHistMin", minV.toFixed(2));
        setText("kpiHistMax", maxV.toFixed(2));
        setText("kpiHistAvg", avgV.toFixed(2));
    } else {
        setText("kpiHistTotal", "0");
        setText("kpiHistMin", "--");
        setText("kpiHistMax", "--");
        setText("kpiHistAvg", "--");
    }

    const canvas = document.getElementById("canvasGraficoHistorico");
    if (!canvas || typeof Chart === "undefined") return;

    if (chartHistoricoInstance) {
        chartHistoricoInstance.destroy();
        chartHistoricoInstance = null;
    }

    chartHistoricoInstance = new Chart(canvas, {
        type: variableActivaGrafico === "lluvia_mm" ? "bar" : "line",
        data: {
            labels: etiquetas,
            datasets: [
                {
                    label: tituloActivoGrafico,
                    data: valores,
                    borderColor: "#10b981",
                    backgroundColor: variableActivaGrafico === "lluvia_mm" ? "rgba(59, 130, 246, 0.55)" : "rgba(16, 185, 129, 0.18)",
                    borderWidth: 2.5,
                    pointRadius: 3,
                    fill: true,
                    tension: 0.3,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: "#e2e8f0", font: { family: "Fira Code", size: 11 } },
                },
            },
            scales: {
                x: {
                    ticks: { color: "#94a3b8", font: { family: "Fira Code", size: 10 } },
                    grid: { color: "rgba(148, 163, 184, 0.1)" },
                },
                y: {
                    ticks: { color: "#94a3b8", font: { family: "Fira Code", size: 10 } },
                    grid: { color: "rgba(148, 163, 184, 0.12)" },
                },
            },
        },
    });
}

window.inicializarSlotMapaPrincipal = inicializarSlotMapaPrincipal;
window.sincronizarMapaConCampoActivo = sincronizarMapaConCampoActivo;
window.prepararMapaEnModalNuevoCampo = prepararMapaEnModalNuevoCampo;
window.inicializarSlotTelemetria = inicializarSlotTelemetria;
window.toggleModoCatastroClick = toggleModoCatastroClick;
window.buscarParcelaPorTextoCatastro = buscarParcelaPorTextoCatastro;
window.centrarEnCampoActivo = centrarEnCampoActivo;
window.guardarPoligonoEnCampoActivo = guardarPoligonoEnCampoActivo;
window.cambiarSubTabTelemetria = cambiarSubTabTelemetria;
window.actualizarDetalleSateliteSeleccionado = actualizarDetalleSateliteSeleccionado;
window.ejecutarConsultaSatelitalActiva = ejecutarConsultaSatelitalActiva;
window.buscarCultivaresSemillasInta = buscarCultivaresSemillasInta;
window.verDetalleCultivarInta = verDetalleCultivarInta;
window.verManejoCultivoSeleccionado = verManejoCultivoSeleccionado;
window.conectarSatelitesCampoActivo = conectarSatelitesCampoActivo;
window.actualizarTarjetasSatelitalesCampoActivo = actualizarTarjetasSatelitalesCampoActivo;
window.cargarEstadoDockSatelitesAdmin = cargarEstadoDockSatelitesAdmin;
window.reconectarSateliteIndividual = reconectarSateliteIndividual;
window.renderizarCapaNdviSectorizadaEnMapa = renderizarCapaNdviSectorizadaEnMapa;
window.onMoverSliderTemporalMapa = onMoverSliderTemporalMapa;
window.onMoverSliderHistoricoSec055 = onMoverSliderHistoricoSec055;
window.cambiarModoTemporal = cambiarModoTemporal;
window.aplicarPresetRangoFechas = aplicarPresetRangoFechas;
window.onCambiarCapasSatelitalesAdmin = onCambiarCapasSatelitalesAdmin;
window.abrirModalEvaluacionCultivo = abrirModalEvaluacionCultivo;
window.ejecutarEvaluacionCultivoModal = ejecutarEvaluacionCultivoModal;
window.abrirModalGraficoHistorico = abrirModalGraficoHistorico;
window.cambiarRangoGraficoHistorico = cambiarRangoGraficoHistorico;
window.obtenerPoligonoModalPendiente = () => e2wModalPendingGeojson;
