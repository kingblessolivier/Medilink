"""A dependency-free stand-in for the Django backend.

Lets the patient app run without Postgres, PostGIS or Redis, and returns all
four wait states on every request - the states that are easy to get wrong and
hard to produce by hand.

Response shapes come from backend/schema.yaml. If a serializer changes, change
this in the same pull request: a mock that has drifted from the contract is
worse than no mock, because it lets a component ship against a shape the server
never sends.

See README.md in this directory.
"""
import json
import re
from datetime import datetime, timedelta, timezone as tzmod
from http.server import BaseHTTPRequestHandler, HTTPServer

KGL = tzmod(timedelta(hours=2))


def now():
    return datetime.now(KGL)


def iso(d):
    return d.isoformat()


def wait(status, minutes=None, people=None):
    return {"status": status, "minutes": minutes, "people_waiting": people, "as_of": iso(now())}


INSURERS = [
    {"code": "mutuelle", "name": "Mutuelle de Sante", "is_public": True},
    {"code": "rssb", "name": "RSSB", "is_public": True},
    {"code": "mmi", "name": "MMI", "is_public": True},
    {"code": "radiant", "name": "Radiant Insurance", "is_public": False},
    {"code": "cash", "name": "Cash / no insurance", "is_public": False},
]

SERVICES = [
    {"code": "general", "name_rw": "Kwivuza rusange", "name_en": "General consultation", "name_fr": "Consultation generale"},
    {"code": "maternity", "name_rw": "Kubyara", "name_en": "Maternity", "name_fr": "Maternite"},
    {"code": "dental", "name_rw": "Amenyo", "name_en": "Dental", "name_fr": "Dentaire"},
    {"code": "laboratory", "name_rw": "Laboratwari", "name_en": "Laboratory", "name_fr": "Laboratoire"},
    {"code": "paediatrics", "name_rw": "Abana", "name_en": "Paediatrics", "name_fr": "Pediatrie"},
]

SPECIALTIES = [
    {"code": "general_practice", "name_rw": "Muganga rusange", "name_en": "General practice", "name_fr": "Medecine generale"},
    {"code": "paediatrics", "name_rw": "Abana", "name_en": "Paediatrics", "name_fr": "Pediatrie"},
    {"code": "obstetrics", "name_rw": "Kubyara", "name_en": "Obstetrics", "name_fr": "Obstetrique"},
]

DISTRICTS = ["Gasabo", "Kicukiro", "Nyarugenge", "Bugesera", "Rwamagana", "Musanze"]


def fac(i, slug, name, level, own, district, sector, dist_m, isopen, w,
        insurers, services, bookable, closing_soon=False, lat=-1.95, lng=30.06):
    return {
        "id": i, "slug": slug, "name": name, "level": level, "ownership": own,
        "district": district, "sector": sector,
        "location": {"lat": lat, "lng": lng},
        "distance_m": dist_m, "phone": "+25078800%04d" % i,
        "is_open": isopen,
        "opens_at": "07:00" if isopen else None,
        "closes_at": "17:00" if isopen else None,
        "closing_soon": closing_soon,
        "accepts_insurer": "mutuelle" in insurers,
        "insurers": insurers, "services": services,
        "wait": w, "bookable": bookable,
    }


FACILITIES = [
    fac(1, "kimironko-health-centre", "Kimironko Health Centre", "health_centre", "public", "Gasabo", "Kimironko",
        850, True, wait("available", 35, 7), ["mutuelle", "rssb"], ["general", "maternity", "laboratory"], True),
    fac(2, "chuk", "CHUK - Centre Hospitalier Universitaire de Kigali", "referral_hospital", "public", "Nyarugenge", "Nyarugenge",
        3200, True, wait("insufficient_data", None, 24), ["mutuelle", "rssb", "mmi"],
        ["general", "maternity", "dental", "laboratory", "paediatrics"], True),
    fac(3, "la-croix-du-sud", "La Croix du Sud Hospital", "clinic", "private", "Gasabo", "Remera",
        1900, True, wait("not_reported"), ["radiant", "cash", "mmi"], ["general", "dental"], False, closing_soon=True),
    fac(4, "remera-health-post", "Remera Health Post", "health_post", "public", "Gasabo", "Remera",
        2400, False, wait("closed"), ["mutuelle"], ["general"], False),
    fac(5, "king-faisal", "King Faisal Hospital", "referral_hospital", "private", "Gasabo", "Kacyiru",
        4100, True, wait("available", 15, 3), ["mmi", "radiant", "cash"], ["general", "paediatrics", "laboratory"], True),
]

BY_SLUG = {f["slug"]: f for f in FACILITIES}


def detail(f):
    d = dict(f)
    d.update({
        "address": "KG 11 Ave, " + f["sector"],
        "email": "info@example.rw",
        "verified_at": iso(now() - timedelta(days=40)),
        "opening_hours": [{"weekday": w, "opens_at": "07:00", "closes_at": "17:00"} for w in range(6)],
        "services": [
            {
                "code": s["code"], "name_rw": s["name_rw"], "name_en": s["name_en"], "name_fr": s["name_fr"],
                "wait": f["wait"] if i == 0 else wait("insufficient_data", None, 4),
                "coverage": [{
                    "insurer": "mutuelle", "insurer_name": "Mutuelle de Sante",
                    "coverage": "full" if i == 0 else "unknown", "note": "",
                }],
            }
            for i, s in enumerate(SERVICES) if s["code"] in f["services"]
        ],
        "insurers": [
            {"code": c, "name": next((x["name"] for x in INSURERS if x["code"] == c), c), "note": "", "confirmed": True}
            for c in f["insurers"]
        ],
    })
    return d


