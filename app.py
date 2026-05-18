# -*- coding: utf-8 -*-
"""
Created on Mon May 18 16:05:31 2026

@author: Rony Joseph
"""

import re
import time
from typing import List, Dict, Any

import pandas as pd
import streamlit as st
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


# =========================================================
# STREAMLIT PAGE CONFIG
# =========================================================

st.set_page_config(
    page_title="Amazon.fr Scraper",
    layout="wide"
)

st.title("Amazon.fr Page-1 Scraper")
st.write("Run your Amazon.fr page-1 competitor scraper from a simple app.")


# =========================================================
# HELPERS
# =========================================================

BSR_LABELS = {
    "classement des meilleures ventes",
    "classement des meilleures ventes d'amazon",
    "classement des meilleures ventes d’amazon",
    "classement des meilleures ventes d’amazon:",
    "best sellers rank",
    "best seller rank",
    "numéro des meilleures ventes",
    "n° des meilleures ventes",
    "classement",
}

STYLE_LABELS = {"style", "style name"}


def clean_text(text: str) -> str:
    if text is None:
        return ""
    return re.sub(r"[\u200e\u200f\u200b\u202f\xa0]", " ", str(text)).strip()


def is_bsr_label(text: str) -> bool:
    t = clean_text(text).lower().strip().rstrip(": ")
    return any(label in t for label in BSR_LABELS)


def is_style_label(text: str) -> bool:
    t = clean_text(text).lower().strip().rstrip(":")
    return t in STYLE_LABELS


def expand_accordions(driver):
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, ".a-expander-header")
        for button in buttons:
            try:
                driver.execute_script("arguments[0].click();", button)
                time.sleep(0.4)
            except Exception:
                pass
        return True
    except Exception:
        return False


def extract_bsr(driver) -> str:
    """Extract BSR using the selector you found plus fallbacks."""

    # 1) class-based labels you found
    try:
        label_elements = driver.find_elements(
            By.CSS_SELECTOR,
            ".a-color-secondary.a-size-base.prodDetSectionEntry"
        )

        for label_el in label_elements:
            label_text = clean_text(
                label_el.get_attribute("textContent") or label_el.text
            ).lower()

            if is_bsr_label(label_text):
                try:
                    row = label_el.find_element(By.XPATH, "./ancestor::tr[1]")
                    cells = row.find_elements(By.XPATH, "./th|./td")
                    if len(cells) >= 2:
                        value = clean_text(cells[-1].get_attribute("textContent") or cells[-1].text)
                        if value:
                            return value
                except Exception:
                    pass

                try:
                    sibling = label_el.find_element(By.XPATH, "./following-sibling::*[1]")
                    value = clean_text(sibling.get_attribute("textContent") or sibling.text)
                    if value:
                        return value
                except Exception:
                    pass
    except Exception:
        pass

    # 2) table rows
    for selector in [
        "#productDetails_detailBullets_sections1 tr",
        "#productDetails_techSpec_section_1 tr"
    ]:
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, selector)
            for row in rows:
                try:
                    cells = row.find_elements(By.XPATH, "./th|./td")
                    if len(cells) >= 2:
                        label = clean_text(cells[0].text).lower()
                        if any(lbl in label for lbl in BSR_LABELS):
                            value = clean_text(cells[-1].text)
                            if value:
                                return value
                except Exception:
                    continue
        except Exception:
            pass

    # 3) detail bullet lists
    for selector in [
        "#detailBullets_feature_div li",
        "#detailBulletsWrapper_feature_div li"
    ]:
        try:
            items = driver.find_elements(By.CSS_SELECTOR, selector)
            for item in items:
                full = clean_text(item.get_attribute("textContent") or item.text)
                lower_full = full.lower()

                if any(lbl in lower_full for lbl in BSR_LABELS):
                    m = re.search(
                        r'(#[\d\s,\.]+\s+(?:dans|in)\s+[^\n<"]{3,80})',
                        full,
                        re.IGNORECASE
                    )
                    if m:
                        return clean_text(m.group(1))
                    return full
        except Exception:
            pass

    # 4) page source fallback
    try:
        source = driver.page_source
        match = re.search(
            r'(?:classement des meilleures ventes|best sellers rank)[^#]*'
            r'(#[\d\s,\.]+\s+(?:dans|in)\s+[^\n<"]{3,80})',
            source,
            re.IGNORECASE
        )
        if match:
            return clean_text(match.group(1))
    except Exception:
        pass

    return "NOT FOUND"


