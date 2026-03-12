"""
Unit tests for pure utility functions in main.py:
  - _validate_url  (SSRF protection)
  - _sanitize_filename
"""
import socket

import pytest
from fastapi import HTTPException

from main import _sanitize_filename, _validate_url


# ---------------------------------------------------------------------------
# _validate_url
# ---------------------------------------------------------------------------

class TestValidateUrl:
    def test_valid_https_url(self, mocker):
        mocker.patch("main.socket.gethostbyname", return_value="93.184.216.34")
        _validate_url("https://example.com/path")  # must not raise

    def test_valid_http_url(self, mocker):
        mocker.patch("main.socket.gethostbyname", return_value="93.184.216.34")
        _validate_url("http://example.com/")  # must not raise

    def test_rejects_ftp_scheme(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("ftp://example.com/file.txt")
        assert exc.value.status_code == 400

    def test_rejects_no_scheme(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("example.com/page")
        assert exc.value.status_code == 400

    def test_rejects_missing_hostname(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("https://")
        assert exc.value.status_code == 400

    def test_rejects_localhost(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("http://localhost/admin")
        assert exc.value.status_code == 400

    def test_rejects_metadata_hostname(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("http://metadata/computeMetadata/v1/")
        assert exc.value.status_code == 400

    def test_rejects_metadata_google_internal(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("http://metadata.google.internal/")
        assert exc.value.status_code == 400

    def test_rejects_aws_metadata_ip(self):
        # 169.254.169.254 is in the link_local range
        with pytest.raises(HTTPException) as exc:
            _validate_url("http://169.254.169.254/latest/meta-data/")
        assert exc.value.status_code == 400

    def test_rejects_loopback_ip(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("http://127.0.0.1/")
        assert exc.value.status_code == 400

    def test_rejects_private_ip_class_a(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("http://10.0.0.1/internal")
        assert exc.value.status_code == 400

    def test_rejects_private_ip_class_c(self):
        with pytest.raises(HTTPException) as exc:
            _validate_url("http://192.168.1.100/")
        assert exc.value.status_code == 400

    def test_rejects_hostname_resolving_to_private_ip(self, mocker):
        mocker.patch("main.socket.gethostbyname", return_value="10.0.0.1")
        with pytest.raises(HTTPException) as exc:
            _validate_url("https://corp.internal/dashboard")
        assert exc.value.status_code == 400

    def test_rejects_dns_failure(self, mocker):
        mocker.patch("main.socket.gethostbyname", side_effect=socket.gaierror("NXDOMAIN"))
        with pytest.raises(HTTPException) as exc:
            _validate_url("https://doesnotexist.invalid/")
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# _sanitize_filename
# ---------------------------------------------------------------------------

class TestSanitizeFilename:
    def test_clean_name_unchanged(self):
        assert _sanitize_filename("SuiteGen") == "SuiteGen"

    def test_strips_apostrophe_and_space(self):
        assert _sanitize_filename("Ziggi's Coffee") == "ZiggisCoffee"

    def test_preserves_hyphens_and_underscores(self):
        assert _sanitize_filename("My-Suite_v2") == "My-Suite_v2"

    def test_strips_exclamation_and_space(self):
        assert _sanitize_filename("Hello World!") == "HelloWorld"

    def test_empty_string_returns_fallback(self):
        assert _sanitize_filename("") == "qa_suite"

    def test_all_special_chars_returns_fallback(self):
        assert _sanitize_filename("!!!@@@###") == "qa_suite"

    def test_truncates_at_50_chars(self):
        long_name = "A" * 60
        result = _sanitize_filename(long_name)
        assert len(result) == 50
        assert result == "A" * 50
