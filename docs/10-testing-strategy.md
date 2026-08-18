# 10 - Testing Strategy

## 1. What actually breaks in this system

Test effort should follow risk, not code volume. In MediLink the dangerous
failures are:

| Failure | Consequence |
|---|---|
| Coordinate order swapped | Every distance wrong, silently. Whole product useless |
| Wait time shown when data is insufficient | Trust destroyed permanently |
| Queue position wrong | Patient arrives at the wrong time |
| Facility scoping missing on one endpoint | Cross-clinic patient data leak |
| Duplicate "Leave now" SMS | Patient spam, wasted money, lost credibility |
| USSD handler raises | Blank screen on a feature phone |
| Offline check-in lost on reconnect | Patients lose their place in the queue |

Everything below targets that list.

## 2. Layers

| Layer | Tool | Share of effort |
|---|---|---|
| Unit - services, calculations | pytest | 50% |
| Integration - API endpoints | pytest + DRF test client | 30% |
| Contract - schema vs. client | drf-spectacular + openapi-typescript diff | 5% |
| Frontend component | Vitest + Testing Library | 10% |
| End-to-end, happy paths only | Playwright | 5% |
| Field testing | Humans, real devices | **Not optional** |

Keep end-to-end coverage deliberately thin. E2E tests are slow and flaky; they
earn their place on two or three critical journeys, not as a substitute for
service-level tests.

## 3. Geo tests - the highest-value tests in the project

```python
# backend/apps/facilities/tests/test_geo.py
import pytest
from django.contrib.gis.geos import Point
from apps.facilities.services import find_nearby

KIGALI_CONVENTION_CENTRE = (-1.9536, 30.0606)


@pytest.mark.django_db
def test_point_argument_order_is_lng_lat(facility_factory):
    """Guards the silent bug that breaks the entire product."""
    remera = facility_factory(location=Point(30.1122, -1.9481, srid=4326))

    lat, lng = KIGALI_CONVENTION_CENTRE
    results, _, _ = find_nearby(lat=lat, lng=lng, radius_m=10_000)

    match = next(f for f in results if f.id == remera.id)
    # Known real-world separation is roughly 5.8 km
    assert 5_000 < match.distance.m < 6_500


@pytest.mark.django_db
def test_radius_is_metres_not_degrees(facility_factory):
    """If the field is geometry rather than geography, this fails."""
    facility_factory(location=Point(29.7370, -2.0736, srid=4326))   # Muhanga

    lat, lng = KIGALI_CONVENTION_CENTRE
    results, _, _ = find_nearby(lat=lat, lng=lng, radius_m=5_000)

    assert results == []      # ~40 km away, must not appear in a 5 km radius


@pytest.mark.django_db
def test_radius_expands_when_results_are_sparse(facility_factory):
    facility_factory(location=Point(30.20, -1.90, srid=4326))   # ~12 km away

    lat, lng = KIGALI_CONVENTION_CENTRE
    results, radius, expanded = find_nearby(lat=lat, lng=lng, radius_m=5_000)

    assert expanded is True
    assert radius >= 10_000
    assert len(results) == 1


@pytest.mark.django_db
def test_nearby_uses_the_spatial_index(django_assert_num_queries, facility_factory):
    facility_factory.create_batch(50)
    lat, lng = KIGALI_CONVENTION_CENTRE

    with django_assert_num_queries(3):        # facilities + insurers + services
        find_nearby(lat=lat, lng=lng, radius_m=5_000)
```

That last test is the N+1 guard. Without it, someone adds an innocent-looking
`facility.insurers.all()` inside a serializer loop and the endpoint quietly
becomes 60 queries.

**Also verify the query plan by hand once per release:**

```sql
EXPLAIN ANALYZE
SELECT id, ST_Distance(location, ST_MakePoint(30.0606, -1.9536)::geography)
FROM facilities_facility
WHERE ST_DWithin(location, ST_MakePoint(30.0606, -1.9536)::geography, 5000);
```

The plan must contain `Index Scan using facility_location_gist`. If it says
`Seq Scan`, the index is missing or the query is not sargable.

## 4. The honesty rule, enforced by tests

```python
@pytest.mark.django_db
def test_wait_is_hidden_below_minimum_sample_size(facility_factory, stat_factory):
    facility = facility_factory(reports_queue=True)
    stat_factory(facility=facility, sample_size=19)      # one below the gate

    snapshot = wait_snapshot([facility.id])

    assert snapshot[facility.id]["status"] == "insufficient_data"
    assert snapshot[facility.id]["minutes"] is None


@pytest.mark.django_db
def test_wait_is_not_reported_for_facilities_without_the_tool(facility_factory):
    facility = facility_factory(reports_queue=False)
    assert wait_snapshot([facility.id])[facility.id]["status"] == "not_reported"
```

