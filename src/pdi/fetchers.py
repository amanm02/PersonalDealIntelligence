"""Safe, bounded public-source fetching for opt-in live collection."""

from __future__ import annotations

import socket
import urllib.error
import urllib.parse
import urllib.request
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pdi.sources import SourcePolicy


DEFAULT_FETCH_TIMEOUT_SECONDS = 10
DEFAULT_MAX_RESPONSE_BYTES = 1_000_000
PUBLIC_FETCH_USER_AGENT = "PersonalDealIntelligence-public-pilot/1.0"
ALLOWED_PUBLIC_CONTENT_TYPES = {
    "application/atom+xml",
    "application/rdf+xml",
    "application/rss+xml",
    "application/x-rss+xml",
    "application/xml",
    "text/plain",
    "text/xml",
}


UrlOpen = Callable[..., Any]


@dataclass(frozen=True)
class SafeFetchResult:
    """Typed result for a bounded public-source fetch attempt."""

    ok: bool
    body_text: str | None = None
    status_code: int | None = None
    content_type: str | None = None
    final_url: str | None = None
    bytes_read: int = 0
    max_size_bytes: int = DEFAULT_MAX_RESPONSE_BYTES
    error_type: str | None = None
    error_message: str | None = None

    @classmethod
    def success(
        cls,
        *,
        body_text: str,
        status_code: int | None,
        content_type: str | None,
        final_url: str | None,
        bytes_read: int,
        max_size_bytes: int,
    ) -> "SafeFetchResult":
        return cls(
            ok=True,
            body_text=body_text,
            status_code=status_code,
            content_type=_normalize_content_type(content_type),
            final_url=_sanitize_url(final_url),
            bytes_read=bytes_read,
            max_size_bytes=max_size_bytes,
        )

    @classmethod
    def failure(
        cls,
        *,
        error_type: str,
        error_message: str,
        status_code: int | None = None,
        content_type: str | None = None,
        final_url: str | None = None,
        bytes_read: int = 0,
        max_size_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    ) -> "SafeFetchResult":
        return cls(
            ok=False,
            status_code=status_code,
            content_type=_normalize_content_type(content_type),
            final_url=_sanitize_url(final_url),
            bytes_read=bytes_read,
            max_size_bytes=max_size_bytes,
            error_type=_sanitize_token(error_type),
            error_message=_sanitize_message(error_message),
        )

    def to_metadata(self) -> dict[str, Any]:
        """Return safe JSON-serializable metadata without response body text."""

        return {
            "ok": self.ok,
            "status_code": self.status_code,
            "content_type": self.content_type,
            "final_url": self.final_url,
            "bytes_read": self.bytes_read,
            "max_size_bytes": self.max_size_bytes,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


def safe_fetch_public_source(
    policy: SourcePolicy,
    *,
    timeout_seconds: int = DEFAULT_FETCH_TIMEOUT_SECONDS,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> SafeFetchResult:
    """Fetch one public source with strict URL, size, and content-type gates."""

    url_error = _validate_public_url(policy.url)
    if url_error is not None:
        return SafeFetchResult.failure(
            error_type=url_error,
            error_message=_error_message(url_error),
            final_url=policy.url,
            max_size_bytes=max_response_bytes,
        )

    request = urllib.request.Request(
        policy.url,
        headers={"User-Agent": PUBLIC_FETCH_USER_AGENT},
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310
            status_code = _response_status(response)
            content_type = _response_content_type(response)
            final_url = _response_final_url(response, policy.url)
            if content_type not in ALLOWED_PUBLIC_CONTENT_TYPES:
                return SafeFetchResult.failure(
                    error_type="unsupported_content_type",
                    error_message="unsupported public-pilot content type",
                    status_code=status_code,
                    content_type=content_type,
                    final_url=final_url,
                    max_size_bytes=max_response_bytes,
                )

            body_bytes = response.read(max_response_bytes + 1)
            bytes_read = len(body_bytes)
            if bytes_read > max_response_bytes:
                return SafeFetchResult.failure(
                    error_type="response_too_large",
                    error_message="public-pilot response exceeded max size",
                    status_code=status_code,
                    content_type=content_type,
                    final_url=final_url,
                    bytes_read=bytes_read,
                    max_size_bytes=max_response_bytes,
                )

            charset = _response_charset(response)
            return SafeFetchResult.success(
                body_text=body_bytes.decode(charset, errors="replace"),
                status_code=status_code,
                content_type=content_type,
                final_url=final_url,
                bytes_read=bytes_read,
                max_size_bytes=max_response_bytes,
            )
    except TimeoutError:
        return _timeout_failure(policy.url, max_response_bytes)
    except socket.timeout:
        return _timeout_failure(policy.url, max_response_bytes)
    except urllib.error.URLError as error:
        if isinstance(error.reason, (TimeoutError, socket.timeout)):
            return _timeout_failure(policy.url, max_response_bytes)
        return SafeFetchResult.failure(
            error_type="network_error",
            error_message="public-pilot fetch failed",
            final_url=policy.url,
            max_size_bytes=max_response_bytes,
        )
    except OSError:
        return SafeFetchResult.failure(
            error_type="network_error",
            error_message="public-pilot fetch failed",
            final_url=policy.url,
            max_size_bytes=max_response_bytes,
        )


def _timeout_failure(url: str, max_size_bytes: int) -> SafeFetchResult:
    return SafeFetchResult.failure(
        error_type="timeout",
        error_message="public-pilot fetch timed out",
        final_url=url,
        max_size_bytes=max_size_bytes,
    )


def _validate_public_url(url: str) -> str | None:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return "bad_url"
    if parsed.username or parsed.password:
        return "url_credentials"
    return None


def _response_status(response: Any) -> int | None:
    status = getattr(response, "status", None)
    if isinstance(status, int):
        return status
    getcode = getattr(response, "getcode", None)
    if callable(getcode):
        value = getcode()
        return value if isinstance(value, int) else None
    return None


def _response_content_type(response: Any) -> str | None:
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    get_content_type = getattr(headers, "get_content_type", None)
    if callable(get_content_type):
        return _normalize_content_type(get_content_type())
    get = getattr(headers, "get", None)
    if callable(get):
        return _normalize_content_type(get("Content-Type"))
    return None


def _response_charset(response: Any) -> str:
    headers = getattr(response, "headers", None)
    get_content_charset = getattr(headers, "get_content_charset", None)
    if callable(get_content_charset):
        return get_content_charset() or "utf-8"
    return "utf-8"


def _response_final_url(response: Any, fallback_url: str) -> str:
    geturl = getattr(response, "geturl", None)
    if callable(geturl):
        value = geturl()
        if isinstance(value, str) and value:
            return value
    return fallback_url


def _normalize_content_type(content_type: str | None) -> str | None:
    if not content_type:
        return None
    return content_type.split(";", 1)[0].strip().lower() or None


def _sanitize_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urllib.parse.urlsplit(url)
    hostname = parsed.hostname or ""
    netloc = hostname
    if parsed.port is not None:
        netloc = f"{netloc}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


def _error_message(error_type: str) -> str:
    messages = {
        "bad_url": "public-pilot URL must be HTTP or HTTPS",
        "url_credentials": "public-pilot URL cannot include credentials",
    }
    return messages.get(error_type, "public-pilot fetch failed")


def _sanitize_message(message: str) -> str:
    collapsed = " ".join(message.replace("\n", " ").replace("\r", " ").split())
    collapsed = re.sub(
        r"https?://[^\s]+",
        lambda match: _sanitize_url(match.group(0)) or "[redacted-url]",
        collapsed,
    )
    return re.sub(
        r"(?i)\b(token|password|secret|cookie|session)[=:][^\s&]+",
        lambda match: f"{match.group(1)}=[redacted]",
        collapsed,
    )


def _sanitize_token(value: str) -> str:
    return value.replace(" ", "_").lower()
