# -*- coding: utf-8 -*-
"""
Script para generar la documentación técnica completa de Earth2Worlds / RotaTerra:
1. documento_tecnologia_earth2worlds.docx (Word enriquecido)
2. static/documento_tecnologia_earth2worlds.html (HTML Interactivo con diseño responsivo)
3. documento_tecnologia_earth2worlds.html (Copia en raíz)
"""

import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def generar_docx():
    doc = docx.Document()
    
    # Configurar márgenes
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    # Estilos de encabezados y párrafos
    styles = doc.styles
    normal_style = styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(40, 30, 20)

    # Portada / Título Principal
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_badge = p_title.add_run("EARTH2WORLDS • ROTATERRA AGROCLIMATIC PLATFORM\n")
    run_badge.font.size = Pt(10)
    run_badge.font.bold = True
    run_badge.font.color.rgb = RGBColor(22, 163, 74)

    run_title = p_title.add_run("Informe de Arquitectura Tecnológica, Infraestructura Cloud y Motor de Recomendación Agronómica")
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(30, 41, 59)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_sub = p_sub.add_run("Auditoría técnica del stack de desarrollo, bases de datos edafoclimáticas, pipeline satelital NASA de 34 años, despliegue en GitHub/Render.com y resolución de autenticación Earthdata.")
    run_sub.font.size = Pt(11)
    run_sub.font.italic = True
    run_sub.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph("—" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 1. RESUMEN EJECUTIVO
    doc.add_heading("1. Resumen Ejecutivo del Proyecto", level=1)
    doc.add_paragraph(
        "Earth2Worlds / RotaTerra es una plataforma agrotecnológica de precisión concebida para la delimitación territorial de parcelas "
        "agrícolas en la República Argentina, el análisis multi-satelital histórico de 34 años (1991–2025) con telemetría de la NASA, "
        "y el cálculo inteligente de recomendaciones de rotación trienal de cultivos para mitigar la degradación edáfica, "
        "disminuir plagas y optimizar el rendimiento agronómico sustentable."
    )

    # 2. STACK TECNOLÓGICO
    doc.add_heading("2. Stack Tecnológico de la Aplicación", level=1)
    doc.add_paragraph(
        "La arquitectura del sistema sigue un modelo decoupled SPA (Single Page Application) asistida por un backend asíncrono en FastAPI:"
    )

    table_stack = doc.add_table(rows=1, cols=3)
    table_stack.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table_stack.rows[0].cells
    hdr[0].text = "Capa / Componente"
    hdr[1].text = "Tecnología Empleada"
    hdr[2].text = "Rol y Función en Earth2Worlds"
    for c in hdr:
        set_cell_background(c, "1E293B")
        for p in c.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)

    items_stack = [
        ("Backend Framework", "FastAPI (Python 3.12+ / 3.14)", "Servidor API REST asíncrono de alto rendimiento con validaciones Pydantic v2 y OpenAPI."),
        ("Servidor ASGI", "Uvicorn (Worker uvloop)", "Servidor de sockets HTTP/WebSockets sin bloqueo con puerto dinámico para Render.com ($PORT)."),
        ("Base de Datos Relacional", "SQLAlchemy 2.0 (SQLite / PostgreSQL)", "Gestor ORM agnóstico para autenticación JWT, usuarios, campos georreferenciados y auditoría."),
        ("Seguridad y Criptografía", "JWT (HS256) + Passlib (Bcrypt)", "Tokens de autenticación firmados con RBAC (Admin, Propietario, Operador) y sesiones efímeras de invitado."),
        ("Frontend & Interfaz SPA", "HTML5 Semántico + Tailwind CSS", "Interfaz en paleta agronómica de tierra y follaje, totalmente responsiva y accesible."),
        ("Motor Geoespacial", "Leaflet 1.9.4 + Geoman (L.PM)", "Visor cartográfico multirresolución, dibujo de polígonos agrícolas y filtrado dentro de Argentina."),
        ("Visualización de Telemetría", "Chart.js 4.4", "Renderizado interactivo de series temporales de 5 años: modos Continuo e Interanual con 4 KPIs en vivo."),
        ("Generador de Informes", "html2pdf.js + jsPDF + html2canvas", "Exportación de informes técnicos de campo en PDF con serie continua e interanual."),
        ("Internacionalización (i18n)", "Módulo JavaScript personalizado", "Soporte bilingüe en vivo (EN / ES) sin recarga de página, con arranque por defecto en inglés.")
    ]

    for cat, tec, rol in items_stack:
        row = table_stack.add_row().cells
        row[0].text = cat
        row[1].text = tec
        row[2].text = rol
        set_cell_background(row[0], "F8FAFC")
        for c in row:
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(2)

    # 3. BASES DE DATOS Y TELEMETRÍA
    doc.add_heading("3. Bases de Datos, Catálogos y Fuentes Satelitales de la NASA", level=1)
    doc.add_paragraph(
        "El motor agronómico de RotaTerra se fundamenta en un acoplamiento estricto de fuentes certificadas de la NASA, complementadas con datos edáficos del INTA:"
    )

    p_sources = doc.add_paragraph()
    p_sources.add_run("1. NASA POWER (Agroclimatology API, 1991–2025 - 34 Años):\n").bold = True
    p_sources.add_run(
        "Serie diaria de radiación solar (ALLSKY_SFC_SW_DWN en MJ/m²/día), temperaturas superficiales extremas y medias (T2M_MAX, T2M_MIN en °C), "
        "humedad relativa, velocidad del viento y evapotranspiración de referencia calculada mediante la ecuación FAO-56 Penman-Monteith (ET₀ en mm/día).\n\n"
    )

    p_sources.add_run("2. NASA GPM IMERG (Global Precipitation Measurement, 10 km):\n").bold = True
    p_sources.add_run(
        "Estimación satelital calibrada por microondas y radar de precipitación diaria y acumulada por período (lluvia_mm), "
        "fundamental para determinar la oferta hídrica de la campaña y el balance acumulado del lote.\n\n"
    )

    p_sources.add_run("3. NASA HLS (Harmonized Landsat Sentinel-2, 30 m):\n").bold = True
    p_sources.add_run(
        "Vigor vegetativo mediante Índice de Vegetación de Diferencia Normalizada (NDVI) a 30 metros de resolución espacial, "
        "utilizado para monitorear el dosel foliar actual y compararlo con anomalías históricas de 5 años.\n\n"
    )

    p_sources.add_run("4. NASA SMAP (Soil Moisture Active Passive, 9 km / 36 km EASE-Grid):\n").bold = True
    p_sources.add_run(
        "Medición radiométrica de microondas en banda L que entrega la retención volumétrica de agua en la capa superficial (0–5 cm) "
        "y en la zona radicular (0–100 cm) en unidades de m³/m³, validando la viabilidad de emergencia y siembra.\n\n"
    )

    p_sources.add_run("5. NASADEM SRTM (30 m):\n").bold = True
    p_sources.add_run(
        "Modelo digital de elevación satelital calibrado que provee la cota altimétrica sobre el nivel del mar (m s.n.m. / m a.s.l.), "
        "el gradiente porcentual de pendiente (%) y el rumbo direccional del escurrimiento hídrico (ej: Este 110°).\n\n"
    )

    p_sources.add_run("6. Cartografía GeoINTA y Suelos HWSD:\n").bold = True
    p_sources.add_run(
        "Cartas de suelo de la República Argentina y base HWSD v2.0 para determinar textura (franco arenoso, franco arcilloso, etc.), "
        "capacidad de retención de agua útil (mm en 0-100 cm), materia orgánica y pH del lote.\n\n"
    )

    p_sources.add_run("7. Catálogo Ecofisiológico de Cultivos (INTA / FAO Ecocrop):\n").bold = True
    p_sources.add_run(
        "Requerimientos biológicos de siembra y desarrollo para Maíz (primera y tardío), Soja (primera y segunda), Girasol, Sorgo granífero, "
        "Maní, Trigo, Cebada y Alfalfa, contrastados contra el clima real de cada cuadrante geográfico."
    )

    # 4. MOTOR DE RECOMENDACIONES Y PLAN TRIENAL
    doc.add_heading("4. Lógica del Motor de Rotaciones RotaTerra (Plan Trienal)", level=1)
    doc.add_paragraph(
        "El motor agronómico (`rotaterra.agronomos.motor`) implementa un algoritmo multicriterio ponderado de 0 a 100% que evalúa:"
    )
    p_motor = doc.add_paragraph()
    p_motor.add_run("• Reglas Críticas Excluyentes (Hard Constraints): ").bold = True
    p_motor.add_run("No repetición de especie monocultivo (ej. maíz sobre maíz, soja sobre soja), pH edáfico dentro de límites tolerables, y umbral térmico mínimo de suelo.\n")
    p_motor.add_run("• Reglas Agroclimáticas de Adaptación (Soft Constraints): ").bold = True
    p_motor.add_run("Margen hídrico frente a la evapotranspiración esperada, riesgo de heladas tardías durante floración/madurez y acumulación de grados día (°Cd).\n")
    p_motor.add_run("• Algoritmo Anti-Monocultivo Trienal Encadenado: ").bold = True
    p_motor.add_run(
        "Año 1 determina la mejor opción según el cultivo previo cosechado. "
        "Año 2 encadena el ganador de Año 1 como precedente, descartando su familia botánica para respetar el intervalo sanitario del INTA. "
        "Año 3 encadena Año 2 y Año 1 cerrando el ciclo trienal mediante alternancia equilibrada de gramíneas y leguminosas."
    )

    # 5. DIAGNÓSTICO RENDER.COM
    doc.add_heading("5. Diagnóstico de Despliegue en Render.com: ¿Por qué fallan Active Vegetation y Sowing Moisture?", level=1)
    p_render = doc.add_paragraph()
    p_render.add_run("Causa Raíz Identificada:\n").bold = True
    p_render.add_run(
        "Los módulos satelitales de Vegetación Activa (HLS Sentinel-2 en `rotaterra/fuentes/hls.py`) y Humedad de Siembra (SMAP en `rotaterra/fuentes/smap.py`) "
        "se conectan directamente a los servidores de datos protegidos de la NASA (NASA Earthdata Login / LP DAAC / NSIDC). "
        "En el código del backend, ambos conectores ejecutan la verificación de credenciales obligatoria:\n"
        "  user = os.environ.get('EARTHDATA_USERNAME')\n"
        "  pwd = os.environ.get('EARTHDATA_PASSWORD')\n"
        "Si alguna de estas dos variables de entorno no existe en el sistema operativo del servidor, el conector lanza de inmediato la excepción "
        "`FaltanCredenciales: HLS/SMAP requiere credenciales de NASA Earthdata`, y el endpoint de FastAPI retorna un código HTTP 503 (Servicio no disponible).\n\n"
    )
    p_render.add_run("¿Por qué funciona en el entorno local pero falla en Render.com?\n").bold = True
    p_render.add_run(
        "1. En el entorno local: Las credenciales están configuradas en el archivo `.env` o en las variables de entorno de Windows/Linux del desarrollador.\n"
        "2. En Render.com: Por estrictas razones de seguridad informática, los archivos `.env` están listados en el `.gitignore` y NUNCA se suben al repositorio de GitHub. "
        "Además, en el archivo de infraestructura `render.yaml`, las claves secretas están marcadas con `sync: false` precisamente para que nadie las exponga públicamente. "
        "En consecuencia, el contenedor de Render se levanta sin estas dos variables.\n"
        "3. ¿Por qué las demás tarjetas sí funcionan en Render? Porque NASA POWER (Lluvia, Temperatura, Evaporación) y NASADEM (Relieve) son APIs de acceso público abierto "
        "que no requieren autenticación básica HTTP con usuario y contraseña de Earthdata.\n\n"
    )
    p_render.add_run("Solución Paso a Paso para Activar HLS y SMAP en Render.com:\n").bold = True
    p_render.add_run(
        "1. Inicia sesión en tu cuenta de https://dashboard.render.com.\n"
        "2. Selecciona tu servicio web activo de Earth2Worlds.\n"
        "3. En el menú lateral izquierdo, haz clic en 'Environment'.\n"
        "4. En la sección 'Environment Variables', haz clic en 'Add Environment Variable'.\n"
        "5. Agrega las siguientes dos variables con tus credenciales gratuitas de NASA Earthdata:\n"
        "   • Clave: EARTHDATA_USERNAME  |  Valor: <tu_usuario_de_earthdata>\n"
        "   • Clave: EARTHDATA_PASSWORD  |  Valor: <tu_contraseña_de_earthdata>\n"
        "6. Haz clic en 'Save Changes'. Render reiniciará automáticamente el servidor en unos segundos, y a partir de ese momento las tarjetas de Active Vegetation y Sowing Moisture responderán con datos satelitales en vivo al 100%."
    )

    # 6. AUDITORÍA DE INCONSISTENCIAS Y CORRECCIONES TEXTUALES
    doc.add_heading("6. Auditoría de Inconsistencias Textuales y Correcciones Implementadas", level=1)
    doc.add_paragraph(
        "Se auditó exhaustivamente la aplicación en busca de anomalías terminológicas, desajustes de unidades y errores de concatenación:"
    )
    p_audit = doc.add_paragraph()
    p_audit.add_run("1. Corrección de Unidades de Evaporación de Suelo (Tarjeta 5):\n").bold = True
    p_audit.add_run(
        "Se corrigió la unidad de evapotranspiración para que reporte estrictamente en `mm/day` (en inglés) y `mm/día` (en español), "
        "eliminando cualquier confusión con unidades energéticas de radiación (MJ/m²).\n\n"
    )
    p_audit.add_run("2. Corrección de Unidades de Altimetría y Rumbo Topográfico (Tarjeta 6):\n").bold = True
    p_audit.add_run(
        "Se dinamicó la unidad de cota entre `m a.s.l. (NASADEM)` en inglés y `m s.n.m. (NASADEM)` en español. "
        "Asimismo, se implementó el traductor direccional para que rumbos como `Este (110°)` se muestren como `East (110°)` en modo inglés.\n\n"
    )
    p_audit.add_run("3. Eliminación del Error de Tartamudeo en el Encabezado de Parcela (Paso 3):\n").bold = True
    p_audit.add_run(
        "Se corrigió el error donde el centroide se imprimía duplicado como `Centroide: Centroide: [-33.65, -65.48] · 2.32 ha`. "
        "Ahora muestra limpiamente `Area: 2.32 ha • Centroid: [-33.6527, -65.4786]` y las etiquetas `EVALUATED PARCEL` y `Previous: Corn`.\n\n"
    )
    p_audit.add_run("4. Navegación Fluida entre Gráficos sin Cerrar el Modal:\n").bold = True
    p_audit.add_run(
        "Se incorporaron botones de desplazamiento anterior/siguiente (◀ / ▶) y atajos de teclado (flecha izquierda y flecha derecha) "
        "para que el usuario pueda explorar las 5 curvas satelitales (NDVI, SMAP, IMERG, Temperatura, Evaporación) en forma continua."
    )

    # Guardar DOCX
    docx_path = "documento_tecnologia_earth2worlds.docx"
    doc.save(docx_path)
    print(f"Documento DOCX generado con éxito en: {os.path.abspath(docx_path)}")

