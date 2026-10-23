// CP01 - Sum First N (Exclusive Bound)
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
//
// Contract: read n, print the sum of the integers 0 .. n-1. The upper bound n
// is exclusive. For n = 0 the range is empty and the sum is 0.
//
// This solution is the correct control. It uses `i < n`, so it iterates
// exactly n times. The variant `variants/CP01__CPP-M01a.cpp` uses `i <= n`
// and reads one item past the upper bound.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    // The upper bound is exclusive. `i < n` gives exactly n iterations.
    long long total = 0;
    for (int i = 0; i < n; ++i) {
        total += i;
    }

    std::cout << total << '\n';
    return 0;
}
