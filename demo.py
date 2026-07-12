# a = 10
# b = 10
# sum = a + b
# If the sum is > 10 then print sum, otheriwse print -> Sum is less than 10

# Conditional Programming - if and else. The "if" should contain a condition that resolves into a boolean
# if sum > 15:
#     print(sum)
# elif sum > 10:
#     print("Sum is less than 0", sum)
# else:
#     print("Sum is between 0 and 10")

# Functions aka Methods
# y = f(x) | y = x * x  -> y is a function of x
# y is the dependent variable
# x is the independent variable
# f is the name of the function

# y = square(x)
# sqaure(x) = x * x
# square(4) = 16

# In Python we write:
# def <name-of-the-function>(<independent-variables>):
#   ... function-body ...

# def square(x):
#     sq = x * x
#     print("Inside ", sq)
#     return sq
#     print("After return") # Unreachable

# y = square(4)
# print("Outside ", y)

# Loop
# 1. We know the number of times we want to repeat
# FOR LOOP

# Syntax:
# for <condition>: [run the loop as long as the condition is True, this usually involves the known number]
# ... loop body ...

# for i in range(5):  # range is (start, stop, skip)
#     if i == 3:
#         continue
#     print("Shantanu ", i)

# 2. We don't know the number of times we want to repeat | this can be used when we know the no of times also
# WHILE LOOP

# i = 0
# while i < 15:
#     print("Shantanu ", i)
#     i += 1


# secret_number = 7
# guess = 0

# while guess != secret_number:
#     guess = int(input("Guess the number: "))

# print("Correct Guess")
