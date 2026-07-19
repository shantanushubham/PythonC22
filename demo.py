# List as an Array

my_list = [3,4,5] # my_list = list()
print(my_list[2])

my_list.append(6)
print(my_list[3])


# from collections import deque

# List as a Stack
# push -> add | pop -> remove
my_stack = []
my_stack.append(10)
my_stack.append(20)
# Removing an element of stack = Removing the last added element // [10, 20, 30, 40, 50] -> my_stack[4] X
# print(my_stack[-2])
my_stack.pop()
print(my_stack)


# List as a Queue
# enqueue/offer -> add | dequeue -> remove
queue = []

queue.append(10)
queue.append(20)

item = queue.pop(0)
print(queue)

l1 = [1,2,3,4,5]
l2 = [6,7,8,9,10]
l1.extend(l2)