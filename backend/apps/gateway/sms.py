"""GSM-7 helpers shared by USSD and SMS.

Re-exported from apps.notifications.sms so there is one implementation and one
place to fix it. USSD and SMS ride the same networks with the same alphabet.
"""

from apps.notifications.sms import GSM7, to_gsm7


def gsm7_safe(text: str) -> str:
    return to_gsm7(text)


def is_gsm7(text: str) -> bool:
    return set(text) <= GSM7


__all__ = ["GSM7", "gsm7_safe", "is_gsm7", "to_gsm7"]
