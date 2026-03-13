"""
generation.py — AI test case generation service.
Feeds crawl data to the Anthropic API and returns structured test cases
organized by page/section for .xlsx output.
"""

import json
import os
import anthropic

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
MODEL = "claude-sonnet-4-6"
SUGGEST_MODEL = "claude-haiku-4-5-20251001"


def generate_test_suite(crawl_data: dict, api_key: str = None) -> dict:
    """
    Main entry point. Takes crawl_data from crawler.py and returns
    a structured test suite ready for xlsx_builder.py.

    api_key: optional user-supplied Anthropic key; falls back to ANTHROPIC_API_KEY env var.

    Returns:
        {
            "site_name": str,
            "base_url": str,
            "summary": str,
            "sections": [
                {
                    "name": str,
                    "source_url": str,
                    "test_cases": [
                        {
                            "id": str,
                            "title": str,
                            "description": str,
                            "preconditions": str,
                            "steps": str,
                            "expected_result": str,
                            "priority": str,   # Critical / High / Medium / Low
                            "category": str,   # Functional / UI / Form / Navigation / etc.
                        }
                    ]
                }
            ]
        }
    """
    resolved_key = api_key or ANTHROPIC_API_KEY
    if not resolved_key:
        raise ValueError("No Anthropic API key provided. Pass an API key in the X-Api-Key header.")
    client = anthropic.Anthropic(api_key=resolved_key)

    pages = crawl_data.get("pages", [])
    base_url = crawl_data.get("base_url", "")

    # Build a condensed, structured context string from crawl data
    context = _build_context(crawl_data)

    # First pass: generate a site-level summary and section breakdown
    site_summary = _generate_site_summary(client, base_url, context)

    # Second pass: generate test cases per page (batched for efficiency)
    sections = _generate_sections(client, pages, base_url)

    return {
        "site_name": _extract_site_name(base_url),
        "base_url": base_url,
        "summary": site_summary,
        "sections": sections,
    }


