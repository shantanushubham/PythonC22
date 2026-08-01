"""
Abstarction is an OOP principle o fhiding implementation details and exposing only the essential functionality
to the user.

The idea is:
1. Show what an object does.
2. Hide how it does it.
"""

from abc import ABC, abstractmethod
from typing import override


class Engine(ABC):

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    def manufacturer_name(self):
        return "TATA"


class PEngine(Engine):

    def start(self):
        print("Starting Pertol Engine")

    def stop(self):
        print("Stopping Petrol Engine")


class DEngine(Engine):

    @override
    def start(self):
        print("Starting Diesel Engine")

    @override
    def stop(self):
        print("Stopping Diesel Engine")


class EEngine(Engine):

    def start(self):
        print("Starting Electric Engine")

    def stop(self):
        print("Stopping Electric Engine")


# e = Engine()
de = DEngine()
de.start()
de.stop()


"""
1. You cannot create an object of an Abstract Class.
2. An abstract class can contain functions/methods that are either:
    2.a. Abstract/Virtual
    2.b. Non-Abstarct (Normal)
"""
