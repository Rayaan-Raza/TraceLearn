def count_positive(nums):
    count = 0
    for x in nums:
        if x > 0:
            count += 1
    return count
