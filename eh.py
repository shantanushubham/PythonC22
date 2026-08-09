# # Exception Handling

# # def drive_to_agra():
# # some code to reach Agra
# # if flat type
# # change tyre


# import datetime


# class AirtribeException(Exception):

#     def __init__(self, message) -> None:
#         self.message = message
#         self.time = datetime.datetime.now()


# # # Situation 1 - we want to handle the exception
# # def test_func(a, b):
# #     try:
# #         if a < b:
# #             raise AirtribeException("a is less than b")
# #     except AirtribeException:
# #         print("Handling Airtribe Exception")


# # Situation 2 - we don't want to handle the exception

# def test_func(a, b):
#     """Compare two values and raise if the first is less than the second.

#     Args:
#         a: First value to compare.
#         b: Second value to compare.

#     Raises:
#         AirtribeException: If a is less than b.
#     """
#     if a < b:
#         raise AirtribeException("a is less than b")


# def hello(a, b):
#     try:
#         test_func(a, b)
#     except AirtribeException | ZeroDivisionError as e:
#         print(f"{e.message} - {e.time}")


# hello(-10, 5)
# print("End of Program")


class MyException(Exception):
    pass


class ShantanuException(MyException):
    pass


class AshishException(MyException):
    pass


def test_function(a):
    if a < 0:
        raise ShantanuException()
    if a > 0:
        raise AshishException()
    print(a)


def caller(a):
    try:
        test_function(a)
    # except (ShantanuException, AshishException) as e:
    #     print("Shantanu or Ashish Exception occurred")
    except MyException as e:
        print("Shantanu or Ashish Exception occurred")


caller(10)
caller(-10)
