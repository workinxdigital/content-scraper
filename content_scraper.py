from flask import Flask, request, jsonify
import requests, random, re, time
from bs4 import BeautifulSoup
import traceback
from urllib.parse import urlparse
import logging
import json

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Proxy Settings
PROXY_HOST = "gate.decodo.com"
PROXY_PORTS = [10001, 10002, 10003, 10004, 10005, 10006, 10007]
USERNAME = "spbb3v1soa"
PASSWORD = "=rY9v15mUg2AkrbEbk"

# More realistic User-Agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36 Edg/119.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
]

# Comprehensive selectors
PRICE_SELECTORS = [
    ".a-price .a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    "#priceblock_saleprice", 
    ".a-price-whole",
    ".a-price-fraction",
    "[data-a-price] .a-offscreen",
    ".a-price.a-text-price .a-offscreen"
]

def get_proxy_url():
    port = random.choice(PROXY_PORTS)
    return f"http://{USERNAME}:{PASSWORD}@{PROXY_HOST}:{port}"

def get_realistic_headers():
    """Generate more realistic headers"""
    user_agent = random.choice(USER_AGENTS)
    
    # Extract browser info from user agent
    is_chrome = "Chrome" in user_agent
    is_firefox = "Firefox" in user_agent
    is_safari = "Safari" in user_agent and "Chrome" not in user_agent
    
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"' if "Windows" in user_agent else '"macOS"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1"
    }
    
    if is_chrome:
        headers["sec-ch-ua"] = '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"'
    
    return headers

def validate_url(url):
    try:
        parsed = urlparse(url)
        amazon_domains = ['amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.ca', 'amazon.in']
        return any(domain in parsed.netloc.lower() for domain in amazon_domains)
    except:
        return False

def extract_asin(url):
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})",
        r"asin=([A-Z0-9]{10})",
        r"/([A-Z0-9]{10})(?:[/?]|$)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_with_session(url, use_proxy=True, max_attempts=3):
    """Use session for better cookie/state management"""
    session = requests.Session()
    
    for attempt in range(max_attempts):
        try:
            headers = get_realistic_headers()
            session.headers.update(headers)
            
            # Setup proxy
            if use_proxy:
                proxy_url = get_proxy_url()
                session.proxies = {"http": proxy_url, "https": proxy_url}
            
            logger.info(f"🔄 Session attempt {attempt + 1} - Fetching: {url}")
            
            # Add random delay
            if attempt > 0:
                delay = random.uniform(5, 10)
                logger.info(f"⏳ Waiting {delay:.1f}s...")
                time.sleep(delay)
            
            # First, visit Amazon homepage to get cookies
            if attempt == 0:
                logger.info("🏠 Visiting Amazon homepage first...")
                home_url = "https://www.amazon.com"
                session.get(home_url, timeout=15)
                time.sleep(random.uniform(2, 4))
            
            # Now fetch the product page
            response = session.get(url, timeout=30)
            logger.info(f"📊 Status: {response.status_code}")
            
            # Check response
            if response.status_code == 200:
                content = response.text.lower()
                
                # More sophisticated CAPTCHA detection
                captcha_indicators = [
                    'captcha', 'robot', 'automated', 'unusual traffic',
                    'security check', 'verify you are human', 'prove you are not a robot'
                ]
                
                if any(indicator in content for indicator in captcha_indicators):
                    logger.warning("🛑 CAPTCHA/Bot detection triggered")
                    continue
                
                if len(response.text) < 10000:  # Amazon pages are usually large
                    logger.warning("⚠️ Response too short, likely blocked")
                    continue
                
                logger.info("✅ Successfully fetched page")
                return response.text
            
        except Exception as e:
            logger.warning(f"❌ Attempt {attempt + 1} failed: {str(e)}")
            time.sleep(random.uniform(3, 6))
    
    return None