def extract_style(driver) -> str:
    """Extract Style / Style Name from tables, bullets, and raw text fallback."""

    # 1) structured tables
    for selector in [
        "#productOverview_feature_div tr",
        "#productDetails_detailBullets_sections1 tr",
        "#productDetails_techSpec_section_1 tr"
    ]:
        try:
            rows = driver.find_elements(By.CSS_SELECTOR, selector)
            for row in rows:
                try:
                    cells = row.find_elements(By.XPATH, "./th|./td")
                    if len(cells) >= 2:
                        label = clean_text(cells[0].text).lower().strip().rstrip(":")
                        if label in STYLE_LABELS:
                            value = clean_text(cells[-1].text)
                            if value:
                                return value
                except Exception:
                    continue
        except Exception:
            pass

    # 2) detail bullets
    for selector in [
        "#detailBullets_feature_div li",
        "#detailBulletsWrapper_feature_div li"
    ]:
        try:
            items = driver.find_elements(By.CSS_SELECTOR, selector)
            for item in items:
                spans = item.find_elements(By.TAG_NAME, "span")
                if len(spans) >= 2:
                    label = clean_text(spans[0].text).lower().strip().rstrip(":")
                    if label in STYLE_LABELS:
                        value = clean_text(spans[1].text)
                        if value:
                            return value
        except Exception:
            pass

    # 3) raw text fallback
    try:
        raw_blocks = []
        for selector in [
            "#productOverview_feature_div",
            "#productDetails_detailBullets_sections1",
            "#productDetails_techSpec_section_1",
            "#detailBulletsWrapper_feature_div",
            "#detailBullets_feature_div"
        ]:
            try:
                txt = clean_text(
                    driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
                )
                if txt:
                    raw_blocks.append(txt)
            except Exception:
                pass

        combined = " ".join(raw_blocks)

        # line-based fallback
        for line in combined.splitlines():
            l = clean_text(line)
            ll = l.lower().strip()

            if ll.startswith("style name"):
                value = clean_text(l[len("style name"):].strip(" :\t-"))
                if value:
                    return value

            if ll.startswith("style"):
                value = clean_text(l[len("style"):].strip(" :\t-"))
                if value:
                    return value

        # regex fallback
        match = re.search(
            r'\bstyle(?:\s+name)?\s+(.+?)(?=\s{2,}|\bbrand\b|\bcolour\b|\bcolor\b|\bmaterial\b|\bitem shape\b|\bpattern\b|\bspecial features\b|\bsize\b|$)',
            combined,
            re.IGNORECASE
        )
        if match:
            value = clean_text(match.group(1))
            if value:
                return value

        match = re.search(
            r'\bstyle\s+([A-Za-zÀ-ÿ0-9 ,&()\/\-]+)',
            combined,
            re.IGNORECASE
        )
        if match:
            value = clean_text(match.group(1))
            if value:
                return value

    except Exception:
        pass

    return "NOT FOUND"


def extract_structured_text(driver) -> str:
    parts = []
    for selector in [
        "#productOverview_feature_div",
        "#productDetails_detailBullets_sections1",
        "#productDetails_techSpec_section_1",
        "#detailBulletsWrapper_feature_div",
        "#detailBullets_feature_div"
    ]:
        try:
            text = clean_text(
                driver.find_element(By.CSS_SELECTOR, selector).get_attribute("textContent")
            )
            if text:
                parts.append(text)
        except Exception:
            pass
    return "\n".join(parts)


