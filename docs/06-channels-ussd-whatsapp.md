# 06 - USSD and WhatsApp Channels

These channels are not a nice-to-have. They are how MediLink reaches patients
without smartphones - which, in rural districts and among elderly patients, is
most of them.

**Design rule: every feature must be reachable in three USSD steps, or rural
users effectively do not have it.** Design the USSD flow *first* for any new
feature. If it cannot fit, reconsider the feature.

## 1. Start the paperwork now

The USSD shortcode is the long pole in this project, and it is administrative,
not technical.

| Task | Who | Typical lead time |
|---|---|---|
| Register a business entity | RDB | Weeks |
| Apply for a USSD shortcode | RURA + MTN / Airtel | **Months** |
| Sign an aggregator contract | Africa's Talking or equivalent | Weeks |
| Negotiate session pricing | Telco | Weeks |
| WhatsApp Business verification | Meta | 2-6 weeks |

Begin these in **Phase 0**, in parallel with development. Waiting until the code
is ready will idle the team for a quarter.

While waiting, develop against the aggregator's **sandbox**, which simulates USSD
sessions without a real shortcode.

## 2. How USSD actually works

A USSD session is a series of HTTP POSTs from the aggregator. It is **stateless
on our side**: each request carries the *entire* input path the user has typed.

```
User dials *384*12345#
  -> POST  text=""                 -> we reply "CON <main menu>"
User presses 1
  -> POST  text="1"                -> we reply "CON <district menu>"
User presses 3
  -> POST  text="1*3"              -> we reply "END <results>"
```

| Field | Meaning |
|---|---|
| `sessionId` | Unique per dial; use as the Redis key |
| `serviceCode` | The shortcode dialled |
| `phoneNumber` | E.164 - **this is the patient identity** |
| `text` | Full input path so far, `*`-separated |

Reply format is plain text:

| Prefix | Effect |
|---|---|
| `CON ` | Show text, keep the session open, await input |
| `END ` | Show text and close the session |

### Hard constraints

| Constraint | Value | Consequence |
|---|---|---|
| Characters per screen | ~160 (182 max) | Three results maximum per screen |
| Session timeout | 20-30 s per step | No slow queries, ever |
| Total session length | Often ~90 s | Under 5 steps end to end |
| Scrolling | None | Most useful item must be first |
| Character set | GSM-7 basic | **No accented characters** |
| Cost | Per session, billed to us or the user | Fewer steps is literally cheaper |

**The GSM-7 constraint bites in Kinyarwanda and French.** Write `Consultation
generale`, not `Consultation générale`. Add a sanitiser and a test that asserts
every USSD string is GSM-7 safe.

## 3. The menu tree

```
*384*12345#
|
+-- 1. Ahantu hafi (Nearby)
|     +-- district -> service -> END: 3 nearest facilities
|
+-- 2. Gutegura (Book)
|     +-- facility -> service -> day -> time -> END: reference code
|
+-- 3. Umurongo wanjye (My queue)
|     +-- END: position + ETA, or "you are not in a queue"
|
+-- 4. Ubwishingizi (Insurance)
|     +-- END: set or view your insurer
|
+-- 5. Ururimi (Language)
      +-- END: rw / en / fr
```

Option 3 is deliberately a **single step** - a patient already waiting must not
navigate a menu to learn their position.

**Returning users skip step one.** After the first session, store the patient's
district on their `Patient` row and go straight to the service menu.

## 4. Implementation

### 4.1 The view

```python
# backend/apps/gateway/views.py
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .ussd import UssdRouter, ussd_response
from .security import verify_aggregator


@csrf_exempt
@require_POST
def ussd(request):
    verify_aggregator(request)          # shared secret + IP allowlist

    session_id = request.POST["sessionId"]
    phone      = normalise_phone(request.POST["phoneNumber"])
    text       = request.POST.get("text", "")

    try:
        router = UssdRouter(session_id=session_id, phone=phone)
        reply  = router.handle(text)
    except Exception:
        logger.exception("ussd_failure", extra={"session": session_id})
        # Never return a blank screen or a 500 - the user sees a dead phone
        reply = ussd_response.end("Serivisi ntibonetse. Ongera ugerageze.")

    return HttpResponse(reply, content_type="text/plain; charset=utf-8")
```

The bare `except` is deliberate here and nowhere else. A traceback reaching the
aggregator means the patient's screen goes blank with no explanation.

### 4.2 The router

