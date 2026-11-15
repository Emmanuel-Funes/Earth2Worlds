# Earth2Worlds · RotaTerra Agroclimatic Intelligence Platform

**Earth2Worlds** is a satellite-powered territorial intelligence and crop rotation planning platform developed for the **NASA Space Apps Challenge 2026**.
RotaTerra connects real-time and historical multi-mission satellite telemetries (34 years of NASA POWER, GPM IMERG, HLS, SMAP, NASADEM, MODIS, VIIRS, ECOSTRESS) to evaluate agroclimatic suitability, soil thermodynamics, and physiological crop requirements, generating a triennial (3-year) sustainable crop rotation plan for agricultural producers and agronomists across Argentina.

---

## 🚀 Access Modes & User Roles

The platform provides friction-free access without mandatory registration barriers for instant agronomic evaluation:

1. **🌾 Farmer Profile (Guided 3-Step Wizard)**:
   - **Step 1: Field Delimitation**: Interactive boundary mapping powered by Leaflet and Geoman. Includes direct coordinate searching (Google Maps format: `lat, lon`), real-time area calculation (ha), centroid tracking, and national territory validation restricted to Argentina.
   - **Step 2: Previous Crop Declaration**: Fast selection of previous harvest (**Corn / Maize**, **Soybean**, **Sunflower**, **Sorghum**, **Peanut**, or **Other / None**) to calculate biological alternation, nutrient balance, and phytosanitary succession intervals.
   - **Step 3: 34-Year NASA Telemetry & Recommendations**: 
     - **34 Years of NASA Data Banner**: Aggregated agroclimatic statistics spanning 34 historical growing seasons.
     - **6 Core Satellite Telemetry Cards**: Active Vegetation (NDVI), Sowing Moisture (SMAP), Accumulated Precipitation (GPM IMERG), Soil Temperature (NASA POWER), Soil Evapotranspiration (MODIS / ECOSTRESS), and Elevation / Slope (NASADEM).
     - **3-Year Crop Rotation Plan**: Triennial sequence (Year 1, Year 2, Year 3) strictly enforcing non-repetition, disease cycle disruption, and soil structure conservation based on INTA and FAO guidelines.
     - **Comprehensive Agronomic Criteria**: Expandable analysis comparing field metrics against crop optimal physiological thresholds across 9 to 10 specific parameters (soil temperature, growing degree days, cycle water demand, moisture at sowing, frost risk).
     - **Multi-Year Interactive Charts**: Modal viewer with continuous 5-year time series and interannual comparisons powered by Chart.js, featuring rapid sequential chart navigation buttons (◀ / ▶).
     - **Technical PDF Report Generator**: Generates an automated PDF report complete with the field's satellite capture, telemetry analysis, and triennial rotation schedule.

2. **🛰️ Agricultural Technician Profile (Full GIS Workspace)**:
   - Comprehensive territorial control center with multi-layer raster/vector feeds, NASA Satellite Dock, GIS layer switcher, interactive historical series charts, and raw satellite telemetry inspection.

3. **🔒 Administrator Profile**:
   - Administrative portal for authenticated users (`admin@earth2worlds.com`) featuring system health diagnostics, database schema inspection, and audit logs.

4. **🧹 Ephemeral Sessions**:
   - Farmer and Agricultural Technician profiles operate in memory on the client side, keeping the database clean while enabling immediate, high-fidelity agronomic simulations.

---

## 🛰️ Satellite Constellation & Data Sources

All primary and fallback data sources originate from NASA and partner space agencies (ESA, NOAA, ISRO):

| Satellite / Mission | Variable & Resolution | Role in Platform | Pipeline Source |
| :--- | :--- | :--- | :--- |
| **NASA POWER** | Daily climate, solar radiation, soil temp (0.5°) | 34-year historical baseline, GDD & thermal models | `rotaterra/fuentes/power.py` |
| **GPM IMERG** | Precipitation & accumulated rain (0.1° / 10 km) | Precipitation monitoring & sowing moisture balance | `rotaterra/fuentes/imerg.py` |
| **HLS (Landsat 8/9 + Sentinel-2)** | NDVI & NDMI surface reflectance (30 m) | High-resolution active vegetation & crop vigor | `rotaterra/fuentes/hls.py` |
| **SMAP L4 / L3** | Surface & root-zone soil moisture (9 km / 36 km) | Available water capacity & seedbed moisture | `rotaterra/fuentes/smap.py` |
| **NASADEM** | Digital elevation & slope dynamics (30 m) | Terrain elevation, drainage direction & relief | `rotaterra/fuentes/nasadem.py` |
| **MODIS (TERRA/AQUA)** | Evapotranspiration (MOD16A2) & thermal anomalies | Actual vs potential ET, water deficit & frost risk | `rotaterra/fuentes/et.py` |
| **ECOSTRESS** | Evapotranspiration & water stress (70 m) | High-resolution microclimate drought detection | `rotaterra/fuentes/ecostress.py` |
| **VIIRS (Suomi-NPP)** | Nighttime Land Surface Temperature (LST) (375 m) | Frost detection during critical phenological stages | `rotaterra/fuentes/viirs_heladas.py` |
| **GRACE-FO** | Terrestrial water storage & groundwater anomalies | Regional water table dynamics | `rotaterra/fuentes/grace.py` |
| **GeoINTA & SISINTA** | Soil texture, organic matter, pH, available water | Argentine official soil cartography (1:50,000) | `rotaterra/fuentes/geointa.py` |

---

## 🏗️ Technical Architecture

- **Backend**: FastAPI (Python 3.11+), Pydantic v2 validation models, JWT HS256 authentication, Bcrypt password hashing, and live schema introspection.
- **Frontend**: Responsive Single Page Application (Tailwind CSS, Vanilla ES6+ JavaScript, Leaflet 1.9.4 with Geoman, Chart.js 4.4).
- **Database**: SQLAlchemy 2.0 ORM over SQLite (`earth2worlds.db`) with native PostgreSQL compatibility for production.
- **Internationalization (i18n)**: Comprehensive bilingual engine (`en` / `es`) supporting real-time language toggling without page reload across all UI elements, toasts, charts, agronomic criteria, and PDF exports.
- **Agronomic Engine (`rotaterra.agronomos`)**: Rule-based evaluation engine implementing FAO-33 water-yield response, thermal degree day summation (Base Temperature $T_b$), INTA phytosanitary succession intervals, and multi-year rotation anti-monoculture optimization.

---

## 📦 Installation & Local Setup

### Prerequisites
- Python 3.11+
- Git

### 1. Clone the repository
```bash
git clone https://github.com/Emmanuel-Funes/Earth2Worlds.git
cd Earth2Worlds
```

### 2. Set up virtual environment
```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4. Initialize Database
```bash
python -m app.init_db
```

### 5. Run the Application
```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Open your browser at `http://127.0.0.1:8000`.

---

## 🧪 Testing

The test suite runs with simulated NASA HTTP responses (`httpx.MockTransport`) requiring no external credentials:

```bash
pytest -q
```

---

## 🌐 Deployment on Render

This repository is configured for one-click deployment on Render via `render.yaml`:
- **Build Command**: `pip install -r requirements.txt && python -m app.init_db`
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Environment Variables**:
  - `PYTHON_VERSION`: `3.11.8`
  - `EARTHDATA_USERNAME`: Your NASA Earthdata username *(optional for live sync)*
  - `EARTHDATA_PASSWORD`: Your NASA Earthdata password *(optional for live sync)*
  - `SECRET_KEY`: Auto-generated JWT secret
