from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Flipkart
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

app = Flask(__name__)
CORS(app)

# ---------------- FLIPKART ----------------
def scrape_flipkart(search_term):

    # 🚀 Headless Chrome (faster)
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    results = []

    # 🔥 ONLY 1 PAGE (FASTER)
    for page in range(1, 2):
        url = f"https://www.flipkart.com/search?q={search_term}&page={page}"
        driver.get(url)
        time.sleep(0.5)

        soup = BeautifulSoup(driver.page_source, "html.parser")
        products = soup.find_all("div", class_="s0NCCf")

        for p in products:
            name = p.find("div", class_="TbCaMn")
            price = p.find("div", class_="hZ3P6w")
            rating = p.find("div", class_="MKiFS6")
            link = p.find("a", href=True)
            image = p.find("img")

            results.append({
                "Product": name.text if name else "N/A",
                "Flipkart Price": price.text if price else "N/A",
                "Flipkart Rating": rating.text if rating else "0",
                "Flipkart Image": image.get("src") if image else "N/A",
                "Flipkart Link": "https://www.flipkart.com" + link["href"] if link else "N/A"
            })

            # 🔥 STOP AFTER 5 PRODUCTS
            if len(results) >= 5:
                break

        # 🔥 STOP PAGE LOOP ALSO
        if len(results) >= 5:
            break

    driver.quit()

    # SORT BY RATING
    def safe_rating(x):
        try:
            return float(x["Flipkart Rating"])
        except:
            return 0

    results = sorted(results, key=safe_rating, reverse=True)

    return results[:5]


# ---------------- AMAZON ----------------
def get_amazon_product(product_name):

    url = "https://real-time-amazon-data.p.rapidapi.com/search"
    headers = {
        "X-RapidAPI-Key": "8ee46b1158msh0e435da66cedce2p10d5c2jsn3b693cd9ec4d",
        "X-RapidAPI-Host": "real-time-amazon-data.p.rapidapi.com"
    }

    params = {
        "query": product_name,
        "country": "IN"
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code != 200:
            return None

        data = response.json()

        products = data.get("data", {}).get("products") or \
                   data.get("data", {}).get("results") or []

        if not products:
            return None

        for p in products:
            title = (p.get("product_title") or "").lower()

            if any(x in title for x in [
                "case","cover","charger","cable",
                "tempered","protector","earbuds","adapter"
            ]):
                continue

            return {
                "title": p.get("product_title"),
                "price": p.get("product_price"),
                "image": p.get("product_photo"),
                "link": p.get("product_url")
            }

        return None

    except Exception as e:
        print("Amazon Error:", e)
        return None


# 🔥 PARALLEL PROCESS FUNCTION
def process_item(item):
    clean_name = item["Product"]
    clean_name = clean_name.replace("Apple", "").strip()
    clean_name = clean_name.split("(")[0].split("-")[0].strip()

    amazon = get_amazon_product(clean_name)

    if not amazon:
        amazon = {
            "title": "Search on Amazon",
            "price": "N/A",
            "image": item["Flipkart Image"],
            "link": f"https://www.amazon.in/s?k={clean_name.replace(' ', '+')}"
        }

    return {
        **item,
        "Amazon Product": amazon["title"],
        "Amazon Price": amazon["price"],
        "Amazon Image": amazon["image"],
        "Amazon Link": amazon["link"]
    }


# ---------------- MAIN API ----------------
@app.route("/search")
def search():

    query = request.args.get("q")

    if not query:
        return jsonify({"error": "No query given"})

    print("Searching for:", query)

    flipkart_data = scrape_flipkart(query)

    # 🚀 PARALLEL AMAZON CALLS (FASTER)
    with ThreadPoolExecutor(max_workers=5) as executor:
        final_results = list(executor.map(process_item, flipkart_data))

    return jsonify(final_results)


if __name__ == "__main__":
    app.run(debug=True)
import os

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