def slots():
    base = now().replace(hour=8, minute=0, second=0, microsecond=0)
    days = []
    for dnum in range(1, 6):
        day = base + timedelta(days=dnum)
        ss = []
        for k in range(14):
            st = day + timedelta(minutes=30 * k)
            ss.append({
                "start": iso(st), "end": iso(st + timedelta(minutes=30)),
                "remaining": 0 if k in (2, 3, 7) else (1 if k % 4 else 3),
                "capacity": 3,
            })
        days.append({"date": day.date().isoformat(), "slots": ss})
    return {"days": days}


def placement(slug, name, district, role, services):
    return {"facility_slug": slug, "facility_name": name, "district": district,
            "role_title": role, "services": services}


def provider(slug, display, full, initials, langs, specs, places, verified=True, photo=""):
    return {"slug": slug, "display_name": display, "full_name": full, "initials": initials,
            "photo_url": photo, "languages": langs, "specialties": specs,
            "placements": places, "verified": verified}


PROVIDERS = [
    provider("dr-uwase-alice", "Dr Uwase Alice", "Alice Uwase", "AU", ["rw", "en"],
             [{"code": "general_practice", "name_rw": "Muganga rusange", "name_en": "General practice",
               "name_fr": "Medecine generale"}],
             [placement("kimironko-health-centre", "Kimironko Health Centre", "Gasabo",
                        "Medical Officer", ["general"])]),
    provider("dr-mugisha-eric", "Dr Mugisha Eric", "Eric Mugisha", "EM", ["rw", "fr"],
             [{"code": "paediatrics", "name_rw": "Abana", "name_en": "Paediatrics", "name_fr": "Pediatrie"}],
             [placement("chuk", "CHUK", "Nyarugenge", "Consultant Paediatrician", ["paediatrics"])]),
    provider("dr-keza-jean", "Dr Keza Jean", "Jean Keza", "JK", ["rw"],
             [{"code": "obstetrics", "name_rw": "Kubyara", "name_en": "Obstetrics", "name_fr": "Obstetrique"}],
             [placement("kimironko-health-centre", "Kimironko Health Centre", "Gasabo",
                        "Midwife", ["maternity"])], verified=False),
]


def route(path, q):
    if path == "/api/v1/districts":
        return 200, {"results": DISTRICTS}
    if path == "/api/v1/insurers":
        return 200, {"results": INSURERS}
    if path == "/api/v1/service-types":
        return 200, {"results": SERVICES}
    if path == "/api/v1/specialties":
        return 200, {"results": SPECIALTIES}
    if path == "/api/v1/triage/status":
        return 200, {"enabled": False, "protocol_version": None, "approved_by": None}
    if path == "/api/v1/queue/current":
        return 204, None
    if path in ("/api/v1/auth/session", "/api/v1/me", "/api/v1/staff/me"):
        return 401, {"type": "authentication_required", "detail": "Sign in."}
    if path == "/api/v1/facilities/nearby":
        return 200, {
            "as_of": iso(now()), "count": len(FACILITIES), "results": FACILITIES,
            "query": {"lat": -1.95, "lng": 30.06, "district": q.get("district"), "radius": 5000,
                      "radius_expanded": False, "insurer": q.get("insurer"), "service": q.get("service"),
                      "specialty": q.get("specialty"), "open_now": q.get("open_now") == "true"},
        }
    if path == "/api/v1/providers":
        return 200, {"count": len(PROVIDERS), "results": PROVIDERS}
    if path == "/api/v1/search":
        term = (q.get("q") or "").replace("+", " ").lower()
        fm = [f for f in FACILITIES if term in f["name"].lower()]
        pm = [p for p in PROVIDERS if term in p["display_name"].lower()]
        return 200, {"query": q.get("q", ""), "groups": [
            {"kind": "facility", "label": "Amavuriro", "results": [
                {"kind": "facility", "slug": f["slug"], "title": f["name"], "subtitle": f["district"], "meta": None}
                for f in fm]},
            {"kind": "provider", "label": "Abaganga", "results": [
                {"kind": "provider", "slug": p["slug"], "title": p["display_name"],
                 "subtitle": p["specialties"][0]["name_en"], "meta": None} for p in pm]},
        ]}

    m = re.match(r"^/api/v1/facilities/([^/]+)$", path)
    if m and m.group(1) in BY_SLUG:
        return 200, detail(BY_SLUG[m.group(1)])
    m = re.match(r"^/api/v1/facilities/([^/]+)/slots$", path)
    if m:
        return 200, slots()
    m = re.match(r"^/api/v1/facilities/([^/]+)/providers$", path)
    if m:
        return 200, {"count": len(PROVIDERS), "results": PROVIDERS}
    m = re.match(r"^/api/v1/providers/([^/]+)$", path)
    if m:
        p = next((x for x in PROVIDERS if x["slug"] == m.group(1)), PROVIDERS[0])
        d = dict(p)
        pass
        return 200, d

    return 200, {"results": [], "count": 0}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body):
        raw = b"" if body is None else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if raw:
            self.wfile.write(raw)

    def do_GET(self):
        p, _, qs = self.path.partition("?")
        q = dict(x.split("=", 1) for x in qs.split("&") if "=" in x)
        try:
            code, body = route(p, q)
        except Exception as exc:
            code, body = 500, {"detail": str(exc)}
        self._send(code, body)

    def do_POST(self):
        self._send(401, {"type": "authentication_required", "detail": "Sign in."})

    def do_OPTIONS(self):
        self._send(204, None)


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8000), Handler).serve_forever()
