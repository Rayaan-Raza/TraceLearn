def first_negative(nums):
    for x in nums:
        if x < 0:
            return x
    return None