# =========================================================
# SCRAPER CORE
# =========================================================

def run_scraper(keyword: str, postal_code: str, output_csv: str, log_box, progress_bar, status_box) -> pd.DataFrame:
    """Run the scraper and return the final dataframe."""

    def log(message: str):
        existing = st.session_state.get("live_logs", [])
        existing.append(message)
        st.session_state["live_logs"] = existing

        # keep last 200 messages to avoid huge UI slowdown
        st.session_state["live_logs"] = st.session_state["live_logs"][-200:]
        log_box.code("\n".join(st.session_state["live_logs"]), language="text")

    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    import os

    # =========================================================
    # CHROME OPTIONS
    # =========================================================

    chrome_options = Options()

    # Stable headless mode for Streamlit Cloud
    chrome_options.add_argument("--headless=new")

    # Required for cloud linux environments
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    # Prevent crashes
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")

    # Better rendering size
    chrome_options.add_argument("--window-size=1920,1080")

    # Prevent automation detection slightly
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # =========================================================
    # CHROME BINARY LOCATION
    # =========================================================

    possible_paths = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        ]

    for path in possible_paths:
        if os.path.exists(path):
            chrome_options.binary_location = path
            break

    # =========================================================
    # CREATE DRIVER
    # =========================================================

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    wait = WebDriverWait(driver, 20)

    decorative_keywords = {
        "lace": 3,
        "dentelle": 3,
        "embroidered": 3,
        "broderie": 3,
        "jacquard": 3,
        "farmhouse": 2,
        "rustic": 2,
        "floral": 2,
        "vintage": 2,
        "boho": 2,
        "elegant": 1,
        "stylish": 1,
        "refined": 1,
        "timeless": 1,
        "luxury": 1,
        "premium": 1,
        "classic": 1,
        "modern": 1,
    }

    waterproof_keywords = {
        "pvc": 4,
        "vinyl": 4,
        "oilproof": 4,
        "waterproof": 3,
        "imperméable": 3,
        "wipe clean": 3,
        "spill proof": 3,
        "coated": 2,
        "enduit": 2,
        "anti stain": 2,
        "anti-tache": 2,
        "stain resistant": 1,
    }

    titles_seen = set()
    product_data: List[Dict[str, Any]] = []

    try:
        log("Opening Amazon.fr")
        driver.get("https://www.amazon.fr")
        time.sleep(5)

        log("Accepting cookies if needed")
        try:
            cookie_button = wait.until(
                EC.element_to_be_clickable((By.ID, "sp-cc-accept"))
            )
            cookie_button.click()
            log("Cookies accepted")
        except Exception:
            log("No cookie popup")

        log(f"Setting delivery location to {postal_code}")
        try:
            delivery_button = wait.until(
                EC.element_to_be_clickable((By.ID, "glow-ingress-block"))
            )
            ActionChains(driver).move_to_element(delivery_button).perform()
            delivery_button.click()
            time.sleep(2)

            postal_input = wait.until(
                EC.presence_of_element_located((By.ID, "GLUXZipUpdateInput"))
            )
            postal_input.clear()
            postal_input.send_keys(postal_code)

            apply_button = wait.until(
                EC.element_to_be_clickable(
                    (By.XPATH, '//input[@aria-labelledby="GLUXZipUpdate-announce"]')
                )
            )
            apply_button.click()
            time.sleep(4)
            log("Delivery location applied")
        except Exception as e:
            log(f"Delivery location error: {e}")

        log(f"Searching keyword: {keyword}")
        search_box = wait.until(
            EC.presence_of_element_located((By.ID, "twotabsearchtextbox"))
        )
        search_box.send_keys(keyword)
        search_box.send_keys(Keys.ENTER)
        time.sleep(5)

        log("Scrolling full page to load products")
        last_height = driver.execute_script("return document.body.scrollHeight")
        while True:
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(3)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(2)

        products = driver.find_elements(By.CSS_SELECTOR, 'div[data-component-type="s-search-result"]')
        log(f"Products found: {len(products)}")

        for position, product in enumerate(products, start=1):
            status_box.text(f"Scraping position {position} / {len(products)}")
            progress_bar.progress(min(position / max(len(products), 1), 1.0))

            try:
                title = product.find_element(By.CSS_SELECTOR, "h2 span").text
            except Exception:
                continue

            if title in titles_seen:
                continue
            titles_seen.add(title)

            log(f"--- Position {position}: {title}")

            # sponsored
            sponsored = "NO"
            try:
                product.find_element(By.CSS_SELECTOR, ".puis-sponsored-label-text")
                sponsored = "YES"
            except Exception:
                sponsored = "NO"

            # price
            try:
                price_whole = product.find_element(By.CSS_SELECTOR, "span.a-price-whole").text
                price_fraction = product.find_element(By.CSS_SELECTOR, "span.a-price-fraction").text
                price = price_whole + "." + price_fraction
            except Exception:
                price = "0"

            try:
                numeric_price = float(price)
            except Exception:
                numeric_price = 0

            # original price
            try:
                original_price = product.find_element(
                    By.CSS_SELECTOR,
                    "span.a-price.a-text-price[data-a-strike='true'] span.a-offscreen"
                ).get_attribute("innerHTML")
                original_price = clean_text(original_price).replace("€", "").replace(",", ".")
                original_price = float(original_price)
            except Exception:
                original_price = numeric_price

            # discount
            try:
                discount_percent = round(((original_price - numeric_price) / original_price) * 100, 2)
            except Exception:
                discount_percent = 0

            # rating
            try:
                rating = product.find_element(By.CSS_SELECTOR, "span.a-icon-alt").get_attribute("innerHTML")
            except Exception:
                rating = "NO RATING"

            # review count
            try:
                review_count = product.find_element(By.CSS_SELECTOR, "span.a-size-mini").get_attribute("innerHTML")
            except Exception:
                review_count = "NO REVIEWS"

            # link
            try:
                link = product.find_element(By.CSS_SELECTOR, "a.a-link-normal").get_attribute("href")
            except Exception:
                continue

            # open product page
            driver.execute_script("window.open(arguments[0]);", link)
            driver.switch_to.window(driver.window_handles[1])
            time.sleep(2)

            # brand
            try:
                brand = driver.find_element(By.ID, "bylineInfo").text
            except Exception:
                brand = "NO BRAND"

            # product text blocks
            try:
                overview_block = driver.find_element(By.ID, "productOverview_feature_div").text
            except Exception:
                overview_block = ""

            try:
                product_info_parts = []
                for selector in [
                    "#productDetails_detailBullets_sections1",
                    "#productDetails_techSpec_section_1",
                    "#detailBulletsWrapper_feature_div"
                ]:
                    try:
                        block = driver.find_element(By.CSS_SELECTOR, selector).text
                        if block:
                            product_info_parts.append(block)
                    except Exception:
                        pass
                product_info = "\n".join(product_info_parts)
            except Exception:
                product_info = ""

            # expand accordions
            expand_accordions(driver)
            log("Accordions expanded")

            # BSR and style
            bsr = extract_bsr(driver)
            style = extract_style(driver)
            log(f"BSR: {bsr}")
            log(f"STYLE: {style}")

            # structured lines
            lines = (overview_block + "\n" + product_info).split("\n")

            # material
            material = "NOT FOUND"
            for line in lines:
                if "material" in line.lower() or "matériau" in line.lower():
                    material = (
                        line
                        .replace("Material", "")
                        .replace("Matériau", "")
                        .strip()
                    )

            # shape
            shape = "NOT FOUND"
            for line in lines:
                if "shape" in line.lower() or "forme" in line.lower():
                    shape = (
                        line
                        .replace("Item Shape", "")
                        .replace("Shape", "")
                        .replace("Forme", "")
                        .strip()
                    )

            # pattern
            pattern = "NOT FOUND"
            for line in lines:
                lower_line = line.lower()
                if "pattern" in lower_line or "motif" in lower_line:
                    pattern = (
                        line
                        .replace("Pattern", "")
                        .replace("Motif", "")
                        .strip()
                    )

            # bullets and title
            try:
                bullet_section = driver.find_element(By.ID, "feature-bullets").text
            except Exception:
                bullet_section = ""

            try:
                product_title = driver.find_element(By.ID, "productTitle").text
            except Exception:
                product_title = title

            # decorative
            decorative_score = 0
            decorative_text = (bullet_section + " " + product_title).lower()
            for word, score in decorative_keywords.items():
                if word in decorative_text:
                    decorative_score += score
            decorative = "YES" if decorative_score >= 3 else "NO"

            # waterproof
            waterproof_score = 0
            waterproof_text = (overview_block + " " + bullet_section + " " + product_title).lower()
            for word, score in waterproof_keywords.items():
                if word in waterproof_text:
                    waterproof_score += score
            waterproof = "YES" if waterproof_score >= 3 else "NO"

            # direct competitor
            material_lower = material.lower()
            shape_lower = shape.lower()
            price_match = False
            if 35 <= numeric_price <= 60:
                price_match = True
            elif 35 <= original_price <= 60 and discount_percent >= 10:
                price_match = True

            direct_competitor = "NO"
            if (
                ("cotton" in material_lower or "coton" in material_lower)
                and ("rectangular" in shape_lower or "rectangle" in shape_lower or "rectangulaire" in shape_lower)
                and decorative == "YES"
                and price_match
            ):
                direct_competitor = "YES"

            log(f"DECORATIVE: {decorative} | WATERPROOF: {waterproof} | DIRECT COMPETITOR: {direct_competitor}")

            product_data.append({
                "keyword": keyword,
                "search_position": position,
                "sponsored": sponsored,
                "direct_competitor": direct_competitor,
                "title": title,
                "brand": brand,
                "price": price,
                "original_price": original_price,
                "discount_percent": discount_percent,
                "rating": rating,
                "review_count": review_count,
                "bsr": bsr,
                "material": material,
                "shape": shape,
                "pattern": pattern,
                "style": style,
                "decorative_score": decorative_score,
                "decorative": decorative,
                "waterproof_score": waterproof_score,
                "waterproof": waterproof,
                "link": link
            })

            pd.DataFrame(product_data).to_csv(output_csv, index=False, encoding="utf-8-sig")
            log("CSV autosaved")

            # close product tab
            driver.close()
            driver.switch_to.window(driver.window_handles[0])
            time.sleep(1.2)

        status_box.success("Scraping complete")
        progress_bar.progress(1.0)
        log("FULL SCRAPE COMPLETE")

    finally:
        try:
            driver.quit()
        except Exception:
            pass

    return pd.DataFrame(product_data)


# =========================================================
# UI
# =========================================================

with st.sidebar:
    st.header("Settings")
    keyword_input = st.text_input("Keyword", value="nappe coton")
    postal_input = st.text_input("Postal code", value="75003")
    output_file = st.text_input("Output CSV", value="amakw1.csv")
    start_button = st.button("Start scraping")

st.subheader("Live logs")
log_box = st.empty()
progress_bar = st.progress(0.0)
status_box = st.empty()

if "live_logs" not in st.session_state:
    st.session_state["live_logs"] = []

if start_button:
    st.session_state["live_logs"] = []
    with st.spinner("Running scraper..."):
        df = run_scraper(
            keyword_input,
            postal_input,
            output_file,
            log_box,
            progress_bar,
            status_box
        )

    st.subheader("Results")
    st.dataframe(df, use_container_width=True)

    csv_data = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name=output_file,
        mime="text/csv"
    )
else:
    st.info("Enter a keyword in the sidebar and click Start scraping.")
