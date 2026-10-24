# This transform obtains information from the UM directory given an e-mail @um.es
# The request is: POST https://www.um.es/ws-siu/directorio/api-ldap_post_v3.php
# The POST body contains: {"term": <email>, "viewId": "search", "option": "unidades", "session_id": "..."}
# The output entities are: Person, EmailAddress, PhoneNumber, Alias (LDAP identifier),
# Organization (Centre, Department), Location (Office, Building, Campus), Phrase (position, area, affiliation)

import os
import re

import requests
from maltego_trx.transform import DiscoverableTransform

API_URL = "https://www.um.es/ws-siu/directorio/api-ldap_post_v3.php"
# umu_transform/session_id.txt
SESSION_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "session_id.txt")
# This is the option sent by the browser
OPTION = "unidades"

def get_session_id():
    try:
        with open(SESSION_FILE, encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return ""


def query_api(email):
    payload = {"term": email, "viewId": "search", "option": OPTION}
    session_id = get_session_id()
    if session_id:
        payload["session_id"] = session_id
    # The API expects Content-Type: application/json
    r = requests.post(API_URL, json=payload, timeout=15)
    return r.json()

# This method is required since the API returns some fields as lists (email, telephone, ...)
def as_list(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]

# Returns only the persons whose e-mail list contains the input e-mail address
def exact_matches(data, email):
    out = []
    for person in data["_embedded"].get("persons", []):
        mails = [mail.lower() for mail in as_list(person.get("email"))]
        for rel in as_list(person.get("relations")):
            mails += [m.lower() for m in as_list(rel.get("email"))]
        if email in mails:
            out.append(person)
    return out

# The API returns the names in upper case; this is purely cosmetic
def title(s):
    return s.title() if s and s.isupper() else s

# Returns a list of (entity_type, value, link_label, json_field)
# json_field is the response field where the data comes from
def collect(person, email):
    items = []
    items.append(("maltego.Person", title(person.get("name")), "UM Directory: name", "name"))
    for m in as_list(person.get("email")):
        if m.lower() != email:
            items.append(("maltego.EmailAddress", m, "UM Directory: additional e-mail", "email"))
    for t in as_list(person.get("telephone")):
        items.append(("maltego.PhoneNumber", t, "UM Directory: phone", "telephone"))
    for i in as_list(person.get("identifier")):
        items.append(("maltego.Alias", i, "UM Directory: LDAP identifier", "identifier"))

    for rel in as_list(person.get("relations")):
        building = rel.get("edificios_desc")
        office = rel.get("officeId")
        office_text = (f"Office {office} ({building})" if building else f"Office {office}") if office else None

        dept = rel.get("unidades_desc") or rel.get("ou")
        area = rel.get("areas_desc") or rel.get("description")

        pos = rel.get("puestos_desc") or rel.get("businessCategory")
        cat = rel.get("businessCategory")

        affiliation = rel.get("filiaciones_desc")
        cargo = rel.get("cargos_desc")

        if affiliation == "Cargo" and cargo:
            # Show the specific institutional role
            role = ("maltego.Phrase", f"Institutional role: {cargo}", "institutional role", "relations.cargos_desc")
        else:
            # Keep other affiliations unchanged (PDI, PAS, etc.)
            role = ("maltego.Phrase", f"Affiliation: {affiliation}" if affiliation else None, "affiliation", "relations.filiaciones_desc")

        fields = [
                    ("maltego.Location",     office_text,                         "office",          "relations.officeId"),
                    ("maltego.Location",     building,                            "building",        "relations.edificios_desc"),
                    ("maltego.Location",     rel.get("campus_desc"),              "campus",          "relations.campus_desc"),
                    ("maltego.Organization", rel.get("centros_desc"),             "faculty/centre",  "relations.centros_desc"),
                    ("maltego.Organization", dept,                                "department/unit", "relations.unidades_desc"),
                    ("maltego.Phrase",       f"Area: {area}" if area else None,   "knowledge area",  "relations.areas_desc"),
                    ("maltego.Phrase",       f"Position: {pos}" if pos else None, "position",        "relations.puestos_desc"),
                    ("maltego.Phrase",       f"Category: {cat}" if cat and cat != pos else None, "category", "relations.businessCategory"),
                    role,
                ]
        
        for etype, value, label, field in fields:
            if value:
                items.append((etype, value, f"UM directory: {label}", field))

        for t in as_list(rel.get("telephone")):
            items.append(("maltego.PhoneNumber", t, "UM Directory: phone", "relations.telephone"))
        # Additional e-mail related to the relations
        for m in as_list(rel.get("email")):
            if m.lower() != email:
                items.append(("maltego.EmailAddress", m, "UM Directory: additional e-mail", "relations.email"))

    return items

class UMDirectory(DiscoverableTransform):
    """Registered in Maltego as 'umdirectory'."""

    @classmethod
    def create_entities(cls, request, response):
        email = request.Value.strip().lower()
        if not re.fullmatch(r"[\w.+-]+@um\.es", email):
            response.addUIMessage("Only @um.es addresses are supported.", "PartialError")
            return
        try:
            data = query_api(email)
        except (requests.RequestException, ValueError) as e:
            response.addUIMessage(f"Directory request failed: {e}", "PartialError")
            return

        if "_embedded" not in data:
            response.addUIMessage(f"Unexpected API response (no persons): {data}", "PartialError")
            return
        people = exact_matches(data, email)
        total = data.get("totalCount", "?")
        if not people:
            response.addUIMessage(f"{total} results but none match {email}.", "Inform")
            return

        src = f"UM directory API ({API_URL}), term={email}"
        seen = set()
        for person in people:
            for etype, value, label, field in collect(person, email):
                value = (value or "").strip()
                # Empty or repeated values are discarded
                if not value or (etype, value) in seen:
                    continue
                seen.add((etype, value))
                ent = response.addEntity(etype, value)
                ent.setLinkLabel(label)
                ent.setNote(f"Obtained from {src}, JSON response field '{field}'. "
                            f"E-mail match among {total} results.")
                # First name and surname are added as separate properties
                if etype == "maltego.Person":
                    ent.addProperty("person.firstnames", "First names", "nostrict", title(person.get("givenName") or ""))
                    ent.addProperty("person.lastname", "Surname", "nostrict", title(person.get("familyName") or ""))