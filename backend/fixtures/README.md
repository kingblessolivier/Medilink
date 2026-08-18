# Fixtures

## `insurers.json`, `service_types.json`

Reference data. Safe to load as-is. Review the Kinyarwanda service names with a
native speaker before launch - some are working translations, not established
signage wording.

## `kigali_facilities.json` - READ THIS BEFORE USING

**The coordinates in this file are approximate and every facility is loaded with
`verified_at: null`, which means none of them appear in patient search.**

They were entered from general knowledge of Kigali, not captured on site. They
are accurate enough to develop and demo against, and **not** accurate enough to
send a patient anywhere.

Phase 0 of the roadmap requires 50+ facilities whose coordinates were recorded
on site. Until a facility has been visited, do not mark it verified.

### Verification procedure

For each facility, one person physically visits and records:

1. **GPS coordinate at the main entrance.** Stand still, wait for accuracy under
   10 m, record 6 decimal places. Do not take the coordinate from a map pin.
2. **Opening hours per weekday**, including lunch closures. Read them off the
   sign; if there is no sign, ask reception and write down who said it.
3. **Insurers accepted.** Ask reception directly. Record any conditions in the
   `note` field, for example "Mutuelle for consultation only".
4. **Services offered**, matched to our `ServiceType` codes.
5. **Phone number that a patient can actually reach**, tested by calling it.
6. **Photo of the entrance** for the record.

Then in Django admin: correct the coordinate, fill in hours, services and
insurers, and use the **"Mark selected facilities as VERIFIED"** action. The
action refuses facilities with no opening hours, because a verified facility
with no hours always reads as closed.

### Load order

```bash
python manage.py loaddata fixtures/insurers.json
python manage.py loaddata fixtures/service_types.json
python manage.py loaddata fixtures/kigali_facilities.json
python manage.py seed_demo          # development only - see below
```

`seed_demo` attaches plausible hours, services and insurers to the loaded
facilities and marks them verified **so that developers see a working app**. It
prints a warning every time it runs. Never run it against production.
