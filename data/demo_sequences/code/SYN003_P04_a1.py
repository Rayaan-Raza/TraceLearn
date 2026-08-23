def find_max_value(nums):
    if not nums:
        return None
    best_i = 0
    for i in range(len(nums)):
        if i > best_i:
            best_i = i
    return best_i
