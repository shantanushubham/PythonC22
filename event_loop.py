# An event loop is something that keeps checking which async task can progress,
# and runs those tasks whenever they are ready.

import asyncio


# ********* EXAMPLE 1 *************
# async def task():
#     print("Task started")
#     await asyncio.sleep(2)  # await keyword gives control back to the event loop
#     print("Task finished")


# # asyncio.run(task())
# loop = asyncio.new_event_loop()  # Us creating a new event-loop

# try:
#     loop.run_until_complete(task())
# finally:
#     loop.close()


# """
# asyncio.run()
#      ↓
# creates Event Loop
#      ↓
# runs task()
#      ↓
# task reaches await asyncio.sleep(2)
#      ↓
# task pauses
#      ↓
# event loop waits
#      ↓
# 2 seconds later
#      ↓
# task resumes
# """


# ********* EXAMPLE 1 *************


# ********* EXAMPLE 2 *************
# async def task_1():
#     print("Task 1 started")
#     await asyncio.sleep(2)
#     print("Task 1 finished")


# async def task_2():
#     print("Task 2 started")
#     await asyncio.sleep(2)
#     print("Task 2 finished")


# async def main():
#     t1 = asyncio.create_task(task_1())
#     t2 = asyncio.create_task(task_2())

#     await t1
#     await t2


# asyncio.run(main())

# """
# Time →

# Task 1:  START ── await sleep ─────────────── RESUME ── FINISH
#                          │
#                          │
# Task 2:             START ── await sleep ───────────── RESUME ── FINISH
#                          │
#                          │
#                     Event Loop

# Task 1 → await → "I'm waiting"

# Event Loop:
#     "Task 1 is waiting.
#      Let me run Task 2."

# Task 2 → await → "I'm waiting"

# Event Loop:
#     "Both are waiting.
#      I'll wait for whichever becomes ready."

# 2 seconds later:

# Task 1 → ready
# Task 2 → ready

# Event Loop → runs them
# """

# ********* EXAMPLE 2 *************


# ********* EXAMPLE 3 *************
import time


async def task(name, seconds):
    print(f"{name} started")
    await asyncio.sleep(seconds)
    # await != Stop the program
    # await = Pause this coroutine and give the event loop an opportunity to run something else
    print(f"{name} finished")


async def main():
    start = time.perf_counter()
    await asyncio.gather(task("Task 1", 3), task("Task 2", 2), task("Task 3", 1))
    print(f"Total time: {time.perf_counter() - start:.2f}s")


asyncio.run(main())

"""
                   ┌───────────────────────┐
                   │       EVENT LOOP      │
                   │                       │
                   │   "Who can run now?"  │
                   └───────────┬───────────┘
                               │
              ┌────────────────┼────────────────┐
              ↓                ↓                ↓
           Task 1           Task 2           Task 3
              │                │                │
          await I/O        await I/O        await I/O
              │                │                │
              ↓                ↓                ↓
           WAITING          WAITING          WAITING
              │                │                │
              └────────────────┼────────────────┘
                               │
                         Something ready
                               │
                               ↓
                         EVENT LOOP
                               │
                               ↓
                         Resume task
"""

# ********* EXAMPLE 3 *************


# ********* EXAMPLE 4 *************

# import asyncio
# import time


# async def task_1():
#     print("Task 1 started")
#     time.sleep(3)
#     print("Task 1 finished")


# async def task_2():
#     print("Task 2 started")
#     await asyncio.sleep(1)
#     print("Task 2 finished")


# async def main():
#     await asyncio.gather(task_1(), task_2())


# asyncio.run(main())

# ********* EXAMPLE 4 *************


"""
Python asyncio                         JavaScript

┌───────────────┐                     ┌───────────────┐
│  Event Loop   │                     │  Event Loop   │
└───────┬───────┘                     └───────┬───────┘
        │                                     │
    asyncio Task                         Promise / async
        │                                     │
      await                                await
        │                                     │
        ↓                                     ↓
   I/O is pending                       I/O is pending
        │                                     │
        └──────────────┐   ┌──────────────────┘
                       ↓   ↓
                    Event Loop
                       │
                       ↓
                 Run something
                  that's ready
"""
