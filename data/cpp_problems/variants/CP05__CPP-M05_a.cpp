// VARIANT - CP05 - CPP-M05 - misunderstanding of a compound boolean comparison.
//
// Defect: the condition is `1 <= x <= 10`. In C++ this is not a chain. It is
// `(1 <= x) <= 10`. The left operand of the second `<=` is a bool, so it
// becomes 0 or 1. The whole condition is always true, so every input prints IN.
//
// Expected behaviour: this variant fails every out-of-range test. The inputs
// 0, 11, -5, 100 and -1 all return IN. The compiler also emits a -Wparentheses
// warning on the comparison.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // BUG: chained comparison. It is always true.
    if (1 <= x <= 10) {
        std::cout << "IN" << '\n';
    } else {
        std::cout << "OUT" << '\n';
    }
    return 0;
}
