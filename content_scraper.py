from flask import Flask, request, jsonify
import requests, random, re, time
from bs4 import BeautifulSoup
import traceback
from urllib.parse import urlparse
import logging

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Proxy Settings
PROXY_HOST = "gate.decodo.com"
PROXY_PORTS = [10001, 10002, 10003, 10004, 10005, 10006, 10007]
USERNAME = "spbb3v1soa"
PASSWORD = "=rY9v15mUg2AkrbEbk"

# Enhanced User-Agents with more variety
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15"
]

# Comprehensive price selectors
PRICE_SELECTORS = [
    ".a-price .a-offscreen",
    "#priceblock_ourprice",
    "#priceblock_dealprice", 
    "#priceblock_saleprice",
    "#priceblock_businessprice",
    "#priceblock_pospromoprice",
    ".a-price-whole",
    ".a-price-fraction",
    ".a-price-symbol",
    "[data-a-price] .a-offscreen",
    ".a-price.a-text-price.a-size-medium.apexPriceToPay .a-offscreen",
    ".a-price-range .a-offscreen"
]

# Title selectors (fallbacks)
TITLE_SELECTORS = [
    "#productTitle",
    ".product-title",
    "h1.a-size-large",
    "h1 span"
]

# Brand selectors
BRAND_SELECTORS = [
    "#bylineInfo",
    ".a-row .a-size-small span.a-color-secondary",
    "[data-brand]",
    ".po-brand .po-break-word"
]

def get_proxy_url():
    """Get a random proxy URL"""
    port = random.choice(PROXY_PORTS)
    return f"http://{USERNAME}:{PASSWORD}@{PROXY_HOST}:{port}"

