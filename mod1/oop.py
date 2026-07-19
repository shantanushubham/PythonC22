# Object Oriented Programming

# Class

# For tea, we need to decide the following:
# 1. Type of Tea -> [MILK, LEMON, GREEN, BLACK]
# 2. Contains Ginger -> True/False
# 3. Contains Sugar -> True/False
# 4. Contains Other Spices -> True/False
# 5. Size -> Tall/Grande/Venti

# Object


class Tea:

    # In Python a constructor is represented by the "__init__" method
    # "this" of other languages = "self" of Python

    def __init__(
        self,
        tea_type,
        contains_ginger,
        contains_sugar,
        contains_other_spices,
        size
    ):
        self.tea_type = tea_type
        self.contains_ginger = contains_ginger
        self.contains_sugar = contains_sugar
        self.contains_other_spices = contains_other_spices
        self.size = size


brahmesh_tea = Tea("MILK", True, True, False, "Grande")
basant_tea = Tea("LEMON", True, False, False, "Venti")
print(brahmesh_tea.tea_type)
print(basant_tea.tea_type)


####### JAVA
# public static void main(String[] args) {
# //        I need to create an object of Tea
# //        In Java, if we want to create an object of a class, we use "new <ClassName>()"

#         Tea brahmeshTea = new Tea(
#                 "MILK",
#                 true,
#                 true,
#                 false,
#                 "Grande");

#         Tea basantTea = new Tea(
#                 "LEMON",
#                 true,
#                 false,
#                 false);

#         System.out.println(brahmeshTea.teaType);
#     }