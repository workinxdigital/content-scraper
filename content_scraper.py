from flask import Flask, request, jsonify
import requests, random, re, time
from bs4 import BeautifulSoup

app = Flask(__name__)
@app.route('/scrape')
def scrape():
    url = request.args.get('url')
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        response = requests.get(url, headers=headers)
        # your scraping logic here, e.g., parse response.text
        return "Success"
    except Exception as e:
        print(f"Error: {e}")
        return "Internal Server Error", 500
        
# Proxy Settings
PROXY_HOST = "gate.decodo.com"
PROXY_PORTS = [10001, 10002, 10003, 10004, 10005, 10006, 10007]
USERNAME = "spbb3v1soa"
PASSWORD = "=rY9v15mUg2AkrbEbk"

# Rotate User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
    "Mozilla/5.0 (X11; Linux x86_64)"
]

# Price selectors (may need updating over time)
PRICE_SELECTORS = [
    ".a-price .a-offscreen", "#priceblock_ourprice", "#priceblock_dealprice",
    "#priceblock_saleprice", "#priceblock_businessprice", "#priceblock_pospromoprice"
]

def get_proxy_url():
    port = random.choice(PROXY_PORTS)
    return f"http://{USERNAME}:{PASSWORD}@{PROXY_HOST}:{port}"

def get_text(element):
    return element.get_text(strip=True) if element else None

def extract_asin(url):
    patterns = [r"/dp/([A-Z0-9]{10})", r"/gp/product/([A-Z0-9]{10})", r"/([A-Z0-9]{10})(?:[/?]|$)"]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_html(url):
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    proxies = {"http": get_proxy_url(), "https": get_proxy_url()}

    for attempt in range(3):
        try:
            print(f"🔄 Attempt {attempt + 1} - Fetching:", url)
            response = requests.get(url, headers=headers, proxies=proxies, timeout=20)
            if "captcha" in response.text.lower():
                print("🛑 CAPTCHA detected. Retrying...")
                time.sleep(2)
                continue
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"⚠️ Error (attempt {attempt + 1}):", str(e))
            time.sleep(1)
    return None

def parse_data(soup):
    title = get_text(soup.select_one("#productTitle"))
    brand = get_text(soup.select_one("#bylineInfo"))

    price, currency = None, None
    for sel in PRICE_SELECTORS:
        price_text = get_text(soup.select_one(sel))
        if price_text:
            match = re.search(r"([$\£₹€])\s*([\d,]+\.?\d*)", price_text)
            if match:
                currency = match.group(1)
                price = float(match.group(2).replace(",", ""))
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
    url = request.args.get("url")
    print("📥 Received URL:", url)

    if not url:
        return jsonify({"error": "Missing ?url= parameter"}), 400

    asin = extract_asin(url)
    print("🔍 ASIN:", asin)

    html = fetch_html(url)
    if not html:
        return jsonify({"error": "Failed to fetch page"}), 500

    soup = BeautifulSoup(html, "html.parser")
    data = parse_data(soup)
    data.update({"url": url, "asin": asin})

    print("✅ Scraped Data:", data)
    return jsonify(data)

if __name__ == '__main__':
    print("🚀 Amazon Scraper running on port 8000")
    app.run(host="0.0.0.0", port=8000)

