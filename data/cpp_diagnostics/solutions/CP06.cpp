// CP06 - Zero Or Not Zero
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
//
// Contract: read x and print ZERO when x equals 0. Print NONZERO otherwise.
// Compare the values. Do not assign.
//
// This solution is the correct control. The condition uses `==`. The variant
// `variants/CP06__CPP-M06a.cpp` uses `=` and always takes the else branch.
// The variant `variants/CP06__CPP-M06b.cpp` assigns to a literal and the
// compiler rejects it.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // A comparison, not an assignment.
    if (x == 0) {
        std::cout << "ZERO" << '\n';
    } else {
        std::cout << "NONZERO" << '\n';
    }
    return 0;
}
