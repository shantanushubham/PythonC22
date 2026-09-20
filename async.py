import threading
import time

arr = [1]
def thread_1():
    for i in range(1, 6):
        time.sleep(2)
        arr[0] +=1
        print("Thread 1:", i)

def thread_2():
    for i in range(1, 6):
        time.sleep(2)
        arr[0] +=2
        print("Thread 2:", i)

def main():
    print("Hello World")

    # GIL - Global Interpreter Lock
    t1 = threading.Thread(target=thread_1)
    t2 = threading.Thread(target=thread_2)

    t1.start()
    t2.start()

    print(arr[0])

    t1.join()
    t2.join()

    print(arr[0])

main()