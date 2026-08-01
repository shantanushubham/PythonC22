# a = "Shantanu"
# b = "Shubham"

# c = a + b

# print(c)

# + -> Add
# + -> Join / Concat


# class Dog:
#     def sound(self):
#         print("Bark")


# class Cat:
#     def sound(self):
#         print("Meow")


# class Cow:
#     def sound(self):
#         print("Moo")


# def animal_sound(animal):
#     animal.sound()


# dog = Dog()
# cat = Cat()
# cow = Cow()

# animal_sound(dog)
# animal_sound(cat)
# animal_sound(cow)


# def add_numbers(a, b):
#     return a + b

def add_numbers(a, b, c=0):
    return a + b + c

print(add_numbers(5, 6))
print(add_numbers(5, 6, 10))

class Employee:
    
    def details(self, name, age=None):
        if age is not None:
            print(f"The name is: {name}, and age is: {age}")
        else:
            print(f"The name is: {name}")

e = Employee()
e.details("Aryan")
e.details("Aryan", 25)

# There are 2 types of Polymorphism:
# 1. Runtime Polymorphism - Function Overriding
# 2. Compiletime Polymorphism - Function Overloading

