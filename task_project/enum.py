from enum import Enum


answer = ["SUNNY", "RAINING", "CLOUDY"]
# NIGHT

my_answer: str = "Shantanu"


class PandavBrother(Enum):
    YUDHISTIRA = "Yudistira"
    BHIMA = "Bhima"
    ARJUNA = "Arjuna"
    NAKULA = "Nakula"
    SAHADEVA = "Sahadeva"


class UserRole(Enum):
    ADMIN = "Admin"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"
