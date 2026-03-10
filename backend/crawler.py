"""
crawler.py — Playwright headless crawler service.
Systematically maps pages, captures DOM structure, forms, interactive elements,
and network requests from a given base URL.
"""

import asyncio
import re
from urllib.parse import urljoin, urlparse
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext


MAX_PAGES = 15  # Keep pipeline under Railway's 300s request timeout
MAX_DEPTH = 2


async def crawl_site(base_url: str, username: Optional[str] = None, password: Optional[str] = None) -> dict:
    """
    Entry point. Crawls base_url up to MAX_PAGES pages deep.
    Returns a structured dict of all discovered pages and their metadata.
    """
    parsed = urlparse(base_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    visited = set()
    pages_data = []
    queue = [(base_url, 0)]  # (url, depth)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (QA-Crawler/1.0)"
        )

        # Handle HTTP basic auth if provided
        if username and password:
            await context.set_http_credentials({"username": username, "password": password})

        while queue and len(visited) < MAX_PAGES:
            url, depth = queue.pop(0)

            if url in visited:
                continue
            if not url.startswith(base_domain):
                continue

            visited.add(url)

            try:
                page_data = await _crawl_page(context, url, base_domain, depth)
                pages_data.append(page_data)

                # Enqueue discovered links if within depth limit
                if depth < MAX_DEPTH:
                    for link in page_data.get("links", []):
                        if link not in visited:
                            queue.append((link, depth + 1))

            except Exception as e:
                pages_data.append({
                    "url": url,
                    "depth": depth,
                    "error": str(e),
                    "title": "Error",
                    "sections": [],
                    "forms": [],
                    "interactive_elements": [],
                    "links": [],
                    "network_requests": [],
                })

        await browser.close()

    return {
        "base_url": base_url,
        "pages_crawled": len(pages_data),
        "pages": pages_data,
    }


async def _crawl_page(context: BrowserContext, url: str, base_domain: str, depth: int) -> dict:
    """Crawl a single page and extract all relevant metadata."""
    page = await context.new_page()
    network_requests = []

    # Capture network requests
    def on_request(request):
        if request.resource_type in ("xhr", "fetch"):
            network_requests.append({
                "url": request.url,
                "method": request.method,
                "resource_type": request.resource_type,
            })

    page.on("request", on_request)

    try:
        await page.goto(url, wait_until="networkidle", timeout=12000)
        await page.wait_for_timeout(1000)  # Let any JS settle

        title = await page.title()
        page_text_sample = await _get_text_sample(page)
        sections = await _extract_sections(page)
        forms = await _extract_forms(page)
        interactive = await _extract_interactive_elements(page)
        links = await _extract_internal_links(page, base_domain)
        nav_items = await _extract_navigation(page)

        return {
            "url": url,
            "depth": depth,
            "title": title,
            "page_text_sample": page_text_sample,
            "sections": sections,
            "forms": forms,
            "interactive_elements": interactive,
            "navigation": nav_items,
            "links": links,
            "network_requests": network_requests[:20],  # Cap to 20 per page
        }
    finally:
        await page.close()


async def _get_text_sample(page: Page) -> str:
    """Extract a brief text sample from the page for context."""
    try:
        text = await page.evaluate("""
            () => {
                const body = document.body;
                const clone = body.cloneNode(true);
                // Remove scripts and styles
                clone.querySelectorAll('script, style, noscript').forEach(el => el.remove());
                return (clone.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 800);
            }
        """)
        return text
    except:
        return ""


async def _extract_sections(page: Page) -> list:
    """Extract semantic sections and headings from the page."""
    try:
        return await page.evaluate("""
            () => {
                const sections = [];
                const headings = document.querySelectorAll('h1, h2, h3, [role="heading"]');
                headings.forEach(h => {
                    sections.push({
                        tag: h.tagName.toLowerCase(),
                        text: h.innerText.trim().slice(0, 100),
                        id: h.id || null,
                        role: h.getAttribute('aria-label') || null,
                    });
                });

                // Also grab landmark regions
                const landmarks = document.querySelectorAll('main, nav, header, footer, section[aria-label], aside');
                landmarks.forEach(el => {
                    sections.push({
                        tag: el.tagName.toLowerCase(),
                        text: (el.getAttribute('aria-label') || el.id || '').slice(0, 100),
                        role: el.getAttribute('role') || null,
                    });
                });

                return sections.slice(0, 30);
            }
        """)
    except:
        return []


