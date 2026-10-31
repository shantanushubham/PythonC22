def count_upto(max_num):
    print("Starting to count")
    current_value = 1
    while current_value <= max_num:
        yield current_value
        current_value += 1
    print("Done counting")

counter = count_upto(5)
print(next(counter))
print(next(counter))
print(next(counter))
print(next(counter))
print(next(counter))
