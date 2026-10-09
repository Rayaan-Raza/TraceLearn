// VARIANT - CP07 - CPP-M07 - iteration that makes no progress.
//
// Defect: the loop multiplies by k but never changes k. The loop state does
// not approach the exit condition.
//
// Expected behaviour: the inputs 0 and 1 terminate and print 1. Every larger
// input runs until the 2000 ms wall-clock limit stops it. This variant shows
// that the sandbox timeout catches a non-progress loop on a small input.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long result = 1;
    int k = n;
    // BUG: k never changes. The loop cannot terminate for k > 1.
    while (k > 1) {
        result *= k;
    }

    std::cout << result << '\n';
    return 0;
}
