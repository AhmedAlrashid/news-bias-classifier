from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json
import re

URL = "https://ground.news/article/democrat-christian-menefee-wins-special-election-for-vacant-deep-blue-house-seat-in-texas"


with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto(URL, wait_until="domcontentloaded", timeout=30_000)
    page.wait_for_timeout(6000)  # allow Next.js RSC + scripts to load

    html = page.content()
    browser.close()

soup = BeautifulSoup(html, "html.parser")


title_elem = soup.find("h1")
title = title_elem.get_text(strip=True) if title_elem else None


sources = []

for a in soup.select("a[href^='https://']"):
    href = a.get("href")
    text = a.get_text(strip=True)

    if not href or not text:
        continue
    if text.lower() in {"read full article", "help center", "subscribe"}:
        continue
    if any(x in href for x in [
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "reddit.com",
        "linkedin.com",
        "bit.ly"
    ]):
        continue

    sources.append({
        "name": text,
        "url": href
    })


script_text = "\n".join(
    script.get_text()
    for script in soup.find_all("script")
    if script.get_text()
)



# Ground News embeds escaped JSON inside scripts:
#   \"politicalBias\":\"leanRight\"
unescaped = bytes(script_text, "utf-8").decode("unicode_escape")


bias_vals = re.findall(
    r'"politicalBias"\s*:\s*"([^"]+)"',
    unescaped
)

reviewers = re.findall(
    r'"reviewer"\s*:\s*\{[^}]*"name"\s*:\s*"([^"]+)"',
    unescaped
)

reference_urls = re.findall(
    r'"referenceUrl"\s*:\s*"([^"]+)"',
    unescaped
)

source_ids = re.findall(
    r'"sourceInfoId"\s*:\s*"([^"]+)"',
    unescaped
)


biasEvidence = []

count = min(
    len(bias_vals),
    len(reviewers),
    len(reference_urls),
    len(source_ids)
)

for i in range(count):
    biasEvidence.append({
        "politicalBias": bias_vals[i],
        "reviewer": reviewers[i],
        "referenceUrl": reference_urls[i],
        "sourceInfoId": source_ids[i]
    })


result = {
    "title": title,
    "sources": sources,
    "biasEvidence": biasEvidence
}

print(json.dumps(result, indent=2))
