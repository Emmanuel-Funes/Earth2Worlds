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
        perfil_tecnico_btn_mini: "Agricultural Specialist Access",
        perfil_guia_farmer_btn: "Farmer User Guide",
        nav_guia_farmer: "Farmer Guide",

        // --- 3-STEP WIZARD (FARMER MODE) ---
        step1_titulo: "Create Parcel",
        step2_titulo: "Previous Planting",
        step3_titulo: "Information & Recommendation",
        
        paso1_cabecera: "Step 1: Delimit your Field in Argentina",
        paso1_instrucciones: "Navigate the map, use the polygon tool on the left to draw the parcel boundaries.",
        btn_dibujar_poligono: "Draw Parcel Polygon",
        btn_limpiar_poligono: "Clear Polygon",
        btn_confirmar_paso1: "Confirm Parcel and Continue →",
        btn_buscar_lugar: "Search Place",
        btn_ir_coord: "Search Place",
        placeholder_coord_google: "Google Coordinates (e.g. -33.68, -65.42)",
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
        cultivo_otro: "Other / None (all crops available)",
        btn_volver_paso1: "← Back to Map",
        btn_confirmar_paso2: "Analyze Historical Information for Recommendations",

        pm_poligono: "Polygon",
        pm_rectangulo: "Rectangle",
        pm_editar: "Edit",
        pm_borrar: "Delete",
        pdf_titulo_reporte: "Agroclimatic & Crop Rotation Technical Report",
        pdf_serie_continua: "Continuous Series (5 Years)",
        pdf_comparativa_interanual: "Interannual Comparison (5 Years)",
        pdf_min: "Min",
        pdf_max: "Max",
        pdf_prom: "Avg",
        pdf_lote_evaluado: "Evaluated Parcel",
        pdf_plan_trienal: "3-Year Triennial Crop Rotation Plan",
        pdf_generado: "Generated on",

        alerta_frontera_titulo: "Parcel outside national boundary",
        alerta_frontera_desc: "The selected parcel is located outside the Argentine Republic territory. Only parcels within the country boundaries are supported.",
        btn_cerrar: "✕ Close",
        badge_lote_evaluado: "EVALUATED PARCEL",
        btn_pdf_esperando_title: "Waiting for 5-year satellite data download...",
        slot_rec_titulo: "Agronomic Crop Rotation Recommendation",
        slot_rec_ventana: "🛰️ Satellite Window: 5 Years NASA",
        slot_rec_procesando: "Processing historical observations from the NASA constellation (NDVI HLS/MODIS, root-zone moisture SMAP, precipitation regime IMERG, and frost risk VIIRS) cross-referenced with declared previous crop...",
        estado_conectando_nasa: "Connecting to NASA Earthdata...",

        paso3_cabecera: "Step 3: 5-Year NASA Satellite Information and Recommended Rotations",
        paso3_desc: "Multi-satellite query across 5 years of history. Click on each card to inspect continuous or interannual charts.",
        banner_espera_analisis: "Evaluating 5 years of NASA satellite telemetry (HLS, SMAP, IMERG, POWER, ET) and computing optimal rotations...",
        banner_34_anios_titulo: "34 years of NASA data at your service",
        banner_34_anios_desc: "NASA POWER historical series (1991 to 2025) with water balance, solar radiation, temperature, and high-precision agroclimatic telemetry.",
        btn_pdf_esperando: "⏳ Waiting for data (5y)...",
        sec_satelital_titulo: "Current Satellite Information",

        // --- 6 TELEMETRY CARDS ---
        card1_titulo: "Active Vegetation",
        card1_sensor: "NASA HLS Sentinel-2 (30m)",
        card1_desc: "Current photosynthetic vigor vs 5-year historical anomaly.",
        
        card2_titulo: "Sowing Moisture",
        card2_sensor: "NASA SMAP L3 / SPL4SMGP (9km/36km)",
        card2_desc: "Root-zone water retention (0-100 cm) and topsoil moisture.",

        card3_titulo: "Soil Temperature",
        card3_sensor: "NASA POWER Daily (AgClimatology)",
        card3_desc: "Surface thermal extremes and frost risk monitoring.",

        card4_titulo: "Topography & Drainage Slope",
        card4_sensor: "NASADEM SRTM (30m)",
        card4_desc: "Field altitude, drainage slope gradient, and runoff bearing.",
        card4_cota_label: "Altitude",
        card4_pendiente_label: "Slope",
        card4_orientacion_label: "Drainage runoff:",

        card5_titulo: "Accumulated Precipitation",
        card5_sensor: "NASA GPM IMERG (10km)",
        card5_desc: "Satellite rainfall records and parcel water regime.",

        card6_titulo: "Soil Evaporation",
        card6_sensor: "NASA POWER / ECOSTRESS (0.5°/70m)",
        card6_desc: "Daily atmospheric water demand and crop water stress.",

        badge_descargando_5y: "⏳ Downloading 5 years...",
        badge_ver_grafico_5y: "📈 View Chart (5y)",

        btn_acceso_admin: "🔒 Admin Access",
        modal_admin_titulo: "Administrator Access",
        grafico_sin_observaciones: "No observations available in this range",
        kpi_obs_label: "Obs",
        kpi_min_label: "Min",
        kpi_max_label: "Max",
        kpi_prom_label: "Avg",
        slot_rec_estado_motor: "Rotation Engine Status:",
        slot_rec_desc_motor: "Slot integrated for the RotaTerra agronomic rotation engine. Evaluates soil sustainability, monoculture reduction, available water capacity, and 5-season cumulative water balance.",

        badge_lote_evaluado: "EVALUATED PARCEL",
        resumen_superficie_label: "Area:",
        resumen_centroide_label: "Centroid:",
        badge_previo_label: "Previous:",
        badge_mapa_inicio_dibujo: "Click on the map to start drawing the parcel polygon",
        card1_pasada_label: "Overpass:",
        card1_calidad_buena: "good",
        card2_celda_label: "9km EASE Cell",
        card3_periodo_label: "Period:",
        card4_max_label: "Max",
        card4_min_label: "Min",
        card5_balance_label: "Radiation Balance",
        card5_unidad: "mm/day (POWER / ECOSTRESS)",
        card6_topografia_label: "Satellite topography (30m)",
        card6_unidad: "m a.s.l. (NASADEM)",
        rumbo_este: "East",
        rumbo_oeste: "West",
        rumbo_norte: "North",
        rumbo_sur: "South",
        rumbo_noreste: "Northeast",
        rumbo_noroeste: "Northwest",
        rumbo_sureste: "Southeast",
        rumbo_suroeste: "Southwest",
        rumbo_plano: "Flat",
        btn_grafico_prev: "Previous Chart (←)",
        btn_grafico_next: "Next Chart (→)",

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
        perfil_tecnico_btn_mini: "Acceso Técnico Agropecuario",
        perfil_guia_farmer_btn: "Guía de Uso Agricultor",
        nav_guia_farmer: "Guía Agricultor",

        // --- 3-STEP WIZARD (FARMER MODE) ---
        step1_titulo: "Crear Parcela",
        step2_titulo: "Última Plantación",
        step3_titulo: "Información y Recomendación",

        paso1_cabecera: "Paso 1: Delimita tu Parcela en Argentina",
        paso1_instrucciones: "Navega por el mapa y utiliza las herramientas de la izquierda para trazar el límite del lote.",
        btn_dibujar_poligono: "Dibujar Polígono del Lote",
        btn_limpiar_poligono: "Limpiar Polígono",
        btn_confirmar_paso1: "Confirmar Parcela y Continuar →",
        btn_buscar_lugar: "Buscar Lugar",
        btn_ir_coord: "Buscar Lugar",
        placeholder_coord_google: "Coordenadas Google (ej: -33.68, -65.42)",
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
        cultivo_otro: "Otro / Ninguno (todos los cultivos disponibles)",
        btn_volver_paso1: "← Volver al Mapa",
        btn_confirmar_paso2: "Analizar Información histórica para recomendaciones",

        pm_poligono: "Polígono",
        pm_rectangulo: "Rectángulo",
        pm_editar: "Editar",
        pm_borrar: "Borrar",
        pdf_titulo_reporte: "Informe Técnico Agroclimático y Rotación de Cultivos",
        pdf_serie_continua: "Serie Continua (5 Años)",
        pdf_comparativa_interanual: "Comparativa Interanual (5 Años)",
        pdf_min: "Mín",
        pdf_max: "Máx",
        pdf_prom: "Prom",
        pdf_lote_evaluado: "Lote Evaluado",
        pdf_plan_trienal: "Plan Trienal de Rotación de Cultivos",
        pdf_generado: "Generado el",

        alerta_frontera_titulo: "Lote fuera del límite nacional",
        alerta_frontera_desc: "El lote seleccionado se encuentra fuera del territorio de la República Argentina. Solo se admiten parcelas dentro de las fronteras del país.",
        btn_cerrar: "✕ Cerrar",
        badge_lote_evaluado: "LOTE EVALUADO",
        btn_pdf_esperando_title: "Aguardando descarga de 5 años de datos satelitales...",
        slot_rec_titulo: "Recomendación Agronómica de Rotación de Cultivos",
        slot_rec_ventana: "🛰️ Ventana Satelital: 5 Años NASA",
        slot_rec_procesando: "Procesando observaciones históricas de la constelación de la NASA (NDVI HLS/MODIS, humedad radicular SMAP, régimen hídrico IMERG y riesgo de heladas VIIRS) cruzadas con el cultivo previo declarado...",
        estado_conectando_nasa: "Conectando con NASA Earthdata...",

        paso3_cabecera: "Paso 3: Información Satelital de 5 Años y Recomendación de Rotaciones",
        paso3_desc: "Consulta multi-satelital de 5 años de historia. Haz clic en cada tarjeta para inspeccionar los gráficos continuos o interanuales.",
        banner_espera_analisis: "Evaluando 5 años de telemetría satelital NASA (HLS, SMAP, IMERG, POWER, ET) y calculando rotaciones óptimas...",
        banner_34_anios_titulo: "34 años de datos de la NASA a tu servicio",
        banner_34_anios_desc: "Serie histórica NASA POWER (1991 a 2025) con balance hídrico, radiación, temperaturas y registro agroclimático de alta precisión.",
        btn_pdf_esperando: "⏳ Aguardando datos (5a)...",
        sec_satelital_titulo: "Información Satelital actual",

        // --- 6 TELEMETRY CARDS ---
        card1_titulo: "Vegetación Activa",
        card1_sensor: "NASA HLS Sentinel-2 (30m)",
        card1_desc: "Vigor fotosintético actual vs anomalía histórica de 5 años.",

        card2_titulo: "Humedad para Siembra",
        card2_sensor: "NASA SMAP L3 / SPL4SMGP (9km/36km)",
        card2_desc: "Retención de agua en zona radicular (0-100 cm) y suelo superficial.",

        card3_titulo: "Temperatura de Suelo",
        card3_sensor: "NASA POWER Daily (AgClimatología)",
        card3_desc: "Extremos térmicos superficiales y monitoreo de riesgo de heladas.",

        card4_titulo: "Topografía y Pendiente de Drenaje",
        card4_sensor: "NASADEM SRTM (30m)",
        card4_desc: "Cota del campo, pendiente de escurrimiento y rumbo topográfico.",
        card4_cota_label: "Cota",
        card4_pendiente_label: "Pendiente",
        card4_orientacion_label: "Escurrimiento hacia:",

        card5_titulo: "Precipitación acumulada",
        card5_sensor: "NASA GPM IMERG (10km)",
        card5_desc: "Registro satelital de lluvias y régimen hídrico de la parcela.",

        card6_titulo: "Evaporación del Suelo",
        card6_sensor: "NASA POWER / ECOSTRESS (0.5°/70m)",
        card6_desc: "Demanda atmosférica diaria de agua y estrés hídrico de cultivos.",

        badge_descargando_5y: "⏳ Descargando 5 años...",
        badge_ver_grafico_5y: "📈 Ver Gráfico (5a)",

        btn_acceso_admin: "🔒 Acceso Administrador",
        modal_admin_titulo: "Acceso Administrador",
        grafico_sin_observaciones: "Sin observaciones disponibles en este rango",
        kpi_obs_label: "Obs",
        kpi_min_label: "Mín",
        kpi_max_label: "Máx",
        kpi_prom_label: "Prom",
        slot_rec_estado_motor: "Estado del Motor de Rotación:",
        slot_rec_desc_motor: "Slot reservado e integrado para el nuevo motor agronómico de Rotaterra. Evalúa la sustentabilidad del suelo, reducción de monocultivo, disponibilidad de agua útil y balance hídrico acumulado de las últimas 5 campañas.",

        badge_lote_evaluado: "LOTE EVALUADO",
        resumen_superficie_label: "Superficie:",
        resumen_centroide_label: "Centroide:",
        badge_previo_label: "Previo:",
        badge_mapa_inicio_dibujo: "Haz clic en el mapa para iniciar el polígono",
        card1_pasada_label: "Pasada:",
        card1_calidad_buena: "buena",
        card2_celda_label: "Celda 9km EASE",
        card3_periodo_label: "Periodo:",
        card4_max_label: "Máx",
        card4_min_label: "Mín",
        card5_balance_label: "Balance de Radiación",
        card5_unidad: "mm/día (POWER / ECOSTRESS)",
        card6_topografia_label: "Topografía satelital (30m)",
        card6_unidad: "m s.n.m. (NASADEM)",
        rumbo_este: "Este",
        rumbo_oeste: "Oeste",
        rumbo_norte: "Norte",
        rumbo_sur: "Sur",
        rumbo_noreste: "Noreste",
        rumbo_noroeste: "Noroeste",
        rumbo_sureste: "Sureste",
        rumbo_suroeste: "Suroeste",
        rumbo_plano: "Plano",
        btn_grafico_prev: "Gráfico anterior (←)",
        btn_grafico_next: "Siguiente gráfico (→)",

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
    "soja de primera": { en: "Early Soybean", es: "Soja de primera" },
    "soja de segunda": { en: "Late Soybean", es: "Soja de segunda" },
    "maíz": { en: "Corn (Maize)", es: "Maíz" },
    "maiz": { en: "Corn (Maize)", es: "Maíz" },
    "maíz de primera": { en: "Early Corn", es: "Maíz de primera" },
    "maiz de primera": { en: "Early Corn", es: "Maíz de primera" },
    "maíz tardío": { en: "Late Corn", es: "Maíz tardío" },
    "maiz tardio": { en: "Late Corn", es: "Maíz tardío" },
    "girasol": { en: "Sunflower", es: "Girasol" },
    "maní": { en: "Peanut", es: "Maní" },
    "mani": { en: "Peanut", es: "Maní" },
    "trigo": { en: "Wheat", es: "Trigo" },
    "cebada": { en: "Barley", es: "Cebada" },
    "sorgo": { en: "Sorghum", es: "Sorgo" },
    "sorgo granifero": { en: "Grain Sorghum", es: "Sorgo granífero" },
    "sorgo granífero": { en: "Grain Sorghum", es: "Sorgo granífero" },
    "alfalfa": { en: "Alfalfa / Pasture", es: "Alfalfa / Pastura" },
    "barbecho": { en: "Fallow", es: "Barbecho" },
    "otro": { en: "Other", es: "Otro" }
};

