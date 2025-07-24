from flask import Flask, request, jsonify
import json, logging, random, re, time
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# Proxy Settings (if needed)
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

def fetch_html(url):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    proxies = {"http": get_proxy_url(), "https": get_proxy_url()}
    try:
        resp = requests.get(url, headers=headers, proxies=proxies, timeout=20)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print("Fetch error:", e)
        return None

def parse_data(soup):
    title = get_text(soup.select_one("#productTitle"))
    brand = get_text(soup.select_one("#bylineInfo"))
    
    price = None
    currency = None
    for sel in PRICE_SELECTORS:
        p = get_text(soup.select_one(sel))
        if p:
            match = re.match(r"([$\£₹€])\s*([\d,]+\.?\d*)", p)
            if match:
                currency, price = match.group(1), float(match.group(2).replace(",", ""))
                break

    reviews = get_text(soup.select_one("#acrCustomerReviewText"))
    review_count = int(reviews.split()[0].replace(",", "")) if reviews else 0

    return {
        "title": title,
        "brand": brand,
        "price": price,
        "currency": currency,
        "reviewsCount": review_count
    }

@app.route('/')
def home():
    return "✅ Scraper is running. Use /scrape?url=... to scrape a product."

@app.route('/scrape')
def scrape():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing ?url="}), 400

    asin = extract_asin(url)
    html = fetch_html(url)
    if not html:
        return jsonify({"error": "Failed to fetch"}), 500

    soup = BeautifulSoup(html, "html.parser")
    data = parse_data(soup)
    data.update({"url": url, "asin": asin})
    return jsonify(data)

if __name__ == '__main__':
    print("✅ Scraper is running. Use /scrape?url=...")
    app.run(host="0.0.0.0", port=8000)
