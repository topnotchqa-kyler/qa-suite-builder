"""
crawler.py — Playwright headless crawler service.
Systematically maps pages, captures DOM structure, forms, interactive elements,
and network requests from a given base URL.
"""

import asyncio
import json
import os
import re
from urllib.parse import urljoin, urlparse
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext


# Override via env vars for local development (no Railway 300s timeout applies).
# Production defaults are conservative to stay well under Railway's limit.
MAX_PAGES = int(os.getenv("MAX_PAGES", "20"))
MAX_DEPTH = int(os.getenv("MAX_DEPTH", "2"))
# Max representatives crawled per detected URL template (e.g. blog posts, location pages).
# Production: 1 keeps the budget free for structurally distinct pages.
# Local: set MAX_TEMPLATE_REPS=3 in .env for cross-instance coverage.
MAX_TEMPLATE_REPS = int(os.getenv("MAX_TEMPLATE_REPS", "1"))

# In-page interaction limits (tabs / accordions)
MAX_TAB_GROUPS = 2       # Max distinct tab groups to process per page
MAX_TABS_PER_GROUP = 5   # Max individual tabs per group
MAX_ACCORDIONS = 5       # Max accordion items to expand per page
INTERACTION_TIMEOUT = 800  # ms to wait after a click for panel content to render

# Asset file extensions that should never be treated as crawlable pages.
_ASSET_URL_RE = re.compile(
    r'\.(jpg|jpeg|png|gif|svg|webp|ico|bmp|tiff|'
    r'pdf|doc|docx|xls|xlsx|ppt|pptx|zip|tar|gz|rar|'
    r'mp4|mp3|wav|avi|mov|webm|ogg|'
    r'woff|woff2|ttf|eot|otf|'
    r'js|css|map)(\?|$)',
    re.IGNORECASE,
)


def _url_template_key(url: str) -> "str | None":
    """
    Return a template key if this URL looks like an instance of a repeated
    page template, otherwise return None.

    A URL is a template instance when it has 2+ path segments and the terminal
    segment is a slug (contains a hyphen) or is purely numeric (date archives).

    Examples:
      /blog/spring-at-ziggis-coffee/           -> "/blog/"
      /locations/15-s-rockrimmon-blvd-co/      -> "/locations/"
      /career-listings/assistant-manager-sc/   -> "/career-listings/"
      /menu-category/hot-coffees/              -> "/menu-category/"
      /blog/2026/03/                           -> "/blog/2026/"
      /about/                                  -> None  (single segment)
      /franchise/                              -> None  (single segment)
    """
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if not path:
        return None
    segments = [s for s in path.split("/") if s]
    if len(segments) < 2:
        return None
    terminal = segments[-1]
    is_slug = ("-" in terminal) or terminal.isdigit()
    if not is_slug:
        return None
    return "/" + "/".join(segments[:-1]) + "/"


