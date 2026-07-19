# Data Structures - for all languages

# 1. Arrays -> A contonious memory is allocated
# int -> 4 bytes | [22, 23, 21, 22, 24]
# ["Shantanu", "Shubham", "Satyam", "Vishal", "Anurag"]
# [True, False, False, True, False]
# In languages like Java, an array has a fixed type and a pre-defined size
# int[] ar = new int[5];  
# [0][0][0][20][0] -> 5 * 4 = 20 bytes
#  0  1  2   3  4 | array[3] -> 20
#              M213 1  2 3 4               
# [][][][]   ||[22][23][][][]||    [][][][][][][][][][][][][][][][]
#               ar -> M213
# ar[0] = 22
# ar[1] = 23

# 2. LinkedList 
# []->[]->[]->[]->X

# A LinkedList is also homogenous in nature. It doesn't have a fixed size. 2, 10, 15
# ListNode ll = new ListNode(2);
# In a LL, we store 2 things
# 1. the value
# 2. the address to the next value

# M213   0         1 2 3 4 5   6       7 8    9
# RAM   [10, M2139][][][][][][2, M2130][][][15, null]
#                               ll   

# 3. String -> Ultimately, a string is a character array.
# A string is immutable.
# first_name = "Shantan" -> ['S']['h']['a']['n']['t']['a']['n']
#                                    
# last_name = "Shubham" -> ['S']['h']['u']['b']['h']['a']['m']
#                                       ln
# first_name = first_name + 'u' -> ['u'] | ['S']['h']['a']['n']['t']['a']['n']['u']
#                                                       fn


# 4. Stack -> LIFO (Last In First Out)
# Start: [1][4]

# 5. Queue -> FIFO (First In First Out)
# Start: [2][3][4] :End


# 6. Set -> A set is like a list, but it cannot contain duplicates.
# set -> [1,1,1,2,2,2,2] -> [1,2]


# In Python -> Array + LinkedList + Stack + Queue = All are represented by something called as a list.

