/**
 * Earth2Worlds - Sincronización dinámica de Provincia ➔ Localidad ➔ Código Postal de Argentina.
 */

const _cacheLocalidadesPorProvincia = {};

/**
 * Inicializa un trío de controles (select provincia, select ciudad/localidad, input código postal).
 * @param {string} selectProvinciaId
 * @param {string} selectCiudadId
 * @param {string} inputCpId
 * @param {object} valoresIniciales - { provincia, ciudad, codigo_postal }
 */
async function initArgentinaGeoSelectors(
    selectProvinciaId,
    selectCiudadId,
    inputCpId,
    valoresIniciales = {}
) {
    const selProv = document.getElementById(selectProvinciaId);
    const selCiudad = document.getElementById(selectCiudadId);
    const inpCp = document.getElementById(inputCpId);
    if (!selProv || !selCiudad) return;

    try {
        const res = await fetch("/api/geo/provincias");
        const data = await res.json();
        const provincias = Array.isArray(data.provincias) ? data.provincias : [];

        selProv.innerHTML =
            `<option value="">Seleccionar provincia...</option>` +
            provincias
                .map((p) => `<option value="${escapeHtml(p)}">${escapeHtml(p)}</option>`)
                .join("");

        const provInicial = valoresIniciales.provincia || "San Luis";
        if (provincias.includes(provInicial)) {
            selProv.value = provInicial;
            await cargarLocalidadesEnSelect(
                provInicial,
                selCiudad,
                inpCp,
                valoresIniciales.ciudad || "Villa Mercedes",
                valoresIniciales.codigo_postal || ""
            );
        }

        selProv.addEventListener("change", async () => {
            await cargarLocalidadesEnSelect(selProv.value, selCiudad, inpCp, "", "");
        });

        selCiudad.addEventListener("change", () => {
            const selectedOption = selCiudad.options[selCiudad.selectedIndex];
            const cpAsociado = selectedOption ? selectedOption.getAttribute("data-cp") : "";
            if (inpCp && cpAsociado) {
                inpCp.value = cpAsociado;
            }
        });
    } catch (err) {
        console.error("[Earth2Worlds] Error cargando catálogo geográfico:", err);
    }
}

/**
 * Carga las localidades de una provincia en el select correspondiente y sincroniza el CP.
 */
async function cargarLocalidadesEnSelect(
    provincia,
    selCiudad,
    inpCp,
    ciudadPreseleccionada = "",
    cpPreseleccionado = ""
) {
    if (!provincia) {
        selCiudad.innerHTML = `<option value="">Seleccione primero una provincia...</option>`;
        if (inpCp) inpCp.value = "";
        return;
    }

    let localidades = _cacheLocalidadesPorProvincia[provincia];
    if (!localidades) {
        const res = await fetch(`/api/geo/localidades/${encodeURIComponent(provincia)}`);
        const data = await res.json();
        localidades = Array.isArray(data.localidades) ? data.localidades : [];
        _cacheLocalidadesPorProvincia[provincia] = localidades;
    }

    selCiudad.innerHTML =
        `<option value="">Seleccionar localidad...</option>` +
        localidades
            .map(
                (item) =>
                    `<option value="${escapeHtml(item.localidad)}" data-cp="${escapeHtml(item.cp)}">${escapeHtml(
                        item.localidad
                    )} (CP ${escapeHtml(item.cp)})</option>`
            )
            .join("");

    if (ciudadPreseleccionada) {
        const existe = localidades.find(
            (l) => l.localidad.toLowerCase() === ciudadPreseleccionada.toLowerCase()
        );
        if (existe) {
            selCiudad.value = existe.localidad;
            if (inpCp) inpCp.value = cpPreseleccionado || existe.cp;
            return;
        }
    }

    if (localidades.length > 0) {
        selCiudad.value = localidades[0].localidad;
        if (inpCp) inpCp.value = cpPreseleccionado || localidades[0].cp;
    } else if (inpCp) {
        inpCp.value = cpPreseleccionado || "";
    }
}

window.initArgentinaGeoSelectors = initArgentinaGeoSelectors;
window.cargarLocalidadesEnSelect = cargarLocalidadesEnSelect;
