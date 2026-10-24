# This transform checks if the Proxynova API relates an e-mail with a
# password and returns a phrase that servers as an indicator of success
import html
import re

import requests
from maltego_trx.transform import DiscoverableTransform


API_URL = "https://api.proxynova.com/comb"


def check_exposure(email):
    # Results given an e-mail are requested
    response = requests.get(
        API_URL,
        params={
            "highlight": 1,
            "query": email
        },
        timeout=15
    )

    response.raise_for_status()
    data = response.json()

    # This field contains a list of strings with the search results
    lines = data.get("lines", [])

    if not isinstance(lines, list):
        raise ValueError("Unexpected API response format")

    for line in lines:
        if not isinstance(line, str):
            continue

        # Remove HTML highlighted and decode HTML entities
        clean = re.sub(r"</?strong>", "", line, flags=re.I)
        clean = html.unescape(clean)

        # A result has the format email:password
        returned_email, separator, password = clean.partition(":")

        if not separator:
            continue

        # Exact email comparison
        if returned_email.strip().casefold() != email.casefold():
            continue

        # Only check whether a password is present
        if password:
            return True

    return False


class ProxyNovaExposure(DiscoverableTransform):

    @classmethod
    def create_entities(cls, request, response):

        # Obtain the value introduced in Maltego
        email = request.Value.strip().lower()

        if not re.fullmatch(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", email):
            response.addUIMessage(
                "Invalid email address.",
                "PartialError"
            )
            return

        # Request to ProxyNova
        try:
            exposed = check_exposure(email)

        except (requests.RequestException, ValueError) as e:
            response.addUIMessage(
                f"ProxyNova request failed: {e}",
                "PartialError"
            )
            return

        if exposed:
            value = "Password exposure: Detected"
        else:
            value = "Password exposure: Not confirmed"

        # Result is not represented as a password, but as a phrase
        entity = response.addEntity(
            "maltego.Phrase",
            value
        )

        entity.setLinkLabel(
            "ProxyNova: credential exposure"
        )

        entity.setNote(
            "The e-mail was compared against the ProxyNova API search results. "
            "A positive result is to find an entry containing a non-empty password. "
            "A negative result does not rule out exposure, as the API may return only a subset of matches. "
        )
        