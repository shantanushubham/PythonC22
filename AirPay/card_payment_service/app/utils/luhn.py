"""The Luhn (mod 10) check that card numbers use."""


def luhn_valid(pan: str) -> bool:
    """True when the digits-only card number passes. The last digit is the check digit."""
    total = 0
    for index, character in enumerate(reversed(pan)):
        digit = int(character)
        if index % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def luhn_check_digit(payload: str) -> str:
    """The check digit that makes `payload + digit` pass the Luhn test."""
    total = 0
    for index, character in enumerate(reversed(payload)):
        digit = int(character)
        if index % 2 == 0:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - (total % 10)) % 10)
