import os
import sys
import time
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
SCREENSHOTS_DIR = os.path.abspath("docs/user-guide-farmer/screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def run():
    print(f"Launching Playwright using Chrome at: {CHROME_PATH}", flush=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=CHROME_PATH,
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--window-size=1440,950"]
        )
        context = browser.new_context(viewport={"width": 1440, "height": 950})
        page = context.new_page()

        print("Navigating to http://127.0.0.1:8000/ ...", flush=True)
        page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        time.sleep(2)

        # Ensure language is English
        page.evaluate("if (typeof cambiarIdioma === 'function') cambiarIdioma('en');")
        time.sleep(1)

        # 1. Capture Access Mode Selection Modal
        print("Capturing 01_access_mode_selection.png...", flush=True)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_access_mode_selection.png"), full_page=False)

        # 2. Click "Enter as Farmer"
        print("Entering as Farmer...", flush=True)
        btn_farmer = page.locator("button:has-text('Enter as Farmer')")
        if btn_farmer.count() > 0:
            btn_farmer.first.click()
        else:
            page.evaluate("iniciarModoDesdeSelector('basico');")
        time.sleep(2)

        # Ensure language is English
        page.evaluate("if (typeof cambiarIdioma === 'function') cambiarIdioma('en');")
        time.sleep(1)

        # Capture Step 1 Map
        print("Capturing 02_step1_field_delimitation_map.png...", flush=True)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_step1_field_delimitation_map.png"), full_page=False)

        # 3. Simulate drawing a realistic parcel in San Luis, Argentina
        print("Drawing test parcel on Leaflet map...", flush=True)
        page.evaluate("""() => {
            if (mapaBasico) {
                const lat = -33.6527;
                const lon = -65.4786;
                mapaBasico.setView([lat, lon], 14);

                const coords = [
                    [lat - 0.003, lon - 0.005],
                    [lat - 0.003, lon + 0.005],
                    [lat + 0.003, lon + 0.005],
                    [lat + 0.003, lon - 0.005],
                    [lat - 0.003, lon - 0.005]
                ];
                const polygon = L.polygon(coords, { color: '#16a34a', weight: 3, fillColor: '#22c55e', fillOpacity: 0.25 });
                polygon.addTo(mapaBasico);

                // Trigger pm:create event simulation
                mapaBasico.fire('pm:create', { layer: polygon });
            }
        }""")
        time.sleep(2)

        print("Capturing 03_step1_parcel_drawn_calculated.png...", flush=True)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_step1_parcel_drawn_calculated.png"), full_page=False)

        # 4. Advance to Step 2
        print("Advancing to Step 2...", flush=True)
        page.evaluate("irAPasoBasico2();")
        time.sleep(1.5)
        page.evaluate("if (typeof cambiarIdioma === 'function') cambiarIdioma('en');")
        time.sleep(0.5)

        print("Capturing 04_step2_previous_crop_selection.png...", flush=True)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_step2_previous_crop_selection.png"), full_page=False)

        # 5. Execute Analysis
        print("Executing historical telemetry and crop recommendation analysis...", flush=True)
        btn_analizar = page.locator("#btnAnalizarBasico")
        if btn_analizar.count() > 0:
            btn_analizar.first.click()
        else:
            page.evaluate("ejecutarAnalisisBasico();")

        # Wait until recommendations populate
        print("Waiting for recommendation cards to populate...", flush=True)
        for i in range(40):
            has_recs = page.evaluate("() => document.querySelectorAll('.details-reglas-cultivo').length > 0")
            if has_recs:
                print(f"Recommendations successfully populated after {i+1} seconds!", flush=True)
                break
            time.sleep(1)

        time.sleep(2)
        page.evaluate("if (typeof cambiarIdioma === 'function') cambiarIdioma('en');")
        time.sleep(1)

        # Scroll to telemetry cards and banner
        page.evaluate("document.getElementById('slotRecomendacionCultivos')?.scrollIntoView({ behavior: 'instant' });")
        time.sleep(1)

        print("Capturing 05_step3_telemetry_cards_and_banner.png...", flush=True)
        page.evaluate("window.scrollTo(0, 300);")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "05_step3_telemetry_cards_and_banner.png"), full_page=False)

        # 6. Capture 3-Year Crop Rotation Plan
        print("Capturing 06_triennial_crop_rotation_plan.png...", flush=True)
        page.evaluate("document.querySelector('#slotRecomendacionCultivos')?.scrollIntoView({ behavior: 'instant' });")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "06_triennial_crop_rotation_plan.png"), full_page=False)

        # 7. Capture Agronomic Recommendation Cards
        print("Capturing 07_agronomic_recommendation_cards.png...", flush=True)
        page.evaluate("document.getElementById('grillaCultivosEvaluados')?.scrollIntoView({ behavior: 'instant' });")
        time.sleep(1)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "07_agronomic_recommendation_cards.png"), full_page=False)

        # 8. Expand Agronomic Criteria on first card
        print("Expanding agronomic criteria...", flush=True)
        page.evaluate("""() => {
            const details = document.querySelector('.details-reglas-cultivo');
            if (details) details.open = true;
        }""")
        time.sleep(1)
        print("Capturing 08_agronomic_criteria_expanded.png...", flush=True)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "08_agronomic_criteria_expanded.png"), full_page=False)

        # 9. Open Telemetry Chart Modal
        print("Opening Telemetry Chart Modal...", flush=True)
        page.evaluate("if (typeof abrirModalGrafico === 'function') abrirModalGrafico('ndvi');")
        time.sleep(2)
        print("Capturing 09_telemetry_5year_chart_modal.png...", flush=True)
        page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "09_telemetry_5year_chart_modal.png"), full_page=False)

        browser.close()
        print("All screenshots captured successfully!", flush=True)

if __name__ == "__main__":
    run()
