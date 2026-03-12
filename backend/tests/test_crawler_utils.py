"""
Unit tests for pure utility functions in crawler.py:
  - _url_template_key
  - _select_urls_from_sitemap
"""
import pytest

import crawler
from crawler import _select_urls_from_sitemap, _url_template_key


# ---------------------------------------------------------------------------
# _url_template_key
# ---------------------------------------------------------------------------

class TestUrlTemplateKey:
    def test_slug_with_hyphen(self):
        assert _url_template_key("https://example.com/blog/spring-at-ziggis/") == "/blog/"

    def test_location_slug(self):
        assert _url_template_key("https://example.com/locations/15-s-rockrimmon-blvd-co/") == "/locations/"

    def test_numeric_terminal_segment(self):
        # "03" is purely numeric → treated as template instance
        assert _url_template_key("https://example.com/blog/2026/03/") == "/blog/2026/"

    def test_single_segment_returns_none(self):
        assert _url_template_key("https://example.com/about/") is None

    def test_root_path_returns_none(self):
        assert _url_template_key("https://example.com/") is None

    def test_no_slug_no_numeric_returns_none(self):
        # "widget" has no hyphen and isn't numeric
        assert _url_template_key("https://example.com/products/widget/") is None

    def test_multi_segment_slug(self):
        # terminal "reviews" has no hyphen — returns None
        # Correction: "blue-widget" in middle makes terminal "reviews" non-slug
        assert _url_template_key("https://example.com/products/widget/reviews/") is None

    def test_nested_slug_path(self):
        # terminal "blue-widget" has hyphen → template key is parent path
        assert _url_template_key("https://example.com/products/blue-widget/") == "/products/"

    def test_career_listing(self):
        assert _url_template_key("https://example.com/career-listings/assistant-manager-sc/") == "/career-listings/"


# ---------------------------------------------------------------------------
# _select_urls_from_sitemap
# ---------------------------------------------------------------------------

class TestSelectUrlsFromSitemap:
    @pytest.fixture(autouse=True)
    def set_env_defaults(self, monkeypatch):
        """Ensure stable MAX_TEMPLATE_REPS and MAX_PAGES for all tests."""
        monkeypatch.setattr(crawler, "MAX_TEMPLATE_REPS", 1)
        monkeypatch.setattr(crawler, "MAX_PAGES", 20)

    def test_unique_pages_all_included(self):
        urls = [
            "https://example.com/",
            "https://example.com/about/",
            "https://example.com/contact/",
        ]
        selected, arch = _select_urls_from_sitemap(urls, "https://example.com", {})
        assert set(selected) == set(urls)

    def test_template_reps_capped_at_one(self):
        urls = [
            "https://example.com/blog/post-one/",
            "https://example.com/blog/post-two/",
            "https://example.com/blog/post-three/",
            "https://example.com/about/",
        ]
        selected, arch = _select_urls_from_sitemap(urls, "https://example.com", {})
        blog_posts = [u for u in selected if "/blog/" in u]
        assert len(blog_posts) == 1
        assert "https://example.com/about/" in selected

    def test_architecture_total_urls(self):
        urls = ["https://example.com/blog/post-{}/".format(i) for i in range(5)]
        urls += ["https://example.com/about/"]
        _, arch = _select_urls_from_sitemap(urls, "https://example.com", {})
        assert arch["total_urls_in_sitemap"] == 6

    def test_architecture_unique_pages_count(self):
        urls = [
            "https://example.com/about/",
            "https://example.com/contact/",
            "https://example.com/blog/post-one/",
        ]
        _, arch = _select_urls_from_sitemap(urls, "https://example.com", {})
        assert arch["unique_pages"] == 2  # /about/ and /contact/ have no slug

    def test_architecture_template_families(self):
        urls = [
            "https://example.com/blog/post-one/",
            "https://example.com/blog/post-two/",
            "https://example.com/locations/downtown-co/",
        ]
        _, arch = _select_urls_from_sitemap(urls, "https://example.com", {})
        assert arch["template_families"]["/blog/"] == 2
        assert arch["template_families"]["/locations/"] == 1

    def test_hint_map_overrides_template_key(self):
        """A hint_map entry should override auto-detected template key."""
        url = "https://example.com/news/breaking-story/"
        # Without hint_map, this would auto-detect as /news/ template.
        # With hint_map pointing to /articles/, it should bucket under /articles/.
        hint_map = {url: "/articles/"}
        _, arch = _select_urls_from_sitemap([url], "https://example.com", hint_map)
        assert "/articles/" in arch["template_families"]
        assert "/news/" not in arch["template_families"]

    def test_empty_input_returns_empty(self):
        selected, arch = _select_urls_from_sitemap([], "https://example.com", {})
        assert selected == []
        assert arch["total_urls_in_sitemap"] == 0
        assert arch["unique_pages"] == 0
        assert arch["template_families"] == {}

    def test_all_unique_no_template_families(self):
        urls = [
            "https://example.com/",
            "https://example.com/about/",
            "https://example.com/contact/",
        ]
        _, arch = _select_urls_from_sitemap(urls, "https://example.com", {})
        assert arch["template_families"] == {}
