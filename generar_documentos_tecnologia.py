# -*- coding: utf-8 -*-
"""
Generador de Documentación Técnica de Arquitectura de Earth2Worlds / RotaTerra:
- documento_tecnologia_earth2worlds.docx (Word formal de especificación tecnológica)
- static/documento_tecnologia_earth2worlds.html (HTML Interactivo)
- documento_tecnologia_earth2worlds.html (Copia en raíz)
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

def generar_docx():
    doc = docx.Document()
    
    # Márgenes estándar de 1 pulgada
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)

    styles = doc.styles
    normal_style = styles['Normal']
    normal_style.font.name = 'Calibri'
    normal_style.font.size = Pt(11)
    normal_style.font.color.rgb = RGBColor(30, 41, 59)

    # Portada / Título Principal
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_badge = p_title.add_run("EARTH2WORLDS • ROTATERRA AGROCLIMATIC PLATFORM\n")
    run_badge.font.size = Pt(10)
    run_badge.font.bold = True
    run_badge.font.color.rgb = RGBColor(22, 163, 74)

    run_title = p_title.add_run("Especificación Técnica de Arquitectura, Tecnologías Cloud, Pipeline Satelital y Motor de Rotaciones")
    run_title.font.size = Pt(20)
    run_title.font.bold = True
    run_title.font.color.rgb = RGBColor(15, 23, 42)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_sub = p_sub.add_run("Documento de arquitectura de software, infraestructura de despliegue continuo, catálogos edafológicos, series históricas NASA de 34 años y modelos fisiológicos agronómicos.")
    run_sub.font.size = Pt(10.5)
    run_sub.font.italic = True
    run_sub.font.color.rgb = RGBColor(100, 116, 139)

    doc.add_paragraph("—" * 50).alignment = WD_ALIGN_PARAGRAPH.CENTER

    # 1. RESUMEN EJECUTIVO
    doc.add_heading("1. Resumen Ejecutivo del Sistema", level=1)
    doc.add_paragraph(
        "Earth2Worlds / RotaTerra es una plataforma web agroclimática orientada a la delimitación territorial de parcelas "
        "agrícolas en la República Argentina, el análisis multi-satelital histórico de 34 años (1991–2025) con telemetría de la NASA, "
        "y el cálculo algorítmico de planes trienales de rotación de cultivos para mitigar la degradación edáfica, "
        "reducir la presión de plagas y malezas y maximizar la resiliencia hídrica."
    )

    # 2. STACK TECNOLÓGICO
    doc.add_heading("2. Stack Tecnológico y Componentes de Software", level=1)
    doc.add_paragraph(
        "El sistema adopta una arquitectura desacoplada SPA (Single Page Application) asistida por un backend asíncrono en FastAPI:"
    )

    table_stack = doc.add_table(rows=1, cols=3)
    table_stack.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table_stack.rows[0].cells
    hdr[0].text = "Capa / Módulo"
    hdr[1].text = "Tecnología Empleada"
    hdr[2].text = "Función y Alcance Técnico"
    for c in hdr:
        set_cell_background(c, "1E293B")
        for p in c.paragraphs:
            for r in p.runs:
                r.font.bold = True
                r.font.color.rgb = RGBColor(255, 255, 255)

    items_stack = [
        ("Backend Framework", "FastAPI (Python 3.12+ / 3.14)", "Servidor API REST asíncrono con validación estricta de esquemas Pydantic v2 y OpenAPI."),
        ("Servidor ASGI", "Uvicorn (Worker uvloop)", "Servidor de sockets HTTP asíncrono sin bloqueo de E/S, adaptado a puertos dinámicos ($PORT)."),
        ("Capa de Persistencia", "SQLAlchemy 2.0 ORM", "Mapeo relacional agnóstico compatible con SQLite 3 (local) y PostgreSQL (producción)."),
        ("Autenticación y RBAC", "JWT (HS256) + Passlib (Bcrypt)", "Control de acceso basado en roles (Admin, Propietario, Operador) y sesiones efímeras de invitado."),
        ("Frontend & Interfaz", "HTML5 Semántico + Tailwind CSS", "Interfaz reactiva estructurada en paleta agronómica de bajo consumo de recursos."),
        ("Motor Geoespacial", "Leaflet 1.9.4 + Geoman (L.PM)", "Visor cartográfico interactivo, captura vectorial de parcelas y validación territorial argentina."),
        ("Series Temporales", "Chart.js 4.4", "Renderizado de series continuas de 5 años y comparativa interanual con selección de presets."),
        ("Generación de Reportes", "html2pdf.js + jsPDF + html2canvas", "Compilación de informes técnicos agronómicos en PDF con curvas satelitales y métricas de campo."),
        ("Internacionalización (i18n)", "Módulo i18n reactivo (JS)", "Soporte bilingüe integral (Inglés / Español) en tiempo real con arranque por defecto en inglés.")
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
    doc.add_heading("3. Bases de Datos Edáficas y Constelación Satelital NASA", level=1)
    doc.add_paragraph(
        "El motor agronómico integra un conjunto de bases de datos de observación terrestre y cartografía agropecuaria:"
    )

    p_sources = doc.add_paragraph()
    p_sources.add_run("1. NASA POWER (Agroclimatology API, 1991–2025 - 34 Años):\n").bold = True
    p_sources.add_run(
        "Provee series diarias de radiación solar incidente (ALLSKY_SFC_SW_DWN en MJ/m²/día), temperaturas extremas superficiales (T2M_MAX, T2M_MIN en °C), "
        "humedad relativa, velocidad del viento y evapotranspiración de referencia Penman-Monteith (ET₀ en mm/día).\n\n"
    )

    p_sources.add_run("2. NASA GPM IMERG (Global Precipitation Measurement, 10 km):\n").bold = True
    p_sources.add_run(
        "Constelación multi-satelital de radar y microondas para estimación de precipitación diaria y acumulada por período (lluvia_mm).\n\n"
    )

    p_sources.add_run("3. NASA HLS (Harmonized Landsat Sentinel-2, 30 m):\n").bold = True
    p_sources.add_run(
        "Imágenes ópticas multiespectrales de 30 metros de resolución espacial para la cuantificación del Índice de Vegetación de Diferencia Normalizada (NDVI) "
        "y evaluación del vigor fotosintético actual frente a la media histórica.\n\n"
    )

    p_sources.add_run("4. NASA SMAP (Soil Moisture Active Passive, 9 km / 36 km EASE-Grid):\n").bold = True
    p_sources.add_run(
        "Radiometría de microondas en banda L (1.4 GHz) que mide la humedad volumétrica del suelo en la capa superficial (0–5 cm) "
        "y en la zona radicular (0–100 cm) en unidades de m³/m³.\n\n"
    )

    p_sources.add_run("5. NASADEM SRTM (30 m):\n").bold = True
    p_sources.add_run(
        "Modelo digital de elevación de 30 metros para cálculo de cota altimétrica sobre el nivel del mar, gradiente de pendiente (%) "
        "y orientación del drenaje hídrico de la parcela.\n\n"
    )

    p_sources.add_run("6. Cartografía GeoINTA y HWSD v2.0:\n").bold = True
    p_sources.add_run(
        "Cartas de suelo oficiales de la República Argentina y base global armonizada HWSD para caracterización de textura edáfica, "
        "capacidad de retención de agua útil (mm de 0 a 100 cm), salinidad y pH.\n\n"
    )

    p_sources.add_run("7. Catálogo Ecofisiológico de Cultivos (INTA / FAO Ecocrop):\n").bold = True
    p_sources.add_run(
        "Parámetros ecofisiológicos de temperatura base, requerimientos térmicos de ciclo (°Cd), consumo hídrico y sensibilidad fitosanitaria "
        "para Maíz, Soja, Girasol, Sorgo granífero, Maní, Trigo, Cebada y Alfalfa."
    )

    # 4. MOTOR DE ROTACIONES
    doc.add_heading("4. Algoritmo del Motor de Rotaciones RotaTerra (Plan Trienal)", level=1)
    doc.add_paragraph(
        "El motor agronómico (`rotaterra.agronomos.motor`) ejecuta un proceso de evaluación multicriterio ponderado de 0 a 100%:"
    )
    p_motor = doc.add_paragraph()
    p_motor.add_run("• Reglas Críticas Excluyentes (Hard Constraints): ").bold = True
    p_motor.add_run("Restricción biológica contra monocultivo sucesivo, tolerancia de pH edáfico y piso térmico mínimo de siembra.\n")
    p_motor.add_run("• Criterios Agroclimáticos de Adaptación (Soft Constraints): ").bold = True
    p_motor.add_run("Balance hídrico del ciclo respecto a la evapotranspiración de demanda, probabilidad de heladas tempranas/tardías y acumulación de grados día (°Cd).\n")
    p_motor.add_run("• Algoritmo de Encadenamiento Trienal Anti-Monocultivo: ").bold = True
    p_motor.add_run(
        "Año 1 determina el cultivo óptimo según el cultivo precedente. "
        "Año 2 encadena el ganador del Año 1 y excluye su especie para respetar el intervalo sanitario del INTA. "
        "Año 3 encadena Año 2 y Año 1 cerrando el ciclo trienal mediante alternancia biológica entre gramíneas y leguminosas."
    )

    # 5. AUTENTICACIÓN NASA EARTHDATA
    doc.add_heading("5. Infraestructura de Autenticación y Acceso Seguro a NASA Earthdata", level=1)
    doc.add_paragraph(
        "La arquitectura de conectores de Earth2Worlds categoriza las fuentes de datos según su esquema de autorización:"
    )
    p_auth = doc.add_paragraph()
    p_auth.add_run("• APIs de Consulta Abierta: ").bold = True
    p_auth.add_run("NASA POWER y NASADEM SRTM operan bajo protocolos públicos REST/WCS que no requieren cabeceras de autorización HTTP.\n")
    p_auth.add_run("• Capas Multiespectrales Protegidas (NASA Earthdata Login): ").bold = True
    p_auth.add_run(
        "NASA HLS (Sentinel-2) y NASA SMAP requieren autenticación HTTP Basic contra los repositorios LP DAAC y NSIDC. "
        "Los conectores del backend leen las credenciales criptográficas desde las variables de entorno del sistema operativo "
        "(`EARTHDATA_USERNAME` y `EARTHDATA_PASSWORD`), garantizando el desacoplamiento seguro entre el código fuente y las credenciales de producción."
    )

    # 6. INTERNACIONALIZACIÓN Y NORMALIZACIÓN DE UNIDADES
    doc.add_heading("6. Sistema de Internacionalización (i18n) y Normalización de Unidades Físicas", level=1)
    doc.add_paragraph(
        "La plataforma implementa un motor reactivo de internacionalización en JavaScript con soporte bilingüe integral (Inglés / Español) "
        "y normalización estricta de variables físicas:"
    )
    p_i18n = doc.add_paragraph()
    p_i18n.add_run("• Temperatura: ").bold = True
    p_i18n.add_run("Grados Celsius (°C) para valores superficiales y Grados Día base (°Cd) para suma térmica de ciclo.\n")
    p_i18n.add_run("• Humedad Edáfica: ").bold = True
    p_i18n.add_run("Fracción volumétrica de agua en metros cúbicos por metro cúbico (m³/m³) y porcentaje de agua útil disponible (%).\n")
    p_i18n.add_run("• Precipitación y Evapotranspiración: ").bold = True
    p_i18n.add_run("Milímetros (mm) de lámina de agua acumulada y milímetros por día (mm/day en inglés; mm/día en español) para tasas de evapotranspiración Penman-Monteith (ET₀).\n")
    p_i18n.add_run("• Topografía y Rumbo: ").bold = True
    p_i18n.add_run("Metros sobre el nivel del mar (m a.s.l. en inglés; m s.n.m. en español), pendiente de escurrimiento en porcentaje (%) y rumbo azimutal direccional.")

    docx_path = "documento_tecnologia_earth2worlds.docx"
    doc.save(docx_path)
    print(f"Documento DOCX generado: {os.path.abspath(docx_path)}")

def generar_html():
    html_content = """<!DOCTYPE html>