function traducirNombreCultivo(nombre) {
    if (!nombre) return "";
    const clean = String(nombre).trim().toLowerCase();
    if (TRADUCCION_CULTIVOS[clean] && TRADUCCION_CULTIVOS[clean][idiomaActual]) {
        return TRADUCCION_CULTIVOS[clean][idiomaActual];
    }
    return nombre;
}

function traducirEstadoCultivo(estado) {
    if (!estado) return "";
    const s = String(estado).trim().toLowerCase();
    if (s.includes("recomenda") || s.includes("optimal") || s.includes("optimo")) {
        return idiomaActual === "en" ? "Recommended" : "Recomendable";
    }
    if (s.includes("cuidado") || s.includes("caution") || s.includes("reserva")) {
        return idiomaActual === "en" ? "With caution" : "Con cuidado";
    }
    if (s.includes("desaconseja") || s.includes("not recommended") || s.includes("descartad")) {
        return idiomaActual === "en" ? "Not recommended" : "No recomendable";
    }
    return estado;
}

function traducirEtiquetaAnio(anio, etiqueta) {
    if (idiomaActual === "en") {
        const str = String(etiqueta || "").toLowerCase();
        if (anio === 1 || str.includes("1") || str.includes("próxima") || str.includes("proxima")) {
            return "YEAR 1 (NEXT SEASON)";
        }
        if (anio === 2 || str.includes("2") || str.includes("siguiente")) {
            return "YEAR 2 (SUBSEQUENT SEASON)";
        }
        if (anio === 3 || str.includes("3") || str.includes("tercera")) {
            return "YEAR 3 (THIRD SEASON)";
        }
        return `YEAR ${anio}`;
    }
    return etiqueta || `AÑO ${anio}`;
}

