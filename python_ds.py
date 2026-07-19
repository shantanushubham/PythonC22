# Tuple
# It is like a list, that is immutable.

my_tuple = (1, 2, 3, [4, 5, 6], ("Shantanu", "Shubham"))  # my_tuple = tuple()
# my_tuple[2] = [40,50,60]
print(my_tuple)


# [1][2][3][abc][def]  -> 123
#      tuple

# [4][5][6][7] -> abc

# [40][50][60] -> xyz

# ["Shantanu"]["Shubham"] -> def


# Set
my_set = {1, 2, 3, 4, 5, 6, 7, 7, 8, 9, 10}
my_set.add(10)
my_set.remove(1)
print("Set", my_set)

# Day 4
# Dictionary
# C++ -> unordered_map of object, object
# Java -> HashMap of Object, Object
# JS -> JS Object with any key type

# A dictionary is a key-value pair.
my_dict = {}
my_dict = {"shantanu": 42, "zoiba": 58, "shantanu": 100}
my_dict["utkarsh"] = 55
my_dict["zoiba"] = "AirTribe"


my_dict_items = list[tuple[str, int]](my_dict.items()) # [("shantanu", 100), ("zoiba", "AirTribe")]

for i in range(len(my_dict_items)):
    item = my_dict_items[i]
    print(f"Key: {item[0]} and Value: {item[1]}")


# print(my_dict["shantanu"])


# RAM: [][][][][["shantanu"][100]][][][][][]
#               my_dict


# Type Casting means, changing data from type A to type B without changing memory
# []["Shantanu"]   -> a: int = 100 | b = (long) a
#    b

# [][dict_itmes][]
#      123

# [][list(dict_itmes)][]
#       451