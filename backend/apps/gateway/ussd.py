"""USSD routing.

A USSD session is stateless on our side: each request carries the entire input
path the user has typed, `*`-separated. Redis holds only what would be
unreadable to re-derive - resolved district, the facility list a number refers
to, the slot list a number refers to.

Step budget per feature, counted from the main menu:

    My queue      1   deliberately - somebody already waiting must not
                      navigate a menu to learn their position
    Insurance     2
    Language      2
    Nearby        3   district -> service -> results
    Book          4   district -> service -> facility -> slot

Booking is the one feature that exceeds the three-step rule in docs/06. It
cannot be compressed further without guessing on the patient's behalf which
facility they mean, and a wrong guess sends somebody to the wrong hospital.
The rule holds for everything a patient needs in a hurry.
"""

import logging

from django.conf import settings
from django.utils import timezone

from apps.facilities.models import Facility, ServiceType
from apps.insurance.models import Insurer
from apps.patients.models import Patient, normalise_phone
from apps.queueing.models import QueueEntry
from apps.queueing.services import eta_for
from apps.scheduling.models import Appointment
from apps.scheduling.services import BookingError, available_slots, book

from . import strings as S
from .session import clear_state, get_state, set_state
from .sms import gsm7_safe

logger = logging.getLogger(__name__)

MAX_USSD_CHARS = 160
MAX_MENU_ITEMS = 3  # three results per screen; there is no scrolling

# Kigali first - most sessions come from here. A short list keeps the district
# screen inside one 160-character screen.
DISTRICTS = ["Gasabo", "Kicukiro", "Nyarugenge"]

LANGUAGE_CODES = ["rw", "en", "fr"]


def con(text: str) -> str:
    """Keep the session open."""
    return "CON " + _fit(text)


def end(text: str) -> str:
    """Show text and close the session."""
    return "END " + _fit(text)


def _fit(text: str) -> str:
    safe = gsm7_safe(text)
    if len(safe) > MAX_USSD_CHARS:
        logger.warning("ussd_truncated", extra={"length": len(safe)})
        safe = safe[:MAX_USSD_CHARS]
    return safe


def numbered(header: str, items: list[str]) -> str:
    lines = [header] + [f"{i}. {label}" for i, label in enumerate(items, 1)]
    return "\n".join(lines)


def short_name(name: str, limit: int = 20) -> str:
    """Fit a facility name on one USSD line.

    Abbreviates the common suffixes first, then trims on a WORD boundary.
    A hard slice produces "Croix du Sud Hospita" on a Nokia screen, which a
    patient has to decode rather than read.
    """
    for long, short in (
        ("Health Centre", "HC"),
        ("Health Center", "HC"),
        ("District Hospital", "DH"),
        ("Referral Hospital", "RH"),
        ("International Hospital", "Intl H"),
        ("Polyclinic", "PC"),
        ("Health Post", "HP"),
        ("Hospital", "Hosp"),
    ):
        name = name.replace(long, short)

    name = name.strip()
    if len(name) <= limit:
        return name

    trimmed = name[:limit].rsplit(" ", 1)[0].rstrip(" ,-")
    # A single very long word has no boundary to trim on; slice it rather
    # than return an empty string.
    return trimmed or name[:limit]