def get_enhanced_headers():
    """Get enhanced headers to mimic real browser"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0"
    }

def validate_url(url):
    """Validate if URL is a proper Amazon product URL"""
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Check if it's an Amazon domain
        amazon_domains = ['amazon.com', 'amazon.co.uk', 'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.ca', 'amazon.in']
        is_amazon = any(domain in parsed.netloc.lower() for domain in amazon_domains)
        
        return is_amazon
    except:
        return False

def get_text(element):
    """Safely extract text from BeautifulSoup element"""
    return element.get_text(strip=True) if element else None

def extract_asin(url):
    """Extract ASIN from Amazon URL with multiple patterns"""
    patterns = [
        r"/dp/([A-Z0-9]{10})",
        r"/gp/product/([A-Z0-9]{10})", 
        r"/product/([A-Z0-9]{10})",
        r"asin=([A-Z0-9]{10})",
        r"/([A-Z0-9]{10})(?:[/?]|$)"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def fetch_html(url, use_proxy=True):
    """Fetch HTML with enhanced error handling and retry logic"""
    headers = get_enhanced_headers()
    
    # Setup proxies if enabled
    proxies = None
    if use_proxy:
        try:
            proxy_url = get_proxy_url()
            proxies = {"http": proxy_url, "https": proxy_url}
        except Exception as e:
            logger.warning(f"Proxy setup failed: {e}")
            proxies = None

    for attempt in range(5):  # Increased retry attempts
        try:
            logger.info(f"🔄 Attempt {attempt + 1} - Fetching: {url}")
            
            # Randomize delay between requests
            if attempt > 0:
                delay = random.uniform(2, 5)
                logger.info(f"⏳ Waiting {delay:.1f}s before retry...")
                time.sleep(delay)
            
            response = requests.get(
                url, 
                headers=headers, 
                proxies=proxies, 
                timeout=30,
                allow_redirects=True
            )
            
            logger.info(f"📊 Status Code: {response.status_code}")
            
            # Check for common blocking responses
            if response.status_code == 503:
                logger.warning("🚫 Service unavailable (503)")
                continue
                
            if response.status_code == 429:
                logger.warning("🚫 Rate limited (429)")
                time.sleep(10)
                continue
            
            # Check for CAPTCHA
            response_text = response.text.lower()
            if any(keyword in response_text for keyword in ['captcha', 'robot', 'automated']):
                logger.warning("🛑 CAPTCHA/Bot detection triggered")
                # Try without proxy on next attempt
                if use_proxy and attempt < 2:
                    proxies = None
                continue
            
            response.raise_for_status()
            
            # Validate response content
            if len(response.text) < 1000:
                logger.warning("⚠️ Response too short, might be blocked")
                continue
                
            logger.info("✅ Successfully fetched HTML")
            return response.text
            
        except requests.exceptions.Timeout:
            logger.warning(f"⏰ Timeout on attempt {attempt + 1}")
        except requests.exceptions.ProxyError:
            logger.warning(f"🔌 Proxy error on attempt {attempt + 1}")
            proxies = None  # Disable proxy for next attempt
        except requests.exceptions.RequestException as e:
            logger.warning(f"🌐 Request error on attempt {attempt + 1}: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error on attempt {attempt + 1}: {str(e)}")
    
    logger.error("💥 All fetch attempts failed")
    return None

def extract_price_info(soup):
    """Extract price with multiple fallback methods"""
    price, currency = None, None
    
    # Method 1: Try standard selectors
    for selector in PRICE_SELECTORS:
        try:
            elements = soup.select(selector)
            for element in elements:
                price_text = get_text(element)
                if price_text:
                    # Enhanced price regex
                    match = re.search(r'([₹$£€¥₩])\s*([\d,]+\.?\d*)', price_text)
                    if match:
                        currency = match.group(1)
                        price_str = match.group(2).replace(',', '')
                        try:
                            price = float(price_str)
                            return price, currency
                        except ValueError:
                            continue
        except Exception as e:
            logger.debug(f"Price extraction error for {selector}: {e}")
            continue
    
    # Method 2: Look for price in JSON-LD structured data
    try:
        scripts = soup.find_all('script', type='application/ld+json')
        for script in scripts:
            import json
            data = json.loads(script.string)
            if isinstance(data, dict) and 'offers' in data:
                offers = data['offers']
                if isinstance(offers, dict) and 'price' in offers:
                    price = float(offers['price'])
                    currency = offers.get('priceCurrency', '$')
                    return price, currency
    except:
        pass
    
    return price, currency

def extract_title(soup):
    """Extract title with multiple fallback selectors"""
    for selector in TITLE_SELECTORS:
        try:
            element = soup.select_one(selector)
            if element:
                title = get_text(element)
                if title and len(title.strip()) > 0:
                    return title.strip()
        except:
            continue
    return None

def extract_brand(soup):
    """Extract brand with multiple fallback selectors"""
    for selector in BRAND_SELECTORS:
        try:
            element = soup.select_one(selector)
            if element:
                brand_text = get_text(element)
                if brand_text:
                    # Clean up brand text
                    brand = re.sub(r'^(by|visit the|brand:)\s*', '', brand_text, flags=re.IGNORECASE)
                    return brand.strip()
        except:
            continue
    return None

def extract_reviews_count(soup):
    """Extract review count with multiple methods"""
    selectors = [
        "#acrCustomerReviewText",
        "[data-hook='total-review-count']",
        ".a-link-normal .a-size-base",
        "#reviewsMedley .a-link-normal"
    ]
    
    for selector in selectors:
        try:
            element = soup.select_one(selector)
            if element:
                reviews_text = get_text(element)
                if reviews_text:
                    # Extract number from text like "1,234 ratings" or "1,234 customer reviews"
                    match = re.search(r'([\d,]+)', reviews_text.replace(',', ''))
                    if match:
                        try:
                            return int(match.group(1).replace(',', ''))
                        except ValueError:
                            continue
        except:
            continue
    return 0

def extract_rating(soup):
    """Extract product rating"""
    selectors = [
        "[data-hook='average-star-rating'] .a-icon-alt",
        ".a-icon-alt",
        "[aria-label*='out of 5 stars']"
    ]
    
    for selector in selectors:
        try:
            element = soup.select_one(selector)
            if element:
                rating_text = element.get('aria-label', '') or get_text(element) or ''
                match = re.search(r'([\d.]+)\s*out of', rating_text)
                if match:
                    try:
                        return float(match.group(1))
                    except ValueError:
                        continue
        except:
            continue
    return None

def parse_data(soup):
    """Parse all product data with comprehensive error handling"""
    try:
        # Extract all data points
        title = extract_title(soup)
        brand = extract_brand(soup)
        price, currency = extract_price_info(soup)
        review_count = extract_reviews_count(soup)
        rating = extract_rating(soup)
        
        # Extract availability
        availability = None
        availability_selectors = ["#availability span", ".a-color-success", ".a-color-price"]
        for selector in availability_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    availability = get_text(element)
                    break
            except:
                continue
        
        return {
            "title": title,
            "brand": brand,
            "price": price,
            "currency": currency,
            "rating": rating,
            "reviewsCount": review_count,
            "availability": availability,
            "success": True
        }
        
    except Exception as e:
        logger.error(f"❌ Error in parse_data: {str(e)}")
        return {
            "title": None,
            "brand": None,
            "price": None,
            "currency": None,
            "rating": None,
            "reviewsCount": 0,
            "availability": None,
            "success": False,
            "error": str(e)
        }

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "message": "✅ Amazon Scraper API is running",
        "endpoints": {
            "/scrape": "Scrape Amazon product data",
            "/health": "Health check",
            "/test": "Test with a simple URL"
        },
        "usage": "/scrape?url=AMAZON_PRODUCT_URL"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": time.time()})

@app.route('/test')
def test():
    """Test endpoint with a simple HTTP request"""
    try:
        url = request.args.get('url', 'https://httpbin.org/get')
        headers = get_enhanced_headers()
        response = requests.get(url, headers=headers, timeout=10)
        
        return jsonify({
            "status": "success",
            "url": url,
            "status_code": response.status_code,
            "response_length": len(response.text),
            "headers_sent": dict(headers)
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/scrape')
def scrape():
    try:
        url = request.args.get("url")
        use_proxy = request.args.get("proxy", "true").lower() == "true"
        
        logger.info(f"📥 Received scrape request for: {url}")
        
        if not url:
            return jsonify({"error": "Missing ?url= parameter", "success": False}), 400
        
        # Validate URL
        if not validate_url(url):
            return jsonify({"error": "Invalid Amazon URL", "success": False}), 400
        
        # Extract ASIN
        asin = extract_asin(url)
        logger.info(f"🔍 ASIN: {asin}")
        
        # Fetch HTML
        html = fetch_html(url, use_proxy=use_proxy)
        if not html:
            return jsonify({
                "error": "Failed to fetch page after multiple attempts", 
                "success": False,
                "suggestion": "Try again later or check if the URL is accessible"
            }), 500
        
        # Parse HTML
        soup = BeautifulSoup(html, "html.parser")
        data = parse_data(soup)
        
        # Add metadata
        data.update({
            "url": url,
            "asin": asin,
            "scraped_at": time.time(),
            "proxy_used": use_proxy
        })
        
        logger.info(f"✅ Scraped data: {data}")
        return jsonify(data)
    
    except Exception as e:
        logger.error(f"❌ Error in /scrape: {str(e)}")
        traceback.print_exc()
        return jsonify({
            "error": "Internal server error", 
            "details": str(e),
            "success": False
        }), 500

if __name__ == '__main__':
    logger.info("🚀 Starting Amazon Scraper on port 8000")
    app.run(host="0.0.0.0", port=8000, debug=False)
