/**
 * Earth2Worlds / RotaTerra - Internationalization (i18n) Module
 * Default Language: English ('en') - NO PERSISTENCE (Always resets to English on load)
 */

let idiomaActual = "en";

const DICCIONARIO_I18N = {
    en: {
        // --- NAVBAR & HEADER ---
        nav_telemetria_activa: "🛰️ Active Telemetry",
        nav_subtitulo: "Agroclimatic Platform & Crop Rotation",
        nav_modo_label: "Mode",
        nav_mapa_secciones: "Section Map",
        nav_guia: "Segmentation Guide",
        nav_diagrama_bd: "DB Diagram",
        nav_salir: "Sign Out",
        nav_cargando: "LOADING",
        btn_cambiar_modo: "⇄ Switch Mode",

        // --- ACCESS MODE SELECTOR MODAL ---
        modal_selector_badge: "🌍 RotaTerra • Agroclimatic Platform",
        modal_selector_titulo: "Choose your Access Mode",
        modal_selector_subtitulo: "Care for your land, empower your future with RotaTerra!",
        modal_selector_desc: "Select how you want to explore the platform. Test sessions do not require registration or store permanent data in the system.",
        
        perfil_agricultor_titulo: "Farmer",
        perfil_agricultor_badge: "Farmer",
        perfil_agricultor_desc: "Designed for agile and direct assessment. Draw a single parcel in Argentina, declare the previous crop, and evaluate 5 years of historical NASA telemetry with crop rotation recommendations.",
        perfil_agricultor_item1: "Parcel polygon delimiter in Argentina (Leaflet + Geoman)",
        perfil_agricultor_item2: "Quick selection of previous crop (Corn, Soybean, Sunflower, etc.)",
        perfil_agricultor_item3: "5 years of NASA telemetry (NDVI, SMAP, IMERG)",
        perfil_agricultor_item4: "RotaTerra crop rotation recommendations",
        perfil_agricultor_btn: "Enter as Farmer →",

        perfil_tecnico_titulo: "Agricultural Specialist",
        perfil_tecnico_badge: "Agricultural Specialist",
        perfil_tecnico_desc: "Full access to territorial control center: multi-resolution GIS viewer, satellite layer drawer, NASA Satellite Dock, 6 interactive telemetry cards, and temporal series charts (Chart.js).",
        perfil_tecnico_item1: "GIS viewer with WMS layers and NASA Satellite Dock",
        perfil_tecnico_item2: "All 6 live interactive telemetry cards",
        perfil_tecnico_item3: "Temporal series chart generator (Chart.js)",
        perfil_tecnico_item4: "Ephemeral session without dirtying the database",
        perfil_tecnico_btn: "Enter as Agricultural Specialist →",

        // --- 3-STEP WIZARD (FARMER MODE) ---
        step1_titulo: "Create Parcel (Global)",
        step2_titulo: "Previous Planting",
        step3_titulo: "Telemetry & Recommendation",
        
        paso1_cabecera: "Step 1: Delimit your Field in Argentina",
        paso1_instrucciones: "Navigate the map, use the polygon tool on the left to draw the parcel boundaries, or select a predefined demo parcel.",
        btn_dibujar_poligono: "Draw Parcel Polygon",
        btn_limpiar_poligono: "Clear Polygon",
        btn_confirmar_paso1: "Confirm Parcel and Continue →",
        alerta_poligono_requerido: "Please draw or select a parcel polygon on the map before continuing.",

        paso2_cabecera: "Step 2: Select Previous Harvested Crop",
        paso2_instrucciones: "Indicate what crop was recently harvested to calculate the optimal agroclimatic rotation, nutrient balance, and phytosanitary succession.",
        label_cultivo_previo: "Previous Crop",
        opcion_seleccionar: "-- Select Crop --",
        cultivo_soja: "Soybean",
        cultivo_maiz: "Corn / Maize",
        cultivo_girasol: "Sunflower",
        cultivo_trigo: "Wheat",
        cultivo_cebada: "Barley",
        cultivo_sorgo: "Sorghum",
        cultivo_mani: "Peanut",
        cultivo_alfalfa: "Alfalfa / Pasture",
        cultivo_barbecho: "Fallow (Unplanted)",
        btn_volver_paso1: "← Back to Map",
        btn_confirmar_paso2: "Analyze 5-Year Telemetry & Rotations →",

        paso3_cabecera: "Step 3: 5-Year NASA Telemetry & Recommended Rotations",
        paso3_desc: "Multi-satellite query across 5 years of history. Click on each card to inspect continuous or interannual charts.",
        banner_espera_analisis: "Evaluating 5 years of NASA satellite telemetry (HLS, SMAP, IMERG, POWER, ET) and computing optimal rotations...",

        // --- 6 TELEMETRY CARDS ---
        card1_titulo: "NDVI Vegetation Vigor",
        card1_sensor: "NASA HLS Sentinel-2 (30m)",
        card1_desc: "Current photosynthetic vigor vs 5-year historical anomaly.",
        
        card2_titulo: "Root-Zone Soil Moisture",
        card2_sensor: "NASA SMAP L3 / SPL4SMGP (9km/36km)",
        card2_desc: "Root-zone water retention (0-100 cm) and topsoil moisture.",

        card3_titulo: "Surface Temperature & Frost",
        card3_sensor: "NASA POWER Daily (AgClimatology)",
        card3_desc: "Surface thermal extremes and frost risk monitoring.",

        card4_titulo: "Topography & Drainage Slope",
        card4_sensor: "NASADEM SRTM (30m)",
        card4_desc: "Field altitude, drainage slope gradient, and runoff bearing.",
        card4_cota_label: "Altitude",
        card4_pendiente_label: "Slope",
        card4_orientacion_label: "Drainage runoff:",

        card5_titulo: "Daily & Accumulated Rainfall",
        card5_sensor: "NASA GPM IMERG (10km)",
        card5_desc: "Satellite rainfall records and parcel water regime.",

        card6_titulo: "Evapotranspiration & Stress",
        card6_sensor: "NASA ECOSTRESS / ET (70m/1km)",
        card6_desc: "Daily atmospheric water demand and crop water stress.",

        badge_descargando_5y: "⏳ Downloading 5 years...",
        badge_ver_grafico_5y: "📈 View Chart (5 Years)",

        // --- CROP ROTATION RECOMMENDATION ENGINE ---
        rotacion_seccion_titulo: "Agronomic Crop Recommendations for Next Season",
        rotacion_seccion_subtitulo: "Evaluated by RotaTerra Agronomic Engine with 5-year NASA agroclimatic telemetry, thermal thresholds, and soil moisture.",
        rotacion_coincidencia_optima: "Optimal Match:",
        rotacion_siembra_desde: "Recommended sowing: from",
        rotacion_criterio_comparativo: "Comparative Selection Criterion:",
        rotacion_ver_reglas: "View Technical Rules & Criteria",
        rotacion_campo_vs_optimo: "Your Field vs Crop Optimal Requirement:",
        rotacion_campo_valor: "Your field:",
        rotacion_optimo_valor: "Optimal:",
        rotacion_minimo_valor: "Minimum:",
        rotacion_recomendado_valor: "Recommended:",
        rotacion_fuente_label: "Source:",

        dictamen_recomendable: "Recommended",
        dictamen_con_cuidado: "With Caution",
        dictamen_desaconsejado: "Not Recommended",

        // --- CHART MODAL ---
        modal_grafico_ultimo_valor: "LAST VALUE",
        modal_grafico_btn_1m: "1 Month",
        modal_grafico_btn_3m: "3 Months",
        modal_grafico_btn_1y: "1 Year",
        modal_grafico_btn_3y: "3 Years",
        modal_grafico_btn_5y: "5 Years",
        modal_grafico_btn_custom: "Custom",
        modal_grafico_modo_label: "MODE:",
        modal_grafico_modo_continuo: "📈 Continuous",
        modal_grafico_modo_interanual: "🔄 Interannual",
        modal_grafico_btn_2y: "2 Years",
        modal_grafico_btn_4y: "4 Years",
        modal_grafico_desde: "From",
        modal_grafico_hasta: "To",
        modal_grafico_aplicar: "Apply",
        modal_grafico_campana: "Campaign",
        modal_grafico_obs: "Obs:",
        modal_grafico_min: "Min:",
        modal_grafico_max: "Max:",
        modal_grafico_prom: "Avg:",
        modal_grafico_banner_interanual: "Interannual Comparison Mode: Overlay curves for each annual campaign (January to December). Click legend tags to isolate specific years.",

        // --- MONTHS ---
        mes_ene: "Jan",
        mes_feb: "Feb",
        mes_mar: "Mar",
        mes_abr: "Apr",
        mes_may: "May",
        mes_jun: "Jun",
        mes_jul: "Jul",
        mes_ago: "Aug",
        mes_sep: "Sep",
        mes_oct: "Oct",
        mes_nov: "Nov",
        mes_dic: "Dec",

        // --- AUTH & LOGIN ---
        auth_badge_seguro: "SECURE JWT ACCESS",
        auth_login_titulo: "Sign in to RotaTerra",
        auth_login_subtitulo: "Access with your email or username (Admin).",
        auth_email_o_usuario: "Email or Username",
        auth_password: "Password",
        auth_btn_ver: "Show",
        auth_btn_ocultar: "Hide",
        auth_btn_ingresar: "Sign in to RotaTerra",
        auth_probar_sin_cuenta: "← Explore without account (Farmer / Specialist)",
        auth_dueno_pregunta: "Are you an agricultural landowner?",
        auth_link_registro: "Register as Owner",
        auth_footer: "RotaTerra • San Luis, Argentina",
        auth_registro_titulo: "Register as Owner",
        auth_registro_subtitulo: "Create your farm owner account and manage your land units.",
        auth_nombre_completo: "Full Name",
        auth_correo: "Email Address",
        auth_btn_registrarse: "Create Account",
        auth_ya_tienes_cuenta: "Already have an account?",
        auth_iniciar_sesion: "Sign in"
    },
    es: {
        // --- NAVBAR & HEADER ---
        nav_telemetria_activa: "🛰️ Telemetría Activa",
        nav_subtitulo: "Plataforma Agroclimática y Rotación de Cultivos",
        nav_modo_label: "Modo",
        nav_mapa_secciones: "Mapa de Secciones",
        nav_guia: "Guía Segmentación",
        nav_diagrama_bd: "Diagrama BD",
        nav_salir: "Salir",
        nav_cargando: "CARGANDO",
        btn_cambiar_modo: "⇄ Cambiar Modo",

        // --- ACCESS MODE SELECTOR MODAL ---
        modal_selector_badge: "🌍 RotaTerra • Plataforma Agroclimática",
        modal_selector_titulo: "Elige tu Modalidad de Acceso",
        modal_selector_subtitulo: "¡Cuida tu tierra, potencia tu futuro con RotaTerra!",
        modal_selector_desc: "Selecciona cómo deseas explorar la plataforma. Las sesiones de prueba no requieren registro ni guardan datos permanentes en el sistema.",

        perfil_agricultor_titulo: "Agricultor",
        perfil_agricultor_badge: "Agricultor",
        perfil_agricultor_desc: "Diseñado para evaluación ágil y directa. Dibuja un único lote en el territorio argentino, declara la última plantación y evalúa la telemetría histórica de 5 años con recomendación de rotación de cultivos.",
        perfil_agricultor_item1: "Delimitador de polígono en Argentina (Leaflet + Geoman)",
        perfil_agricultor_item2: "Selección rápida de cultivo previo (Maíz, Soja, Girasol, etc.)",
        perfil_agricultor_item3: "5 años de telemetría NASA (NDVI, SMAP, IMERG)",
        perfil_agricultor_item4: "Recomendación de rotación de cultivos Rotaterra",
        perfil_agricultor_btn: "Ingresar como Agricultor →",

        perfil_tecnico_titulo: "Técnico Agropecuario",
        perfil_tecnico_badge: "Técnico Agropecuario",
        perfil_tecnico_desc: "Acceso total al centro de control territorial: visor GIS multirresolución, panel lateral de capas satelitales, Dock Satelital NASA, las 6 tarjetas de telemetría interactivas y generación de gráficas de series temporales (Chart.js).",
        perfil_tecnico_item1: "Visor GIS con capas WMS y Dock Satelital NASA",
        perfil_tecnico_item2: "Las 6 tarjetas métricas interactivas en vivo",
        perfil_tecnico_item3: "Generador de gráficos de series temporales Chart.js",
        perfil_tecnico_item4: "Sesión efímera sin ensuciar la base de datos",
        perfil_tecnico_btn: "Ingresar como Técnico Agropecuario →",

        // --- 3-STEP WIZARD (FARMER MODE) ---
        step1_titulo: "Crear Lote (Global)",
        step2_titulo: "Última Plantación",
        step3_titulo: "Telemetría y Recomendación",

        paso1_cabecera: "Paso 1: Delimita tu Parcela en Argentina",
        paso1_instrucciones: "Navega por el mapa, utiliza la herramienta de polígono a la izquierda para trazar el límite del lote o selecciona una parcela de demostración.",
        btn_dibujar_poligono: "Dibujar Polígono del Lote",
        btn_limpiar_poligono: "Limpiar Polígono",
        btn_confirmar_paso1: "Confirmar Parcela y Continuar →",
        alerta_poligono_requerido: "Por favor dibuja o selecciona un polígono de parcela en el mapa antes de continuar.",

        paso2_cabecera: "Paso 2: Selecciona el Último Cultivo Cosechado",
        paso2_instrucciones: "Indica qué cultivo fue cosechado recientemente para calcular la rotación agroclimática óptima, balance de nutrientes y sucesión fitosanitaria.",
        label_cultivo_previo: "Cultivo Previo",
        opcion_seleccionar: "-- Seleccionar Cultivo --",
        cultivo_soja: "Soja",
        cultivo_maiz: "Maíz",
        cultivo_girasol: "Girasol",
        cultivo_trigo: "Trigo",
        cultivo_cebada: "Cebada",
        cultivo_sorgo: "Sorgo",
        cultivo_mani: "Maní",
        cultivo_alfalfa: "Alfalfa / Pastura",
        cultivo_barbecho: "Barbecho (Sin siembra)",
        btn_volver_paso1: "← Volver al Mapa",
        btn_confirmar_paso2: "Analizar Telemetría 5 Años y Rotaciones →",

        paso3_cabecera: "Paso 3: Telemetría Satelital NASA 5 Años y Rotaciones Sugeridas",
        paso3_desc: "Consulta multi-satelital de 5 años de historia. Haz clic en cada tarjeta para inspeccionar los gráficos continuos o interanuales.",
        banner_espera_analisis: "Evaluando 5 años de telemetría satelital NASA (HLS, SMAP, IMERG, POWER, ET) y calculando rotaciones óptimas...",

        // --- 6 TELEMETRY CARDS ---
        card1_titulo: "Índice de Vigor NDVI",
        card1_sensor: "NASA HLS Sentinel-2 (30m)",
        card1_desc: "Vigor fotosintético actual vs anomalía histórica de 5 años.",

        card2_titulo: "Humedad Radicular del Suelo",
        card2_sensor: "NASA SMAP L3 / SPL4SMGP (9km/36km)",
        card2_desc: "Retención de agua en zona radicular (0-100 cm) y suelo superficial.",

        card3_titulo: "Temperatura de Superficie y Heladas",
        card3_sensor: "NASA POWER Daily (AgClimatología)",
        card3_desc: "Extremos térmicos superficiales y monitoreo de riesgo de heladas.",

        card4_titulo: "Altimetría y Pendiente de Drenaje",
        card4_sensor: "NASADEM SRTM (30m)",
        card4_desc: "Cota del campo, pendiente de escurrimiento y rumbo topográfico.",
        card4_cota_label: "Cota",
        card4_pendiente_label: "Pendiente",
        card4_orientacion_label: "Escurrimiento hacia:",

        card5_titulo: "Precipitación Diaria y Acumulada",
        card5_sensor: "NASA GPM IMERG (10km)",
        card5_desc: "Registro satelital de lluvias y régimen hídrico de la parcela.",

        card6_titulo: "Evapotranspiración y Estrés",
        card6_sensor: "NASA ECOSTRESS / ET (70m/1km)",
        card6_desc: "Demanda atmosférica diaria de agua y estrés hídrico de cultivos.",

        badge_descargando_5y: "⏳ Descargando 5 años...",
        badge_ver_grafico_5y: "📈 Ver Gráfico (5 Años)",

        // --- CROP ROTATION RECOMMENDATION ENGINE ---
        rotacion_seccion_titulo: "Recomendaciones Agronómicas para la Próxima Campaña",
        rotacion_seccion_subtitulo: "Evaluadas por el Motor Agronómico RotaTerra con 5 años de telemetría agroclimática NASA, umbrales térmicos y humedad edáfica.",
        rotacion_coincidencia_optima: "Coincidencia Óptima:",
        rotacion_siembra_desde: "Siembra recomendada: desde",
        rotacion_criterio_comparativo: "Criterio Comparativo frente a otras opciones:",
        rotacion_ver_reglas: "Ver Reglas Técnicas y Criterios",
        rotacion_campo_vs_optimo: "Tu campo vs Óptimo del cultivo:",
        rotacion_campo_valor: "Tu campo:",
        rotacion_optimo_valor: "Óptimo:",
        rotacion_minimo_valor: "Mínimo:",
        rotacion_recomendado_valor: "Recomendado:",
        rotacion_fuente_label: "Fuente:",

        dictamen_recomendable: "Recomendable",
        dictamen_con_cuidado: "Con Cuidado",
        dictamen_desaconsejado: "Desaconsejado",

        // --- CHART MODAL ---
        modal_grafico_ultimo_valor: "ÚLTIMO VALOR",
        modal_grafico_btn_1m: "1 Mes",
        modal_grafico_btn_3m: "3 Meses",
        modal_grafico_btn_1y: "1 Año",
        modal_grafico_btn_3y: "3 Años",
        modal_grafico_btn_5y: "5 Años",
        modal_grafico_btn_custom: "Personalizado",
        modal_grafico_modo_label: "MODO:",
        modal_grafico_modo_continuo: "📈 Continuo",
        modal_grafico_modo_interanual: "🔄 Interanual",
        modal_grafico_btn_2y: "2 Años",
        modal_grafico_btn_4y: "4 Años",
        modal_grafico_desde: "Desde",
        modal_grafico_hasta: "Hasta",
        modal_grafico_aplicar: "Aplicar",
        modal_grafico_campana: "Campaña",
        modal_grafico_obs: "Obs:",
        modal_grafico_min: "Mín:",
        modal_grafico_max: "Máx:",
        modal_grafico_prom: "Prom:",
        modal_grafico_banner_interanual: "Modo Comparativa Interanual: Curvas superpuestas de cada campaña anual (Enero a Diciembre). Haz clic en las etiquetas de la leyenda para aislar años específicos.",

        // --- MONTHS ---
        mes_ene: "Ene",
        mes_feb: "Feb",
        mes_mar: "Mar",
        mes_abr: "Abr",
        mes_may: "May",
        mes_jun: "Jun",
        mes_jul: "Jul",
        mes_ago: "Ago",
        mes_sep: "Sep",
        mes_oct: "Oct",
        mes_nov: "Nov",
        mes_dic: "Dic",

        // --- AUTH & LOGIN ---
        auth_badge_seguro: "ACCESO SEGURO JWT",
        auth_login_titulo: "Ingresar a RotaTerra",
        auth_login_subtitulo: "Accede con tu correo electrónico o usuario (Admin).",
        auth_email_o_usuario: "Correo Electrónico o Usuario",
        auth_password: "Contraseña",
        auth_btn_ver: "Ver",
        auth_btn_ocultar: "Ocultar",
        auth_btn_ingresar: "Iniciar Sesión en RotaTerra",
        auth_probar_sin_cuenta: "← Probar sin cuenta (Modo Agricultor / Técnico)",
        auth_dueno_pregunta: "¿Eres dueño de un establecimiento productivo?",
        auth_link_registro: "Regístrate como Propietario",
        auth_footer: "RotaTerra • San Luis, Argentina",
        auth_registro_titulo: "Registrarse como Propietario",
        auth_registro_subtitulo: "Crea tu cuenta de titular productivo y administra tus establecimientos.",
        auth_nombre_completo: "Nombre Completo",
        auth_correo: "Correo Electrónico",
        auth_btn_registrarse: "Crear Cuenta",
        auth_ya_tienes_cuenta: "¿Ya tienes cuenta?",
        auth_iniciar_sesion: "Iniciar Sesión"
    }
};

