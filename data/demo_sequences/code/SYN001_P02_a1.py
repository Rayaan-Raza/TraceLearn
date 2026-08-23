def count_positive(nums):
    c = 0
    for i in range(len(nums)):
        if nums[i] > 0:
            c += 1
    return c - (1 if nums else 0)
