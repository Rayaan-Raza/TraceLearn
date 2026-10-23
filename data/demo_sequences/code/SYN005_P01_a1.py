def sum_first_n(n):
    # ambiguous: uses n+1 but only for positive n
    if n <= 0:
        return 0
    total = 0
    for i in range(n + 1):
        total += i
    return total