And on the frontend, all four states must render:

```tsx
describe("WaitLine", () => {
  it.each([
    ["available",         "About 40 min"],
    ["not_reported",      "Wait time not available"],
    ["insufficient_data", "Wait time not available"],
    ["closed",            "Closed"],
  ])("renders %s", (status, expected) => {
    render(<WaitLine wait={{ status, minutes: 43 }} />)
    expect(screen.getByText(new RegExp(expected, "i"))).toBeInTheDocument()
  })
})
```

Note the `available` case asserts "About 40 min" from an input of 43 - the
rounding rule is part of the contract, not cosmetic.

## 5. Queue correctness

```python
@pytest.mark.django_db
def test_position_counts_only_waiting_entries_ahead(queue_entry_factory, facility):
    a = queue_entry_factory(facility=facility, joined_at=t("09:00"))
    b = queue_entry_factory(facility=facility, joined_at=t("09:10"))
    c = queue_entry_factory(facility=facility, joined_at=t("09:20"))

    assert c.position() == 3

    a.status = QueueEntry.Status.SERVED
    a.save()

    assert c.position() == 2        # served patients no longer count


@pytest.mark.django_db
def test_position_is_scoped_per_service(queue_entry_factory, facility,
                                        general, maternity):
    queue_entry_factory(facility=facility, service_type=general)
    entry = queue_entry_factory(facility=facility, service_type=maternity)

    assert entry.position() == 1    # separate queues, separate positions


@pytest.mark.django_db
def test_check_in_is_idempotent(api_client, staff_user):
    api_client.force_authenticate(staff_user)
    payload = {"service": "general_consultation", "phone": "+250788123456"}
    headers = {"HTTP_IDEMPOTENCY_KEY": "abc-123"}

    first  = api_client.post("/api/v1/queue/entries", payload, **headers)
    second = api_client.post("/api/v1/queue/entries", payload, **headers)

    assert first.data["id"] == second.data["id"]
    assert QueueEntry.objects.count() == 1
```

## 6. Facility scoping - the leak test

Run this against **every** staff endpoint. Parametrise it so a newly added
endpoint that is not covered is obvious in review.

```python
STAFF_ENDPOINTS = [
    ("get",  "/api/v1/queue/board"),
    ("get",  "/api/v1/queue/entries/{entry_id}"),
    ("post", "/api/v1/queue/entries/{entry_id}/call"),
    ("post", "/api/v1/queue/entries/{entry_id}/serve"),
    ("post", "/api/v1/queue/entries/{entry_id}/skip"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("method,path", STAFF_ENDPOINTS)
def test_staff_cannot_reach_another_facility(api_client, method, path,
                                             staff_at_a, entry_at_b):
    api_client.force_authenticate(staff_at_a.user)
    response = getattr(api_client, method)(path.format(entry_id=entry_at_b.id))
    assert response.status_code in (403, 404)
```

## 7. Notification deduplication

```python
@pytest.mark.django_db(transaction=True)
def test_leave_now_sms_sent_only_once(queue_entry, mock_sms):
    send_leave_now_sms(queue_entry.id)
    send_leave_now_sms(queue_entry.id)       # simulates overlapping beat runs

    assert mock_sms.send.call_count == 1
    assert Notification.objects.filter(
        queue_entry=queue_entry, kind="leave_now"
    ).count() == 1
```

`transaction=True` matters: the defence is a database unique constraint, and
constraints are not exercised inside the default rolled-back test transaction.

## 8. USSD tests

```python
@pytest.mark.django_db
@pytest.mark.parametrize("text,expected_prefix", [
    ("",       "CON"),      # main menu
    ("1",      "CON"),      # district menu
    ("1*2",    "CON"),      # service menu
    ("1*2*1",  "END"),      # results
    ("3",      "END"),      # my queue - one step
    ("9",      "END"),      # invalid choice, handled gracefully
])
def test_ussd_paths(client, text, expected_prefix):
    response = client.post("/api/v1/gateway/ussd", {
        "sessionId": "s1", "phoneNumber": "+250788123456",
        "serviceCode": "*384*1#", "text": text,
    })
    assert response.status_code == 200
    assert response.content.decode().startswith(expected_prefix)


@pytest.mark.django_db
def test_ussd_never_returns_blank_on_backend_failure(client, monkeypatch):
    monkeypatch.setattr(UssdRouter, "handle",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError()))

    response = client.post("/api/v1/gateway/ussd", {
        "sessionId": "s1", "phoneNumber": "+250788123456", "text": "",
    })
    body = response.content.decode()
    assert response.status_code == 200
    assert body.startswith("END")
    assert len(body) > 4
```