def generar_html():
    html_content = """<!DOCTYPE html>
<html lang="es" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earth2Worlds / RotaTerra • Documento Técnico de Arquitectura y Tecnologías</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        code, pre { font-family: 'JetBrains Mono', monospace; }
        .tab-btn.active {
            background-color: #16a34a;
            color: #ffffff;
            box-shadow: 0 4px 6px -1px rgba(22, 163, 74, 0.3);
        }
    </style>
</head>
<body class="bg-[#faf7f2] text-[#241810] min-h-screen antialiased selection:bg-emerald-500 selection:text-white">

    <!-- Header Principal -->
    <header class="bg-white border-b-2 border-[#8c6547]/30 sticky top-0 z-50 shadow-sm backdrop-blur-md bg-white/95">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-4">
            <div class="flex items-center gap-3">
                <span class="text-3xl">🌍</span>
                <div>
                    <h1 class="font-extrabold text-xl sm:text-2xl text-[#100b07] tracking-tight">Earth2Worlds / RotaTerra</h1>
                    <p class="text-xs text-[#785843] font-medium">Informe Técnico de Arquitectura, Tecnologías Cloud, Satélites NASA y Algoritmos Agronómicos</p>
                </div>
            </div>
            <div class="flex items-center gap-2">
                <a href="/static/index.html" class="px-3.5 py-1.5 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs shadow-sm transition flex items-center gap-1.5">
                    <span>🚀</span> Ir a la Aplicación
                </a>
            </div>
        </div>
    </header>

    <!-- Navegación por Pestañas Interactivas -->
    <nav class="max-w-7xl mx-auto px-4 sm:px-6 pt-6">
        <div class="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none border-b border-[#dfd2c6]">
            <button onclick="cambiarPestana('stack')" id="tab-stack" class="tab-btn active px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                💻 1. Stack Tecnológico
            </button>
            <button onclick="cambiarPestana('nube')" id="tab-nube" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                ☁️ 2. GitHub & Render.com
            </button>
            <button onclick="cambiarPestana('satelites')" id="tab-satelites" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🛰️ 3. Bases de Datos & NASA
            </button>
            <button onclick="cambiarPestana('rotaterra')" id="tab-rotaterra" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🔄 4. Motor de Rotaciones
            </button>
            <button onclick="cambiarPestana('render-fix')" id="tab-render-fix" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🛠️ 5. Solución Render (HLS / SMAP)
            </button>
            <button onclick="cambiarPestana('inconsistencias')" id="tab-inconsistencias" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🔍 6. Auditoría Textual
            </button>
        </div>
    </nav>

    <!-- Contenido Principal Dinámico -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">

        <!-- SECCIÓN 1: STACK TECNOLÓGICO -->
        <section id="sec-stack" class="space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-emerald-100 border border-emerald-400 flex items-center justify-center text-2xl">⚡</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Stack Tecnológico de Alto Rendimiento</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Arquitectura moderna decoupled con backend asíncrono y Single Page Application (SPA).</p>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-4">
                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-md">BACKEND</span>
                        <h3 class="font-bold text-lg text-[#100b07]">FastAPI + Python 3.14</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Framework moderno asíncrono con tipado estricto Pydantic v2, serialización ultra-rápida y documentación automática interactiva en Swagger UI (/docs).</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-sky-800 bg-sky-100 px-2 py-0.5 rounded-md">MAPAS GIS</span>
                        <h3 class="font-bold text-lg text-[#100b07]">Leaflet 1.9.4 + Geoman</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Visor geoespacial interactivo para trazado de polígonos agrícolas, con cálculo de superficie en hectáreas (ha), centroide y limitador estricto dentro de la frontera argentina.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-md">GRÁFICAS 5A</span>
                        <h3 class="font-bold text-lg text-[#100b07]">Chart.js 4.4</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Motor de gráficas responsivas con modos Continuo e Interanual, presets rápidos (1m, 3m, 1a, 3a, 5a) y navegación fluida con flechas entre variables satelitales.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded-md">SEGURIDAD</span>
                        <h3 class="font-bold text-lg text-[#100b07]">JWT (HS256) + Bcrypt</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Control de acceso basado en roles (Admin, Propietario, Operador) con soporte para sesiones efímeras sin persistencia para visitantes agricultores o técnicos.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-teal-800 bg-teal-100 px-2 py-0.5 rounded-md">PERSISTENCIA</span>
                        <h3 class="font-bold text-lg text-[#100b07]">SQLAlchemy 2.0 ORM</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Capa de datos agnóstica configurada para operar con SQLite 3 localmente (earth2worlds.db) y PostgreSQL en entornos de producción en la nube.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-rose-800 bg-rose-100 px-2 py-0.5 rounded-md">REPORTING</span>
                        <h3 class="font-bold text-lg text-[#100b07]">html2pdf.js + jsPDF</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Compilador de informes técnicos en PDF en tiempo real con renderizado vectorial de curvas temporales, metadatos del lote y plan trienal recomendado.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 2: GITHUB Y RENDER.COM -->
        <section id="sec-nube" class="hidden space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-sky-100 border border-sky-400 flex items-center justify-center text-2xl">☁️</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Despliegue Continuo (CI/CD) en GitHub y Render.com</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Estrategia de ramas unificadas y despliegue automatizado en la nube.</p>
                    </div>
                </div>

                <div class="space-y-4 text-xs sm:text-sm text-[#382a21] leading-relaxed">
                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07] flex items-center gap-2">
                            <span>🌿</span> Rama Principal de Despliegue: <code class="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-300">main</code>
                        </h3>
                        <p>Todas las características y módulos (autenticación JWT, base de datos, visor satelital NASA, motor RotaTerra, visualizador de 5 años y generador de PDF) están consolidados en la rama <code>main</code>, y replicados de forma idéntica en las ramas <code>rotaterra-completo</code> y <code>RENDER-earth2worlds-todo-junto</code>.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07] flex items-center gap-2">
                            <span>🚀</span> Configuración del Web Service en Render.com
                        </h3>
                        <ul class="list-disc pl-5 space-y-1.5 text-xs text-[#5c4636]">
                            <li><strong>Entorno de Ejecución:</strong> Python 3 en contenedor Linux.</li>
                            <li><strong>Comando de Construcción (Build Command):</strong> <code>pip install -r requirements.txt</code></li>
                            <li><strong>Comando de Inicio (Start Command):</strong> <code>uvicorn app.main:app --host 0.0.0.0 --port $PORT</code></li>
                            <li><strong>Puerto Dinámico:</strong> Uvicorn escucha en la variable <code>$PORT</code> inyectada dinámicamente por la infraestructura de Render.</li>
                        </ul>
                    </div>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 3: BASES DE DATOS Y NASA -->
        <section id="sec-satelites" class="hidden space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-amber-100 border border-amber-400 flex items-center justify-center text-2xl">🛰️</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Bases de Datos Edáficas y Constelación Satelital NASA</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">34 años de historia climática (1991–2025) y cartografía agronómica nacional.</p>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07] flex items-center gap-2"><span>🌦️</span> NASA POWER (34 Años)</h3>
                        <p class="text-xs text-[#5c4636]">Serie agroclimática continua de 1991 a 2025. Registra radiación incidente, temperaturas extremas diarias (máxima y mínima), y evapotranspiración de referencia FAO-56 ($ET_0$).</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07] flex items-center gap-2"><span>🌧️</span> NASA GPM IMERG</h3>
                        <p class="text-xs text-[#5c4636]">Constelación de radar y microondas para estimación de precipitación diaria acumulada a 10 km de resolución. Determina el régimen pluviométrico del lote.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07] flex items-center gap-2"><span>🌱</span> NASA HLS (Sentinel-2 / Landsat)</h3>
                        <p class="text-xs text-[#5c4636]">Imágenes multiespectrales a 30 metros de resolución espacial para calcular el índice NDVI de vegetación activa y vigor fotosintético frente a la media de 5 años.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07] flex items-center gap-2"><span>💧</span> NASA SMAP (9km / 36km)</h3>
                        <p class="text-xs text-[#5c4636]">Radiometría pasiva en banda L para estimar la humedad del suelo en la zona radicular (0–100 cm) y en superficie en unidades volumétricas ($m^3/m^3$).</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07] flex items-center gap-2"><span>⛰️</span> NASADEM SRTM (30m)</h3>
                        <p class="text-xs text-[#5c4636]">Modelo digital de elevación que entrega cota altimétrica precisa (m s. n. m. / m a.s.l.), cálculo trigonométrico de pendiente (%) y dirección de escurrimiento.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07] flex items-center gap-2"><span>🗺️</span> GeoINTA & Catálogo de Suelos</h3>
                        <p class="text-xs text-[#5c4636]">Cartas edáficas del INTA y HWSD v2.0 para texturas (franco arenoso a arcilloso), retención de agua útil en 1 metro de perfil y banco agronómico de pH.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 4: MOTOR DE ROTACIONES -->
        <section id="sec-rotaterra" class="hidden space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-emerald-100 border border-emerald-400 flex items-center justify-center text-2xl">🔄</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Motor de Recomendación y Plan Trienal RotaTerra</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Algoritmo multicriterio ponderado de sucesión agroclimática y salud de suelos.</p>
                    </div>
                </div>

                <div class="space-y-4 text-xs sm:text-sm text-[#382a21] leading-relaxed">
                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">1. Evaluación de Restricciones Duras y Blandas</h3>
                        <p>El motor contrasta el lote contra 10 reglas agroclimáticas fundamentales: temperatura de suelo para siembra, acumulación de grados día (°Cd), riesgo de heladas tardías, balance hídrico acumulado, agua útil en siembra, profundidad efectiva del perfil edáfico, tolerancia a salinidad, textura y pH.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">2. Algoritmo Anti-Monocultivo y Encadenamiento Trienal</h3>
                        <p>Para evitar degradación de suelos y acumulación de malezas o patógenos específicos:</p>
                        <ul class="list-disc pl-5 space-y-1 text-xs text-[#5c4636]">
                            <li><strong>Año 1 (Próxima Campaña):</strong> Evalúa los cultivos viables y selecciona la mejor opción agronómica según el cultivo cosechado recientemente.</li>
                            <li><strong>Año 2 (Siguiente Campaña):</strong> Encadena el ganador de Año 1 al historial del lote y excluye su especie para respetar el intervalo sanitario del INTA.</li>
                            <li><strong>Año 3 (Tercera Campaña):</strong> Encadena Año 2 y Año 1 cerrando el ciclo con alternancia biológica entre gramíneas y leguminosas.</li>
                        </ul>
                    </div>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 5: SOLUCIÓN RENDER (HLS / SMAP) -->
        <section id="sec-render-fix" class="hidden space-y-6">
            <div class="bg-white border-2 border-emerald-600 rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-emerald-100 border border-emerald-400 flex items-center justify-center text-2xl">🛠️</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">¿Por qué no funcionan Active Vegetation y Sowing Moisture en Render.com?</h2>
                        <p class="text-xs sm:text-sm text-emerald-800 font-semibold">Explicación técnica de la causa raíz y guía paso a paso de resolución.</p>
                    </div>
                </div>

                <div class="p-5 rounded-2xl bg-amber-50 border border-amber-300 text-xs sm:text-sm text-amber-950 space-y-2">
                    <h3 class="font-bold text-base text-amber-900 flex items-center gap-1.5">
                        <span>⚠️</span> Diagnóstico Técnico: Credenciales de NASA Earthdata Faltantes
                    </h3>
                    <p class="leading-relaxed">
                        A diferencia de NASA POWER y NASADEM que son de consulta pública irrestricta, <strong>NASA HLS (Sentinel-2)</strong> y <strong>NASA SMAP (Humedad radicular)</strong> requieren autenticación obligatoria mediante <em>HTTP Basic Auth</em> contra el sistema <strong>NASA Earthdata Login</strong>.
                    </p>
                    <p class="leading-relaxed">
                        En el backend (<code>rotaterra/fuentes/hls.py</code> y <code>rotaterra/fuentes/smap.py</code>), el código busca las variables <code>EARTHDATA_USERNAME</code> y <code>EARTHDATA_PASSWORD</code>. Si no existen, lanza la excepción <code>FaltanCredenciales</code> y FastAPI retorna <strong>HTTP 503</strong>.
                    </p>
                    <p class="leading-relaxed font-semibold">
                        Localmente funciona porque tu archivo <code>.env</code> tiene las credenciales. En GitHub y Render, el archivo <code>.env</code> está ignorado por seguridad, por lo que Render no las tiene configuradas de forma predeterminada.
                    </p>
                </div>

                <div class="p-5 rounded-2xl bg-emerald-50 border border-emerald-300 text-xs sm:text-sm text-emerald-950 space-y-3">
                    <h3 class="font-bold text-base text-emerald-900 flex items-center gap-1.5">
                        <span>✅</span> Pasos para solucionarlo en 2 minutos en Render.com:
                    </h3>
                    <ol class="list-decimal pl-5 space-y-2 text-xs text-[#241810]">
                        <li>Ingresa a tu cuenta en <a href="https://dashboard.render.com" target="_blank" class="text-emerald-700 underline font-bold">dashboard.render.com</a>.</li>
                        <li>Haz clic en tu servicio web de <strong>Earth2Worlds</strong>.</li>
                        <li>En el menú de la izquierda, entra a <strong>Environment</strong>.</li>
                        <li>En la sección <strong>Environment Variables</strong>, haz clic en el botón <strong>Add Environment Variable</strong>.</li>
                        <li>Agrega estas dos variables (utilizando tu cuenta de Earthdata):
                            <div class="mt-2 p-3 bg-white rounded-xl border border-emerald-300 font-mono text-xs space-y-1">
                                <div><strong class="text-emerald-800">EARTHDATA_USERNAME</strong> = &lt;tu_usuario_de_nasa_earthdata&gt;</div>
                                <div><strong class="text-emerald-800">EARTHDATA_PASSWORD</strong> = &lt;tu_contraseña_de_nasa_earthdata&gt;</div>
                            </div>
                        </li>
                        <li>Haz clic en <strong>Save Changes</strong>. Render desplegará el cambio automáticamente y tanto Active Vegetation como Sowing Moisture comenzarán a funcionar de inmediato en la web.</li>
                    </ol>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 6: AUDITORÍA TEXTUAL -->
        <section id="sec-inconsistencias" class="hidden space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-rose-100 border border-rose-400 flex items-center justify-center text-2xl">🔍</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Auditoría de Inconsistencias Textuales y Correcciones</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Detalle de incongruencias detectadas y resueltas en el código fuente.</p>
                    </div>
                </div>

                <div class="space-y-3 text-xs sm:text-sm text-[#382a21]">
                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-1">
                        <strong class="text-rose-900 block font-bold">1. Corrección de Unidades de Evaporación de Suelo (Tarjeta 5):</strong>
                        <p class="text-xs text-[#5c4636]">Se normalizó la visualización para que siempre reporte en <code>mm/day</code> (EN) y <code>mm/día</code> (ES), eliminando cualquier valor erróneo de radiación energética en dicha tarjeta.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-1">
                        <strong class="text-rose-900 block font-bold">2. Corrección del Tartamudeo de Centroide (Paso 3):</strong>
                        <p class="text-xs text-[#5c4636]">Se eliminó la duplicación que generaba <code>Centroide: Centroide: [-33.65, -65.48] · 2.32 ha</code>. Ahora muestra limpiamente <code>Centroid: [-33.6527, -65.4786]</code>.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-1">
                        <strong class="text-rose-900 block font-bold">3. Traducción Completa de Tarjetas de Cultivo y Explicaciones:</strong>
                        <p class="text-xs text-[#5c4636]">Tanto los nombres compuestos (Grain Sorghum, Early Soybean, Late Corn), como las explicaciones de selección comparativa y los dictámenes (Recommended / Recommended), ahora se traducen en su totalidad al inglés sin textos residuales en español.</p>
                    </div>

                    <div class="p-4 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-1">
                        <strong class="text-rose-900 block font-bold">4. Navegación Fluida entre Gráficos con Flechas y Teclado:</strong>
                        <p class="text-xs text-[#5c4636]">Se agregaron botones ◀ y ▶ en el encabezado del modal de telemetría y atajos de teclado (flechas izquierda/derecha) para recorrer los 5 gráficos sin tener que cerrar y abrir.</p>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <!-- Script de Pestañas Interactivas -->
    <script>
        function cambiarPestana(id) {
            const tabs = ['stack', 'nube', 'satelites', 'rotaterra', 'render-fix', 'inconsistencias'];
            tabs.forEach(t => {
                const sec = document.getElementById('sec-' + t);
                const btn = document.getElementById('tab-' + t);
                if (t === id) {
                    if (sec) sec.classList.remove('hidden');
                    if (btn) btn.classList.add('active');
                } else {
                    if (sec) sec.classList.add('hidden');
                    if (btn) btn.classList.remove('active');
                }
            });
        }
    </script>
</body>
</html>
"""
    # Guardar en static y en la raíz
    with open("static/documento_tecnologia_earth2worlds.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    with open("documento_tecnologia_earth2worlds.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Documentos HTML generados con éxito en static/ y raíz.")

if __name__ == "__main__":
    generar_docx()
    generar_html()
