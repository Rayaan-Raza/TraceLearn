def first_negative(nums):
    for x in nums:
        if nums[x] < 0:
            return nums[x]
    return None