### Character-set and length tests

```python
GSM7 = set("@£$¥èéùìòÇØøÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
           "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà\n\r")


@pytest.mark.parametrize("lang", ["rw", "en", "fr"])
def test_all_ussd_strings_are_gsm7_and_short(lang):
    for key, value in load_ussd_strings(lang).items():
        assert set(value) <= GSM7, f"{lang}.{key} contains non-GSM7 characters"
        assert len(value) <= 160,  f"{lang}.{key} is {len(value)} chars"
```

This is the test that catches `générale` before a telco turns it into `g?n?rale`
on a patient's phone.

## 9. Frontend tests worth writing

| Test | Why |
|---|---|
| Home renders state A / B / C from `GET /queue/current` | The core screen logic |
| Geolocation denied reaches the district picker | Most common real-world path |
| Out-of-bounds coordinate does not call the API | Prevents a 400 loop |
| Offline shows cached results with a timestamp | Honesty under degradation |
| Queue view never renders cached data | A stale position is actively harmful |
| Kinyarwanda strings do not overflow their containers | Layout survives 1.4x expansion |

## 10. Performance tests

```python
@pytest.mark.django_db
def test_nearby_stays_fast_with_realistic_data(facility_factory, benchmark):
    facility_factory.create_batch(500)      # roughly all of Kigali
    lat, lng = KIGALI_CONVENTION_CENTRE

    result = benchmark(lambda: find_nearby(lat=lat, lng=lng, radius_m=5_000))
    assert benchmark.stats["mean"] < 0.15   # 150 ms p50 target from doc 04
```

Frontend budget, enforced in CI:

```json
{ "bundlesize": [{ "path": "dist/assets/index-*.js", "maxSize": "150 kB" }] }
```

## 11. Field testing - the tests that matter most

None of the above proves the product works. These do:

| Test | Method | Gate |
|---|---|---|
| Real device, real network | Low-end Android on 3G, not the emulator | Phase 0 |
| Real feature phone | Actual Nokia, real SIM, both MTN and Airtel | Phase 3 |
| Reception stopwatch test | Time 20 real check-ins with a stopwatch | Phase 1 |
| Unplug test | Disconnect the network mid-shift; verify nothing is lost | Phase 1 |
| Sunlight test | Read the screen outdoors at midday | Phase 0 |
| Elderly user test | Someone over 65 completes a search unaided | Phase 0 |
| Kinyarwanda review | A native speaker reviews every string | Every phase |

The elderly user test regularly finds more real problems than the entire
automated suite. Do it early and repeat it.

## 12. CI pipeline

```yaml
# .github/workflows/ci.yml (outline)
jobs:
  backend:
    services:
      postgres: { image: postgis/postgis:16-3.4 }
      redis:    { image: redis:7-alpine }
    steps:
      - ruff check .
      - python manage.py makemigrations --check --dry-run   # no missing migrations
      - pytest --cov=apps --cov-fail-under=70
      - pip-audit

  schema:
    steps:
      - python manage.py spectacular --file schema.yaml
      - git diff --exit-code schema.yaml    # committed schema must be current

  frontend:
    steps:
      - npm ci
      - npm run gen:api && git diff --exit-code src/api/types.ts
      - npm run lint
      - npm run test
      - npm run build && npx bundlesize
      - npm audit --audit-level=high
```

The two `git diff --exit-code` steps are what keep the API contract honest: a
backend change that alters the schema fails the build until the generated client
is regenerated and committed.

## 13. Coverage targets

| Area | Target | Rationale |
|---|---|---|
| `apps/facilities/services.py` | 95% | Geo logic is silent when wrong |
| `apps/queueing/services.py` | 95% | Position and ETA are the product |
| `apps/gateway/` | 90% | A crash means a blank phone screen |
| Serializers and views | 80% | |
| Admin, migrations | Not measured | |
| Overall | 70% floor in CI | |

Coverage is a floor, not a goal. A 95%-covered geo module with no
coordinate-order test is worse than a 70%-covered one that has it.
