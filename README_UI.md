# Earth2Worlds · Web Platform and User Interface (UI)

Agroclimatic and territorial intelligence platform developed by the **Earth2Worlds** team for the NASA Space Apps Challenge 2026.
It connects real-time and historical (5-year / 34-year) satellite telemetry from **NASA** and partner agencies to optimize agricultural decision-making and crop rotation.

---

## 🚀 Access Modes and User Experience

The platform enables direct, frictionless access without registration barriers for rapid evaluation:

1. **🌾 Farmer Profile (Guided 3-Step Wizard)**:
   - **Step 1: Parcel Delimitation**: Interactive parcel mapping with Leaflet + Geoman, coordinate search, real-time acreage calculation (ha), centroid tracking, and national territory boundary alerts restricted to Argentina.
   - **Step 2: Previous Crop Declaration**: Fast selection among 5 strategic crops (**Corn / Maize**, **Soybean**, **Sunflower**, **Sorghum**, **Peanut**) or **Other / None**.
   - **Step 3: Telemetry & Recommendations**: Interactive field polygon, progressive loading of 6 satellite cards with current values and multi-year data, 34-year NASA POWER climate statistics, and the INTA/FAO-based agronomic recommendation engine displaying a 3-Year Crop Rotation Plan.
2. **🛰️ Agricultural Technician Profile (Comprehensive GIS Workspace)**:
   - Full GIS workstation: multi-resolution imagery, NASA Satellite Dock, thematic layer switcher, interactive metric cards, and 5-year temporal series charts (Chart.js) with fast navigation.
3. **🔒 Administrator Profile**:
   - Administrative portal for authenticated users (`admin@earth2worlds.com`) featuring field registries, database schema introspection, and architecture diagnostics.
4. **🧹 Ephemeral Client Sessions**:
   - Farmer and Agricultural Technician profiles operate in memory on the client side, keeping the database clean while enabling immediate, high-fidelity agronomic simulations.

---

## 🛠️ Technical Architecture

- **Frontend**: Responsive SPA in Dark Mode (Tailwind CSS, Vanilla JS ES6+, Leaflet 1.9.4 with Geoman, Chart.js).
- **Backend**: FastAPI with Python 3.11+, Pydantic v2, JWT HS256 authentication, strict RBAC, and live schema introspection.
- **Database**: SQLAlchemy 2.0 over SQLite (`earth2worlds.db`) with PostgreSQL production compatibility.
- **Rotaterra Satellite Engine**: Independent satellite retrieval modules with automatic fallbacks adhering to a unified JSON contract (`rotaterra/contrato.py`).
