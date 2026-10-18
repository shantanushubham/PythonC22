"""Card networks and how to recognize them from a card number.

Open/Closed: each network is described by data (a `NetworkProfile`). To support a new
network, add a profile to the registry. `NetworkRegistry` and the services that use it
do not change.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum


class CardNetwork(str, Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    DINERS = "diners"
    AMERICAN_EXPRESS = "american_express"
    RUPAY = "rupay"


@dataclass(frozen=True)
class PrefixRange:
    """Matches card numbers whose first `digits` digits fall within `low`..`high`."""

    digits: int
    low: int
    high: int

    def matches(self, pan: str) -> bool:
        if len(pan) < self.digits:
            return False
        return self.low <= int(pan[: self.digits]) <= self.high


@dataclass(frozen=True)
class NetworkProfile:
    network: CardNetwork
    pan_lengths: tuple[int, ...]
    prefixes: tuple[PrefixRange, ...]
    cvv_length: int = 3

    def matches(self, pan: str) -> bool:
        return len(pan) in self.pan_lengths and any(
            prefix.matches(pan) for prefix in self.prefixes
        )


# RuPay ranges are the ones this mock accepts (508, 60, 65, 81, 82). Real NPCI BIN
# tables are narrower; this is enough to route test cards.
DEFAULT_PROFILES: tuple[NetworkProfile, ...] = (
    NetworkProfile(
        network=CardNetwork.VISA,
        pan_lengths=(13, 16, 19),
        prefixes=(PrefixRange(1, 4, 4),),
    ),
    NetworkProfile(
        network=CardNetwork.MASTERCARD,
        pan_lengths=(16,),
        prefixes=(PrefixRange(2, 51, 55), PrefixRange(4, 2221, 2720)),
    ),
    NetworkProfile(
        network=CardNetwork.DINERS,
        pan_lengths=(14,),
        prefixes=(PrefixRange(2, 36, 36), PrefixRange(2, 38, 39), PrefixRange(3, 300, 305)),
    ),
    NetworkProfile(
        network=CardNetwork.AMERICAN_EXPRESS,
        pan_lengths=(15,),
        prefixes=(PrefixRange(2, 34, 34), PrefixRange(2, 37, 37)),
        cvv_length=4,
    ),
    NetworkProfile(
        network=CardNetwork.RUPAY,
        pan_lengths=(16,),
        prefixes=(
            PrefixRange(3, 508, 508),
            PrefixRange(2, 60, 60),
            PrefixRange(2, 65, 65),
            PrefixRange(2, 81, 82),
        ),
    ),
)


class NetworkRegistry:
    def __init__(self, profiles: Iterable[NetworkProfile]) -> None:
        self._profiles = tuple(profiles)

    @property
    def networks(self) -> list[CardNetwork]:
        return [profile.network for profile in self._profiles]

    def identify(self, pan: str) -> NetworkProfile | None:
        """Return the profile matching a digits-only card number, or None."""
        for profile in self._profiles:
            if profile.matches(pan):
                return profile
        return None


def default_registry() -> NetworkRegistry:
    return NetworkRegistry(DEFAULT_PROFILES)