async def _extract_forms(page: Page) -> list:
    """Extract all forms with their fields and validation attributes."""
    try:
        return await page.evaluate("""
            () => {
                const forms = [];
                document.querySelectorAll('form').forEach((form, fi) => {
                    const fields = [];
                    form.querySelectorAll('input, select, textarea, button[type]').forEach(el => {
                        fields.push({
                            tag: el.tagName.toLowerCase(),
                            type: el.type || null,
                            name: el.name || null,
                            id: el.id || null,
                            placeholder: el.placeholder || null,
                            label: (() => {
                                if (el.id) {
                                    const lbl = document.querySelector(`label[for="${el.id}"]`);
                                    if (lbl) return lbl.innerText.trim().slice(0, 80);
                                }
                                const parent = el.closest('label');
                                if (parent) return parent.innerText.trim().slice(0, 80);
                                return null;
                            })(),
                            required: el.required || false,
                            pattern: el.pattern || null,
                            min: el.min || null,
                            max: el.max || null,
                            aria_label: el.getAttribute('aria-label') || null,
                        });
                    });
                    forms.push({
                        index: fi,
                        id: form.id || null,
                        action: form.action || null,
                        method: form.method || 'get',
                        fields: fields,
                    });
                });
                return forms;
            }
        """)
    except:
        return []


async def _extract_interactive_elements(page: Page) -> list:
    """Extract buttons, links, modals triggers, and other interactive elements."""
    try:
        return await page.evaluate("""
            () => {
                const elements = [];
                const selectors = [
                    'button:not([type="submit"]):not([type="reset"])',
                    'a[href]',
                    '[role="button"]',
                    '[role="tab"]',
                    '[role="menuitem"]',
                    '[data-toggle]',
                    '[data-modal]',
                    'details > summary',
                ];
                const seen = new Set();
                selectors.forEach(sel => {
                    document.querySelectorAll(sel).forEach(el => {
                        const text = (el.innerText || el.getAttribute('aria-label') || el.title || '').trim().slice(0, 80);
                        const key = `${el.tagName}:${text}`;
                        if (!seen.has(key) && text) {
                            seen.add(key);
                            elements.push({
                                tag: el.tagName.toLowerCase(),
                                text: text,
                                role: el.getAttribute('role') || null,
                                href: el.href || null,
                                aria_label: el.getAttribute('aria-label') || null,
                            });
                        }
                    });
                });
                return elements.slice(0, 50);
            }
        """)
    except:
        return []


async def _extract_navigation(page: Page) -> list:
    """Extract navigation menu items."""
    try:
        return await page.evaluate("""
            () => {
                const items = [];
                const navs = document.querySelectorAll('nav, [role="navigation"]');
                navs.forEach(nav => {
                    nav.querySelectorAll('a').forEach(a => {
                        const text = a.innerText.trim().slice(0, 60);
                        if (text) items.push({ text, href: a.href || null });
                    });
                });
                return [...new Map(items.map(i => [i.text, i])).values()].slice(0, 20);
            }
        """)
    except:
        return []


async def _extract_internal_links(page: Page, base_domain: str) -> list:
    """Extract all internal links from the page."""
    try:
        links = await page.evaluate("""
            (baseDomain) => {
                const hrefs = [];
                document.querySelectorAll('a[href]').forEach(a => {
                    const href = a.href;
                    if (href && !href.includes('#') && !href.startsWith('mailto:') && !href.startsWith('tel:')) {
                        hrefs.push(href);
                    }
                });
                return [...new Set(hrefs)].filter(h => h.startsWith(baseDomain));
            }
        """, base_domain)
        return links[:20]
    except:
        return []