```python
# backend/apps/gateway/ussd.py
MAX_USSD_CHARS = 160


def con(text: str) -> str:
    return "CON " + gsm7(text)[:MAX_USSD_CHARS]


def end(text: str) -> str:
    return "END " + gsm7(text)[:MAX_USSD_CHARS]


class UssdRouter:
    def __init__(self, session_id: str, phone: str):
        self.session_id = session_id
        self.phone = phone
        self.patient = Patient.objects.filter(phone=phone).first()
        self.lang = self.patient.language if self.patient else "rw"

    def handle(self, text: str) -> str:
        steps = text.split("*") if text else []

        if not steps:
            return self.main_menu()

        handler = {
            "1": self.nearby,
            "2": self.book,
            "3": self.my_queue,
            "4": self.insurance,
            "5": self.language,
        }.get(steps[0])

        if handler is None:
            return end(t("invalid_choice", self.lang))
        return handler(steps[1:])

    def main_menu(self) -> str:
        return con(t("ussd_main_menu", self.lang))

    def my_queue(self, steps) -> str:
        entry = active_queue_entry(self.phone)
        if entry is None:
            return end(t("no_active_queue", self.lang))
        return end(t("queue_status", self.lang,
                     position=entry.position(),
                     minutes=entry.eta_minutes(),
                     facility=short_name(entry.facility.name)))
```

### 4.3 Session state in Redis

Anything longer than about three steps needs cached intermediate state - re-deriving
it from the `text` path becomes unreadable and slow.

```python
# backend/apps/gateway/session.py
import json
from django.core.cache import cache

TTL_SECONDS = 180        # comfortably longer than any USSD session


def get_state(session_id: str) -> dict:
    raw = cache.get(f"ussd:{session_id}")
    return json.loads(raw) if raw else {}


def set_state(session_id: str, state: dict) -> None:
    cache.set(f"ussd:{session_id}", json.dumps(state), TTL_SECONDS)
```

Typical use: the nearby flow stores the resolved district and the facility ID
list, so the booking flow can accept "2" as a facility choice without re-running
the geo query.

### 4.4 Performance

**Every USSD handler must complete in under 2 seconds.** The aggregator times out
around 20-30 seconds, but on a congested network our share of that budget is
small.

- No `select_related`-less queries in a handler.
- Cache nearby-by-district results for 60 s - a district's facility list does not
  change.
- Never call an external API inline. Queue it to Celery and reply immediately.

## 5. Nearby facilities over USSD

No GPS exists on a feature phone, so **district and sector replace coordinates**.

```python
def nearby(self, steps) -> str:
    if not steps:
        if self.patient and self.patient.district:
            return self.nearby([self.patient.district_index])   # skip a step
        return con(t("choose_district", self.lang))

    district = DISTRICTS[int(steps[0]) - 1]

    if len(steps) == 1:
        set_state(self.session_id, {"district": district})
        return con(t("choose_service", self.lang))

    service = SERVICES[int(steps[1]) - 1]
    facilities = find_nearby_by_district(
        district=district, service=service,
        insurer=self.patient.insurer_code if self.patient else None,
        limit=3,
    )
    if not facilities:
        return end(t("no_facilities", self.lang, district=district))

    lines = [
        f"{i}. {short_name(f.name)} {format_wait_ussd(f.wait)}"
        for i, f in enumerate(facilities, 1)
    ]
    return end(t("nearby_header", self.lang) + "\n" + "\n".join(lines))
```

Formatting for 160 characters is a real engineering constraint:

```python
def short_name(name: str, limit: int = 22) -> str:
    """'Kimironko Health Centre' -> 'Kimironko HC'"""
    for long, short in (("Health Centre", "HC"), ("Health Center", "HC"),
                        ("District Hospital", "DH"), ("Polyclinic", "PC"),
                        ("Health Post", "HP")):
        name = name.replace(long, short)
    return name[:limit]


def format_wait_ussd(wait) -> str:
    if wait["status"] != "available":
        return ""                      # omit entirely - never say "unknown"
    return f"- min {wait['minutes']}"
```

Omitting an unknown wait rather than printing "unknown" saves characters *and*
honours the honesty rule: absence communicates "we do not know" without spending
a word on it.

## 6. WhatsApp

WhatsApp is the middle tier: richer than USSD, cheaper to reach than a PWA
install, and already on most smartphones in Kigali.

### 6.1 Webhook verification

