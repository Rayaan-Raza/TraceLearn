// VARIANT - CP01 - CPP-M01 - exclusive upper bound treated as inclusive.
//
// Defect: the loop condition is `i <= n`. The upper bound n is exclusive, so
// this loop runs n + 1 times. It adds one extra term to the sum.
//
// Expected behaviour: this variant fails every test case. The boundary tests
// with n = 0 and n = 1 fail first.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long total = 0;
    // BUG: `<=` makes the exclusive upper bound inclusive.
    for (int i = 0; i <= n; ++i) {
        total += i;
    }

    std::cout << total << '\n';
    return 0;
}
