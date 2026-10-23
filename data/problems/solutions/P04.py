def find_max_value(nums):
    if not nums:
        return None
    best = nums[0]
    for x in nums:
        if x > best:
            best = x
    return best