function traducirExplicacionSeleccion(texto) {
    if (!texto) return "";
    if (idiomaActual !== "en") return texto;

    // Pattern 1: 1ª OPCIÓN RECOMENDADA
    let m = texto.match(/1ª OPCIÓN RECOMENDADA \((\d+)% de coincidencia óptima\):/i);
    if (m) {
        return `1st RECOMMENDED CHOICE (${m[1]}% optimal match): Best agronomic alternative for your field. Outperforms all other options with excellent water supply, high frost-free maturity probability, and complete harmony with soil conditions and season rotation.`;
    }

    // Pattern 2: Opción Nª (X% de coincidencia óptima)
    m = texto.match(/Opción (\d+)ª \((\d+)% de coincidencia óptima\): Cultivo completamente viable y recomendable, pero se ubica por detrás de (.+?) \((\d+)%\)/i);
    if (m) {
        const topEn = traducirNombreCultivo(m[3]);
        return `Choice #${m[1]} (${m[2]}% optimal match): Fully viable and recommended crop, but ranks behind ${topEn} (${m[4]}%) due to tighter water margins or growing degree-day accumulation relative to biological optima.`;
    }

    // Pattern 3: Opción Nª con reservas (X% de coincidencia)
    m = texto.match(/Opción (\d+)ª con reservas \((\d+)% de coincidencia\): Queda postergado frente a (.+?) debido a advertencias técnicas en tu campo \((.+?)\)/i);
    if (m) {
        const topEn = traducirNombreCultivo(m[3]);
        let advEn = m[4];
        if (advEn.toLowerCase().includes("temperatura del suelo")) advEn = "Soil temperature for sowing";
        else if (advEn.toLowerCase().includes("humedad")) advEn = "Soil moisture at sowing";
        else if (advEn.toLowerCase().includes("precaución")) advEn = "climatic precaution";
        return `Choice #${m[1]} with caution (${m[2]}% match): Ranked behind ${topEn} due to technical warnings on your field (${advEn}); requires moisture monitoring or specific field management.`;
    }

    // Pattern 4: Descartado (X% de coincidencia)
    m = texto.match(/Descartado \((\d+)% de coincidencia\): No es conveniente para esta campaña frente a las opciones recomendadas porque no supera reglas críticas para tu campo \((.+?)\)/i);
    if (m) {
        let critEn = m[2];
        if (critEn.toLowerCase().includes("no repetir")) critEn = "Do not repeat species";
        else if (critEn.toLowerCase().includes("temperatura")) critEn = "Soil temperature for sowing";
        else if (critEn.toLowerCase().includes("agua")) critEn = "Cycle water demand";
        return `Not recommended (${m[1]}% match): Not advised for this season compared to recommended choices because it does not pass critical rules for your field (${critEn}).`;
    }

    // Pattern 5: Sucesión agronómica recomendada tras
    m = texto.match(/Sucesión agronómica recomendada tras (.+?): respeta el intervalo sanitario del INTA y mantiene la cobertura del suelo/i);
    if (m) {
        const cultEn = traducirNombreCultivo(m[1]);
        return `Recommended agronomic succession after ${cultEn}: complies with INTA sanitary interval and preserves soil cover.`;
    }

    // Pattern 6: Rotación trienal equilibrada tras
    m = texto.match(/Rotación trienal equilibrada tras (.+?) y (.+?): diversifica familias botánicas y optimiza el balance de nutrientes/i);
    if (m) {
        const c1En = traducirNombreCultivo(m[1]);
        const c2En = traducirNombreCultivo(m[2]);
        return `Balanced 3-year rotation after ${c1En} and ${c2En}: diversifies botanical families and optimizes nutrient balance.`;
    }

    return texto;
}

