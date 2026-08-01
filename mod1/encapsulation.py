"""
Encapsulation is an OOP principle of bundling data (attributes) and methods that operate on that data
into a single class, while restricting direct access to the internal state of the object.

The goal is:
1. Protect an object's data.
2. Control how data is accessed and modified.
3. Hide implementation details from the outside world.
"""

# # Example without Encapuslation
# class BankAccount:

#     def __init__(self, balance) -> None:
#         self.balance = balance

# account = BankAccount(1000)
# account.balance = -5000
# print(account.balance)

# Encapuslation using Methods
# class BankAccount:

#     def __init__(self, balance) -> None:
#         self.balance = balance

#     def deposit(self, amount):
#         self.balance += amount

#     def withdraw(self, amount):
#         if amount <= self.balance:
#             self.balance -= amount
#         else:
#             print("Insufficient Balance")


# account = BankAccount(1000)
# account.deposit(500)
# account.withdraw(300)
# account.balance = -5000
# print(account.balance)


# Access Modification
# 1. Public members (accessible from everywhere)
# 2. Protected Members [_] (marked for internal use only) [CONVENTION]
# 3. Private Members [__] (cannot be accessed outside the class)
class Student:

    def __init__(self) -> None:
        self.name = "Alice"
        self._marks = 95
        self.__parent_number = "1234567890"

    def get_parent_number(self):
        return self.__parent_number

    def set_parent_number(self, parent_number):
        self.__parent_number = parent_number


s = Student()
print(s._Student__parent_number) # It works but is discouraged!!!
print(s.get_parent_number())
