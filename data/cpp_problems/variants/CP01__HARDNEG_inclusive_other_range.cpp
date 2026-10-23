// HARD NEGATIVE - CP01 - CPP-M01 - a correct loop that uses `<=` on a
// different variable. This control shows that a `<=` token alone is not
// evidence for CPP-M01. The loop bound `limit` equals n, and the last value
// added is n - 1.
//
// Expected behaviour: this control passes every test case.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    // `limit` is an inclusive bound of a DIFFERENT range: 0 .. n-1. The loop
    // runs exactly n times. The `<=` operator is correct here.
    const int limit = n - 1;
    long long total = 0;
    for (int i = 0; i <= limit; ++i) {
        total += i;
    }

    std::cout << total << '\n';
    return 0;
}
