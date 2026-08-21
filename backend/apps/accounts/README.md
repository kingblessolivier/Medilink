# Unified sign-in

One form, three kinds of user, one place that decides which is which.

The three surfaces used to have three sign-ins: patients through a phone and an
SMS code, facility staff and platform admins through `/auth/token`. Merging the
clients into one app means merging the doors too - a receptionist and a patient
may well share a browser, and "which login page do I open?" is not a question
either of them should have to answer.

## What did NOT change

**Patient tokens are still not Django users.** `PatientPrincipal` has no
`staffmember` attribute, so it cannot satisfy `IsFacilityStaff` no matter what
a view forgets to check. That structural separation is what makes the
facility-scoping model in docs/08 hold, and unifying the *form* must not
unify the *principals*.

**OTP still works.** USSD and WhatsApp callers have a phone and no password,
and always will - a feature phone is not going to hold one. Password sign-in
is additive: it is how the web works, not a replacement for how the phone
works. It is also the recovery path when somebody forgets their password.

## Order of attempts

Staff first, then patient. Both failures return the identical message, so the
endpoint cannot be used to discover which usernames exist.
