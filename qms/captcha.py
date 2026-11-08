"""
Captcha for the account request page.

Two back ends, chosen by settings.QMS_CAPTCHA:

  * "pow" (default): a self-hosted proof-of-work challenge in the ALTCHA format. The browser
    finds a number whose SHA-256, with a random salt, matches the challenge; this takes a
    second or two of computation. No third party, no cookies, no puzzle to read, no keys.
  * "turnstile": Cloudflare Turnstile, when QMS_TURNSTILE_SITE_KEY and
    QMS_TURNSTILE_SECRET_KEY are set. The token is checked with Cloudflare's siteverify API.

A proof-of-work challenge is signed with the secret key, expires, and is bound to the browser
session: it can be used once, by the session it was issued to.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse
import urllib.request

from django.conf import settings

SESSION_KEY = "qms_captcha_challenge"
TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def backend() -> str:
    if (settings.QMS_CAPTCHA == "turnstile" and settings.QMS_TURNSTILE_SITE_KEY
            and settings.QMS_TURNSTILE_SECRET_KEY):
        return "turnstile"
    return "pow"


def _sign(text: str) -> str:
    key = ("qms-captcha:" + settings.SECRET_KEY).encode()
    return hmac.new(key, text.encode(), hashlib.sha256).hexdigest()


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def new_challenge(request) -> dict:
    """A fresh proof-of-work challenge for this session (replaces any earlier one)."""
    expires = int(time.time()) + settings.QMS_CAPTCHA_TTL_SECONDS
    salt = f"{secrets.token_hex(12)}?expires={expires}"
    maxnumber = settings.QMS_CAPTCHA_DIFFICULTY
    challenge = _sha(salt + str(secrets.randbelow(maxnumber)))
    request.session[SESSION_KEY] = challenge
    return {"algorithm": "SHA-256", "challenge": challenge, "maxnumber": maxnumber,
            "salt": salt, "signature": _sign(challenge)}


def verify_pow(request, payload: str) -> bool:
    """Checks a solution (base64 JSON: algorithm, challenge, number, salt, signature)."""
    issued = request.session.pop(SESSION_KEY, None)  # single use, whatever the outcome
    try:
        data = json.loads(base64.b64decode(payload or "", validate=True))
        challenge, salt = str(data["challenge"]), str(data["salt"])
        number, signature = int(data["number"]), str(data["signature"])
        expires = int(urllib.parse.parse_qs(salt.split("?", 1)[1])["expires"][0])
    except (ValueError, KeyError, IndexError, TypeError):
        return False
    return (issued is not None and hmac.compare_digest(issued, challenge)
            and data.get("algorithm") == "SHA-256"
            and hmac.compare_digest(signature, _sign(challenge))
            and 0 <= number <= settings.QMS_CAPTCHA_DIFFICULTY
            and hmac.compare_digest(_sha(salt + str(number)), challenge)
            and expires >= time.time())


def verify_turnstile(token: str) -> bool:
    if not token or len(token) > 2048:
        return False
    body = urllib.parse.urlencode({"secret": settings.QMS_TURNSTILE_SECRET_KEY,
                                   "response": token}).encode()
    try:
        with urllib.request.urlopen(TURNSTILE_VERIFY_URL, data=body, timeout=8) as resp:
            return bool(json.loads(resp.read()).get("success"))
    except Exception:  # noqa: BLE001 - network failure means not verified
        return False


def verify(request) -> bool:
    """True when the posted captcha was solved."""
    if backend() == "turnstile":
        return verify_turnstile(request.POST.get("cf-turnstile-response", ""))
    return verify_pow(request, request.POST.get("captcha", ""))


def solve(challenge: dict) -> str:
    """Solves a proof-of-work challenge, as the browser does. For tests and monitoring."""
    for n in range(challenge["maxnumber"] + 1):
        if _sha(challenge["salt"] + str(n)) == challenge["challenge"]:
            return base64.b64encode(json.dumps({
                "algorithm": "SHA-256", "challenge": challenge["challenge"], "number": n,
                "salt": challenge["salt"], "signature": challenge["signature"]}).encode()).decode()
    raise ValueError("no solution")
