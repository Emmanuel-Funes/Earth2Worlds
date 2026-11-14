/**
 * Earth2Worlds - Módulos Integrados de Cartografía (Leaflet + Geoman + Catastro SL)
 * y Telemetría Satelital / Banco de Semillas INTA (Rotaterra).
 *
 * Se enchufa en los contenedores:
 *   - [SEC-05.2] #slotModuloMapa
 *   - [SEC-05.3] #slotModuloTelemetria
 *   - [SEC-09.1] #slotModalMapa
 */

let e2wMainMap = null;
let e2wMainDrawnLayer = null;
let e2wOtherFieldsLayer = null;
let e2wPendingGeojsonMain = null;
let e2wPendingAreaHaMain = null;
let e2wCatastroClickActivo = false;

let e2wModalMap = null;
let e2wModalDrawnLayer = null;
let e2wModalPendingGeojson = null;

let catalogoSatelitesRotaterra = [];
let resumenSemillasInta = null;

/**
 * Calcula la superficie aproximada en hectáreas de un GeoJSON Polygon en EPSG:4326.
 * @param {object} polygonGeoJson
 * @returns {number|null}
 */
function calcularSuperficieHa(polygonGeoJson) {
    if (!polygonGeoJson || polygonGeoJson.type !== "Polygon" || !Array.isArray(polygonGeoJson.coordinates)) {
        return null;
    }
    const ring = polygonGeoJson.coordinates[0];
    if (!Array.isArray(ring) || ring.length < 4) return null;

    const R = 6378137; // Radio terrestre WGS84 en metros
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

    const puedeEditar = currentUser && (currentUser.rol === "admin" || currentUser.rol === "propietario");

    slot.innerHTML = `
        <div class="flex flex-col h-full justify-between space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
                <div>
                    <div class="flex items-center gap-2">
                        <span class="px-2.5 py-0.5 rounded-lg text-[11px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                            [SEC-05.2] VISOR GIS + CATASTRO SAN LUIS
                        </span>
                        <span id="slotMapaEstadoCampo" class="text-xs font-mono text-slate-400">
                            WGS 84 (EPSG:4326)
                        </span>
                    </div>
                    <h3 class="font-heading text-lg font-bold text-white mt-1">
                        Delimitación de Lote y Parcelas Rurales
                    </h3>
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
            <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-2 bg-slate-950/80 border border-slate-800 rounded-xl p-2.5">
                <span class="text-[11px] font-mono text-slate-400 uppercase px-1">Catastro San Luis:</span>
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
                    class="px-3 py-1.5 rounded-lg text-xs font-mono bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition"
                >
                    Centrar Lote
                </button>
            </div>

            <!-- Contenedor del mapa Leaflet -->
            <div id="e2wLeafletMainMap" class="w-full h-[380px] rounded-xl border border-slate-800 overflow-hidden z-10"></div>

            <!-- Pie informativo del polígono -->
            <div class="rounded-xl bg-slate-950/90 border border-slate-800 px-4 py-2.5 flex flex-wrap items-center justify-between gap-2 text-xs font-mono">
                <span id="infoPoligonoMapaPrincipal" class="text-slate-300">
                    Selecciona un campo o dibuja un polígono en el mapa.
                </span>
                <span id="infoAreaMapaPrincipal" class="text-emerald-400 font-semibold"></span>
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
        center: [-33.6757, -65.4578], // Villa Mercedes, San Luis
        zoom: 12,
        layers: [satLayer],
    });

    L.control.layers({ "Satélite (Esri)": satLayer, "Mapa Callejero (OSM)": osmLayer }).addTo(e2wMainMap);

    e2wOtherFieldsLayer = L.featureGroup().addTo(e2wMainMap);
    e2wMainDrawnLayer = L.featureGroup().addTo(e2wMainMap);

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
}

function sincronizarMapaConCampoActivo() {
    if (!e2wMainMap || !e2wMainDrawnLayer) return;

    e2wMainDrawnLayer.clearLayers();
    e2wOtherFieldsLayer.clearLayers();
    e2wPendingGeojsonMain = null;
    e2wPendingAreaHaMain = null;

    const btnGuardar = document.getElementById("btnGuardarPoligonoCampoActivo");
    if (btnGuardar) btnGuardar.classList.add("hidden");

    const infoEl = document.getElementById("infoPoligonoMapaPrincipal");
    const areaEl = document.getElementById("infoAreaMapaPrincipal");

    // Dibujar otros campos en gris/celeste tenue
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
            style: { color: "#10b981", weight: 3, fillColor: "#10b981", fillOpacity: 0.25 },
        });
        geoLayer.eachLayer((l) => {
            vincularEdicionCapaPrincipal(l);
            e2wMainDrawnLayer.addLayer(l);
        });
        const bounds = e2wMainDrawnLayer.getBounds();
        if (bounds.isValid()) {
            e2wMainMap.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
        }
        const ha = activo.superficie_ha ?? calcularSuperficieHa(polyActivo);
        if (infoEl) infoEl.textContent = `Polígono activo de "${activo.nombre_campo}" (#${activo.id})`;
        if (areaEl) areaEl.textContent = ha ? `${ha} ha` : "";
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
        e2wMainMap.fitBounds(bounds, { padding: [30, 30], maxZoom: 16 });
    } else {
        e2wMainMap.setView([-33.6757, -65.4578], 12);
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

    mostrarToast(`Polígono GeoJSON guardado en "${data.nombre_campo}" (${data.superficie_ha ?? "-"} ha).`, "success");
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
 * [JS-10] CONTROLADOR DE TELEMETRÍA ROTATERRA Y BANCO DE SEMILLAS INTA
 * =========================================================================== */

async function inicializarSlotTelemetria() {
    const slot = document.getElementById("slotModuloTelemetria");
    if (!slot) return;

    const hoy = new Date();
    const hace30 = new Date(hoy.getTime() - 30 * 86400000);
    const hastaStr = hoy.toISOString().slice(0, 10);
    const desdeStr = hace30.toISOString().slice(0, 10);

    slot.innerHTML = `
        <div class="flex flex-col h-full justify-between space-y-4">
            <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b border-slate-800 pb-3">
                <div>
                    <span class="px-2.5 py-0.5 rounded-lg text-[11px] font-mono bg-sky-500/15 text-sky-300 border border-sky-500/30">
                        [SEC-05.3] MOTOR ROTATERRA (NASA + INTA)
                    </span>
                    <h3 class="font-heading text-lg font-bold text-white mt-1">
                        Telemetría Satelital y Banco de Semillas INTA
                    </h3>
                </div>

                <div class="flex items-center gap-1.5">
                    <button
                        id="btnSubTabSatelites"
                        type="button"
                        onclick="cambiarSubTabTelemetria('satelites')"
                        class="px-3 py-1.5 rounded-xl text-xs font-heading font-bold bg-sky-500 text-slate-950 transition"
                    >
                        Satélites y Suelo (21)
                    </button>
                    <button
                        id="btnSubTabSemillas"
                        type="button"
                        onclick="cambiarSubTabTelemetria('semillas')"
                        class="px-3 py-1.5 rounded-xl text-xs font-heading font-semibold bg-slate-800 text-slate-300 hover:bg-slate-700 transition"
                    >
                        Semillas INTA
                    </button>
                </div>
            </div>

            <!-- SUB-PANEL 1: CONSULTA SATELITAL Y FUENTES ROTATERRA -->
            <div id="subPanelSatelites" class="space-y-4">
                <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div class="sm:col-span-3">
                        <label for="selectSateliteRotaterra" class="block text-[11px] font-mono uppercase text-slate-400 mb-1">
                            Fuente Principal + Cadena Automática de Respaldos:
                        </label>
                        <select
                            id="selectSateliteRotaterra"
                            onchange="actualizarDetalleSateliteSeleccionado()"
                            class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs text-slate-100 focus:outline-none focus:border-sky-500"
                        >
                            <option value="HLS">Cargando catálogo de satélites...</option>
                        </select>
                        <p id="infoRespaldosSatelite" class="text-[11px] font-mono text-slate-400 mt-1"></p>
                    </div>

                    <div>
                        <label for="rtFechaDesde" class="block text-[11px] font-mono uppercase text-slate-400 mb-1">
                            Desde
                        </label>
                        <input
                            id="rtFechaDesde"
                            type="date"
                            value="${desdeStr}"
                            class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs font-mono text-slate-100"
                        />
                    </div>
                    <div>
                        <label for="rtFechaHasta" class="block text-[11px] font-mono uppercase text-slate-400 mb-1">
                            Hasta
                        </label>
                        <input
                            id="rtFechaHasta"
                            type="date"
                            value="${hastaStr}"
                            class="w-full rounded-xl bg-slate-950 border border-slate-800 px-3 py-2 text-xs font-mono text-slate-100"
                        />
                    </div>
                    <div class="flex items-end">
                        <button
                            id="btnEjecutarConsultaRotaterra"
                            type="button"
                            onclick="ejecutarConsultaSatelitalActiva()"
                            class="w-full py-2 px-4 rounded-xl bg-sky-500 hover:bg-sky-400 text-slate-950 font-heading font-bold text-xs shadow-lg shadow-sky-500/20 transition"
                        >
                            Consultar Lote Activo
                        </button>
                    </div>
                </div>

                <!-- Estado y resultados de la consulta -->
                <div id="resultadoConsultaRotaterra" class="rounded-xl bg-slate-950/90 border border-slate-800 p-4 max-h-[340px] overflow-y-auto text-xs space-y-3">
                    <p id="slotTelemetriaEstadoCampo" class="text-slate-400 font-mono">
                        Selecciona un campo con polígono (o dibuja uno en el mapa) y pulsa "Consultar Lote Activo".
                    </p>
                </div>
            </div>

            <!-- SUB-PANEL 2: BANCO DE SEMILLAS INTA -->
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
                    <div class="flex items-end gap-2">
                        <button
                            type="button"
                            onclick="verManejoCultivoSeleccionado()"
                            class="w-full py-2 px-3 rounded-xl bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 font-mono text-xs transition"
                        >
                            Ver Guía de Manejo
                        </button>
                    </div>
                </div>

                <div id="resultadoSemillasInta" class="rounded-xl bg-slate-950/90 border border-slate-800 p-4 max-h-[340px] overflow-y-auto text-xs space-y-2">
                    <p class="text-slate-400 font-mono">Cargando Banco de Semillas del INTA...</p>
                </div>
            </div>
        </div>
    `;

    await cargarCatalogoSatelitesRotaterra();
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

        // Agrupar por categoría
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
        console.error("[Earth2Worlds] Error cargando satélites Rotaterra:", err);
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
    btn.textContent = "Consultando NASA / INTA...";
    out.innerHTML = `
        <div class="py-6 text-center space-y-2">
            <p class="font-mono text-sky-300 animate-pulse">
                Consultando ${escapeHtml(satelite)} y su cadena de respaldos en tiempo real...
            </p>
            <p class="text-[11px] text-slate-500">
                La petición va directo a los servidores oficiales (NASA / INTA) y puede demorar entre segundos y un par de minutos.
            </p>
        </div>
    `;

    try {
        const res = await authFetch("/api/rotaterra/consulta", {
            method: "POST",
            body: JSON.stringify(payload),
        });
        const data = await res.json();

        if (!res.ok) {
            const detalle = data.detail;
            const msg = typeof detalle === "object" && detalle !== null ? detalle.mensaje : detalle;
            const intentos = typeof detalle === "object" && detalle !== null && Array.isArray(detalle.intentos) ? detalle.intentos : [];

            out.innerHTML = `
                <div class="rounded-xl border border-rose-500/40 bg-rose-500/10 p-3 text-rose-200 space-y-2">
                    <p class="font-semibold">${escapeHtml(msg || "No se pudieron obtener observaciones.")}</p>
                    ${
                        intentos.length > 0
                            ? `<div class="text-[11px] font-mono space-y-1 pt-2 border-t border-rose-500/20">
                                ${intentos
                                    .map(
                                        (i) =>
                                            `<div>&bull; <strong>${escapeHtml(i.satelite)}</strong>: ${escapeHtml(
                                                i.resultado
                                            )} — ${escapeHtml(i.mensaje || "")}</div>`
                                    )
                                    .join("")}
                               </div>`
                            : ""
                    }
                </div>
            `;
            return;
        }

        renderizarRespuestaConsultaRotaterra(data);
    } catch (_err) {
        out.innerHTML = `<p class="text-rose-400 font-mono">Error de red al consultar el motor Rotaterra.</p>`;
    } finally {
        btn.disabled = false;
        btn.textContent = "Consultar Lote Activo";
    }
}

function renderizarRespuestaConsultaRotaterra(data) {
    const out = document.getElementById("resultadoConsultaRotaterra");
    const obs = Array.isArray(data.observaciones) ? data.observaciones : [];

    // Agrupar resumen por variable con valores numéricos válidos
    const porVariable = {};
    obs.forEach((o) => {
        if (!porVariable[o.variable]) {
            porVariable[o.variable] = {
                unidad: o.unidad,
                fuente: o.fuente,
                resolucion_m: o.resolucion_m,
                valores: [],
                ultimo: null,
                ultimaNota: o.nota || "",
            };
        }
        if (o.valor !== null && o.valor !== undefined && o.calidad !== "descartada") {
            porVariable[o.variable].valores.push(Number(o.valor));
            porVariable[o.variable].ultimo = o.valor;
            porVariable[o.variable].ultimaNota = o.nota || "";
        }
    });

    const resumenCards = Object.entries(porVariable)
        .map(([variable, info]) => {
            const vals = info.valores;
            const prom = vals.length > 0 ? (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(2) : "S/D";
            const ult = info.ultimo !== null ? info.ultimo : "S/D";
            return `
                <div class="rounded-xl bg-slate-900 border border-slate-800 p-3">
                    <div class="flex items-center justify-between text-[11px] font-mono text-slate-400">
                        <span>${escapeHtml(variable)}</span>
                        <span class="text-emerald-400">${escapeHtml(info.fuente)} (${info.resolucion_m ?? "-"}m)</span>
                    </div>
                    <p class="font-heading text-base font-bold text-white mt-1">
                        Último: ${escapeHtml(ult)} <span class="text-xs font-normal text-slate-400">${escapeHtml(info.unidad)}</span>
                    </p>
                    <p class="text-[11px] font-mono text-slate-400">
                        Promedio período: ${escapeHtml(prom)} ${escapeHtml(info.unidad)} (${vals.length} dato(s))
                    </p>
                </div>
            `;
        })
        .join("");

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
                Fuente principal usada: <strong>${escapeHtml(data.fuente_usada)}</strong>
            </span>
            <span class="font-mono text-slate-400">
                ${obs.length} observación(es) recibida(s)
            </span>
        </div>

        ${resumenCards ? `<div class="grid grid-cols-1 sm:grid-cols-2 gap-2">${resumenCards}</div>` : ""}

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
        if (!res.ok) {
            out.innerHTML = `<p class="text-rose-400">No se pudo cargar el banco de semillas INTA.</p>`;
            return;
        }
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
        out.innerHTML = `<p class="text-rose-400">Error cargando el banco de semillas.</p>`;
    }
}

async function buscarCultivaresSemillasInta() {
    const out = document.getElementById("resultadoSemillasInta");
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
            <span>Mostrando ${lista.length} de ${data.total} cultivares INTA (Corte INASE: ${escapeHtml(
        resumenSemillasInta?.fecha_corte_inase || "-"
    )})</span>
            <span class="text-emerald-400">Solo INTA</span>
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
                            ${c.ensayos ? ` · Red: ${escapeHtml(c.ensayos)}` : ""}
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

async function verDetalleCultivarInta(cultivarId) {
    const out = document.getElementById("resultadoSemillasInta");
    const res = await authFetch(`/api/rotaterra/semillas/cultivares/${encodeURIComponent(cultivarId)}`);
    if (!res.ok) return;
    const data = await res.json();
    const c = data.cultivar || {};
    const ficha = Array.isArray(data.ficha) ? data.ficha : [];
    const ensayos = data.ensayos || {};

    out.innerHTML = `
        <div class="space-y-3">
            <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                <div>
                    <h4 class="font-heading text-sm font-bold text-white">${escapeHtml(c.cultivar)} (${escapeHtml(c.cultivo)})</h4>
                    <p class="text-[11px] font-mono text-slate-400">ID INASE: ${escapeHtml(c.cultivar_id)} · Obtentor: ${escapeHtml(c.solicitante || "INTA")}</p>
                </div>
                <button
                    type="button"
                    onclick="buscarCultivaresSemillasInta()"
                    class="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-slate-800 text-slate-300"
                >
                    &larr; Volver al listado
                </button>
            </div>

            <div>
                <span class="font-mono text-[11px] uppercase text-emerald-400 block mb-1">Ficha Oficial INTA:</span>
                ${
                    ficha.length === 0
                        ? `<p class="text-slate-400 font-mono text-[11px]">${escapeHtml(
                              typeof data.ficha === "string" ? data.ficha : "Sin ficha publicada."
                          )}</p>`
                        : `<ul class="space-y-1 text-[11px]">${ficha
                              .map(
                                  (f) =>
                                      `<li><strong class="text-slate-200">${escapeHtml(f.atributo)}:</strong> ${escapeHtml(
                                          f.valor
                                      )} <span class="text-slate-500 font-mono">(${escapeHtml(f.fuente)})</span></li>`
                              )
                              .join("")}</ul>`
                }
            </div>

            <div>
                <span class="font-mono text-[11px] uppercase text-sky-400 block mb-1">Redes de Ensayos:</span>
                ${
                    Object.keys(ensayos).length === 0
                        ? `<p class="text-slate-500 text-[11px]">Sin registros en redes de ensayos cargadas.</p>`
                        : Object.entries(ensayos)
                              .map(
                                  ([redKey, info]) =>
                                      `<div class="rounded-lg bg-slate-900 border border-slate-800 p-2 mb-1">
                                          <span class="font-mono text-sky-300">${escapeHtml(info.red)}</span>
                                          <p class="text-[11px] text-slate-300 mt-0.5">${info.resultados.length} registro(s) en la red (${escapeHtml(redKey)}).</p>
                                       </div>`
                              )
                              .join("")
                }
            </div>
        </div>
    `;
}

async function verManejoCultivoSeleccionado() {
    const cultivo = document.getElementById("selectCultivoSemillas")?.value;
    const out = document.getElementById("resultadoSemillasInta");
    if (!cultivo) {
        mostrarToast("Selecciona primero un cultivo en el desplegable para ver su guía de manejo.", "info");
        return;
    }

    const res = await authFetch(`/api/rotaterra/semillas/manejo?cultivo=${encodeURIComponent(cultivo)}&solo_con_dato=true`);
    const data = await res.json();
    if (!res.ok) {
        mostrarToast(data.detail || "No hay guía de manejo para ese cultivo.", "error");
        return;
    }
    const filas = Array.isArray(data.filas) ? data.filas : [];

    out.innerHTML = `
        <div class="space-y-2">
            <div class="flex items-center justify-between border-b border-slate-800 pb-2">
                <span class="font-heading text-sm font-bold text-emerald-400">Guía de Manejo INTA — ${escapeHtml(cultivo)}</span>
                <button
                    type="button"
                    onclick="buscarCultivaresSemillasInta()"
                    class="px-2.5 py-1 rounded-lg text-[11px] font-mono bg-slate-800 text-slate-300"
                >
                    &larr; Volver a Cultivares
                </button>
            </div>
            <div class="divide-y divide-slate-800/60">
                ${filas
                    .map(
                        (f) => `
                    <div class="py-1.5">
                        <span class="font-mono text-sky-300 font-semibold">${escapeHtml(f.tema)}:</span>
                        <span class="text-slate-200 ml-1">${escapeHtml(f.valor)}</span>
                        <span class="block text-[10px] font-mono text-slate-500">Fuente: ${escapeHtml(f.fuente || "INTA")}</span>
                    </div>
                `
                    )
                    .join("")}
            </div>
        </div>
    `;
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
window. obtenerPoligonoModalPendiente = () => e2wModalPendingGeojson;
