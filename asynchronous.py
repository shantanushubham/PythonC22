# import asyncio
# import time


# async def task():
#     print("Task started")
    
#     # Blocking Waiting
#     # time.sleep(2) # The CPU core will be occupied for these 2 seconds while the execution waits for 2 seconds. If you want 
#         # other thread to take the CPU core while waiting, use threading.Thread()

#     # Non-blocking waiting
#     await asyncio.sleep(2) # The CPU core wilk be idle for these 2 seconds while the execution waits for 2 seconds. 
#         # This uses Event Loop - I will teach in sometime.

#         # It means -> Pause this coroutine until this operation is ready, and allow the event loop to run other work.
#     print("Task finished")

# asyncio.run(task())

# # Coroutine = Promise


import asyncio


async def task_1():
    for i in range(1, 6):
        await asyncio.sleep(2)
        print("Task 1:", i)


async def task_2():
    for i in range(1, 6):
        await asyncio.sleep(2)
        print("Task 2:", i)


# async def main():

# ******* PART 1 starts **********
    # This is not concurrent
    # await task_1()
    # await task_2()
# ******* PART 2 ends **********

# ******* PART 2 starts **********

    # # This is concurrent.
    # t1 = asyncio.create_task(task_1())
    # t2 = asyncio.create_task(task_2())

    # # create_task() takes a coroutine and schedules it to run concurrently on the current event loop.
    # # Calling as async function doesn't not start running ut. create_task() schedules it to run.

    # await t1
    # await t2

# ******* PART 2 ends **********

# ******* PART 3 starts **********

    # This is concurrent.
    # await asyncio.gather(task_1(), task_2())

    # Part 3 is a cleaner way to write Part 2

# ******* PART 3 ends **********


# asyncio.run(main())




# ****** EXAMPLE ******

async def download_file(name, seconds):
    print(f"Downloading {name}...")

    await asyncio.sleep(seconds)

    print(f"{name} downloaded")


async def main():
    await asyncio.gather(
        download_file("file1", 3),
        download_file("file2", 2),
        download_file("file3", 1)
    )


asyncio.run(main())

"""
Sequential:

file1 ───── 3 sec
             file2 ───── 2 sec
                         file3 ─ 1 sec
Total = 6 sec


Async:

file1 ───────────── 3 sec
file2 ─────── 2 sec
file3 ── 1 sec

Total ≈ 3 sec
"""

# **** EXAMPLE ENDS **********