/**
 * Obtiene la traducción para una clave dada según el idioma activo.
 */
function t(clave, fallback = "") {
    const lang = idiomaActual || "en";
    if (DICCIONARIO_I18N[lang] && DICCIONARIO_I18N[lang][clave] !== undefined) {
        return DICCIONARIO_I18N[lang][clave];
    }
    if (DICCIONARIO_I18N["en"] && DICCIONARIO_I18N["en"][clave] !== undefined) {
        return DICCIONARIO_I18N["en"][clave];
    }
    return fallback || clave;
}

/**
 * Mapeo de nombres de cultivos para traducción en recomendaciones
 */
const TRADUCCION_CULTIVOS = {
    "soja": { en: "Soybean", es: "Soja" },
    "maíz": { en: "Corn (Maize)", es: "Maíz" },
    "maiz": { en: "Corn (Maize)", es: "Maíz" },
    "girasol": { en: "Sunflower", es: "Girasol" },
    "maní": { en: "Peanut", es: "Maní" },
    "mani": { en: "Peanut", es: "Maní" },
    "trigo": { en: "Wheat", es: "Trigo" },
    "cebada": { en: "Barley", es: "Cebada" },
    "sorgo": { en: "Sorghum", es: "Sorgo" },
    "alfalfa": { en: "Alfalfa / Pasture", es: "Alfalfa / Pastura" }
};

