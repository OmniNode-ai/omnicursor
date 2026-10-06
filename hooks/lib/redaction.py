"""Secret redaction for every prompt fragment that leaves the machine (A5).

Byte-for-byte port of the secret-pattern table from the authoritative donor,
``omniclaude/src/omniclaude/hooks/schemas.py`` (the copy that gates OmniClaude's
broadcast topics — NOT the ``secret_redactor.py`` twin). The pattern list below
must stay byte-identical to the donor's; ``tests/test_redaction.py`` enforces
byte-parity. Pure stdlib (``re`` only) — safe to import from any hook.

The patterns are designed for use with sub()/subn(), NOT findall() (capturing
groups exist only where the replacement needs backreferences).
"""

from __future__ import annotations

import re

_SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # API keys with common prefixes
    # Note: No capturing groups - sub()/subn() replace the full match
    (re.compile(r"\bsk-[a-zA-Z0-9]{20,}", re.IGNORECASE), "sk-***REDACTED***"),
    (re.compile(r"\bAKIA[A-Z0-9]{16}", re.IGNORECASE), "AKIA***REDACTED***"),
    (re.compile(r"\bghp_[a-zA-Z0-9]{36}", re.IGNORECASE), "ghp_***REDACTED***"),
    (re.compile(r"\bgho_[a-zA-Z0-9]{36}", re.IGNORECASE), "gho_***REDACTED***"),
    (
        re.compile(r"\bxox[baprs]-[a-zA-Z0-9-]{10,}", re.IGNORECASE),
        "xox*-***REDACTED***",
    ),
    # Stripe API keys (publishable, secret, and restricted)
    # Format: (sk|pk|rk)_(live|test)_[a-zA-Z0-9]{24,}
    # Reference: https://stripe.com/docs/keys
    # Note: (?:...) is non-capturing group for alternation, not for backreference
    (
        re.compile(r"\b(?:sk|pk|rk)_(?:live|test)_[a-zA-Z0-9]{24,}", re.IGNORECASE),
        "stripe_***REDACTED***",
    ),
    # Google Cloud Platform API keys
    # Format: AIza[0-9A-Za-z-_]{35}
    # Reference: https://cloud.google.com/docs/authentication/api-keys
    (re.compile(r"\bAIza[0-9A-Za-z\-_]{35}"), "AIza***REDACTED***"),
    # JWT tokens (JSON Web Tokens)
    # Format: base64url(header).base64url(payload).base64url(signature)
    # Header always starts with eyJ (base64 of '{"')
    # Reference: RFC 7519 (JSON Web Token)
    (
        re.compile(r"\beyJ[a-zA-Z0-9_-]*\.eyJ[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"),
        "jwt_***REDACTED***",
    ),
    # Private keys (PEM format)
    # Matches RSA, EC, DSA, OPENSSH, generic, and encrypted private key headers
    # Reference: RFC 7468 (Textual Encodings of PKIX, PKCS, and CMS Structures)
    # Reference: OpenSSH PROTOCOL.key format for OPENSSH keys
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
        ),
        "-----BEGIN ***REDACTED*** PRIVATE KEY-----",
    ),
    # Bearer tokens
    (
        re.compile(
            r"(Bearer\s+)[a-zA-Z0-9._-]{20,}",
            re.IGNORECASE,  # pragma: allowlist secret
        ),
        r"\1***REDACTED***",
    ),
    # Password in URLs (postgres://user:password@host, mysql://user:password@host, mongodb://...)  # pragma: allowlist secret
    # This pattern intentionally covers all database connection string formats.
    # Bounded to a URL authority -- no whitespace/slash/@ inside the userinfo
    # (OMN-15462/OMN-16277 fix). MUST stay in sync with
    # plugins/onex/hooks/lib/secret_redactor.py -- the prior unbounded
    # classes (`[^:]+`/`[^@]+`) matched "any later colon, any later @"
    # across whitespace and newlines, mass-redacting ordinary multi-line
    # text that merely contained a URL followed eventually by a colon and
    # an @ref-pin.
    (re.compile(r"(://[^:/\s@]+:)[^@/\s]+(@)"), r"\1***REDACTED***\2"),
    # Generic secret patterns in key=value format
    # Note: Requires 8+ char values to reduce false positives like "password=true"
    # Word boundary \b ensures we don't match "reset_password" when looking for "password"
    (
        re.compile(
            r"(\b(?:password|passwd|secret|token|api_key|apikey|auth)\s*[=:]\s*)['\"]?[^\s'\"]{8,}['\"]?",
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
    # Secret-bearing key NAMES with no word boundary before the label root
    # (OMN-16277). MUST stay in sync with
    # plugins/onex/hooks/lib/secret_redactor.py -- see that module's
    # comment for the full rationale (JSON/map keys like "clientSecret"
    # have no \b between "client" and "Secret", both word characters).
    (
        re.compile(
            r'(["\']?[A-Za-z][A-Za-z0-9_]*(?:secret|token|passwd|password|'
            r'apikey|api_key|credential)[A-Za-z0-9_]*["\']?\s*[:=]\s*)'
            r"""["']?[A-Za-z0-9+/=_.\-]{8,}""",
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
    # Prose-form credential mentions (OMN-15062). MUST stay in sync with
    # plugins/onex/hooks/lib/secret_redactor.py's SECRET_PATTERNS -- see
    # that module's docstring for the coverage-limit rationale (bare
    # unlabeled high-entropy strings are NOT caught by this or any pattern
    # here; a labeled mention like "the password is <token>" is).
    (
        re.compile(
            r"(\b(?:password|passwd|secret|credential|api[_ ]?key|token)\b"
            r"(?:\s+\S+){0,4}?\s+(?:is|was|[=:])\s*[`'\"]?)"
            r"([A-Za-z0-9!@#$%^&*()_+\-.]{10,})",
            re.IGNORECASE,
        ),
        r"\1***REDACTED***",
    ),
]

# Default preview length — mirrors the donor's PROMPT_PREVIEW_MAX_LENGTH.
PREVIEW_MAX_LENGTH: int = 100

# Control characters (except tab/newline handling done by callers) that must
# never flow into an emitted payload or an injected context block.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Any whitespace run (including newlines) — collapsed to one space when text is
# flattened into a single-line context (prevents fake markdown headers/blocks).
_WHITESPACE_RUN_RE = re.compile(r"\s+")


def redact_secrets(text: str) -> str:
    """Redact all known secret patterns; no truncation (donor: sanitize_text)."""
    out = text
    for pattern, replacement in _SECRET_PATTERNS:
        out = pattern.sub(replacement, out)
    return out


def sanitize_preview(text: str, max_length: int = PREVIEW_MAX_LENGTH) -> str:
    """Redact then truncate — donor semantics (_sanitize_prompt_preview).

    Truncation reserves 3 chars for the ``...`` suffix, so the result never
    exceeds *max_length*.
    """
    sanitized = redact_secrets(text)
    if len(sanitized) > max_length:
        return sanitized[: max_length - 3] + "..."
    return sanitized


def sanitize_pattern_text(text: str, max_length: int = 300) -> str:
    """Sanitize externally-fetched pattern text before context injection.

    Fetched pattern ids/descriptions are untrusted input that flows into the
    model's ``additional_context`` (prompt-injection surface): strip control
    characters, collapse every whitespace run (so multi-line text cannot fake
    markdown headers, comment markers, or new list items), redact secrets,
    and cap the length.
    """
    flattened = _WHITESPACE_RUN_RE.sub(" ", _CONTROL_CHARS_RE.sub("", text)).strip()
    return sanitize_preview(flattened, max_length=max_length)
