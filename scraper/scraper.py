from playwright.sync_api import sync_playwright
import re
import time
import random
import json
import os
from pathlib import Path
from datetime import datetime


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


def title_to_slug(title):
    """Convert article title to URL slug format"""
    # Convert to lowercase and replace spaces and special chars with hyphens
    slug = re.sub(r'[^a-zA-Z0-9\s-]', '', title.lower())
    slug = re.sub(r'\s+', '-', slug)
    slug = re.sub(r'-+', '-', slug)  # Remove multiple hyphens
    slug = slug.strip('-')  # Remove leading/trailing hyphens
    return slug


def discover_article_urls_from_homepage(link,max_articles=25):
    """Go to Ground News homepage and extract article titles to build URLs"""
    article_urls = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Set to True for production
        page = browser.new_page()
        
        try:
            print("Going to Ground News homepage...")
            page.goto(link, wait_until="domcontentloaded", timeout=60_000)
        except Exception as e:
            print(f"  -> Homepage load error: {e}")
            browser.close()
            return article_urls
        
        # Handle popups
        page.evaluate("""
        () => {
            const modal = document.querySelector('#modal-content-wrapper');
            if (modal) modal.remove();
            const cookie = document.querySelector('.osano-cm-window');
            if (cookie) cookie.remove();
        }
        """)
        
        # Scroll to load more articles
        for i in range(3):
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)
        
        # Extract article titles - try multiple selectors
        titles = page.evaluate("""
        () => {
            // Focus on extracting existing article links first (most reliable)
            const articleLinks = [];
            
            // Get all existing article links
            const linkElements = document.querySelectorAll('a[href*="/article/"]');
            for (const el of linkElements) {
                const href = el.getAttribute('href');
                if (href && href.includes('/article/') && href.length > 10) {
                    const fullSlug = href.split('/article/')[1];
                    if (fullSlug && fullSlug.includes('_')) {  // Ensure it has the ID part
                        articleLinks.push(fullSlug);
                    }
                }
            }
            
            // If we don't have enough links, try to extract from titles
            if (articleLinks.length < 5) {
                const titleSelectors = [
                    'h1', 'h2', 'h3',  // Headlines 
                    '.headline', '.title',     // Common class names
                    '[data-article]', '[data-story]'  // Data attributes
                ];
                
                for (const selector of titleSelectors) {
                    const elements = document.querySelectorAll(selector);
                    for (const el of elements) {
                        const text = el.innerText || el.textContent;
                        
                        if (text && text.trim().length > 10) {
                            // Add title text for manual slug creation
                            articleLinks.push(text.trim());
                        }
                    }
                }
            }
            
            // Remove duplicates
            return [...new Set(articleLinks)];
        }
        """)
        
        browser.close()
    
    # Convert titles to URLs
    for title in titles[:max_articles]:
        if '/' in title and title.startswith('/'):
            # Already a full path
            article_urls.append(f"https://ground.news{title}")
        elif '_' in title and len(title) > 10:
            # Already a slug with ID (e.g., "warner-reopens-talks_f65462")
            article_urls.append(f"https://ground.news/article/{title}")
        else:
            # Convert title to slug and add placeholder ID
            slug = title_to_slug(title)
            if slug:
                # Add a placeholder ID since we don't know the real one
                placeholder_id = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=6))
                article_urls.append(f"https://ground.news/article/{slug}_{placeholder_id}")
    
    print(f"Discovered {len(article_urls)} article URLs")
    return article_urls

def extract_headline_and_summary(raw_text):
    lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

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
        for line in content[1:]:
            if any(stop in line for stop in ["day ago", "days ago", "Read Full Article"]):
                break
            summary_parts.append(line)
        summary = " ".join(summary_parts) if summary_parts else None

    return headline, summary