function traducirNombreCultivo(nombre) {
    if (!nombre) return "";
    const clean = String(nombre).trim().toLowerCase();
    if (TRADUCCION_CULTIVOS[clean] && TRADUCCION_CULTIVOS[clean][idiomaActual]) {
        return TRADUCCION_CULTIVOS[clean][idiomaActual];
    }
    return nombre;
}

/**
 * Cambia el idioma activo en la sesión (sin persistencia).
 * Aplica los cambios a todo el DOM y re-renderiza componentes dinámicos.
 */
function cambiarIdioma(nuevoIdioma) {
    if (nuevoIdioma !== "en" && nuevoIdioma !== "es") return;
    idiomaActual = nuevoIdioma;
    document.documentElement.lang = nuevoIdioma;

    // 1. Traducir elementos con atributo data-i18n
    document.querySelectorAll("[data-i18n]").forEach((el) => {
        const key = el.getAttribute("data-i18n");
        const texto = t(key);
        if (texto) {
            // Preservar iconos hijos si existen con clase especial o actualizar texto directo
            if (el.querySelector("span, svg, strong") && el.getAttribute("data-i18n-target") === "self-only") {
                el.childNodes.forEach((node) => {
                    if (node.nodeType === Node.TEXT_NODE && node.nodeValue.trim()) {
                        node.nodeValue = " " + texto + " ";
                    }
                });
            } else {
                el.textContent = texto;
            }
        }
    });

    // 2. Traducir placeholders con data-i18n-ph
    document.querySelectorAll("[data-i18n-ph]").forEach((el) => {
        const key = el.getAttribute("data-i18n-ph");
        const texto = t(key);
        if (texto) el.placeholder = texto;
    });

    // 3. Traducir títulos/tooltips con data-i18n-title
    document.querySelectorAll("[data-i18n-title]").forEach((el) => {
        const key = el.getAttribute("data-i18n-title");
        const texto = t(key);
        if (texto) el.title = texto;
    });

    // 4. Actualizar botones del selector de idioma en el DOM
    actualizarBotonesSelectorIdioma(idiomaActual);

    // 5. Re-renderizar modal de gráficos si está abierto
    if (typeof window.cargarYRenderizarGraficoTelemetria === "function") {
        const modal = document.getElementById("modalGraficoTelemetria");
        if (modal && !modal.classList.contains("hidden")) {
            window.cargarYRenderizarGraficoTelemetria();
        }
    }

    // 6. Si hay recomendaciones visibles, re-renderizar para traducir nombres y dictámenes
    if (window._ultimasRecomendacionesCache && typeof window.renderizarTarjetasRecomendaciones === "function") {
        window.renderizarTarjetasRecomendaciones(window._ultimasRecomendacionesCache);
    }
}

