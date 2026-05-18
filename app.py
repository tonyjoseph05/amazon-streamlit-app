# -*- coding: utf-8 -*-
"""
Created on Mon May 18 16:05:31 2026

@author: Rony Joseph
"""

import re
import time
import os
from urllib.parse import quote_plus
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
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
    "best sellers rank",
    "best seller rank",
    "n° des meilleures ventes",
    "classement",
}

STYLE_LABELS = {
    "style",
    "style name"
}


def clean_text(text: str) -> str:
    if not text:
        return ""
    return re.sub(r"[\u200e\u200f\u200b\u202f\xa0]", " ", str(text)).strip()


def expand_accordions(driver):
    try:
        buttons = driver.find_elements(By.CSS_SELECTOR, ".a-expander-header")
        for button in buttons:
            try:
                driver.execute_script("arguments[0].click();", button)
                time.sleep(0.3)
            except Exception:
                pass
    except Exception:
        pass


def extract_bsr(driver) -> str:

    selectors = [
        "#detailBullets_feature_div li",
        "#detailBulletsWrapper_feature_div li",
    ]

    for selector in selectors:
        try:
            items = driver.find_elements(By.CSS_SELECTOR, selector)

            for item in items:

                full = clean_text(
                    item.get_attribute("textContent") or item.text
                )

                lower = full.lower()

                if any(label in lower for label in BSR_LABELS):
                    return full

        except Exception:
            pass

    return "NOT FOUND"


def extract_style(driver) -> str:

    selectors = [
        "#productOverview_feature_div tr",
        "#productDetails_detailBullets_sections1 tr",
        "#productDetails_techSpec_section_1 tr"
    ]

    for selector in selectors:

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
                    pass

        except Exception:
            pass

    return "NOT FOUND"


def build_driver():

    chrome_options = Options()

    # =========================================================
    # CLOUD SAFE
    # =========================================================

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")

    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")

    chrome_options.add_argument("--window-size=1920,1080")

    chrome_options.add_argument(
        "--disable-blink-features=AutomationControlled"
    )

    # =========================================================
    # BROWSER PATH
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
    # DRIVER
    # =========================================================

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )

    driver.set_page_load_timeout(60)

    return driver


# =========================================================
# SCRAPER
# =========================================================