async def crawl_site(base_url: str, username: Optional[str] = None, password: Optional[str] = None) -> dict:
    """
    Entry point. Crawls base_url up to MAX_PAGES pages deep.
    Returns a structured dict of all discovered pages and their metadata.
    """
    parsed = urlparse(base_url)
    base_domain = f"{parsed.scheme}://{parsed.netloc}"

    visited = set()
    queued = {base_url}          # prevents re-adding URLs at deeper depths
    template_counts: dict = {}   # template_key -> number of reps already queued
    pages_data = []
    queue = [(base_url, 0)]  # (url, depth)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-dev-shm-usage",  # Use /tmp instead of /dev/shm (critical in Docker)
                "--disable-gpu",
                "--disable-extensions",
                "--disable-background-networking",
                "--disable-sync",
                "--metrics-recording-only",
                "--mute-audio",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (QA-Crawler/1.0)",
            http_credentials={"username": username, "password": password} if (username and password) else None,
        )

        # Attempt form-based login if credentials provided
        if username and password:
            login_page = await context.new_page()
            try:
                await login_page.goto(base_url, wait_until="load", timeout=15000)
                logged_in = await _perform_form_login(login_page, username, password)
                if logged_in:
                    post_login_url = login_page.url
                    queue = [(post_login_url, 0)]
            except Exception:
                pass  # Fall back to crawling public pages
            finally:
                await login_page.close()

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
                    # Nav links are enqueued directly from the navigation data
                    # (not via page_data["links"]) so they are never dropped by
                    # the links[:20] cap in _extract_internal_links.  This
                    # ensures top-level pages like /franchise/ reach depth=1
                    # even when the homepage has more than 20 unique links.
                    nav_hrefs = {
                        n["href"] for n in page_data.get("navigation", [])
                        if n.get("href") and n["href"].startswith(base_domain)
                    }
                    # Only enqueue URLs not already queued — prevents the same
                    # URL being re-added at increasing depths as every page
                    # re-discovers the shared nav bar.
                    nav_entries = [
                        (href, depth + 1)
                        for href in nav_hrefs
                        if href not in visited and href not in queued
                    ]
                    content_entries = []
                    for link in page_data.get("links", []):
                        if link in visited or link in queued or link in nav_hrefs:
                            continue
                        key = _url_template_key(link)
                        if key is not None:
                            if template_counts.get(key, 0) >= MAX_TEMPLATE_REPS:
                                continue  # Enough reps for this template — skip
                            template_counts[key] = template_counts.get(key, 0) + 1
                        content_entries.append((link, depth + 1))

                    for href, _ in nav_entries:
                        queued.add(href)
                    for link, _ in content_entries:
                        queued.add(link)
                    # Nav links before the current queue; content links after
                    queue = nav_entries + queue + content_entries

            except Exception as e:
                pages_data.append({
                    "url": url,
                    "depth": depth,
                    "template_key": _url_template_key(url),
                    "error": str(e),
                    "title": "Error",
                    "sections": [],
                    "forms": [],
                    "interactive_elements": [],
                    "links": [],
                    "network_requests": [],
                    "virtual_sections": [],
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
        await page.goto(url, wait_until="load", timeout=15000)
        await page.wait_for_timeout(1000)  # Let any JS settle

        title = await page.title()
        page_text_sample = await _get_text_sample(page)
        sections = await _extract_sections(page)
        forms = await _extract_forms(page)
        interactive = await _extract_interactive_elements(page)
        links = await _extract_internal_links(page, base_domain)
        nav_items = await _extract_navigation(page)

        # In-page feature extraction: tabs and accordions (depth-gated to protect timeout budget)
        virtual_sections = []
        if depth < MAX_DEPTH:
            try:
                virtual_sections = await asyncio.wait_for(
                    _extract_virtual_sections(page),
                    timeout=12.0,
                )
            except Exception:
                pass  # Never block the crawl for virtual section failures

        return {
            "url": url,
            "depth": depth,
            "template_key": _url_template_key(url),  # None for unique pages
            "title": title,
            "page_text_sample": page_text_sample,
            "sections": sections,
            "forms": forms,
            "interactive_elements": interactive,
            "navigation": nav_items,
            "links": links,
            "network_requests": network_requests[:20],  # Cap to 20 per page
            "virtual_sections": virtual_sections,
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


async def _extract_virtual_sections(page: Page) -> list:
    """
    Coordinator: detect tabs and accordions, activate each, and extract revealed content.
    Returns a list of virtual_section dicts representing each hidden content state found.
    """
    virtual_sections = []

    try:
        vs_tabs = await _extract_tab_virtual_sections(page)
        virtual_sections.extend(vs_tabs)
    except Exception:
        pass

    try:
        vs_accordions = await _extract_accordion_virtual_sections(page)
        virtual_sections.extend(vs_accordions)
    except Exception:
        pass

    return virtual_sections


async def _extract_tab_virtual_sections(page: Page) -> list:
    """
    Click each tab in each tablist and extract the revealed panel content.
    Uses index-based JS interaction to avoid stale ElementHandle issues after DOM mutations.
    """
    results = []

    # Collect all tab group metadata upfront in a single JS call
    groups = await page.evaluate(f"""
        () => {{
            const TAB_GROUP_LIMIT = {MAX_TAB_GROUPS};
            const TAB_LIMIT = {MAX_TABS_PER_GROUP};
            const tablists = [...document.querySelectorAll('[role="tablist"], .nav-tabs, [data-tabs]')]
                .slice(0, TAB_GROUP_LIMIT);

            return tablists.map((tablist, ti) => {{
                // Derive group label
                let groupLabel = tablist.getAttribute('aria-label');
                if (!groupLabel) {{
                    const labelId = tablist.getAttribute('aria-labelledby');
                    if (labelId) {{
                        const el = document.getElementById(labelId);
                        if (el) groupLabel = el.innerText.trim().slice(0, 60);
                    }}
                }}
                if (!groupLabel) {{
                    let prev = tablist.previousElementSibling;
                    while (prev) {{
                        if (/^H[1-6]$/.test(prev.tagName)) {{ groupLabel = prev.innerText.trim().slice(0, 60); break; }}
                        prev = prev.previousElementSibling;
                    }}
                }}
                if (!groupLabel) groupLabel = 'Tab Group ' + (ti + 1);

                const triggers = [...tablist.querySelectorAll('[role="tab"], .nav-link')]
                    .slice(0, TAB_LIMIT)
                    .map((t, i) => ({{
                        tablistIndex: ti,
                        triggerIndex: i,
                        label: (t.innerText || t.getAttribute('aria-label') || '').trim().slice(0, 80),
                        href: t.getAttribute('href') || '',
                        isSelected: t.getAttribute('aria-selected') === 'true' || t.classList.contains('active'),
                    }}))
                    .filter(t => t.label && (!t.href || t.href.startsWith('#')));

                return {{ groupLabel, tablistIndex: ti, triggers }};
            }});
        }}
    """)

    for group in groups:
        group_label = group["groupLabel"]
        tablist_idx = group["tablistIndex"]

        for trigger_meta in group["triggers"]:
            tab_idx = trigger_meta["triggerIndex"]
            trigger_label = trigger_meta["label"]
            is_selected = trigger_meta["isSelected"]

            # Skip click for the default-selected first tab — it's already visible
            if not (is_selected and tab_idx == 0):
                try:
                    # Click by index via JS — no stale ElementHandle risk
                    await page.evaluate(f"""
                        () => {{
                            const tablists = [...document.querySelectorAll('[role="tablist"], .nav-tabs, [data-tabs]')];
                            const tablist = tablists[{tablist_idx}];
                            if (!tablist) return;
                            const triggers = [...tablist.querySelectorAll('[role="tab"], .nav-link')];
                            const trigger = triggers[{tab_idx}];
                            if (trigger) trigger.click();
                        }}
                    """)
                    await page.wait_for_timeout(INTERACTION_TIMEOUT)
                except Exception:
                    continue

            panel_data = await page.evaluate(f"""
                () => {{
                    const tablists = [...document.querySelectorAll('[role="tablist"], .nav-tabs, [data-tabs]')];
                    const tablist = tablists[{tablist_idx}];
                    if (!tablist) return null;
                    const triggers = [...tablist.querySelectorAll('[role="tab"], .nav-link')];
                    const trigger = triggers[{tab_idx}];

                    let panel = null;

                    // Tier 1: aria-controls
                    if (trigger) {{
                        const cid = trigger.getAttribute('aria-controls');
                        if (cid) panel = document.getElementById(cid);
                    }}

                    // Tier 2: visible [role="tabpanel"] within tablist parent
                    if (!panel) {{
                        const root = tablist.parentElement || document.body;
                        panel = [...root.querySelectorAll('[role="tabpanel"]')].find(p =>
                            !p.hidden &&
                            p.getAttribute('aria-hidden') !== 'true' &&
                            getComputedStyle(p).display !== 'none' &&
                            getComputedStyle(p).visibility !== 'hidden'
                        );
                    }}

                    // Tier 3: Bootstrap .tab-pane.active
                    if (!panel) {{
                        const root = tablist.parentElement || document.body;
                        panel = root.querySelector('.tab-pane.active, .tab-panel.active, .tab-content > .active');
                    }}

                    if (!panel) return null;

                    return {{
                        panel_text: (panel.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 600),
                        panel_headings: [...panel.querySelectorAll('h1,h2,h3,h4')]
                            .map(h => h.innerText.trim().slice(0, 80)).filter(Boolean).slice(0, 5),
                        panel_forms: panel.querySelector('form') !== null,
                        panel_links: [...panel.querySelectorAll('a')]
                            .map(a => a.innerText.trim().slice(0, 60)).filter(Boolean).slice(0, 5),
                    }};
                }}
            """)

            if panel_data and panel_data.get("panel_text"):
                results.append({
                    "type": "tab",
                    "group_label": group_label,
                    "trigger_label": trigger_label,
                    **panel_data,
                })

    return results


async def _extract_accordion_virtual_sections(page: Page) -> list:
    """
    Expand each <details>/<summary> accordion and extract the revealed content.
    Uses index-based JS interaction to avoid stale ElementHandle issues after DOM mutations.
    """
    results = []

    # Collect all accordion metadata upfront in a single JS call
    items = await page.evaluate(f"""
        () => {{
            const LIMIT = {MAX_ACCORDIONS};
            return [...document.querySelectorAll('details > summary')]
                .slice(0, LIMIT)
                .map((summary, i) => {{
                    const details = summary.parentElement;
                    const wrapper = details.parentElement;
                    const heading = wrapper ? wrapper.querySelector('h1,h2,h3,h4') : null;
                    return {{
                        index: i,
                        label: summary.innerText.trim().slice(0, 80),
                        wasOpen: details.open,
                        groupLabel: heading ? heading.innerText.trim().slice(0, 60) : 'Accordion',
                    }};
                }})
                .filter(item => item.label);
        }}
    """)

    for item in items:
        idx = item["index"]
        trigger_label = item["label"]
        group_label = item["groupLabel"]
        was_open = item["wasOpen"]

        if not was_open:
            try:
                await page.evaluate(f"""
                    () => {{
                        const summaries = [...document.querySelectorAll('details > summary')];
                        if (summaries[{idx}]) summaries[{idx}].click();
                    }}
                """)
                await page.wait_for_timeout(INTERACTION_TIMEOUT)
            except Exception:
                continue

        panel_data = await page.evaluate(f"""
            () => {{
                const details = [...document.querySelectorAll('details')][{idx}];
                if (!details || !details.open) return null;
                const clone = details.cloneNode(true);
                const s = clone.querySelector('summary');
                if (s) s.remove();
                const text = (clone.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 600);
                if (!text) return null;
                return {{
                    panel_text: text,
                    panel_headings: [...details.querySelectorAll('h1,h2,h3,h4')]
                        .map(h => h.innerText.trim().slice(0, 80)).filter(Boolean).slice(0, 5),
                    panel_forms: details.querySelector('form') !== null,
                    panel_links: [...details.querySelectorAll('a')]
                        .map(a => a.innerText.trim().slice(0, 60)).filter(Boolean).slice(0, 5),
                }};
            }}
        """)

        if panel_data:
            results.append({
                "type": "accordion",
                "group_label": group_label,
                "trigger_label": trigger_label,
                **panel_data,
            })

        # Restore to closed if it was closed before we opened it
        if not was_open:
            try:
                await page.evaluate(f"""
                    () => {{ const d = [...document.querySelectorAll('details')][{idx}]; if (d) d.open = false; }}
                """)
            except Exception:
                pass

    return results


async def _perform_form_login(page: Page, username: str, password: str) -> bool:
    """
    Attempt to fill and submit a login form on the current page.
    Returns True if login appears successful (URL changed after submission).
    """
    try:
        # Confirm a password field is present — reliable login form indicator
        password_field = await page.query_selector("input[type='password']")
        if not password_field:
            return False

        # Find username/email field: prefer email type, fall back to text inputs
        username_field = (
            await page.query_selector("input[type='email']")
            or await page.query_selector("input[name*='email']")
            or await page.query_selector("input[name*='user']")
            or await page.query_selector("input[id*='email']")
            or await page.query_selector("input[id*='user']")
            or await page.query_selector("input[type='text']")
        )

        if username_field:
            await username_field.fill(username)
        await password_field.fill(password)

        # Find and click the submit button
        submit = (
            await page.query_selector("button[type='submit']")
            or await page.query_selector("input[type='submit']")
            or await page.query_selector("button:has-text('Sign in')")
            or await page.query_selector("button:has-text('Log in')")
            or await page.query_selector("button:has-text('Login')")
        )

        if not submit:
            return False

        initial_url = page.url
        await submit.click()
        try:
            # Wait for URL change; SPAs may never reach networkidle so catch timeout
            await page.wait_for_function(
                f"() => location.href !== {json.dumps(initial_url)}",
                timeout=10000,
            )
        except Exception:
            pass  # Check URL below regardless

        # Login succeeded if URL changed (redirected away from login page)
        return page.url != initial_url

    except Exception:
        return False


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
        # Strip asset/binary URLs — they are never crawlable pages
        page_links = [h for h in links if not _ASSET_URL_RE.search(h)]
        return page_links[:20]
    except:
        return []