class UssdRouter:
    def __init__(self, session_id: str, phone: str):
        self.session_id = session_id
        self.phone = phone
        self.patient = Patient.objects.filter(phone=phone).first()
        self.lang = self.patient.language if self.patient else "rw"

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def handle(self, text: str) -> str:
        steps = [s for s in text.split("*")] if text else []

        if not steps or steps == [""]:
            return con(S.t(S.MAIN_MENU, self.lang))

        handlers = {
            "1": self.nearby,
            "2": self.booking,
            "3": self.my_queue,
            "4": self.insurance,
            "5": self.language,
        }
        handler = handlers.get(steps[0])
        if handler is None:
            return end(S.t(S.INVALID_CHOICE, self.lang))
        return handler(steps[1:])

    # ------------------------------------------------------------------
    # 3. My queue - one step, on purpose
    # ------------------------------------------------------------------

    def my_queue(self, steps) -> str:
        if self.patient is None:
            return end(S.t(S.NO_ACTIVE_QUEUE, self.lang))

        entry = (
            QueueEntry.objects.filter(
                patient=self.patient, status__in=QueueEntry.OPEN_STATUSES
            )
            .select_related("facility", "service_type")
            .order_by("-joined_at")
            .first()
        )
        if entry is None:
            return end(S.t(S.NO_ACTIVE_QUEUE, self.lang))

        facility = short_name(entry.facility.name)

        if entry.status == QueueEntry.Status.CALLED:
            return end(
                S.t(
                    S.QUEUE_CALLED,
                    self.lang,
                    ticket=entry.ticket_code,
                    facility=facility,
                )
            )

        estimate = eta_for(entry)
        if estimate["eta_minutes"] is None:
            # No reliable statistics - say so rather than invent a number.
            return end(
                S.t(
                    S.QUEUE_STATUS_NO_ETA,
                    self.lang,
                    position=estimate["position"],
                    facility=facility,
                )
            )

        return end(
            S.t(
                S.QUEUE_STATUS,
                self.lang,
                position=estimate["position"],
                facility=facility,
                minutes=estimate["eta_minutes"],
            )
        )

    # ------------------------------------------------------------------
    # 1. Nearby - district, service, results
    # ------------------------------------------------------------------

    def nearby(self, steps) -> str:
        district, steps, outcome = self._resolve_district(steps)
        if outcome == self.DISTRICT_INVALID:
            return end(S.t(S.INVALID_CHOICE, self.lang))
        if outcome == self.DISTRICT_ASK:
            return con(numbered(S.t(S.CHOOSE_DISTRICT, self.lang), DISTRICTS))

        if not steps:
            return self._service_menu()

        service = self._service_from(steps[0])
        if service is None:
            return end(S.t(S.INVALID_CHOICE, self.lang))

        facilities = self._facilities_in(district, service)
        if not facilities:
            return end(S.t(S.NO_FACILITIES, self.lang, district=district))

        lines = [
            f"{short_name(f.name)}{self._wait_suffix(f, service)}"
            for f in facilities
        ]
        return end(numbered(S.t(S.NEARBY_HEADER, self.lang), lines))

    def _wait_suffix(self, facility, service) -> str:
        """Omit an unknown wait entirely.

        Absence says "we do not know" without spending characters on it, and
        without implying a number we cannot stand behind.
        """
        from apps.facilities.wait import STATUS_AVAILABLE, wait_snapshot

        snapshot = wait_snapshot([facility], service_code=service.code)
        wait = snapshot.get(facility.id, {})
        if wait.get("status") != STATUS_AVAILABLE:
            return ""
        return f" {wait['minutes']}min"

    # ------------------------------------------------------------------
    # 2. Book - district, service, facility, slot
    # ------------------------------------------------------------------

    def booking(self, steps) -> str:
        if self.patient is None:
            return end(S.t(S.SIGN_IN_FIRST, self.lang))

        district, steps, outcome = self._resolve_district(steps)
        if outcome == self.DISTRICT_INVALID:
            return end(S.t(S.INVALID_CHOICE, self.lang))
        if outcome == self.DISTRICT_ASK:
            return con(numbered(S.t(S.CHOOSE_DISTRICT, self.lang), DISTRICTS))

        if not steps:
            return self._service_menu()

        service = self._service_from(steps[0])
        if service is None:
            return end(S.t(S.INVALID_CHOICE, self.lang))

        facilities = self._facilities_in(district, service)
        if not facilities:
            return end(S.t(S.NO_FACILITIES, self.lang, district=district))

        if len(steps) == 1:
            set_state(
                self.session_id,
                {"facilities": [f.id for f in facilities], "service": service.code},
            )
            return con(
                numbered(
                    S.t(S.CHOOSE_FACILITY, self.lang),
                    [short_name(f.name) for f in facilities],
                )
            )

        state = get_state(self.session_id)
        if not state.get("facilities"):
            return end(S.t(S.SESSION_EXPIRED, self.lang))

        facility = self._pick(Facility, state["facilities"], steps[1])
        if facility is None:
            return end(S.t(S.INVALID_CHOICE, self.lang))

        days = available_slots(facility=facility, service_type=service)
        slots = [s for day in days for s in day["slots"] if s["remaining"] > 0]
        slots = slots[:MAX_MENU_ITEMS]
        if not slots:
            return end(S.t(S.NO_SLOTS, self.lang))

        if len(steps) == 2:
            state["slots"] = [s["start"].isoformat() for s in slots]
            state["facility"] = facility.id
            set_state(self.session_id, state)
            labels = [
                timezone.localtime(s["start"]).strftime("%a %H:%M") for s in slots
            ]
            return con(numbered(S.t(S.CHOOSE_SLOT, self.lang), labels))

        return self._confirm_booking(state, facility, service, steps[2])

    def _confirm_booking(self, state, facility, service, choice) -> str:
        from datetime import datetime

        stored = state.get("slots") or []
        index = self._index(choice, len(stored))
        if index is None:
            return end(S.t(S.INVALID_CHOICE, self.lang))

        slot_start = datetime.fromisoformat(stored[index])

        try:
            appointment = book(
                facility=facility,
                service_type=service,
                patient=self.patient,
                slot_start=slot_start,
                booked_via=Appointment.BookedVia.USSD,
            )
        except BookingError as exc:
            return end(S.t(S.BOOKING_FAILED, self.lang, reason=str(exc)[:80]))
        finally:
            clear_state(self.session_id)

        return end(
            S.t(
                S.BOOKED,
                self.lang,
                reference=appointment.reference,
                facility=short_name(facility.name),
                time=timezone.localtime(appointment.slot_start).strftime("%a %H:%M"),
            )
        )

    # ------------------------------------------------------------------
    # 4. Insurance and 5. Language
    # ------------------------------------------------------------------

    def insurance(self, steps) -> str:
        insurers = list(Insurer.objects.all()[:5])
        if not steps:
            return con(
                numbered(
                    S.t(S.CHOOSE_INSURER, self.lang), [i.name for i in insurers]
                )
            )

        index = self._index(steps[0], len(insurers))
        if index is None:
            return end(S.t(S.INVALID_CHOICE, self.lang))

        insurer = insurers[index]
        patient = self._ensure_patient()
        patient.insurer = insurer
        patient.save(update_fields=["insurer"])
        return end(S.t(S.INSURER_SAVED, self.lang, insurer=insurer.name))

    def language(self, steps) -> str:
        if not steps:
            return con(S.t(S.CHOOSE_LANGUAGE, self.lang))

        index = self._index(steps[0], len(LANGUAGE_CODES))
        if index is None:
            return end(S.t(S.INVALID_CHOICE, self.lang))

        self.lang = LANGUAGE_CODES[index]
        patient = self._ensure_patient()
        patient.language = self.lang
        patient.save(update_fields=["language"])
        return end(S.t(S.LANGUAGE_SAVED, self.lang))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _ensure_patient(self) -> Patient:
        """A USSD caller is identified by their phone number, so a session is
        enough to create the row."""
        if self.patient is None:
            self.patient, _ = Patient.objects.get_or_create(
                phone=normalise_phone(self.phone)
            )
        return self.patient

    # District resolution outcomes.
    DISTRICT_OK = "ok"
    DISTRICT_ASK = "ask"
    DISTRICT_INVALID = "invalid"

    def _resolve_district(self, steps):
        """Returning users skip the district screen entirely.

        Returns (district, remaining_steps, outcome).

        An invalid choice must be reported as INVALID, not silently re-prompted.
        USSD input is append-only: the bad digit stays in `text` forever, so
        re-showing the menu would read the same bad digit again on the next
        request and trap the caller in a loop they cannot escape without
        redialling.
        """
        if self.patient and self.patient.district:
            return self.patient.district, steps, self.DISTRICT_OK

        if not steps:
            return None, steps, self.DISTRICT_ASK

        index = self._index(steps[0], len(DISTRICTS))
        if index is None:
            return None, steps, self.DISTRICT_INVALID

        district = DISTRICTS[index]
        if self.patient:
            self.patient.district = district
            self.patient.save(update_fields=["district"])
        return district, steps[1:], self.DISTRICT_OK

    def _service_menu(self) -> str:
        services = self._services()
        labels = [getattr(s, f"name_{self.lang}", s.name_en) for s in services]
        return con(numbered(S.t(S.CHOOSE_SERVICE, self.lang), labels))

    def _services(self):
        return list(ServiceType.objects.order_by("sort_order")[:MAX_MENU_ITEMS])

    def _service_from(self, choice):
        services = self._services()
        index = self._index(choice, len(services))
        return services[index] if index is not None else None

    def _facilities_in(self, district, service):
        return list(
            Facility.objects.filter(
                verified_at__isnull=False,
                district=district,
                services__service_type=service,
                services__available=True,
            ).distinct()[:MAX_MENU_ITEMS]
        )

    @staticmethod
    def _index(choice: str, length: int) -> int | None:
        """Menu choices are 1-based and typed by hand on a numeric keypad."""
        if not choice.isdigit():
            return None
        index = int(choice) - 1
        return index if 0 <= index < length else None

    def _pick(self, model, ids, choice):
        index = self._index(choice, len(ids))
        if index is None:
            return None
        return model.objects.filter(pk=ids[index]).first()


def ussd_settings_ok() -> bool:
    """True when a real aggregator is configured."""
    return bool(getattr(settings, "USSD_SHARED_SECRET", ""))
