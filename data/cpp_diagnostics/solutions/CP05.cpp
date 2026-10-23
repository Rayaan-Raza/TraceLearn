// CP05 - Range Check 1 To 10
// Target misconception: CPP-M05 (misunderstanding compound boolean comparison)
//
// Contract: read x and print IN when x is inside the closed range 1 to 10.
// Print OUT otherwise. Use an explicit conjunction of two comparisons.
//
// This solution is the correct control. It uses `1 <= x && x <= 10`. The
// variant `variants/CP05__CPP-M05a.cpp` uses the mathematical chain
// `1 <= x <= 10`. In C++ that expression is `(1 <= x) <= 10`, which is always
// true, so the variant reports IN for every input.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // Two comparisons joined by &&. Each operand is a boolean.
    if (1 <= x && x <= 10) {
        std::cout << "IN" << '\n';
    } else {
        std::cout << "OUT" << '\n';
    }
    return 0;
}