function traducirRumbo(rumbo) {
    if (!rumbo) return "";
    const clean = String(rumbo).trim().toLowerCase();
    const map = {
        "este": t("rumbo_este", "East"),
        "oeste": t("rumbo_oeste", "West"),
        "norte": t("rumbo_norte", "North"),
        "sur": t("rumbo_sur", "South"),
        "noreste": t("rumbo_noreste", "Northeast"),
        "noroeste": t("rumbo_noroeste", "Northwest"),
        "sureste": t("rumbo_sureste", "Southeast"),
        "suroeste": t("rumbo_suroeste", "Southwest"),
        "plano": t("rumbo_plano", "Flat")
    };
    return map[clean] || rumbo;
}

const TRADUCCION_REGLAS = {
    "temperatura del suelo para sembrar": { en: "Soil temperature for sowing", es: "Temperatura del suelo para sembrar" },
    "grados día: llega a madurar": { en: "Growing degree-days: reaches maturity", es: "Grados día: llega a madurar" },
    "grados dia: llega a madurar": { en: "Growing degree-days: reaches maturity", es: "Grados día: llega a madurar" },
    "humedad del suelo a la siembra": { en: "Soil moisture at sowing", es: "Humedad del suelo a la siembra" },
    "agua del ciclo (60 % de la demanda)": { en: "Cycle water (60% of water demand)", es: "Agua del ciclo (60 % de la demanda)" },
    "agua del ciclo (60% de la demanda)": { en: "Cycle water (60% of water demand)", es: "Agua del ciclo (60 % de la demanda)" },
    "textura": { en: "Soil texture", es: "Textura" },
    "textura (arcilla)": { en: "Soil texture (clay)", es: "Textura (arcilla)" },
    "profundidad del suelo": { en: "Soil effective depth", es: "Profundidad del suelo" },
    "ph": { en: "Soil pH", es: "pH" },
    "no repetir la especie": { en: "Do not repeat species (Rotation interval)", es: "No repetir la especie" },
    "sales": { en: "Salinity (Electrical conductivity)", es: "Sales" },
    "helada después de sembrar": { en: "Frost risk after sowing", es: "Helada después de sembrar" },
    "helada despues de sembrar": { en: "Frost risk after sowing", es: "Helada después de sembrar" },
    "calor en el período crítico": { en: "Heat stress in critical period", es: "Calor en el período crítico" },
    "calor en el periodo critico": { en: "Heat stress in critical period", es: "Calor en el período crítico" }
};