/**
 * Actualiza el estado visual de los botones [EN | ES]
 */
function actualizarBotonesSelectorIdioma(lang) {
    document.querySelectorAll(".btn-lang-en").forEach((btn) => {
        if (lang === "en") {
            btn.className = btn.className.replace(/text-[^\s]+/g, "").replace(/bg-[^\s]+/g, "");
            btn.classList.add("bg-[#16a34a]", "text-white", "font-bold", "shadow-sm");
        } else {
            btn.className = btn.className.replace(/text-[^\s]+/g, "").replace(/bg-[^\s]+/g, "");
            btn.classList.add("text-[#523725]", "hover:text-[#100b07]", "font-semibold");
        }
    });

    document.querySelectorAll(".btn-lang-es").forEach((btn) => {
        if (lang === "es") {
            btn.className = btn.className.replace(/text-[^\s]+/g, "").replace(/bg-[^\s]+/g, "");
            btn.classList.add("bg-[#16a34a]", "text-white", "font-bold", "shadow-sm");
        } else {
            btn.className = btn.className.replace(/text-[^\s]+/g, "").replace(/bg-[^\s]+/g, "");
            btn.classList.add("text-[#523725]", "hover:text-[#100b07]", "font-semibold");
        }
    });
}

/**
 * Retorna los nombres de los 12 meses según el idioma activo
 */
function obtenerNombresMesesI18n() {
    return [
        t("mes_ene", "Jan"),
        t("mes_feb", "Feb"),
        t("mes_mar", "Mar"),
        t("mes_abr", "Apr"),
        t("mes_may", "May"),
        t("mes_jun", "Jun"),
        t("mes_jul", "Jul"),
        t("mes_ago", "Aug"),
        t("mes_sep", "Sep"),
        t("mes_oct", "Oct"),
        t("mes_nov", "Nov"),
        t("mes_dic", "Dec"),
    ];
}

// Inicialización automática siempre en INGLÉS ('en')
document.addEventListener("DOMContentLoaded", () => {
    idiomaActual = "en"; // Siempre arranca en inglés por defecto (sin persistencia)
    cambiarIdioma("en");
});

// Exportaciones globales
window.t = t;
window.cambiarIdioma = cambiarIdioma;
window.traducirNombreCultivo = traducirNombreCultivo;
window.obtenerNombresMesesI18n = obtenerNombresMesesI18n;
window.DICCIONARIO_I18N = DICCIONARIO_I18N;
