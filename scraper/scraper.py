from playwright.sync_api import sync_playwright

URL = "https://ground.news/article/democrat-christian-menefee-wins-special-election-for-vacant-deep-blue-house-seat-in-texas"


def load_all_articles(page, max_clicks=30):
    for _ in range(max_clicks):
        clicked = page.evaluate("""
        () => {
            const btn = document.querySelector('#more-stories');
            if (!btn || btn.disabled) return false;
            btn.click();
            return true;
        }
        """)
        if not clicked:
            break
        page.wait_for_timeout(800)  # allow React to render

def extract_headline_and_summary(raw_text):
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]

    # Find the index of "Ownership"
    try:
        ownership_idx = lines.index("Ownership")
    except ValueError:
        return None, None

    content = lines[ownership_idx + 1:]

    if not content:
        return None, None

    headline = content[0]

    summary = None
    if len(content) > 1:
        # Stop summary at timestamps / junk
        summary_parts = []
        for l in content[1:]:
            if any(stop in l for stop in ["day ago", "days ago", "Read Full Article"]):
                break
            summary_parts.append(l)
        summary = " ".join(summary_parts) if summary_parts else None

    return headline, summary


def scrape():
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(URL, wait_until="domcontentloaded", timeout=60_000)
        page.evaluate("""
        () => {
            const modal = document.querySelector('#modal-content-wrapper');
            if (modal) modal.remove();

            const cookie = document.querySelector('.osano-cm-window');
            if (cookie) cookie.remove();
        }
        """)
        page.wait_for_selector("div[id='article-summary']", timeout=60_000)
        load_all_articles(page)
        cards = page.query_selector_all("div[id='article-summary']")
        print(f"Found {len(cards)} article cards")

        for card in cards:
            text = card.inner_text()

            link_el = card.query_selector("a[href]")
            if not link_el:
                continue

            href = link_el.get_attribute("href")

            # ---- Bias detection (capture all 7 labels like in Sakhawat et al., 2026) ----
            match text:
                case _ if "Far Right" in text:
                    bias = "Far Right"
                case _ if "Right" in text:
                    bias = "Right"
                case _ if "Lean Right" in text:
                    bias = "Lean Right"
                case _ if "Center" in text:
                    bias = "Center"
                case _ if "Lean Left" in text:
                    bias = "Lean Left"
                case _ if "Left" in text:
                    bias = "Left"
                case _ if "Far Left" in text:
                    bias = "Far Left"
                case _:
                    continue  # skip if no bias found

            # ---- outlet = first non-empty line ----
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            outlet = lines[0]

            # ---- headline + summary (YOU ALREADY WROTE THIS) ----
            headline, summary = extract_headline_and_summary(text)

            results.append({
                "outlet": outlet,
                "bias": bias,
                "headline": headline,
                "summary": summary,
                "ground_news_interest_url": "https://ground.news" + href
            })


        browser.close()

    return results


if __name__ == "__main__":
    data = scrape()
    print(f"\nCollected {len(data)} articles\n")
    for d in data:
        print(d)