def run_scraper(
    keyword: str,
    postal_code: str,
    output_csv: str,
    log_box,
    progress_bar,
    status_box
) -> pd.DataFrame:

    # =========================================================
    # LOGGER
    # =========================================================

    def log(message: str):

        existing = st.session_state.get("live_logs", [])

        existing.append(message)

        st.session_state["live_logs"] = existing[-200:]

        log_box.code(
            "\n".join(st.session_state["live_logs"]),
            language="text"
        )

    # =========================================================
    # DRIVER
    # =========================================================

    driver = build_driver()

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
    }

    waterproof_keywords = {
        "pvc": 4,
        "vinyl": 4,
        "waterproof": 3,
        "imperméable": 3,
        "wipe clean": 3,
        "spill proof": 3,
    }

    titles_seen = set()

    product_data: List[Dict[str, Any]] = []

    try:

        # =====================================================
        # OPEN AMAZON
        # =====================================================

        log("Opening Amazon.fr")

        driver.get("https://www.amazon.fr")

        time.sleep(5)

        # =====================================================
        # ACCEPT COOKIES
        # =====================================================

        log("Accepting cookies if needed")

        try:

            cookie_button = wait.until(
                EC.element_to_be_clickable(
                    (By.ID, "sp-cc-accept")
                )
            )

            cookie_button.click()

            log("Cookies accepted")

            time.sleep(2)

        except Exception:
            log("No cookie popup")

        # =====================================================
        # DELIVERY LOCATION
        # =====================================================

        log(f"Setting delivery location to {postal_code}")

        try:

            delivery_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable(
                    (By.ID, "glow-ingress-block")
                )
            )

            driver.execute_script(
                "arguments[0].click();",
                delivery_button
            )

            time.sleep(2)

            postal_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located(
                    (By.ID, "GLUXZipUpdateInput")
                )
            )

            postal_input.clear()

            postal_input.send_keys(postal_code)

            applied = False

            possible_buttons = [

                (
                    By.XPATH,
                    '//input[@aria-labelledby="GLUXZipUpdate-announce"]'
                ),

                (
                    By.XPATH,
                    '//button[contains(@id,"GLUXZipUpdate")]'
                ),
            ]

            for locator in possible_buttons:

                try:

                    apply_button = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable(locator)
                    )

                    driver.execute_script(
                        "arguments[0].click();",
                        apply_button
                    )

                    applied = True

                    break

                except Exception:
                    pass

            time.sleep(4)

            if applied:
                log("Delivery location applied")
            else:
                log("Delivery popup opened but apply button not found")

        except Exception as e:
            log(f"Delivery location error: {e}")

        # =====================================================
        # SEARCH
        # =====================================================

        log(f"Searching keyword: {keyword}")

        search_url = f"https://www.amazon.fr/s?k={quote_plus(keyword)}"
        driver.get(search_url)
        time.sleep(3)

        def has_products():
            selectors = [
                'div[data-component-type="s-search-result"]',
                'div.s-main-slot div[data-asin]',
                'div.s-result-item[data-asin]',
            ]
            for selector in selectors:
                try:
                    if driver.find_elements(By.CSS_SELECTOR, selector):
                        return True
                except Exception:
                    pass
            return False

        ready = False
        end_time = time.time() + 30

        while time.time() < end_time:
            if has_products():
                ready = True
                break
            time.sleep(1)

        log(f"Search URL: {driver.current_url}")
        log(f"Search title: {driver.title}")

        if not ready:
            try:
                driver.save_screenshot("amazon_search_failed.png")
            except Exception:
                pass

            page_text = (driver.title or "") + "\n" + (driver.page_source or "")
            log("Search page did not expose product cards.")
            log(page_text[:1000])

            raise Exception("Amazon search results failed to load.")

        # =====================================================
        # HUMAN-LIKE SEARCH
        # =====================================================

        search_url = f"https://www.amazon.fr/s?k={quote_plus(keyword)}"

        driver.get(search_url)

        # wait for DOM
        time.sleep(5)

        # small human-like scroll
        try:
            driver.execute_script("window.scrollTo(0, 300)")
            time.sleep(1)

            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)
        except Exception:
            pass

        # =====================================================
        # WAIT FOR PRODUCTS
        # =====================================================

        products_loaded = False

        for _ in range(30):

            try:

                products = driver.find_elements(
                    By.CSS_SELECTOR,
                    'div[data-component-type="s-search-result"]'
                )

                if len(products) > 0:
                    products_loaded = True
                    break

            except Exception:
                pass

            time.sleep(1)

        log(
            f"Current URL: {driver.current_url} | "
            f"Title: {driver.title}"
        )

        if not products_loaded:

            page_text = (
                (driver.title or "") +
                " " +
                (driver.page_source or "")
            ).lower()

            if (
                "captcha" in page_text
                or
                "robot" in page_text
                or
                "sorry" in page_text
            ):
                raise Exception(
                    "Amazon blocked the scraper with CAPTCHA."
                )

            raise Exception(
                "Amazon search results failed to load."
            )

        log("Search results loaded successfully")

        # =====================================================
        # SCROLL
        # =====================================================

        log("Scrolling page")

        last_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        while True:

            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )

            time.sleep(2)

            new_height = driver.execute_script(
                "return document.body.scrollHeight"
            )

            if new_height == last_height:
                break

            last_height = new_height

        driver.execute_script("window.scrollTo(0, 0);")

        time.sleep(2)

        # =====================================================
        # PRODUCTS
        # =====================================================

        products = driver.find_elements(
            By.CSS_SELECTOR,
            'div[data-component-type="s-search-result"]'
        )

        log(f"Products found: {len(products)}")

        for position, product in enumerate(products, start=1):

            status_box.text(
                f"Scraping position {position}/{len(products)}"
            )

            progress_bar.progress(
                min(position / max(len(products), 1), 1.0)
            )

            try:
                title = product.find_element(
                    By.CSS_SELECTOR,
                    "h2 span"
                ).text
            except Exception:
                continue

            if title in titles_seen:
                continue

            titles_seen.add(title)

            log(f"Position {position}: {title}")

            # =================================================
            # SPONSORED
            # =================================================

            sponsored = "NO"

            try:
                product.find_element(
                    By.CSS_SELECTOR,
                    ".puis-sponsored-label-text"
                )
                sponsored = "YES"
            except Exception:
                pass

            # =================================================
            # PRICE
            # =================================================

            try:

                whole = product.find_element(
                    By.CSS_SELECTOR,
                    "span.a-price-whole"
                ).text

                fraction = product.find_element(
                    By.CSS_SELECTOR,
                    "span.a-price-fraction"
                ).text

                price = f"{whole}.{fraction}"

            except Exception:
                price = "0"

            try:
                numeric_price = float(
                    price.replace(",", ".")
                )
            except Exception:
                numeric_price = 0

            # =================================================
            # RATING
            # =================================================

            try:
                rating = product.find_element(
                    By.CSS_SELECTOR,
                    "span.a-icon-alt"
                ).text
            except Exception:
                rating = "NO RATING"

            # =================================================
            # REVIEWS
            # =================================================

            try:
                review_count = product.find_element(
                    By.CSS_SELECTOR,
                    "span.a-size-base.s-underline-text"
                ).text
            except Exception:
                review_count = "NO REVIEWS"

            # =================================================
            # PRODUCT LINK
            # =================================================

            try:

                link = product.find_element(
                    By.CSS_SELECTOR,
                    "a.a-link-normal.s-no-outline"
                ).get_attribute("href")

            except Exception:
                continue

            # =================================================
            # OPEN PRODUCT PAGE
            # =================================================

            driver.execute_script(
                "window.open(arguments[0]);",
                link
            )

            driver.switch_to.window(driver.window_handles[1])

            time.sleep(3)

            # =================================================
            # BRAND
            # =================================================

            try:
                brand = driver.find_element(
                    By.ID,
                    "bylineInfo"
                ).text
            except Exception:
                brand = "NO BRAND"

            # =================================================
            # OVERVIEW
            # =================================================

            try:
                overview_block = driver.find_element(
                    By.ID,
                    "productOverview_feature_div"
                ).text
            except Exception:
                overview_block = ""

            # =================================================
            # PRODUCT INFO
            # =================================================

            product_info_parts = []

            selectors = [

                # main detail tables
                "#productDetails_detailBullets_sections1",
                "#productDetails_techSpec_section_1",

                # bullet wrappers
                "#detailBulletsWrapper_feature_div",
                "#detailBullets_feature_div",

                # overview
                "#productOverview_feature_div",

                # feature bullets
                "#feature-bullets",

                # additional info
                "#aplus",

                # technical details
                "#technicalSpecifications_section_1",

                # generic tables
                "table.a-normal.a-spacing-micro",
                "table.a-keyvalue",

                # expandable sections
                ".a-expander-content",

            ]

            seen_blocks = set()

            for selector in selectors:

                try:

                    elements = driver.find_elements(
                        By.CSS_SELECTOR,
                        selector
                    )

                    for element in elements:

                        try:

                            text = clean_text(
                                element.get_attribute("textContent")
                                or
                                element.text
                            )

                            if (
                                text
                                and
                                len(text) > 20
                                and
                                text not in seen_blocks
                            ):

                                seen_blocks.add(text)

                                product_info_parts.append(text)

                        except Exception:
                            pass

                except Exception:
                    pass

            product_info = "\n\n".join(product_info_parts)

            log(
                f"Collected product info blocks: "
                f"{len(product_info_parts)}"
            )

            # =================================================
            # EXPAND
            # =================================================

            expand_accordions(driver)

            # =================================================
            # BSR / STYLE
            # =================================================

            bsr = extract_bsr(driver)

            style = extract_style(driver)

            # =================================================
            # MATERIAL / SHAPE / PATTERN
            # =================================================

            lines = (
                overview_block +
                "\n" +
                product_info
            ).split("\n")

            material = "NOT FOUND"
            shape = "NOT FOUND"
            pattern = "NOT FOUND"

            for line in lines:

                lower = line.lower()

                if "material" in lower or "matériau" in lower:
                    material = line

                if "shape" in lower or "forme" in lower:
                    shape = line

                if "pattern" in lower or "motif" in lower:
                    pattern = line

            # =================================================
            # BULLETS
            # =================================================

            try:
                bullet_section = driver.find_element(
                    By.ID,
                    "feature-bullets"
                ).text
            except Exception:
                bullet_section = ""

            # =================================================
            # DECORATIVE SCORE
            # =================================================

            decorative_score = 0

            decorative_text = (
                bullet_section +
                " " +
                title
            ).lower()

            for word, score in decorative_keywords.items():

                if word in decorative_text:
                    decorative_score += score

            decorative = (
                "YES"
                if decorative_score >= 3
                else "NO"
            )

            # =================================================
            # WATERPROOF SCORE
            # =================================================

            waterproof_score = 0

            waterproof_text = (
                overview_block +
                " " +
                bullet_section +
                " " +
                title
            ).lower()

            for word, score in waterproof_keywords.items():

                if word in waterproof_text:
                    waterproof_score += score

            waterproof = (
                "YES"
                if waterproof_score >= 3
                else "NO"
            )

            # =================================================
            # DIRECT COMPETITOR
            # =================================================

            material_lower = material.lower()

            shape_lower = shape.lower()

            price_match = 35 <= numeric_price <= 60

            direct_competitor = "NO"

            if (
                (
                    "cotton" in material_lower
                    or
                    "coton" in material_lower
                )
                and
                (
                    "rectangular" in shape_lower
                    or
                    "rectangle" in shape_lower
                    or
                    "rectangulaire" in shape_lower
                )
                and decorative == "YES"
                and price_match
            ):
                direct_competitor = "YES"

            # =================================================
            # SAVE
            # =================================================

            product_data.append({

                "keyword": keyword,

                "search_position": position,

                "sponsored": sponsored,

                "direct_competitor": direct_competitor,

                "title": title,

                "brand": brand,

                "price": price,

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

            # =================================================
            # AUTOSAVE
            # =================================================

            pd.DataFrame(product_data).to_csv(
                output_csv,
                index=False,
                encoding="utf-8-sig"
            )

            log("CSV autosaved")

            # =================================================
            # CLOSE TAB
            # =================================================

            driver.close()

            driver.switch_to.window(driver.window_handles[0])

            time.sleep(1)

        # =====================================================
        # COMPLETE
        # =====================================================

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

    keyword_input = st.text_input(
        "Keyword",
        value="nappe coton"
    )

    postal_input = st.text_input(
        "Postal code",
        value="75003"
    )

    output_file = st.text_input(
        "Output CSV",
        value="amakw1.csv"
    )

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

    st.dataframe(
        df,
        use_container_width=True
    )

    csv_data = df.to_csv(index=False).encode("utf-8-sig")

    st.download_button(
        "Download CSV",
        data=csv_data,
        file_name=output_file,
        mime="text/csv"
    )

else:
    st.info(
        "Enter a keyword in the sidebar and click Start scraping."
    )