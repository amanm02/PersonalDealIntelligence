import socket
import ssl
import urllib.error
from datetime import date

from pdi.fetchers import SafeFetchResult, safe_fetch_public_source
from pdi.sources import SourcePolicy


class FakeHeaders:
    def __init__(self, content_type, charset=None):
        self._content_type = content_type
        self._charset = charset

    def get_content_type(self):
        return self._content_type

    def get_content_charset(self):
        return self._charset


class FakeResponse:
    def __init__(
        self,
        *,
        body,
        content_type="application/rss+xml",
        status=200,
        final_url="https://example.test/feed.xml",
        charset=None,
    ):
        self._body = body
        self.headers = FakeHeaders(content_type, charset=charset)
        self.status = status
        self._final_url = final_url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self, size=-1):
        return self._body if size < 0 else self._body[:size]

    def geturl(self):
        return self._final_url


def test_safe_fetch_success_returns_typed_metadata_without_body_leak():
    source_policy = policy(url="https://example.test/feed.xml?token=secret")
    body = b"<?xml version='1.0'?><rss><channel /></rss>"
    response = FakeResponse(
        body=body,
        content_type="application/rss+xml",
        final_url="https://example.test/feed.xml?token=secret#frag",
    )

    result = safe_fetch_public_source(
        source_policy,
        max_response_bytes=128,
        urlopen=lambda request, timeout: response,
    )

    assert result.ok is True
    assert result.body_text == "<?xml version='1.0'?><rss><channel /></rss>"
    assert result.status_code == 200
    assert result.content_type == "application/rss+xml"
    assert result.final_url == "https://example.test/feed.xml"
    assert result.bytes_read == len(body)
    metadata = result.to_metadata()
    assert "body_text" not in metadata
    assert "secret" not in str(metadata)


def test_safe_fetch_unsupported_content_type_fails_closed_and_sanitizes_url():
    source_policy = policy()

    result = safe_fetch_public_source(
        source_policy,
        urlopen=lambda request, timeout: FakeResponse(
            body=b"<html></html>",
            content_type="text/html",
            final_url="https://example.test/feed.xml?token=secret",
        ),
    )

    assert result.ok is False
    assert result.error_type == "unsupported_content_type"
    assert result.error_message == "unsupported public-pilot content type"
    assert result.content_type == "text/html"
    assert result.final_url == "https://example.test/feed.xml"
    assert "secret" not in str(result.to_metadata())


def test_safe_fetch_oversized_response_fails_closed_with_size_metadata():
    source_policy = policy()

    result = safe_fetch_public_source(
        source_policy,
        max_response_bytes=5,
        urlopen=lambda request, timeout: FakeResponse(
            body=b"123456",
            content_type="text/plain",
        ),
    )

    assert result.ok is False
    assert result.error_type == "response_too_large"
    assert result.bytes_read == 6
    assert result.max_size_bytes == 5


def test_safe_fetch_timeout_fails_closed_deterministically():
    source_policy = policy()

    def timeout_fetcher(request, timeout):
        raise socket.timeout("timed out with token=secret")

    result = safe_fetch_public_source(source_policy, urlopen=timeout_fetcher)

    assert result.ok is False
    assert result.error_type == "timeout"
    assert result.error_message == "public-pilot fetch timed out"
    assert "secret" not in str(result.to_metadata())


def test_safe_fetch_tls_certificate_error_is_explainable_without_secret_leak():
    source_policy = policy()

    def certificate_error_fetcher(request, timeout):
        raise urllib.error.URLError(
            ssl.SSLCertVerificationError(
                1,
                "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: "
                "unable to get local issuer certificate token=secret",
            )
        )

    result = safe_fetch_public_source(source_policy, urlopen=certificate_error_fetcher)

    assert result.ok is False
    assert result.error_type == "tls_certificate_error"
    assert result.error_message == "public-pilot TLS certificate verification failed"
    assert result.final_url == "https://example.test/feed.xml"
    assert "secret" not in str(result.to_metadata())


def test_safe_fetch_bad_url_fails_before_urlopen():
    called = False

    def fetcher(request, timeout):
        nonlocal called
        called = True
        raise AssertionError("bad URLs must not reach urlopen")

    result = safe_fetch_public_source(policy(url="ftp://example.test/feed.xml"), urlopen=fetcher)

    assert result.ok is False
    assert result.error_type == "bad_url"
    assert result.error_message == "public-pilot URL must be HTTP or HTTPS"
    assert called is False


def test_safe_fetch_url_credentials_fail_before_urlopen_without_leaking_secret():
    called = False

    def fetcher(request, timeout):
        nonlocal called
        called = True
        raise AssertionError("credential URLs must not reach urlopen")

    result = safe_fetch_public_source(
        policy(url="https://user:secret@example.test/feed.xml?token=secret"),
        urlopen=fetcher,
    )

    assert result.ok is False
    assert result.error_type == "url_credentials"
    assert result.error_message == "public-pilot URL cannot include credentials"
    assert result.final_url == "https://example.test/feed.xml"
    assert "secret" not in str(result.to_metadata())
    assert "user" not in str(result.to_metadata())
    assert called is False


def policy(**overrides):
    values = {
        "source_id": "test-public-pilot-rss",
        "source_group": "public-pilot",
        "publisher_name": "Test Publisher",
        "name": "Test Public Pilot RSS",
        "url": "https://example.test/feed.xml",
        "source_type": "rss_feed",
        "source_class": "third_party",
        "category_scope": ("banking",),
        "subcategory_scope": ("checking_bonus",),
        "coverage_purpose": "Public-pilot fetcher shell test source.",
        "trust_tier": "community",
        "official_source": False,
        "deposit_account_source": True,
        "brokerage_source": False,
        "credit_card_source": False,
        "fixture_enabled": False,
        "source_priority": 50,
        "region_scope": ("US",),
        "enabled": True,
        "collection_method": "rss_feed",
        "max_frequency_hours": 48,
        "requires_login": False,
        "allow_scrape": False,
        "allow_api": False,
        "allow_rss": True,
        "allow_email_parse": False,
        "robots_policy_notes": "RSS only; no scraping.",
        "terms_policy_notes": "Public feed test policy.",
        "rate_limit_notes": "At most once every 48 hours.",
        "compliance_status": "approved",
        "last_reviewed_at": date(2026, 6, 21),
        "notes": "Fetcher unit test policy.",
    }
    values.update(overrides)
    return SourcePolicy(**values)
