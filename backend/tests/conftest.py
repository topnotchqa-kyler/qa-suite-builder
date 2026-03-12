"""
Shared pytest fixtures for QA Suite Builder backend tests.
"""
import pytest


@pytest.fixture
def sample_page():
    """A fully-populated page dict matching crawler output shape."""
    return {
        "url": "https://example.com/products/blue-widget/",
        "title": "Blue Widget",
        "template_key": None,
        "page_text_sample": "Our best-selling widget.",
        "sections": [{"text": "Product Details"}, {"text": "Reviews"}],
        "forms": [
            {
                "fields": [
                    {
                        "label": "Email",
                        "name": "email",
                        "placeholder": "",
                        "type": "email",
                        "required": True,
                        "tag": "input",
                    },
                    {
                        "label": "Message",
                        "name": "message",
                        "placeholder": "Your message",
                        "type": "textarea",
                        "required": False,
                        "tag": "textarea",
                    },
                    {
                        "label": "Send",
                        "name": "",
                        "placeholder": "",
                        "type": "submit",
                        "tag": "button",
                    },
                ],
            }
        ],
        "interactive_elements": [{"text": "Add to Cart"}, {"text": "View Gallery"}],
        "navigation": [{"text": "Home"}, {"text": "Products"}, {"text": "Contact"}],
        "network_requests": [
            {"url": "https://api.example.com/products"},
            {"url": "https://api.example.com/products"},  # duplicate — should be deduped
        ],
        "virtual_sections": [],
    }


@pytest.fixture
def minimal_page():
    """A page with only the minimum fields (all optional arrays empty)."""
    return {
        "url": "https://example.com/",
        "title": "Home",
        "template_key": None,
        "page_text_sample": "",
        "sections": [],
        "forms": [],
        "interactive_elements": [],
        "navigation": [],
        "network_requests": [],
        "virtual_sections": [],
    }


@pytest.fixture
def sample_crawl_data(sample_page, minimal_page):
    """Crawl data dict with two pages and the pages_crawled count expected by _build_context."""
    return {
        "base_url": "https://example.com",
        "pages_crawled": 2,
        "pages": [minimal_page, sample_page],
    }
