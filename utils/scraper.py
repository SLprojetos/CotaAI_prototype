import requests
from bs4 import BeautifulSoup
import os
import time
from typing import List, Dict
from urllib.parse import quote_plus
from concurrent.futures import ThreadPoolExecutor

USER_AGENT = os.getenv("USER_AGENT", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
HEADERS = {"User-Agent": USER_AGENT}
TIMEOUT = 8

SOURCES = [
    "mercado_livre",
    "olx",
    "amazon_br",
    "shopee",
    "magazineluiza",
    "casas_bahia",
    "aliexpress"
]

def search_all_sources_for_item(item: str, max_results_per_site: int = 3) -> List[Dict]:
    """
    Realiza buscas em todas as fontes listadas e retorna resultados como dicionários.
    Cada site tem uma função simples que tenta obter título, preço e link.
    """
    results = []
    # rodada simples de chamadas paralelas por site
    with ThreadPoolExecutor(max_workers=min(6, len(SOURCES))) as ex:
        futures = []
        for src in SOURCES:
            futures.append(ex.submit(_search_site, src, item, max_results_per_site))
        for f in futures:
            try:
                items = f.result()
                results.extend(items)
            except Exception as e:
                results.append({"item": item, "origin": None, "title": None, "price": None, "link": None, "status": f"error: {e}"})
    # adicionar item field
    for r in results:
        r.setdefault("item", item)
    return results

def _search_site(site: str, item: str, max_results: int):
    func = SITE_FUNCS.get(site)
    if not func:
        return []
    try:
        return func(item, max_results)
    except Exception as e:
        return [{"origin": site, "title": None, "price": None, "link": None, "status": f"error: {e}"}]

def _get(url, params=None):
    r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r

def _parse_price(price_str):
    if not price_str:
        return None
    s = price_str.replace("\n", " ").strip()
    # remove non number except , and .
    import re
    s2 = re.sub(r"[^\d,\.]", "", s)
    # normalize comma decimal -> dot
    if s2.count(",") == 1 and s2.count(".") == 0:
        s2 = s2.replace(",", ".")
    # remove thousands separator
    s2 = s2.replace(".", "")
    try:
        return float(s2)
    except:
        try:
            return float(s2.replace(",", "."))
        except:
            return None

# Site-specific (simples e frágil — pode necessitar ajustes)
def search_mercado_livre(item, max_results):
    q = quote_plus(item)
    url = f"https://lista.mercadolivre.com.br/{q}"
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("li.ui-search-layout__item") or soup.select(".ui-search-result__wrapper")
    out = []
    for c in cards[:max_results]:
        title = c.select_one(".ui-search-item__title") or c.select_one(".ui-search-link")
        price = c.select_one(".price-tag .price-tag-fraction") or c.select_one(".andes-money-amount__fraction")
        link = c.select_one("a[href]")
        out.append({
            "origin": "mercado_livre",
            "title": title.get_text(strip=True) if title else None,
            "price": _parse_price(price.get_text() if price else None),
            "link": link["href"] if link else None,
            "status": "ok" if title else "no-title"
        })
    return out

def search_olx(item, max_results):
    q = quote_plus(item)
    url = f"https://www.olx.com.br/list/q-{q}"
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("li.sc-1fcmfeb-2, .sc-1fcmfeb-1")  # OLX changes often
    out = []
    for c in cards[:max_results]:
        title = c.select_one("h2") or c.select_one(".sc-1kn0k8r-1")
        price = c.select_one("p.sc-ifAKCX") or c.select_one(".sc-ifAKCX")
        link = c.select_one("a[href]")
        out.append({
            "origin": "olx",
            "title": title.get_text(strip=True) if title else None,
            "price": _parse_price(price.get_text() if price else None),
            "link": link["href"] if link else None,
            "status": "ok" if title else "no-title"
        })
    return out

def search_amazon_br(item, max_results):
    # Amazon blocks easily; this is a best-effort minimal search using the search page
    q = quote_plus(item)
    url = f"https://www.amazon.com.br/s?k={q}"
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("div.s-result-item")
    out = []
    for c in cards[:max_results]:
        title = c.select_one("h2 a span")
        price_whole = c.select_one(".a-price-whole")
        price_frac = c.select_one(".a-price-fraction")
        link = c.select_one("h2 a[href]")
        price_text = None
        if price_whole:
            price_text = (price_whole.get_text() or "") + (price_frac.get_text() if price_frac else "")
        out.append({
            "origin": "amazon_br",
            "title": title.get_text(strip=True) if title else None,
            "price": _parse_price(price_text),
            "link": ("https://www.amazon.com.br" + link["href"]) if link else None,
            "status": "ok" if title else "no-title"
        })
    return out

def search_shopee(item, max_results):
    q = quote_plus(item)
    url = f"https://shopee.com.br/search?keyword={q}"
    # Shopee usa muito JS — this may return little, but try
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("div.shopee-search-item-result__item") or soup.select(".shopee-search-item-result__item")
    out = []
    for c in cards[:max_results]:
        title = c.select_one("div._10Wbs-") or c.select_one(".yQmmFK")
        price = c.select_one("div._1w9jLI") or c.select_one(".value")
        link = c.select_one("a[href]")
        out.append({
            "origin": "shopee",
            "title": title.get_text(strip=True) if title else None,
            "price": _parse_price(price.get_text() if price else None),
            "link": ("https://shopee.com.br" + link["href"]) if link else None,
            "status": "ok" if title else "no-title"
        })
    return out

def search_magazineluiza(item, max_results):
    q = quote_plus(item)
    url = f"https://www.magazineluiza.com.br/busca/{q}/"
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select(".product-list li") or soup.select(".sc-1k9k6o3-0")
    out = []
    for c in cards[:max_results]:
        title = c.select_one(".product-card__title") or c.select_one("h2")
        price = c.select_one(".product-price")
        link = c.select_one("a[href]")
        out.append({
            "origin": "magazineluiza",
            "title": title.get_text(strip=True) if title else None,
            "price": _parse_price(price.get_text() if price else None),
            "link": ("https://www.magazineluiza.com.br" + link["href"]) if link else None,
            "status": "ok" if title else "no-title"
        })
    return out

def search_casas_bahia(item, max_results):
    q = quote_plus(item)
    url = f"https://www.casasbahia.com.br/busca/{q}/"
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select(".product-item") or soup.select(".sc-")
    out = []
    for c in cards[:max_results]:
        title = c.select_one(".product-title") or c.select_one(".name")
        price = c.select_one(".price")
        link = c.select_one("a[href]")
        out.append({
            "origin": "casas_bahia",
            "title": title.get_text(strip=True) if title else None,
            "price": _parse_price(price.get_text() if price else None),
            "link": ("https://www.casasbahia.com.br" + link["href"]) if link else None,
            "status": "ok" if title else "no-title"
        })
    return out

def search_aliexpress(item, max_results):
    q = quote_plus(item)
    url = f"https://pt.aliexpress.com/wholesale?SearchText={q}"
    resp = _get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select(".list-item, .JIIxO") or soup.select(".product")
    out = []
    for c in cards[:max_results]:
        title = c.select_one(".item-title") or c.select_one("h1")
        price = c.select_one(".price")
        link = c.select_one("a[href]")
        out.append({
            "origin": "aliexpress",
            "title": title.get_text(strip=True) if title else None,
            "price": _parse_price(price.get_text() if price else None),
            "link": (link["href"] if link else None),
            "status": "ok" if title else "no-title"
        })
    return out

SITE_FUNCS = {
    "mercado_livre": search_mercado_livre,
    "olx": search_olx,
    "amazon_br": search_amazon_br,
    "shopee": search_shopee,
    "magazineluiza": search_magazineluiza,
    "casas_bahia": search_casas_bahia,
    "aliexpress": search_aliexpress,
}