def extract_data_from_html(html):
    """Extract product data with multiple methods"""
    soup = BeautifulSoup(html, "html.parser")
    
    # Method 1: Try to extract from JSON-LD structured data first
    try:
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            if script.string:
                data = json.loads(script.string)
                if isinstance(data, dict):
                    # Extract from structured data
                    title = data.get('name')
                    brand = data.get('brand', {}).get('name') if isinstance(data.get('brand'), dict) else data.get('brand')
                    
                    offers = data.get('offers', {})
                    if isinstance(offers, dict):
                        price_text = offers.get('price')
                        currency = offers.get('priceCurrency', '$')
                        try:
                            price = float(price_text) if price_text else None
                        except:
                            price = None
                    else:
                        price, currency = None, None
                    
                    if title:  # If we found structured data
                        return {
                            "title": title,
                            "brand": brand,
                            "price": price,
                            "currency": currency,
                            "method": "structured_data"
                        }
    except Exception as e:
        logger.debug(f"Structured data extraction failed: {e}")
    
    # Method 2: Traditional HTML parsing
    try:
        # Title
        title = None
        title_selectors = ["#productTitle", "h1.a-size-large", ".product-title"]
        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                break
        
        # Brand
        brand = None
        brand_selectors = ["#bylineInfo", ".a-row .a-size-small span.a-color-secondary"]
        for selector in brand_selectors:
            element = soup.select_one(selector)
            if element:
                brand_text = element.get_text(strip=True)
                brand = re.sub(r'^(by|visit the|brand:)\s*', '', brand_text, flags=re.IGNORECASE)
                break
        
        # Price
        price, currency = None, None
        for selector in PRICE_SELECTORS:
            element = soup.select_one(selector)
            if element:
                price_text = element.get_text(strip=True)
                match = re.search(r'([₹$£€¥₩])\s*([\d,]+\.?\d*)', price_text)
                if match:
                    currency = match.group(1)
                    try:
                        price = float(match.group(2).replace(',', ''))
                        break
                    except:
                        continue
        
        return {
            "title": title,
            "brand": brand,
            "price": price,
            "currency": currency,
            "method": "html_parsing"
        }
        
    except Exception as e:
        logger.error(f"HTML parsing failed: {e}")
        return {
            "title": None,
            "brand": None,
            "price": None,
            "currency": None,
            "method": "failed",
            "error": str(e)
        }

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "✅ Enhanced Amazon Scraper API",
        "endpoints": {
            "/scrape": "Scrape Amazon product (with proxy)",
            "/scrape_no_proxy": "Scrape without proxy",
            "/health": "Health check"
        }
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

@app.route('/scrape')
def scrape():
    try:
        url = request.args.get("url")
        
        if not url:
            return jsonify({"error": "Missing ?url= parameter"}), 400
        
        if not validate_url(url):
            return jsonify({"error": "Invalid Amazon URL"}), 400
        
        asin = extract_asin(url)
        logger.info(f"🔍 ASIN: {asin}")
        
        # Try with proxy first
        html = fetch_with_session(url, use_proxy=True)
        
        if not html:
            logger.info("🔄 Retrying without proxy...")
            html = fetch_with_session(url, use_proxy=False)
        
        if not html:
            return jsonify({
                "error": "Failed to fetch page - Amazon is blocking requests",
                "suggestion": "Try again later or use a different approach",
                "asin": asin
            }), 500
        
        # Extract data
        data = extract_data_from_html(html)
        data.update({
            "url": url,
            "asin": asin,
            "scraped_at": time.time()
        })
        
        logger.info(f"✅ Extracted: {data}")
        return jsonify(data)
        
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        traceback.print_exc()
        return jsonify({"error": "Internal server error", "details": str(e)}), 500

@app.route('/scrape_no_proxy')
def scrape_no_proxy():
    """Scrape without using proxy"""
    try:
        url = request.args.get("url")
        
        if not url:
            return jsonify({"error": "Missing ?url= parameter"}), 400
        
        if not validate_url(url):
            return jsonify({"error": "Invalid Amazon URL"}), 400
        
        asin = extract_asin(url)
        html = fetch_with_session(url, use_proxy=False)
        
        if not html:
            return jsonify({"error": "Failed to fetch page"}), 500
        
        data = extract_data_from_html(html)
        data.update({"url": url, "asin": asin, "proxy_used": False})
        
        return jsonify(data)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Enhanced Amazon Scraper")
    app.run(host="0.0.0.0", port=8000, debug=False)
