from playwright.sync_api import sync_playwright

URL = "https://ground.news/article/democrat-christian-menefee-wins-special-election-for-vacant-deep-blue-house-seat-in-texas"

def scrape():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_selector("div[id='article-summary']", timeout=60_000)

        cards = page.query_selector_all("div[id='article-summary']")
        print(f"Found {len(cards)} article cards")

        for card in cards:
            text = card.inner_text()

            link_el = card.query_selector("a[href]")
            if not link_el:
                continue

            href = link_el.get_attribute("href")

            if "Left" in text:
                bias = "Left"
            elif "Center" in text:
                bias = "Center"
            elif "Right" in text:
                bias = "Right"
            else:
                continue  # skip if no bias found

            results.append({
                "bias": bias,
                "link": href,
                "raw_text": text[:200],  # debug-safe
            })

        browser.close()

    return results


if __name__ == "__main__":
    data = scrape()
    print(f"\nCollected {len(data)} articles\n")
    for d in data:
        print(d)