function traducirNombreRegla(regla) {
    if (!regla) return "";
    const clean = String(regla).trim().toLowerCase();
    if (TRADUCCION_REGLAS[clean] && TRADUCCION_REGLAS[clean][idiomaActual]) {
        return TRADUCCION_REGLAS[clean][idiomaActual];
    }
    return regla;
}

function traducirComparativaOptimo(texto) {
    if (!texto) return "";
    if (idiomaActual !== "en") return texto;

    let res = String(texto);
    res = res.replace(/Tu campo:/g, "Your field:");
    res = res.replace(/vs Óptimo:/g, "vs Optimal:");
    res = res.replace(/vs Óptimo ciclo:/g, "vs Optimal cycle:");
    res = res.replace(/vs Óptimo requerimiento:/g, "vs Optimal requirement:");
    res = res.replace(/· Óptimo:/g, "· Optimal:");

    // Specific multi-word patterns before single-word replacements
    res = res.replace(/madura antes de helada en (\d+)\/(\d+) campañas/g, "matures before frost in $1/$2 seasons");
    res = res.replace(/suelo con (\d+) °C en (\d+)\/(\d+) campañas/g, "soil at $1 °C in $2/$3 seasons");
    res = res.replace(/humedad de siembra estimada en (\d+)\/(\d+) campañas/g, "estimated sowing moisture in $1/$2 seasons");
    res = res.replace(/oferta media (\d+) mm/g, "average water supply $1 mm");
    res = res.replace(/en (\d+)\/(\d+) campañas/g, "in $1/$2 seasons");
    res = res.replace(/en (\d+) de cada (\d+) campañas/g, "in $1 out of $2 seasons");
    res = res.replace(/no alcanza (\d+) °C a fin de enero/g, "does not reach $1 °C by late January");

    res = res.replace(/Mínimo de siembra:/g, "Minimum sowing temp:");
    res = res.replace(/Mínimo requerido:/g, "Minimum required:");
    res = res.replace(/Mínimo:/g, "Minimum:");
    res = res.replace(/Recomendado:/g, "Recommended:");
    res = res.replace(/Tolerancia:/g, "Tolerance:");

    res = res.replace(/([\d.]+)\s+a\s+([\d.]+)\s*°Cd/g, "$1 to $2 °Cd");
    res = res.replace(/(\d+)\s*%\s+a\s+(\d+)\s*%/g, "$1% to $2%");
    res = res.replace(/madura hacia el/g, "matures around");
    res = res.replace(/sin serie térmica/g, "no thermal series available");
    res = res.replace(/sin serie de clima/g, "no climate series available");

    res = res.replace(/humedad de siembra estimada/g, "estimated sowing moisture");
    res = res.replace(/de agua útil/g, "available water");
    res = res.replace(/agua útil/g, "available water");
    res = res.replace(/oferta media/g, "average water supply");
    res = res.replace(/de demanda/g, "of crop demand");
    res = res.replace(/campañas/g, "seasons");
    res = res.replace(/campaña/g, "season");

    res = res.replace(/sin pH medido/g, "no measured pH");
    res = res.replace(/sin análisis de conductividad/g, "no conductivity test");
    res = res.replace(/Falta la profundidad/g, "Missing profile depth");
    res = res.replace(/profundidad del suelo/g, "soil depth");
    res = res.replace(/Tope por cultivo/g, "Crop threshold");
    res = res.replace(/Suelo libre de sales/g, "Salt-free soil");
    res = res.replace(/rotación cruzada favorable sin repetir especie/g, "favorable cross-rotation without repeating species");

    res = res.replace(/cultivo previo/g, "previous crop");
    res = res.replace(/no repetir la misma especie/g, "do not repeat the same species");

    return res;
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

    // 6b. Actualizar badge de cultivo previo si existe
    const badgeCultPrev = document.getElementById("badgeCultivoPrevioResumen");
    if (badgeCultPrev && window._ultimasRecomendacionesCache) {
        const cult = window._ultimasRecomendacionesCache.cultivoPrevio || "";
        const labelPrev = nuevoIdioma === "en" ? "Previous: " : "Previo: ";
        const cultNombre = typeof traducirNombreCultivo === "function" ? traducirNombreCultivo(cult) : cult;
        badgeCultPrev.textContent = `${labelPrev}${cultNombre}`;
    }

    // 7. Actualizar etiquetas de Geoman en los mapas según idioma
    if (typeof window.actualizarEtiquetasGeomanI18n === "function") {
        window.actualizarEtiquetasGeomanI18n();
    }

    // 8. Actualizar navModoLabel si existe
    const navModoLabel = document.getElementById("navModoLabel");
    if (navModoLabel) {
        const modoActual = window.modoUsuarioActivo || "basico";
        if (modoActual === "basico") {
            navModoLabel.textContent = nuevoIdioma === "en" ? "Farmer" : "Agricultor";
        } else if (modoActual === "avanzado") {
            navModoLabel.textContent = nuevoIdioma === "en" ? "Agricultural Specialist" : "Técnico Agropecuario";
        } else {
            navModoLabel.textContent = "Admin";
        }
    }

    // 9. Actualizar unidades y notas de tarjetas de telemetría si están en pantalla
    if (typeof window.actualizarTraduccionesTarjetasTelemetria === "function") {
        window.actualizarTraduccionesTarjetasTelemetria();
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
window.traducirEstadoCultivo = traducirEstadoCultivo;
window.traducirEtiquetaAnio = traducirEtiquetaAnio;
window.traducirExplicacionSeleccion = traducirExplicacionSeleccion;
window.traducirRumbo = traducirRumbo;
window.traducirNombreRegla = traducirNombreRegla;
window.traducirComparativaOptimo = traducirComparativaOptimo;
window.obtenerNombresMesesI18n = obtenerNombresMesesI18n;
window.DICCIONARIO_I18N = DICCIONARIO_I18N;
