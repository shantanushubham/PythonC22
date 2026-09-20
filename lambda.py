# A function contains a name, body, argument list


def add(a, b):
    return a + b


print(add(5, 6))

# A lambda is a function that doesn't necessarily have a name.
# Its body is only 1 line (In Python only)


# lambda <argument-list>: <function-body>
lambda_add = lambda a, b: a + b
print(lambda_add(7, 8))


# [1, 10, 3, 70, 11] -> [1, 3, 10, 11, 70]
# Book -> price, name
# [Book(200, "Book1"), Book(300, "Book2")] -> 
my_list: Book = []

sorted(my_list, lambda b1, b2: <how-to-compare>)
