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


def discover_article_urls_from_homepage(link,max_articles=10):
    """Go to Ground News homepage and extract article titles to build URLs"""
    article_urls = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        print("Going to Ground News homepage...")
        page.goto(link, wait_until="domcontentloaded", timeout=60_000)
        
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
                print(f"404 Error: Article not found")
                browser.close()
                return []
            
        except Exception as e:
            print(f"Page load error: {e}")
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
                            print(f"Found alternative content: {alt_selector} ({len(alt_elements)} elements)")
                            found_alternative = True
                            break
                    except:
                        continue
                
                if not found_alternative:
                    print(f"No recognizable article content found")
                    browser.close()
                    return []
                
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

                lines = [line.strip() for line in text.split("\n") if line.strip()]
                outlet = lines[0]

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


def scrape_multiple_from_homepage(link, max_articles=10):
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
    links= ["https://web.archive.org/web/20260224181632/https://ground.news/","https://web.archive.org/web/20260225065854/https://ground.news/","https://web.archive.org/web/20260101005031/https://ground.news/","https://web.archive.org/web/20251213021953/https://ground.news/"]    # MODE 2: Discover from homepage and scrape multiple
    total=0
    for link in links:
        data = scrape_multiple_from_homepage(link,max_articles=10)  # Start small for testing
    
        print(f"\nCollected {data[1]} total sources\n")
        total+=data[1]
        # Save data if we have any
        if data:
            json_file = save_data_to_file(data[0])
            csv_file = save_data_to_csv(data[0])
            
            print(f"\n Ready for ML training!")
            print(f"   JSON: {json_file}")
            print(f"   CSV:  {csv_file}")
        else:
            print("\n  No data collected to save")
        
        # Still print first few records for preview
        for i, d in enumerate(data[0][:3]):
            print(f"\n[{i+1}] {d}")
    print(f"\n=== Final Summary ===")
    print(f"Total sources collected: {total}")