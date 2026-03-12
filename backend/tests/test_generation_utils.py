"""
Unit tests for pure utility functions in generation.py:
  - _extract_site_name
  - _build_context
  - _build_page_context
"""
import pytest

from generation import _build_context, _build_page_context, _extract_site_name


# ---------------------------------------------------------------------------
# _extract_site_name
# ---------------------------------------------------------------------------

class TestExtractSiteName:
    def test_www_stripped(self):
        assert _extract_site_name("https://www.example.com/page") == "Example"

    def test_subdomain_becomes_name(self):
        # netloc = "blog.example.com" → no www → split(".")[0] = "blog" → "Blog"
        assert _extract_site_name("https://blog.example.com") == "Blog"

    def test_hyphenated_domain(self):
        # netloc = "ziggis-coffee.com" → split(".")[0] = "ziggis-coffee" → .title() = "Ziggis-Coffee"
        assert _extract_site_name("https://ziggis-coffee.com") == "Ziggis-Coffee"

    def test_localhost(self):
        assert _extract_site_name("http://localhost") == "Localhost"

    def test_not_a_url_returns_website(self):
        assert _extract_site_name("not-a-url") == "Website"

    def test_empty_string_returns_website(self):
        assert _extract_site_name("") == "Website"


# ---------------------------------------------------------------------------
# _build_context
# ---------------------------------------------------------------------------

class TestBuildContext:
    def test_contains_base_url(self, sample_crawl_data):
        output = _build_context(sample_crawl_data)
        assert "Base URL: https://example.com" in output

    def test_contains_pages_crawled(self, sample_crawl_data):
        output = _build_context(sample_crawl_data)
        assert "Pages crawled: 2" in output

    def test_contains_page_url_header(self, sample_crawl_data):
        output = _build_context(sample_crawl_data)
        assert "--- PAGE: https://example.com/products/blue-widget/ ---" in output

    def test_contains_form_field_label(self, sample_crawl_data):
        output = _build_context(sample_crawl_data)
        assert "Email" in output

    def test_api_urls_deduplicated(self, sample_crawl_data):
        output = _build_context(sample_crawl_data)
        # network_requests has the same URL twice — should appear only once
        assert output.count("api.example.com/products") == 1

    def test_headings_capped_at_8(self):
        """Page with 10 sections should only produce 8 headings in output."""
        crawl_data = {
            "base_url": "https://example.com",
            "pages_crawled": 1,
            "pages": [
                {
                    "url": "https://example.com/",
                    "title": "Home",
                    "sections": [{"text": f"Section {i}"} for i in range(10)],
                    "forms": [],
                    "interactive_elements": [],
                    "navigation": [],
                    "network_requests": [],
                }
            ],
        }
        output = _build_context(crawl_data)
        # Section 8 and 9 should not appear (0-indexed, only 0-7 included)
        assert "Section 7" in output
        assert "Section 8" not in output
        assert "Section 9" not in output


# ---------------------------------------------------------------------------
# _build_page_context
# ---------------------------------------------------------------------------

class TestBuildPageContext:
    def test_sample_page_contains_url(self, sample_page):
        output = _build_page_context(sample_page)
        assert "https://example.com/products/blue-widget/" in output

    def test_sample_page_contains_title(self, sample_page):
        output = _build_page_context(sample_page)
        assert "Blue Widget" in output

    def test_sample_page_contains_form_field(self, sample_page):
        output = _build_page_context(sample_page)
        assert "Email" in output

    def test_sample_page_email_field_marked_required(self, sample_page):
        output = _build_page_context(sample_page)
        assert "Email (required)" in output

    def test_sample_page_contains_interactive_element(self, sample_page):
        output = _build_page_context(sample_page)
        assert "Add to Cart" in output

    def test_sample_page_contains_navigation(self, sample_page):
        output = _build_page_context(sample_page)
        assert "Home" in output

    def test_sample_page_api_deduplicated(self, sample_page):
        output = _build_page_context(sample_page)
        assert output.count("api.example.com/products") == 1

    def test_minimal_page_no_crash(self, minimal_page):
        output = _build_page_context(minimal_page)
        assert "https://example.com/" in output
        assert "Home" in output

    def test_minimal_page_no_form_section(self, minimal_page):
        output = _build_page_context(minimal_page)
        assert "Form" not in output

    def test_minimal_page_no_api_section(self, minimal_page):
        output = _build_page_context(minimal_page)
        assert "API endpoints" not in output

    def test_template_key_shows_representative_note(self, sample_page):
        sample_page["template_key"] = "/products/"
        output = _build_page_context(sample_page)
        assert "Template representative" in output

    def test_virtual_sections_appear(self, sample_page):
        sample_page["virtual_sections"] = [
            {
                "type": "tab",
                "group_label": "Features",
                "trigger_label": "Overview",
                "panel_text": "Main feature overview.",
                "panel_headings": [],
                "panel_forms": [],
                "panel_links": [],
            }
        ]
        output = _build_page_context(sample_page)
        assert "Tab/Accordion panels revealed:" in output
        assert "Overview" in output