def _extract_site_name(base_url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(base_url)
    host = parsed.netloc.replace("www.", "")
    return host.split(".")[0].title() if host else "Website"


def _build_context(crawl_data: dict) -> str:
    """Condense crawl data into a structured string for the AI prompt."""
    lines = [f"Base URL: {crawl_data['base_url']}"]
    lines.append(f"Pages crawled: {crawl_data['pages_crawled']}\n")

    for page in crawl_data.get("pages", []):
        lines.append(f"--- PAGE: {page['url']} ---")
        lines.append(f"Title: {page.get('title', 'Unknown')}")

        if page.get("sections"):
            headings = [s["text"] for s in page["sections"] if s.get("text")][:8]
            lines.append(f"Headings: {', '.join(headings)}")

        if page.get("forms"):
            for form in page["forms"]:
                field_names = [
                    f.get("label") or f.get("name") or f.get("placeholder") or f.get("type", "field")
                    for f in form.get("fields", [])
                    if f.get("tag") != "button"
                ]
                if field_names:
                    lines.append(f"Form fields: {', '.join(field_names[:10])}")

        if page.get("interactive_elements"):
            btns = [e["text"] for e in page["interactive_elements"] if e.get("text")][:8]
            lines.append(f"Interactive elements: {', '.join(btns)}")

        if page.get("navigation"):
            nav = [n["text"] for n in page["navigation"]][:6]
            lines.append(f"Navigation: {', '.join(nav)}")

        if page.get("network_requests"):
            apis = list(set([r["url"] for r in page["network_requests"]]))[:4]
            lines.append(f"API calls: {', '.join(apis)}")

        lines.append("")

    return "\n".join(lines)


def _generate_site_summary(client: anthropic.Anthropic, base_url: str, context: str) -> str:
    """Generate a brief summary of the site for the Dashboard sheet."""
    prompt = f"""Based on this crawl data from {base_url}, write a 2-3 sentence summary 
of what this website does and what the QA test suite covers. Be concise and factual.

{context[:3000]}

Respond with only the summary text, no preamble."""

    message = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text.strip()


def _generate_sections(client: anthropic.Anthropic, pages: list, base_url: str) -> list:
    """Generate test case sections — one per page, batched into groups for efficiency."""
    sections = []
    section_counter = [1]  # mutable for closure

    # Process pages in batches of 3 to limit API calls while keeping context focused
    batch_size = 3
    for i in range(0, len(pages), batch_size):
        batch = pages[i:i + batch_size]
        batch_sections = _generate_batch(client, batch, base_url, section_counter)
        sections.extend(batch_sections)

    return sections


def _generate_batch(client: anthropic.Anthropic, pages: list, base_url: str, counter: list) -> list:
    """Generate test cases for a batch of pages in a single API call."""

    # Build a compact representation of the batch
    pages_context = []
    for page in pages:
        if page.get("error"):
            continue
        page_ctx = _build_page_context(page)
        pages_context.append(page_ctx)

    if not pages_context:
        return []

    combined = "\n\n".join(pages_context)

    prompt = f"""You are a QA engineer generating comprehensive test cases for {base_url}.

Below is crawl data for {len(pages_context)} page(s). For EACH page, generate 5-10 test cases grounded in the actual UI elements, form fields, and interactions found on that page.

CRAWL DATA:
{combined}

Respond ONLY with a valid JSON array. Each element represents one page section:
[
  {{
    "section_name": "Page title or descriptive name",
    "source_url": "the page URL",
    "test_cases": [
      {{
        "id": "TC-001",
        "title": "Short test case title",
        "description": "What this test validates",
        "preconditions": "What must be true before running this test",
        "steps": "1. Step one\\n2. Step two\\n3. Step three",
        "expected_result": "What should happen if the test passes",
        "priority": "Critical|High|Medium|Low",
        "category": "Functional|UI|Form Validation|Navigation|API|Accessibility|Error Handling"
      }}
    ]
  }}
]

Rules:
- Use REAL field names, button labels, and page sections from the crawl data
- Vary priority: not everything is Critical
- Include negative test cases (invalid inputs, error states) where forms exist
- Keep steps concise (3-6 steps each)
- IDs should be sequential starting from TC-{counter[0]:03d}
- Return ONLY the JSON array, no markdown fences, no preamble"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=4000,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = message.content[0].text.strip()

    try:
        # Strip any accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Fallback: return a minimal section indicating the parse issue
        return [{
            "name": f"Page {counter[0]}",
            "source_url": pages[0].get("url", ""),
            "test_cases": [{
                "id": f"TC-{counter[0]:03d}",
                "title": "Test generation parse error",
                "description": "The AI response could not be parsed",
                "preconditions": "N/A",
                "steps": "N/A",
                "expected_result": "N/A",
                "priority": "Low",
                "category": "Functional",
            }]
        }]

    sections = []
    for item in data:
        tc_count = len(item.get("test_cases", []))
        counter[0] += tc_count
        sections.append({
            "name": item.get("section_name", f"Page {counter[0]}"),
            "source_url": item.get("source_url", ""),
            "test_cases": item.get("test_cases", []),
        })

    return sections


def _build_page_context(page: dict) -> str:
    """Build a concise context string for a single page."""
    lines = []
    if page.get("template_key"):
        lines.append(
            f"Template representative for: {page['template_key']}* pages"
            f" — write tests that apply to all pages matching this URL pattern"
        )
    lines += [
        f"URL: {page['url']}",
        f"Title: {page.get('title', 'Unknown')}",
    ]

    if page.get("page_text_sample"):
        lines.append(f"Page content sample: {page['page_text_sample'][:300]}")

    if page.get("sections"):
        headings = [s["text"] for s in page["sections"] if s.get("text")][:10]
        lines.append(f"Page sections/headings: {', '.join(headings)}")

    if page.get("forms"):
        for fi, form in enumerate(page["forms"]):
            fields = []
            for f in form.get("fields", []):
                label = f.get("label") or f.get("name") or f.get("placeholder") or f.get("type", "")
                if label and f.get("tag") != "button":
                    req = " (required)" if f.get("required") else ""
                    fields.append(f"{label}{req}")
            if fields:
                lines.append(f"Form {fi+1} fields: {', '.join(fields[:12])}")
            submit_btns = [
                f.get("label") or f.get("aria_label") or "Submit"
                for f in form.get("fields", [])
                if f.get("tag") == "button" or f.get("type") in ("submit", "reset")
            ]
            if submit_btns:
                lines.append(f"Form {fi+1} actions: {', '.join(submit_btns)}")

    if page.get("interactive_elements"):
        elements = [e["text"] for e in page["interactive_elements"] if e.get("text")][:10]
        lines.append(f"Buttons/interactive: {', '.join(elements)}")

    if page.get("navigation"):
        nav = [n["text"] for n in page["navigation"]][:8]
        lines.append(f"Navigation items: {', '.join(nav)}")

    if page.get("network_requests"):
        apis = list(set([r["url"] for r in page["network_requests"]]))[:5]
        lines.append(f"API endpoints called: {', '.join(apis)}")

    if page.get("virtual_sections"):
        vs_lines = []
        for vs in page["virtual_sections"]:
            label = f"{vs['type'].title()}: {vs.get('group_label', '')} > {vs.get('trigger_label', '')}"
            detail = vs.get("panel_text", "")[:200]
            headings = vs.get("panel_headings", [])
            if headings:
                detail += f" | Sub-sections: {', '.join(headings)}"
            if vs.get("panel_forms"):
                detail += " | Contains form"
            if vs.get("panel_links"):
                detail += f" | Links: {', '.join(vs['panel_links'][:3])}"
            vs_lines.append(f"  - {label}: {detail}")
        if vs_lines:
            lines.append("Tab/Accordion panels revealed:")
            lines.extend(vs_lines)

    return "\n".join(lines)


def generate_field_suggestion(
    field: str,
    current_value: str,
    context: dict,
    api_key: str = None,
) -> str:
    """
    Generate a short inline suggestion to continue `current_value` in `field`.

    Uses SUGGEST_MODEL (Haiku) for speed and cost efficiency.
    Returns a plain string continuation — not a repeat of current_value.
    Raises ValueError if no API key is available.
    """
    resolved_key = api_key or ANTHROPIC_API_KEY
    if not resolved_key:
        raise ValueError("No Anthropic API key provided. Pass an API key in the X-Api-Key header.")

    client = anthropic.Anthropic(api_key=resolved_key)

    field_guidance = {
        "description":     "what this test case validates and why",
        "preconditions":   "the state the system must be in before this test runs",
        "steps":           "numbered step-by-step actions a tester should perform",
        "expected_result": "the observable outcome that indicates the test has passed",
    }
    guidance = field_guidance.get(field, "the field content")
    ctx = context or {}

    prompt = f"""You are helping a QA engineer write a test case. Continue the text below naturally.

Test case context:
  Title: {ctx.get('title', '')}
  Priority: {ctx.get('priority', '')}
  Category: {ctx.get('category', '')}
  Description: {ctx.get('description', '') if field != 'description' else '(being written)'}
  Preconditions: {ctx.get('preconditions', '') if field != 'preconditions' else '(being written)'}
  Steps: {ctx.get('steps', '') if field != 'steps' else '(being written)'}
  Expected Result: {ctx.get('expected_result', '') if field != 'expected_result' else '(being written)'}

Field being written: {field} — this should express {guidance}.

Text so far:
{current_value}

Continue the text naturally from where it ends. Write ONLY the continuation (do not repeat the existing text). Keep it concise — 1-3 sentences or steps maximum. No preamble."""

    message = client.messages.create(
        model=SUGGEST_MODEL,
        max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()

    return "\n".join(lines)
