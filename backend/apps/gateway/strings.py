"""USSD copy.

Two hard constraints, both enforced by tests in tests/test_strings.py:

  1. **160 characters per screen.** There is no scrolling on a feature phone.
     A longer screen is truncated by the network, usually mid-word.
  2. **GSM-7 basic table only.** Characters outside it arrive as `?`.

Kinyarwanda first. It is the default and the majority language of the users
this channel exists for.

Every string here has been kept short at the cost of elegance. That is the
right trade: a rural patient on a feature phone gets three lines, and the most
useful line has to be the first one.
"""

MAIN_MENU = {
    "rw": (
        "MediLink\n"
        "1. Amavuriro hafi\n"
        "2. Gutegura\n"
        "3. Umurongo wanjye\n"
        "4. Ubwishingizi\n"
        "5. Ururimi"
    ),
    "en": (
        "MediLink\n"
        "1. Nearby facilities\n"
        "2. Book\n"
        "3. My queue\n"
        "4. Insurance\n"
        "5. Language"
    ),
    "fr": (
        "MediLink\n"
        "1. Centres proches\n"
        "2. Reserver\n"
        "3. Ma file\n"
        "4. Assurance\n"
        "5. Langue"
    ),
}

CHOOSE_DISTRICT = {
    "rw": "Hitamo akarere:",
    "en": "Choose your district:",
    "fr": "Choisissez votre district:",
}

CHOOSE_SERVICE = {
    "rw": "Hitamo serivisi:",
    "en": "Choose a service:",
    "fr": "Choisissez un service:",
}

CHOOSE_FACILITY = {
    "rw": "Hitamo ivuriro:",
    "en": "Choose a facility:",
    "fr": "Choisissez un centre:",
}

CHOOSE_SLOT = {
    "rw": "Hitamo isaha:",
    "en": "Choose a time:",
    "fr": "Choisissez une heure:",
}

NEARBY_HEADER = {
    "rw": "Amavuriro hafi yawe:",
    "en": "Facilities near you:",
    "fr": "Centres proches:",
}

NO_FACILITIES = {
    "rw": "Nta vuriro riboneka muri {district}.",
    "en": "No facilities found in {district}.",
    "fr": "Aucun centre trouve a {district}.",
}

NO_SLOTS = {
    "rw": "Nta masaha aboneka muri iki gihe.",
    "en": "No times available right now.",
    "fr": "Aucun horaire disponible.",
}

QUEUE_STATUS = {
    "rw": "Uri nomero {position} kuri {facility}.\nIminota isigaye: {minutes}.",
    "en": "You are number {position} at {facility}.\nAbout {minutes} min left.",
    "fr": "Vous etes numero {position} a {facility}.\nEnviron {minutes} min.",
}

QUEUE_STATUS_NO_ETA = {
    "rw": "Uri nomero {position} kuri {facility}.\nIgihe ntikiboneka.",
    "en": "You are number {position} at {facility}.\nWait time not available.",
    "fr": "Vous etes numero {position} a {facility}.\nAttente inconnue.",
}

QUEUE_CALLED = {
    "rw": "Barahamagara {ticket} kuri {facility}. Injira.",
    "en": "You are being called: {ticket} at {facility}.",
    "fr": "On vous appelle: {ticket} a {facility}.",
}

NO_ACTIVE_QUEUE = {
    "rw": "Nta murongo urimo ubu.",
    "en": "You are not in a queue right now.",
    "fr": "Vous n'etes dans aucune file.",
}

BOOKED = {
    "rw": "Byemejwe. Kode: {reference}.\n{facility} saa {time}.",
    "en": "Booked. Ref {reference}.\n{facility} at {time}.",
    "fr": "Reserve. Ref {reference}.\n{facility} a {time}.",
}

BOOKING_FAILED = {
    "rw": "Ntibyakunze: {reason}",
    "en": "Could not book: {reason}",
    "fr": "Echec: {reason}",
}

CHOOSE_INSURER = {
    "rw": "Hitamo ubwishingizi:",
    "en": "Choose your insurance:",
    "fr": "Choisissez votre assurance:",
}

INSURER_SAVED = {
    "rw": "Ubwishingizi bwawe ni {insurer}.",
    "en": "Your insurance is set to {insurer}.",
    "fr": "Votre assurance: {insurer}.",
}

CHOOSE_LANGUAGE = {
    "rw": "Hitamo ururimi:\n1. Kinyarwanda\n2. English\n3. Francais",
    "en": "Choose a language:\n1. Kinyarwanda\n2. English\n3. Francais",
    "fr": "Choisissez la langue:\n1. Kinyarwanda\n2. English\n3. Francais",
}

LANGUAGE_SAVED = {
    "rw": "Ururimi rwahinduwe.",
    "en": "Language updated.",
    "fr": "Langue mise a jour.",
}

INVALID_CHOICE = {
    "rw": "Ntabwo ari amahitamo. Ongera ugerageze.",
    "en": "That is not a valid choice.",
    "fr": "Choix invalide.",
}

SESSION_EXPIRED = {
    "rw": "Igihe cyarangiye. Ongera utangire.",
    "en": "Session expired. Please start again.",
    "fr": "Session expiree. Recommencez.",
}

SERVICE_UNAVAILABLE = {
    "rw": "Serivisi ntibonetse. Ongera ugerageze.",
    "en": "Service unavailable. Please try again.",
    "fr": "Service indisponible. Reessayez.",
}

SIGN_IN_FIRST = {
    "rw": "Banza wiyandikishe kuri MediLink.",
    "en": "Register on MediLink first.",
    "fr": "Inscrivez-vous d'abord.",
}


# Every dict of translations in this module, for the coverage test.
ALL_BUNDLES = {
    name: value
    for name, value in list(globals().items())
    if isinstance(value, dict)
    and name.isupper()
    and set(value) == {"rw", "en", "fr"}
}


def t(bundle: dict, language: str, **context) -> str:
    """Look up a string, falling back to Kinyarwanda."""
    template = bundle.get(language) or bundle["rw"]
    return template.format(**context) if context else template
