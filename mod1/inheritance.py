# from typing import override


# class Engine:

#     NAME = "TATA"

#     def __init__(self, age):
#         self.age = age

#     def start(self):
#         print("Starting Engine")

#     def stop(self):
#         print("Stopping Engine")

#     @staticmethod
#     def hello():
#         print("Hello")

# class PEngine(Engine):
    
#     @override
#     def start(self):
#         # super().start()
#         print("Starting Pertol Engine")

#     @override
#     def stop(self):
#         print("Stopping Petrol Engine")


# class DEngine(Engine):
#     pass

# class EEngine(Engine):
    
#     @override
#     def start(self):
#         print("Starting Electric Engine")

#     @override
#     def stop(self):
#         print("Stopping Electric Engine")

# pe = PEngine()
# pe.start()
# pe.stop()

# ee = EEngine()
# ee.start()
# ee.stop()

pe = PEngine(3)
pe.start()


# class Parent1:

#     def test(self):
#         print("Parent1")

#     def test1(self):
#         print("Parent1")

# class Parent2:

#     def test(self):
#         print("Parent2")

#     def test2(self):
#         print("Parent1")

# class Child(Parent2, Parent1): 
#     pass

# c = Child()
# c.test()