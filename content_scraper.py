from flask import Flask, request, jsonify
import json, logging, random, re, time
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

app = Flask(__name__)

# --- Proxy & Config ---
PROXY_HOST = "gate.decodo.com"
PROXY_PORTS = [10001, 10002, 10003, 10004, 10005, 10006, 10007]
USERNAME = "spbb3v1soa"
PASSWORD = "=rY9v15mUg2AkrbEbk"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X...)",
    "Mozilla/5.0 (X11; Linux x86_64)..."
]

PRICE_SELECTORS = [
    ".a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice",
    "#priceblock_saleprice", "#priceblock_businessprice", "#priceblock_pospromoprice"
]

# --- Utility Functions ---
def get_proxy_url():
    port = random.choice(PROXY_PORTS)
    return f"http://{USERNAME}:{PASSWORD}@{PROXY_HOST}:{port}"

def get_text(el): return el.get_text(strip=True) if el else None

def extract_asin(url):
    patterns = [r"/dp/([A-Z0-9]{10})", r"/gp/product/([A-Z0-9]{10})", r"/([A-Z0-9]{10})(?:[/?]|$)"]
    for p in patterns:
        m = re.search(p, url)
        if m: return m.group(1)
    return None

def fetch_static(url):
    try:
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        proxies = {"http": get_proxy_url(), "https": get_proxy_url()}
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=15)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print("Static fetch error:", e)
        return None

def fetch_full_page(url):
    driver = None
    try:
        opts = Options()
        opts.add_argument(f"--proxy-server={get_proxy_url()}")
        opts.add_argument("--headless=new")
        opts.add_argument("--no-sandbox")
        opts.add_argument(f"user-agent={random.choice(USER_AGENTS)}")
        driver = webdriver.Chrome(options=opts)
        driver.get(url)
        time.sleep(2)
        html = driver.page_source
        driver.quit()
        return html
    except Exception as e:
        print("Selenium fetch error:", e)
        if driver: driver.quit()
        return None

# --- Parsing Functions ---
def parse_listing(soup): return {"title": get_text(soup.select_one("#productTitle")), "brand": get_text(soup.select_one("#bylineInfo"))}
def parse_price_stock(soup):
    for sel in PRICE_SELECTORS:
        p = get_text(soup.select_one(sel))
        if p:
            match = re.match(r"([$\£₹€])\s*([\d,]+\.?\d*)", p)
            if match:
                return {"price": {"value": float(match.group(2).replace(",", "")), "currency": match.group(1)}}
    return {"price": {"value": None, "currency": None}}
def parse_stock(soup): return {"inStock": "In Stock" in (txt := get_text(soup.select_one("#availability"))) if txt else False}
def parse_reviews(soup): return {"reviewsCount": int(get_text(soup.select_one("#acrCustomerReviewText")).split()[0].replace(",", ""))}

# --- API Route ---
@app.route('/scrape', methods=['GET'])
def scrape():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing ?url= param"}), 400

    print(f"Scraping: {url}")
    asin = extract_asin(url)
    html = fetch_static(url) or fetch_full_page(url)
    if not html:
        return jsonify({"error": "Failed to fetch page"}), 500

    soup = BeautifulSoup(html, "html.parser")
    result = {"url": url, "asin": asin}
    result.update(parse_listing(soup))
    result.update(parse_price_stock(soup))
    result.update(parse_stock(soup))
    result.update(parse_reviews(soup))
    return jsonify(result)

# --- Run the Flask App ---
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8000)




