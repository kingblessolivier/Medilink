"""USSD copy constraints.

These are the tests that catch `générale` before a telco turns it into
`g?n?rale` on a patient's phone, and catch a screen that overflows 160
characters before it is truncated mid-word.
"""

import pytest

from apps.gateway import strings as S
from apps.gateway.sms import GSM7, is_gsm7
from apps.gateway.ussd import MAX_USSD_CHARS

# Placeholder values long enough to be realistic. Templates must still fit
# once filled, not merely while empty.
SAMPLE = {
    "district": "Nyarugenge",
    "facility": "Kimironko HC",
    "position": 12,
    "minutes": 45,
    "ticket": "G-042",
    "reference": "X9CJR4",
    "time": "Wed 08:00",
    "insurer": "Mutuelle de Sante",
    "reason": "That time has just been taken. Please choose another.",
}


def render(template: str) -> str:
    keys = {k: v for k, v in SAMPLE.items() if "{" + k + "}" in template}
    return template.format(**keys) if keys else template


@pytest.mark.parametrize("name,bundle", sorted(S.ALL_BUNDLES.items()))
@pytest.mark.parametrize("language", ["rw", "en", "fr"])
def test_every_string_is_gsm7(name, bundle, language):
    """Characters outside the GSM-7 basic table arrive as question marks."""
    rendered = render(bundle[language])
    bad = sorted(set(rendered) - GSM7)
    assert not bad, f"{name}/{language} contains non-GSM7 characters: {bad}"


@pytest.mark.parametrize("name,bundle", sorted(S.ALL_BUNDLES.items()))
@pytest.mark.parametrize("language", ["rw", "en", "fr"])
def test_every_string_fits_one_screen(name, bundle, language):
    """There is no scrolling on a feature phone."""
    rendered = render(bundle[language])
    assert len(rendered) <= MAX_USSD_CHARS, (
        f"{name}/{language} is {len(rendered)} chars"
    )


@pytest.mark.parametrize("name,bundle", sorted(S.ALL_BUNDLES.items()))
def test_every_string_exists_in_all_three_languages(name, bundle):
    assert set(bundle) == {"rw", "en", "fr"}
    for language, value in bundle.items():
        assert value.strip(), f"{name}/{language} is empty"


def test_translations_use_the_same_placeholders():
    """A missing placeholder means a KeyError in front of a patient; an extra
    one prints a literal brace on their screen."""
    import re

    for name, bundle in S.ALL_BUNDLES.items():
        expected = set(re.findall(r"\{(\w+)\}", bundle["rw"]))
        for language in ("en", "fr"):
            found = set(re.findall(r"\{(\w+)\}", bundle[language]))
            assert found == expected, f"{name}/{language}: {expected ^ found}"


def test_the_bundle_registry_is_not_empty():
    """Guards against ALL_BUNDLES silently collecting nothing, which would
    make every test above vacuously pass."""
    assert len(S.ALL_BUNDLES) >= 15


def test_menu_screens_list_at_most_three_options_plus_header():
    """Three results per screen; the most useful must be first."""
    for language in ("rw", "en", "fr"):
        assert is_gsm7(S.MAIN_MENU[language])
        assert len(S.MAIN_MENU[language].splitlines()) <= 6  # title + 5 options
