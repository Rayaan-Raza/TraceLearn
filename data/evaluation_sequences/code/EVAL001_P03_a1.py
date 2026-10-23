def first_negative(nums):
    for i in range(len(nums)):
        if nums[i] < 0:
            return i
    return None
