# Negative Indexing
nums = [10, 20, 30, 40, 50]
print(nums[-1])
print(nums[-2])
print(nums[-3])

# Slicing
# Pythin supports slicing using syntax:
# list[start:stop:step] -> start - I | stop - E | step = 1 (by default)
test = nums[:]
print("Slicing: ", test)


# [10][20][30][40][50] -> 123
#       nums

# [10][20][30][40][50] -> 456
#       test

nums[1:4] = [200, 300]
print(nums)