def scrape(url=None):
    results = []
    target_url = url or URL  # Use provided URL or default

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            # Go to the page with shorter timeout
            response = page.goto(target_url, wait_until="domcontentloaded", timeout=30_000)
            
            # Check HTTP status code first
            if response and response.status >= 400:
                print(f"  -> HTTP {response.status} Error")
                browser.close()
                return []
            
            # Check page title and content for more specific 404 indicators
            page_title = page.title()
            print(f"  -> Page loaded: '{page_title}'")
            
            # More specific 404 detection
            page_content = page.content()
            if (response and response.status == 404) or \
               ("404" in page_title.lower()) or \
               ("not found" in page_title.lower()) or \
               ("page not found" in page_content.lower()[:1000]):
                print(f"  -> 404 Error: Article not found")
                browser.close()
                return []
            
        except Exception as e:
            print(f"  -> Page load error: {e}")
            browser.close()
            return []

        try:
            page.evaluate("""
            () => {
                const modal = document.querySelector('#modal-content-wrapper');
                if (modal) modal.remove();

                const cookie = document.querySelector('.osano-cm-window');
                if (cookie) cookie.remove();
            }
            """)
            
            # Check if article summary exists with timeout
            try:
                page.wait_for_selector("div[id='article-summary']", timeout=15_000)
                print(f"  -> Article content structure found")
            except Exception as selector_error:
                print(f"  -> No article-summary div found: {selector_error}")
                
                # Try alternative selectors that might indicate a valid article page
                alternative_selectors = [
                    ".coverage-card", ".source-card", ".article-header", 
                    "[data-testid='coverage']", ".bias-indicator"
                ]
                
                found_alternative = False
                for alt_selector in alternative_selectors:
                    try:
                        alt_elements = page.query_selector_all(alt_selector)
                        if alt_elements:
                            print(f"  -> Found alternative content: {alt_selector} ({len(alt_elements)} elements)")
                            found_alternative = True
                            break
                    except:
                        continue
                
                if not found_alternative:
                    print(f"  -> No recognizable article content found")
                    browser.close()
                    return []
                
            load_all_articles(page)
            cards = page.query_selector_all("div[id='article-summary']")
            print(f"  -> Found {len(cards)} article cards")

            for card in cards:
                text = card.inner_text()

                link_el = card.query_selector("a[href]")
                if not link_el:
                    continue

                href = link_el.get_attribute("href")

                # ---- Bias detection (only collect Far Left and Lean Right) ----
                match text:
                    case _ if "Far Left" in text:
                        bias = "Far Left"
                    case _ if "Lean Right" in text:
                        bias = "Lean Right"
                    case _:
                        continue  # skip all other bias categories

                # ---- outlet = first non-empty line ----
                lines = [line.strip() for line in text.split("\n") if line.strip()]
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

        except Exception as e:
            print(f"  -> Scraping error: {e}")
        
        browser.close()

    return results


def scrape_multiple_from_homepage(link, max_articles=25):
    """Discover article URLs from homepage and scrape each one"""
    all_results = []
    successful_scrapes = 0
    
    # Discover URLs from homepage
    article_urls = discover_article_urls_from_homepage(link,max_articles)
    
    if not article_urls:
        print("No article URLs discovered from homepage")
        return all_results
    
    # Scrape each discovered URL
    for i, url in enumerate(article_urls):
        print(f"\nScraping [{i+1}/{len(article_urls)}]: {url}")
        
        results = scrape(url)
        if results:
            all_results.extend(results)
            successful_scrapes += 1
            print(f"  -> Success! Found {len(results)} sources")
        else:
            print(f"  -> Skipped (no data found)")
        
        # Be polite to server
        time.sleep(2.0)
    
    print(f"\n=== Summary ===")
    print(f"Attempted: {len(article_urls)} articles")
    print(f"Successful: {successful_scrapes} articles")
    print(f"Total sources: {len(all_results)}")
    
    return all_results, successful_scrapes


def save_data_to_file(data, filename=None):
    """Save scraped data to JSON file with timestamp"""
    if not data:
        print("No data to save")
        return None
    
    # Generate filename with timestamp if not provided
    output_dir = Path("scraper") / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"ground_news_data_{timestamp}.json"
    else:
        filename = output_dir / filename
    
    try:
        # Save as pretty-printed JSON
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"\n Data saved to: {filename}")
        print(f" Total records: {len(data)}")
        
        # Show bias distribution
        bias_counts = {}
        for item in data:
            bias = item.get('bias', 'Unknown')
            bias_counts[bias] = bias_counts.get(bias, 0) + 1
        
        print(f" Bias distribution:")
        for bias, count in sorted(bias_counts.items()):
            print(f"   {bias}: {count}")
        
        return filename
    
    except Exception as e:
        print(f" Error saving data: {e}")
        return None


