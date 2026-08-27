"""Convert the flowchart HTML pages to JPG images using Selenium."""
import os, time
from selenium import webdriver
from selenium.webdriver.edge.options import Options

HTML_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "flowchart_and_modules.html"))
OUT_DIR = os.path.dirname(__file__)

opts = Options()
opts.add_argument("--headless=new")
opts.add_argument("--disable-gpu")
opts.add_argument("--window-size=1400,2000")

driver = webdriver.Edge(options=opts)
driver.get("file:///" + HTML_PATH.replace("\\", "/"))
time.sleep(2)

pages = driver.find_elements("css selector", ".page")
print(f"Found {len(pages)} pages to capture")

for i, page in enumerate(pages, 1):
    # Scroll page into view and capture
    driver.execute_script("arguments[0].scrollIntoView(true);", page)
    time.sleep(0.5)

    # Get page dimensions
    loc = page.location
    size = page.size

    # Take full screenshot then crop to page element
    png_path = os.path.join(OUT_DIR, f"flowchart_page_{i}.png")
    page.screenshot(png_path)

    # Convert PNG to JPG
    from PIL import Image
    img = Image.open(png_path)
    jpg_path = os.path.join(OUT_DIR, f"flowchart_page_{i}.jpg")
    img = img.convert("RGB")
    img.save(jpg_path, "JPEG", quality=95)
    os.remove(png_path)
    print(f"  Saved: {jpg_path}")

driver.quit()
print("Done! All pages converted to JPG.")
