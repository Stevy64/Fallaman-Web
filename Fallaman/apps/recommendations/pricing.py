"""Tarification durée → montant FCFA (avec remise volume)."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


@dataclass(frozen=True)
class PriceQuote:
    kind: str
    duration_days: int
    daily_rate: int
    discount_percent: int
    amount: int
    label: str

    @property
    def savings(self) -> int:
        gross = self.daily_rate * self.duration_days
        return max(0, gross - self.amount)


def available_durations() -> list[int]:
    return list(getattr(settings, "RECO_DURATION_DAYS", [1, 3, 7, 14]))


def daily_rate_for(kind: str) -> int:
    if kind == "profile":
        return int(getattr(settings, "RECO_PROFILE_DAILY_RATE", 400))
    return int(getattr(settings, "RECO_LISTING_DAILY_RATE", 500))


def discount_percent_for(duration_days: int) -> int:
    table = getattr(
        settings,
        "RECO_DURATION_DISCOUNTS",
        {1: 0, 3: 5, 7: 12, 14: 20},
    )
    # settings may store string keys from env — normalize
    normalized = {int(k): int(v) for k, v in dict(table).items()}
    return int(normalized.get(int(duration_days), 0))


def quote(kind: str, duration_days: int) -> PriceQuote:
    days = int(duration_days)
    if days not in available_durations():
        raise ValueError("Durée non disponible")
    rate = daily_rate_for(kind)
    discount = discount_percent_for(days)
    gross = rate * days
    amount = int(round(gross * (100 - discount) / 100))
    amount = max(amount, 100)
    labels = {
        1: "24 heures",
        3: "3 jours",
        7: "7 jours",
        14: "14 jours",
    }
    return PriceQuote(
        kind=kind,
        duration_days=days,
        daily_rate=rate,
        discount_percent=discount,
        amount=amount,
        label=labels.get(days, f"{days} jours"),
    )


def quote_catalog(kind: str) -> list[PriceQuote]:
    return [quote(kind, days) for days in available_durations()]