def save_data_to_csv(data, filename=None):
    """Alternative: Save as CSV for easy viewing in Excel/Google Sheets"""
    if not data:
        print("No data to save")
        return None
        
    import csv
    
    # Generate filename with timestamp if not provided
    output_dir = Path("scraper") / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = output_dir / f"ground_news_data_{timestamp}.csv"
    else:
        filename = output_dir / filename
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        
        print(f"\n CSV saved to: {filename}")
        return filename
    
    except Exception as e:
        print(f" Error saving CSV: {e}")
        return None


if __name__ == "__main__":
    # MODE 1: Scrape single article (original)
    # data = scrape()
    links= [
    "https://web.archive.org//web/20250117/ground.news",
    "https://web.archive.org//web/20250118/ground.news",
    "https://web.archive.org//web/20250119/ground.news",
    "https://web.archive.org//web/20250120/ground.news",
    "https://web.archive.org//web/20250121/ground.news",
    "https://web.archive.org//web/20250122/ground.news",
    "https://web.archive.org//web/20250123/ground.news",
    "https://web.archive.org//web/20250124/ground.news",
    "https://web.archive.org//web/20250125/ground.news",
    "https://web.archive.org//web/20250126/ground.news",
    "https://web.archive.org//web/20250127/ground.news",
    "https://web.archive.org//web/20250128/ground.news",
    "https://web.archive.org//web/20250129/ground.news",
    "https://web.archive.org//web/20250130/ground.news",
    "https://web.archive.org//web/20250131/ground.news",
    "https://web.archive.org//web/20250201/ground.news",
    "https://web.archive.org//web/20250202/ground.news",
    "https://web.archive.org//web/20250204/ground.news",
    "https://web.archive.org//web/20250205/ground.news",
    "https://web.archive.org//web/20250206/ground.news",
    "https://web.archive.org//web/20250207/ground.news",
    "https://web.archive.org//web/20250208/ground.news",
    "https://web.archive.org//web/20250209/ground.news",
    "https://web.archive.org//web/20250210/ground.news",
    "https://web.archive.org//web/20250211/ground.news",
    "https://web.archive.org//web/20250212/ground.news",
    "https://web.archive.org//web/20250213/ground.news",
    "https://web.archive.org//web/20250214/ground.news",
    "https://web.archive.org//web/20250215/ground.news",
    "https://web.archive.org//web/20250216/ground.news",
    "https://web.archive.org//web/20250217/ground.news",
    "https://web.archive.org//web/20250218/ground.news",
    "https://web.archive.org//web/20250219/ground.news",
    "https://web.archive.org//web/20250220/ground.news",
    "https://web.archive.org//web/20250221/ground.news",
    "https://web.archive.org//web/20250222/ground.news",
    "https://web.archive.org//web/20250223/ground.news",
    "https://web.archive.org//web/20250224/ground.news",
    "https://web.archive.org//web/20250225/ground.news",
    "https://web.archive.org//web/20250226/ground.news",
    "https://web.archive.org//web/20250227/ground.news",
    "https://web.archive.org//web/20250228/ground.news",
    "https://web.archive.org//web/20250301/ground.news",
    "https://web.archive.org//web/20250302/ground.news",
    "https://web.archive.org//web/20250303/ground.news",
    "https://web.archive.org//web/20250304/ground.news",
    "https://web.archive.org//web/20250305/ground.news",
    "https://web.archive.org//web/20250306/ground.news",
    "https://web.archive.org//web/20250307/ground.news",
    "https://web.archive.org//web/20250308/ground.news",
    "https://web.archive.org//web/20250309/ground.news",
    "https://web.archive.org//web/20250310/ground.news",
    "https://web.archive.org//web/20250311/ground.news",
    "https://web.archive.org//web/20250312/ground.news",
    "https://web.archive.org//web/20250313/ground.news",
    "https://web.archive.org//web/20250314/ground.news",
    "https://web.archive.org//web/20250315/ground.news",
    "https://web.archive.org//web/20250316/ground.news",
    "https://web.archive.org//web/20250317/ground.news",
    "https://web.archive.org//web/20250318/ground.news",
    "https://web.archive.org//web/20250319/ground.news",
    "https://web.archive.org//web/20250320/ground.news",
    "https://web.archive.org//web/20250321/ground.news",
    "https://web.archive.org//web/20250322/ground.news",
    "https://web.archive.org//web/20250323/ground.news",
    "https://web.archive.org//web/20250324/ground.news",
    "https://web.archive.org//web/20250325/ground.news",
    "https://web.archive.org//web/20250326/ground.news",
    "https://web.archive.org//web/20250327/ground.news",
    "https://web.archive.org//web/20250328/ground.news",
    "https://web.archive.org//web/20250329/ground.news",
    "https://web.archive.org//web/20250330/ground.news",
    "https://web.archive.org//web/20250331/ground.news",
    "https://web.archive.org//web/20250401/ground.news",
    "https://web.archive.org//web/20250402/ground.news",
    "https://web.archive.org//web/20250403/ground.news",
    "https://web.archive.org//web/20250404/ground.news",
    "https://web.archive.org//web/20250405/ground.news",
    "https://web.archive.org//web/20250406/ground.news",
    "https://web.archive.org//web/20250407/ground.news",
    "https://web.archive.org//web/20250408/ground.news",
    "https://web.archive.org//web/20250409/ground.news",
    "https://web.archive.org//web/20250410/ground.news",
    "https://web.archive.org//web/20250411/ground.news",
    "https://web.archive.org//web/20250412/ground.news",
    "https://web.archive.org//web/20250413/ground.news",
    "https://web.archive.org//web/20250414/ground.news",
    "https://web.archive.org//web/20250415/ground.news",
    "https://web.archive.org//web/20250416/ground.news",
    "https://web.archive.org//web/20250417/ground.news",
    "https://web.archive.org//web/20250418/ground.news",
    "https://web.archive.org//web/20250419/ground.news",
    "https://web.archive.org//web/20250420/ground.news",
    "https://web.archive.org//web/20250421/ground.news",
    "https://web.archive.org//web/20250422/ground.news",
    "https://web.archive.org//web/20250423/ground.news",
    "https://web.archive.org//web/20250424/ground.news",
    "https://web.archive.org//web/20250425/ground.news",
    "https://web.archive.org//web/20250426/ground.news",
    "https://web.archive.org//web/20250427/ground.news",
    "https://web.archive.org//web/20250428/ground.news",
    "https://web.archive.org//web/20250429/ground.news",
    "https://web.archive.org//web/20250430/ground.news",
    "https://web.archive.org//web/20250501/ground.news",
    "https://web.archive.org//web/20250502/ground.news",
    "https://web.archive.org//web/20250503/ground.news",
    "https://web.archive.org//web/20250504/ground.news",
    "https://web.archive.org//web/20250505/ground.news",
    "https://web.archive.org//web/20250506/ground.news",
    "https://web.archive.org//web/20250507/ground.news",
    "https://web.archive.org//web/20250508/ground.news",
    "https://web.archive.org//web/20250509/ground.news",
    "https://web.archive.org//web/20250510/ground.news",
    "https://web.archive.org//web/20250511/ground.news",
    "https://web.archive.org//web/20250512/ground.news",
    "https://web.archive.org//web/20250513/ground.news",
    "https://web.archive.org//web/20250514/ground.news",
    "https://web.archive.org//web/20250515/ground.news",
    "https://web.archive.org//web/20250516/ground.news",
    "https://web.archive.org//web/20250517/ground.news",
    "https://web.archive.org//web/20250518/ground.news",
    "https://web.archive.org//web/20250519/ground.news",
    "https://web.archive.org//web/20250520/ground.news",
    "https://web.archive.org//web/20250521/ground.news",
    "https://web.archive.org//web/20250522/ground.news",
    "https://web.archive.org//web/20250523/ground.news",
    "https://web.archive.org//web/20250524/ground.news",
    "https://web.archive.org//web/20250525/ground.news",
    "https://web.archive.org//web/20250526/ground.news",
    "https://web.archive.org//web/20250527/ground.news",
    "https://web.archive.org//web/20250528/ground.news",
    "https://web.archive.org//web/20250529/ground.news",
    "https://web.archive.org//web/20250530/ground.news",
    "https://web.archive.org//web/20250531/ground.news",
    "https://web.archive.org//web/20250601/ground.news",
    "https://web.archive.org//web/20250602/ground.news",
    "https://web.archive.org//web/20250603/ground.news",
    "https://web.archive.org//web/20250604/ground.news",
    "https://web.archive.org//web/20250605/ground.news",
    "https://web.archive.org//web/20250606/ground.news",
    "https://web.archive.org//web/20250607/ground.news",
    "https://web.archive.org//web/20250608/ground.news",
    "https://web.archive.org//web/20250609/ground.news",
    "https://web.archive.org//web/20250610/ground.news",
    "https://web.archive.org//web/20250611/ground.news",
    "https://web.archive.org//web/20250612/ground.news",
    "https://web.archive.org//web/20250613/ground.news",
    "https://web.archive.org//web/20250614/ground.news",
    "https://web.archive.org//web/20250615/ground.news",
    "https://web.archive.org//web/20250616/ground.news",
    "https://web.archive.org//web/20250617/ground.news",
    "https://web.archive.org//web/20250618/ground.news",
    "https://web.archive.org//web/20250619/ground.news",
    "https://web.archive.org//web/20250620/ground.news",
    "https://web.archive.org//web/20250621/ground.news",
    "https://web.archive.org//web/20250622/ground.news",
    "https://web.archive.org//web/20250623/ground.news",
    "https://web.archive.org//web/20250624/ground.news",
    "https://web.archive.org//web/20250625/ground.news",
    "https://web.archive.org//web/20250626/ground.news",
    "https://web.archive.org//web/20250627/ground.news",
    "https://web.archive.org//web/20250628/ground.news",
    "https://web.archive.org//web/20250629/ground.news",
    "https://web.archive.org//web/20250630/ground.news",
    "https://web.archive.org//web/20250701/ground.news",
    "https://web.archive.org//web/20250702/ground.news",
    "https://web.archive.org//web/20250703/ground.news",
    "https://web.archive.org//web/20250704/ground.news",
    "https://web.archive.org//web/20250705/ground.news",
    "https://web.archive.org//web/20250706/ground.news",
    "https://web.archive.org//web/20250707/ground.news",
    "https://web.archive.org//web/20250708/ground.news",
    "https://web.archive.org//web/20250709/ground.news",
    "https://web.archive.org//web/20250710/ground.news",
    "https://web.archive.org//web/20250711/ground.news",
    "https://web.archive.org//web/20250712/ground.news",
    "https://web.archive.org//web/20250713/ground.news",
    "https://web.archive.org//web/20250714/ground.news",
    "https://web.archive.org//web/20250715/ground.news",
    "https://web.archive.org//web/20250716/ground.news",
    "https://web.archive.org//web/20250717/ground.news",
    "https://web.archive.org//web/20250718/ground.news",
    "https://web.archive.org//web/20250719/ground.news",
    "https://web.archive.org//web/20250720/ground.news",
    "https://web.archive.org//web/20250721/ground.news",
    "https://web.archive.org//web/20250722/ground.news",
    "https://web.archive.org//web/20250723/ground.news",
    "https://web.archive.org//web/20250724/ground.news",
    "https://web.archive.org//web/20250725/ground.news",
    "https://web.archive.org//web/20250726/ground.news",
    "https://web.archive.org//web/20250727/ground.news",
    "https://web.archive.org//web/20250728/ground.news",
    "https://web.archive.org//web/20250729/ground.news",
    "https://web.archive.org//web/20250730/ground.news",
    "https://web.archive.org//web/20250731/ground.news",
    "https://web.archive.org//web/20250801/ground.news",
    "https://web.archive.org//web/20250802/ground.news",
    "https://web.archive.org//web/20250803/ground.news",
    "https://web.archive.org//web/20250804/ground.news",
    "https://web.archive.org//web/20250805/ground.news",
    "https://web.archive.org//web/20250806/ground.news",
    "https://web.archive.org//web/20250807/ground.news",
    "https://web.archive.org//web/20250808/ground.news",
    "https://web.archive.org//web/20250809/ground.news",
    "https://web.archive.org//web/20250810/ground.news",
    "https://web.archive.org//web/20250811/ground.news",
    "https://web.archive.org//web/20250812/ground.news",
    "https://web.archive.org//web/20250813/ground.news",
    "https://web.archive.org//web/20250814/ground.news",
    "https://web.archive.org//web/20250815/ground.news",
    "https://web.archive.org//web/20250816/ground.news",
    "https://web.archive.org//web/20250817/ground.news",
    "https://web.archive.org//web/20250818/ground.news",
    "https://web.archive.org//web/20250819/ground.news",
    "https://web.archive.org//web/20250820/ground.news",
    "https://web.archive.org//web/20250821/ground.news",
    "https://web.archive.org//web/20250822/ground.news",
    "https://web.archive.org//web/20250823/ground.news",
    "https://web.archive.org//web/20250824/ground.news",
    "https://web.archive.org//web/20250825/ground.news",
    "https://web.archive.org//web/20250826/ground.news",
    "https://web.archive.org//web/20250827/ground.news",
    "https://web.archive.org//web/20250828/ground.news",
    "https://web.archive.org//web/20250829/ground.news",
    "https://web.archive.org//web/20250830/ground.news",
    "https://web.archive.org//web/20250831/ground.news",
    "https://web.archive.org//web/20250901/ground.news",
    "https://web.archive.org//web/20250902/ground.news",
    "https://web.archive.org//web/20250903/ground.news",
    "https://web.archive.org//web/20250904/ground.news",
    "https://web.archive.org//web/20250905/ground.news",
    "https://web.archive.org//web/20250906/ground.news",
    "https://web.archive.org//web/20250907/ground.news",
    "https://web.archive.org//web/20250908/ground.news",
    "https://web.archive.org//web/20250909/ground.news",
    "https://web.archive.org//web/20250910/ground.news",
    "https://web.archive.org//web/20250911/ground.news",
    "https://web.archive.org//web/20250912/ground.news",
    "https://web.archive.org//web/20250913/ground.news",
    "https://web.archive.org//web/20250914/ground.news",
    "https://web.archive.org//web/20250915/ground.news",
    "https://web.archive.org//web/20250916/ground.news",
    "https://web.archive.org//web/20250917/ground.news",
    "https://web.archive.org//web/20250918/ground.news",
    "https://web.archive.org//web/20250919/ground.news",
    "https://web.archive.org//web/20250920/ground.news",
    "https://web.archive.org//web/20250921/ground.news",
    "https://web.archive.org//web/20250922/ground.news",
    "https://web.archive.org//web/20250923/ground.news",
    "https://web.archive.org//web/20250924/ground.news",
    "https://web.archive.org//web/20250925/ground.news",
    "https://web.archive.org//web/20250926/ground.news",
    "https://web.archive.org//web/20250927/ground.news",
    "https://web.archive.org//web/20250928/ground.news",
    "https://web.archive.org//web/20250929/ground.news",
    "https://web.archive.org//web/20250930/ground.news",
    "https://web.archive.org//web/20251001/ground.news",
    "https://web.archive.org//web/20251002/ground.news",
    "https://web.archive.org//web/20251003/ground.news",
    "https://web.archive.org//web/20251004/ground.news",
    "https://web.archive.org//web/20251005/ground.news",
    "https://web.archive.org//web/20251006/ground.news",
    "https://web.archive.org//web/20251007/ground.news",
    "https://web.archive.org//web/20251008/ground.news",
    "https://web.archive.org//web/20251009/ground.news",
    "https://web.archive.org//web/20251010/ground.news",
    "https://web.archive.org//web/20251011/ground.news",
    "https://web.archive.org//web/20251012/ground.news",
    "https://web.archive.org//web/20251013/ground.news",
    "https://web.archive.org//web/20251014/ground.news",
    "https://web.archive.org//web/20251015/ground.news",
    "https://web.archive.org//web/20251016/ground.news",
    "https://web.archive.org//web/20251017/ground.news",
    "https://web.archive.org//web/20251018/ground.news",
    "https://web.archive.org//web/20251019/ground.news",
    "https://web.archive.org//web/20251020/ground.news",
    "https://web.archive.org//web/20251021/ground.news",
    "https://web.archive.org//web/20251022/ground.news",
    "https://web.archive.org//web/20251023/ground.news",
    "https://web.archive.org//web/20251024/ground.news",
    "https://web.archive.org//web/20251025/ground.news",
    "https://web.archive.org//web/20251026/ground.news",
    "https://web.archive.org//web/20251028/ground.news",
    "https://web.archive.org//web/20251029/ground.news",
    "https://web.archive.org//web/20251030/ground.news",
    "https://web.archive.org//web/20251031/ground.news",
    "https://web.archive.org//web/20251101/ground.news",
    "https://web.archive.org//web/20251102/ground.news",
    "https://web.archive.org//web/20251103/ground.news",
    "https://web.archive.org//web/20251104/ground.news",
    "https://web.archive.org//web/20251105/ground.news",
    "https://web.archive.org//web/20251106/ground.news",
    "https://web.archive.org//web/20251107/ground.news",
    "https://web.archive.org//web/20251108/ground.news",
    "https://web.archive.org//web/20251109/ground.news",
    "https://web.archive.org//web/20251110/ground.news",
    "https://web.archive.org//web/20251111/ground.news",
    "https://web.archive.org//web/20251112/ground.news",
    "https://web.archive.org//web/20251113/ground.news",
    "https://web.archive.org//web/20251114/ground.news",
    "https://web.archive.org//web/20251115/ground.news",
    "https://web.archive.org//web/20251116/ground.news",
    "https://web.archive.org//web/20251117/ground.news",
    "https://web.archive.org//web/20251118/ground.news",
    "https://web.archive.org//web/20251119/ground.news",
    "https://web.archive.org//web/20251120/ground.news",
    "https://web.archive.org//web/20251122/ground.news",
    "https://web.archive.org//web/20251124/ground.news",
    "https://web.archive.org//web/20251125/ground.news",
    "https://web.archive.org//web/20251126/ground.news",
    "https://web.archive.org//web/20251127/ground.news",
    "https://web.archive.org//web/20251128/ground.news",
    "https://web.archive.org//web/20251129/ground.news",
    "https://web.archive.org//web/20251130/ground.news",
    "https://web.archive.org//web/20251201/ground.news",
    "https://web.archive.org//web/20251202/ground.news",
    "https://web.archive.org//web/20251203/ground.news",
    "https://web.archive.org//web/20251204/ground.news",
    "https://web.archive.org//web/20251205/ground.news",
    "https://web.archive.org//web/20251206/ground.news",
    "https://web.archive.org//web/20251207/ground.news",
    "https://web.archive.org//web/20251208/ground.news",
    "https://web.archive.org//web/20251209/ground.news",
    "https://web.archive.org//web/20251210/ground.news",
    "https://web.archive.org//web/20251211/ground.news",
    "https://web.archive.org//web/20251212/ground.news",
    "https://web.archive.org//web/20251213/ground.news",
    "https://web.archive.org//web/20251214/ground.news",
    "https://web.archive.org//web/20251215/ground.news",
    "https://web.archive.org//web/20251216/ground.news",
    "https://web.archive.org//web/20251217/ground.news",
    "https://web.archive.org//web/20251218/ground.news",
    "https://web.archive.org//web/20251219/ground.news",
    "https://web.archive.org//web/20251220/ground.news",
    "https://web.archive.org//web/20251221/ground.news",
    "https://web.archive.org//web/20251222/ground.news",
    "https://web.archive.org//web/20251223/ground.news",
    "https://web.archive.org//web/20251224/ground.news",
    "https://web.archive.org//web/20251225/ground.news",
    "https://web.archive.org//web/20251226/ground.news",
    "https://web.archive.org//web/20251227/ground.news",
    "https://web.archive.org//web/20251228/ground.news",
    "https://web.archive.org//web/20251229/ground.news",
    "https://web.archive.org//web/20251230/ground.news",
    "https://web.archive.org//web/20251231/ground.news",
]
    total=0
    for link in links:
        try:
            data = scrape_multiple_from_homepage(link,max_articles=10)  # Start small for testing
        
            print(f"\nCollected {data[1]} total sources\n")
            total+=data[1]
            # Save data if we have any
            if data:
                # Save as JSON (best for ML training)
                json_file = save_data_to_file(data[0])
                
                # Optional: Also save as CSV for easy viewing
                csv_file = save_data_to_csv(data[0])
                
                print(f"\n Ready for ML training!")
                print(f"   JSON: {json_file}")
                print(f"   CSV:  {csv_file}")
            else:
                print("\n  No data collected to save")
            
            # Still print first few records for preview
            for i, d in enumerate(data[0][:3]):
                print(f"\n[{i+1}] {d}")
                
        except Exception as e:
            print(f"\n  -> Skipping link due to error: {e}")
            print(f"  -> Continuing with next link...")
    print(f"\n=== Final Summary ===")
    print(f"Total sources collected: {total}")