```python
@csrf_exempt
def whatsapp(request):
    if request.method == "GET":
        # Meta's one-time subscription handshake
        if request.GET.get("hub.verify_token") == settings.WA_VERIFY_TOKEN:
            return HttpResponse(request.GET["hub.challenge"])
        return HttpResponseForbidden()

    if not verify_signature(request):       # X-Hub-Signature-256, HMAC-SHA256
        return HttpResponseForbidden()

    handle_whatsapp_message.delay(json.loads(request.body))
    return HttpResponse(status=200)         # respond fast, always
```

**Always return 200 immediately and process in Celery.** Meta retries on
non-200 with backoff, and a slow handler produces duplicate messages.

### 6.2 Interactive messages

WhatsApp supports buttons and list pickers - use them instead of asking patients
to type numbers.

```python
def send_nearby_list(phone, facilities):
    send_whatsapp(phone, {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "header": {"type": "text", "text": "Amavuriro hafi yawe"},
            "body":   {"text": "Hitamo ivuriro:"},
            "action": {
                "button": "Reba amavuriro",
                "sections": [{
                    "title": "Hafi yawe",
                    "rows": [
                        {
                            "id": f"facility:{f.id}",
                            "title": f.name[:24],
                            "description": f"{f.distance_m/1000:.1f}km - "
                                           f"{wait_text(f.wait)}",
                        }
                        for f in facilities[:10]
                    ],
                }],
            },
        },
    })
```

WhatsApp allows accented characters and up to 4096 characters per message - the
GSM-7 and 160-character constraints do **not** apply here. Keep the messages
short anyway; a wall of text on a phone is unreadable.

### 6.3 The 24-hour window

Meta permits free-form replies only within 24 hours of the patient's last
message. Outside that window, only pre-approved **template messages** may be
sent.

This directly affects our reminders. Register these templates in advance:

| Template | Trigger |
|---|---|
| `appointment_reminder` | 24 h and 2 h before a slot |
| `queue_leave_now` | `leave_by` reached |
| `queue_called` | Receptionist pressed "Call" |
| `appointment_cancelled` | Facility cancelled |

Template approval takes days and rejections are common. Submit them during
Phase 2, not the week before launch.

## 7. SMS

SMS is the **primary notification channel** because it reaches every phone,
including patients who are out of data.

```python
# backend/apps/notifications/tasks.py
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_leave_now_sms(self, queue_entry_id):
    entry = QueueEntry.objects.select_related("patient", "facility").get(
        pk=queue_entry_id
    )
    if entry.status != QueueEntry.Status.WAITING:
        return                                     # they were already called

    try:
        Notification.objects.create(               # unique constraint = dedupe
            patient=entry.patient, channel="sms", kind="leave_now",
            queue_entry=entry,
            body=t("sms_leave_now", entry.patient.language,
                   position=entry.position(),
                   facility=short_name(entry.facility.name)),
        )
    except IntegrityError:
        return                                     # already sent - do nothing

    sms_gateway.send(entry.patient.phone, notification.body)
```

The `IntegrityError` catch is the whole duplicate-SMS defence. A Celery beat task
running every minute *will* occasionally overlap itself; the database unique
constraint, not application logic, is what guarantees a patient receives "Leave
now" exactly once.

Keep every SMS **under 160 characters** - a longer message is billed as two.

```
MediLink: Uri nomero 3 kuri Kimironko HC.
Genda ubu. Igihe: ~15 min.
```

## 8. One brain, three mouths

USSD, WhatsApp and the PWA must never contain their own business logic. They are
**presentation adapters** over the same service functions.

```
gateway/ussd.py     ──┐
gateway/whatsapp.py ──┼──> apps/*/services.py ──> models
api/views.py        ──┘
```

If booking rules live in `services.book_appointment()`, then a fix applies to all
three channels at once. If they live in a view, a USSD user and an app user get
different behaviour - and that bug will be found by a patient, at a hospital.

## 9. Channel testing

| Test | Method |
|---|---|
| USSD menu paths | Unit tests posting `text="1*3*2"` directly to the view |
| 160-character limit | Assert every generated string, in all three languages |
| GSM-7 safety | Assert no character outside the GSM-7 basic set |
| Session expiry | Simulate a state gap and assert a graceful restart, not a crash |
| Backend down | Assert `END` with a friendly message, never a blank reply |
| WhatsApp signature | Assert forged signatures return 403 |
| SMS deduplication | Fire the beat task twice concurrently; assert one row, one send |

Then test on a **real feature phone with a real SIM** before launch. Aggregator
sandboxes do not reproduce real network latency, telco character mangling, or
what an actual Nokia renders.
