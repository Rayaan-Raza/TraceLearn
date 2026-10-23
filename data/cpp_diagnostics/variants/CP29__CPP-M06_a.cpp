// CP29 - Sign Of A Number
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    const char* answer = "NEGATIVE";
    // A comparison, not an assignment.
    if (x = 0) {
        answer = "ZERO";
    } else if (x > 0) {
        answer = "POSITIVE";
    }

    std::cout << answer << '\n';
    return 0;
}