<html lang="es" class="scroll-smooth">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Earth2Worlds / RotaTerra • Especificación Técnica de Arquitectura</title>
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
                    <p class="text-xs text-[#785843] font-medium">Especificación Técnica de Arquitectura, Tecnologías Cloud, Pipeline Satelital y Algoritmos Agronómicos</p>
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
                ☁️ 2. Infraestructura CI/CD
            </button>
            <button onclick="cambiarPestana('satelites')" id="tab-satelites" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🛰️ 3. Bases de Datos & NASA
            </button>
            <button onclick="cambiarPestana('rotaterra')" id="tab-rotaterra" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🔄 4. Motor de Rotaciones
            </button>
            <button onclick="cambiarPestana('earthdata')" id="tab-earthdata" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🔒 5. Autenticación Earthdata
            </button>
            <button onclick="cambiarPestana('i18n')" id="tab-i18n" class="tab-btn px-4 py-2 rounded-xl text-xs sm:text-sm font-bold text-[#5c4636] hover:bg-[#ede3da] transition whitespace-nowrap">
                🌐 6. Internacionalización & Metrología
            </button>
        </div>
    </nav>

    <!-- Contenido Principal -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 py-8 space-y-8">

        <!-- SECCIÓN 1: STACK TECNOLÓGICO -->
        <section id="sec-stack" class="space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-emerald-100 border border-emerald-400 flex items-center justify-center text-2xl">⚡</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Stack Tecnológico de Alto Rendimiento</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Arquitectura desacoplada SPA con backend asíncrono en FastAPI y frontend de baja huella de memoria.</p>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 pt-4">
                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-md">BACKEND</span>
                        <h3 class="font-bold text-lg text-[#100b07]">FastAPI + Python 3.14</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Framework asíncrono con validación estricta Pydantic v2, serialización de alto rendimiento y documentación automática OpenAPI.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-sky-800 bg-sky-100 px-2 py-0.5 rounded-md">GEOESPACIAL</span>
                        <h3 class="font-bold text-lg text-[#100b07]">Leaflet 1.9.4 + Geoman</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Visor cartográfico interactivo para trazado vectorial de parcelas agrícolas con cálculo geométrico de superficie y centroide.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-md">SERIES TEMPORALES</span>
                        <h3 class="font-bold text-lg text-[#100b07]">Chart.js 4.4</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Motor de visualización gráfica para series temporales de 5 años: modos Continuo e Interanual con 4 KPIs calculados en vivo.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-amber-800 bg-amber-100 px-2 py-0.5 rounded-md">SEGURIDAD</span>
                        <h3 class="font-bold text-lg text-[#100b07]">JWT (HS256) + Bcrypt</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Matriz de control de acceso RBAC (Admin, Propietario, Operador) y soporte para sesiones efímeras de invitado sin ensuciar la base de datos.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-teal-800 bg-teal-100 px-2 py-0.5 rounded-md">PERSISTENCIA</span>
                        <h3 class="font-bold text-lg text-[#100b07]">SQLAlchemy 2.0 ORM</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Capa de persistencia agnóstica configurada para desarrollo en SQLite 3 (earth2worlds.db) y producción en PostgreSQL.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <span class="text-xs font-mono font-bold text-rose-800 bg-rose-100 px-2 py-0.5 rounded-md">REPORTING</span>
                        <h3 class="font-bold text-lg text-[#100b07]">html2pdf.js + jsPDF</h3>
                        <p class="text-xs text-[#5c4636] leading-relaxed">Generación de informes técnicos agronómicos en PDF en tiempo real con renderizado de curvas satelitales y atributos del lote.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 2: INFRAESTRUCTURA CI/CD -->
        <section id="sec-nube" class="hidden space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-sky-100 border border-sky-400 flex items-center justify-center text-2xl">☁️</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Infraestructura de Despliegue Continuo (CI/CD)</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Estrategia de ramas unificadas en GitHub y hosting cloud en Render.com.</p>
                    </div>
                </div>

                <div class="space-y-4 text-xs sm:text-sm text-[#382a21] leading-relaxed">
                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">Rama Oficial de Despliegue: <code class="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-300">main</code></h3>
                        <p>La rama <code>main</code> contiene el código consolidado y validado mediante suite de tests automatizados (pytest), sincronizada de forma espejo con <code>rotaterra-completo</code> y <code>RENDER-earth2worlds-todo-junto</code>.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">Parámetros del Web Service en Render.com</h3>
                        <ul class="list-disc pl-5 space-y-1.5 text-xs text-[#5c4636]">
                            <li><strong>Entorno de Ejecución:</strong> Python 3 sobre contenedor Linux.</li>
                            <li><strong>Build Command:</strong> <code>pip install -r requirements.txt</code></li>
                            <li><strong>Start Command:</strong> <code>uvicorn app.main:app --host 0.0.0.0 --port $PORT</code></li>
                            <li><strong>Enlace de Red:</strong> Uvicorn escucha en la interfaz 0.0.0.0 utilizando la variable <code>$PORT</code> provista por el router de Render.</li>
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
                        <p class="text-xs sm:text-sm text-[#785843]">Integración de 34 años de registros agroclimáticos y cartografía de suelos del INTA.</p>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07]">🌦️ NASA POWER (34 Años, 1991–2025)</h3>
                        <p class="text-xs text-[#5c4636]">Serie agroclimática continua de radiación solar incidente (MJ/m²/día), temperaturas extremas superficiales (°C) y evapotranspiración de referencia Penman-Monteith (ET₀ en mm/día).</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07]">🌧️ NASA GPM IMERG (10 km)</h3>
                        <p class="text-xs text-[#5c4636]">Algoritmo calibrado por microondas y radar satelital que entrega precipitación acumulada diaria y por campaña agrícola (lluvia_mm).</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07]">🌱 NASA HLS (Sentinel-2 / Landsat, 30 m)</h3>
                        <p class="text-xs text-[#5c4636]">Observación multiespectral de 30 metros de resolución espacial para cuantificación del índice NDVI y vigor fotosintético actual.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07]">💧 NASA SMAP (9 km / 36 km EASE-Grid)</h3>
                        <p class="text-xs text-[#5c4636]">Radiometría pasiva en banda L para estimación de humedad volumétrica del suelo en la zona radicular (0–100 cm) en m³/m³.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07]">⛰️ NASADEM SRTM (30 m)</h3>
                        <p class="text-xs text-[#5c4636]">Modelo digital de elevación que entrega cota altimétrica sobre el nivel del mar, pendiente de escurrimiento (%) y rumbo azimutal de drenaje.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-sm text-[#100b07]">🗺️ GeoINTA & Catálogo HWSD</h3>
                        <p class="text-xs text-[#5c4636]">Cartas de suelo de la República Argentina para determinación de texturas edáficas, capacidad de agua útil en 1 metro y rangos agronómicos de pH.</p>
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
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Algoritmo del Motor de Rotaciones RotaTerra (Plan Trienal)</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Evaluación multicriterio ponderada de sucesión agroclimática y balance biológico de nutrientes.</p>
                    </div>
                </div>

                <div class="space-y-4 text-xs sm:text-sm text-[#382a21] leading-relaxed">
                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">1. Evaluación de Restricciones Duras y Blandas</h3>
                        <p>El motor analiza 10 reglas agroclimáticas fundamentales: temperatura de suelo para siembra, acumulación de grados día (°Cd), riesgo de heladas tardías, balance hídrico acumulado, agua útil en siembra, profundidad efectiva del perfil edáfico, tolerancia a salinidad, textura y pH.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">2. Encadenamiento Trienal Anti-Monocultivo</h3>
                        <ul class="list-disc pl-5 space-y-1.5 text-xs text-[#5c4636]">
                            <li><strong>Año 1 (Próxima Campaña):</strong> Determina el cultivo óptimo según el cultivo cosechado recientemente y la telemetría histórica del lote.</li>
                            <li><strong>Año 2 (Siguiente Campaña):</strong> Encadena el ganador del Año 1 al historial del lote y excluye su especie para respetar el intervalo sanitario del INTA.</li>
                            <li><strong>Año 3 (Tercera Campaña):</strong> Encadena Año 2 y Año 1 cerrando el ciclo trienal mediante alternancia biológica equilibrada de gramíneas y leguminosas.</li>
                        </ul>
                    </div>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 5: AUTENTICACIÓN EARTHDATA -->
        <section id="sec-earthdata" class="hidden space-y-6">
            <div class="bg-white border-2 border-emerald-600 rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-emerald-100 border border-emerald-400 flex items-center justify-center text-2xl">🔒</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Infraestructura de Autenticación y Acceso Seguro a NASA Earthdata</h2>
                        <p class="text-xs sm:text-sm text-emerald-800 font-semibold">Mecanismo de autorización de los conectores satelitales en entornos cloud y producción.</p>
                    </div>
                </div>

                <div class="space-y-4 text-xs sm:text-sm text-[#382a21] leading-relaxed">
                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">Diferenciación de Capas por Nivel de Autorización</h3>
                        <p>Las APIs de <strong>NASA POWER</strong> (clima diario) y <strong>NASADEM</strong> (elevación SRTM) operan sobre servidores públicos que no requieren cabeceras de autorización HTTP. En contraste, las misiones <strong>NASA HLS (Sentinel-2)</strong> y <strong>NASA SMAP (Humedad radicular)</strong> requieren autenticación HTTP Basic contra los centros de distribución <em>LP DAAC</em> y <em>NSIDC</em>.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">Inyección Segura de Credenciales en Entornos Cloud</h3>
                        <p>Los conectores en <code>rotaterra/fuentes/hls.py</code> y <code>rotaterra/fuentes/smap.py</code> leen las credenciales criptográficas mediante variables de entorno:</p>
                        <div class="p-3 bg-white rounded-xl border border-[#dfd2c6] font-mono text-xs space-y-1">
                            <div><strong class="text-emerald-800">EARTHDATA_USERNAME</strong>: Identificador de usuario registrado en NASA Earthdata Login.</div>
                            <div><strong class="text-emerald-800">EARTHDATA_PASSWORD</strong>: Token / Contraseña de acceso autorizada.</div>
                        </div>
                        <p class="text-xs text-[#5c4636]">Este desacoplamiento previene la exposición de secretos en el control de versiones (Git) y permite configurar las credenciales de manera aislada en el panel de variables de entorno del proveedor de infraestructura cloud.</p>
                    </div>
                </div>
            </div>
        </section>

        <!-- SECCIÓN 6: INTERNACIONALIZACIÓN Y METROLOGÍA -->
        <section id="sec-i18n" class="hidden space-y-6">
            <div class="bg-white border-2 border-[#8c6547] rounded-3xl p-6 sm:p-8 shadow-sm space-y-4">
                <div class="flex items-center gap-3">
                    <span class="w-12 h-12 rounded-2xl bg-sky-100 border border-sky-400 flex items-center justify-center text-2xl">🌐</span>
                    <div>
                        <h2 class="font-extrabold text-2xl text-[#100b07]">Sistema de Internacionalización (i18n) y Normalización de Unidades</h2>
                        <p class="text-xs sm:text-sm text-[#785843]">Arquitectura bilingüe reactiva y estandarización de magnitudes agroclimáticas.</p>
                    </div>
                </div>

                <div class="space-y-4 text-xs sm:text-sm text-[#382a21] leading-relaxed">
                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">Motor Reactivo Bilingüe en JavaScript</h3>
                        <p>El módulo <code>static/js/i18n.js</code> mantiene diccionarios estructurados para inglés y español, aplicando traducción inmediata sin recarga de página sobre etiquetas del DOM (<code>data-i18n</code>), placeholders, títulos de reglas agronómicas y comparativas directas de campo vs requerimiento óptimo.</p>
                    </div>

                    <div class="p-5 rounded-2xl bg-[#faf7f2] border border-[#dfd2c6] space-y-2">
                        <h3 class="font-bold text-base text-[#100b07]">Matriz de Normalización de Unidades Agroclimáticas</h3>
                        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-2">
                            <div class="p-3 bg-white rounded-xl border border-[#dfd2c6]">
                                <strong class="text-[#100b07] block text-xs">Temperatura & Grados Día</strong>
                                <span class="text-xs text-[#5c4636]">Grados Celsius (°C) para extremos térmicos diarios y Grados Día (°Cd) para acumulación fenológica de ciclo.</span>
                            </div>
                            <div class="p-3 bg-white rounded-xl border border-[#dfd2c6]">
                                <strong class="text-[#100b07] block text-xs">Humedad de Suelo</strong>
                                <span class="text-xs text-[#5c4636]">Retención volumétrica de agua en m³/m³ (0-100 cm) y porcentaje de agua útil disponible (%).</span>
                            </div>
                            <div class="p-3 bg-white rounded-xl border border-[#dfd2c6]">
                                <strong class="text-[#100b07] block text-xs">Precipitación & Evapotranspiración</strong>
                                <span class="text-xs text-[#5c4636]">Milímetros acumulados (mm) para lluvia y milímetros por día (mm/day / mm/día) para evapotranspiración Penman-Monteith (ET₀).</span>
                            </div>
                            <div class="p-3 bg-white rounded-xl border border-[#dfd2c6]">
                                <strong class="text-[#100b07] block text-xs">Topografía & Relieve</strong>
                                <span class="text-xs text-[#5c4636]">Cota en metros sobre el nivel del mar (m a.s.l. / m s.n.m.), pendiente (%) y rumbo direccional azimutal.</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </section>

    </main>

    <!-- Script de Pestañas Interactivas -->
    <script>
        function cambiarPestana(id) {
            const tabs = ['stack', 'nube', 'satelites', 'rotaterra', 'earthdata', 'i18n'];
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
    with open("static/documento_tecnologia_earth2worlds.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    with open("documento_tecnologia_earth2worlds.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("Documentos HTML generados con éxito en static/ y raíz.")

if __name__ == "__main__":
    generar_docx()
    generar_html()
