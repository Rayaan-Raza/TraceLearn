// CP27 - Water State From A Temperature
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int t = 0;
    if (!(std::cin >> t)) {
        return 0;
    }

    // Two comparisons joined by &&. Each operand is a boolean.
    const char* answer = "GAS";
    if (t <= 0) {
        answer = "SOLID";
    } else if (t >= 1 && t <= 99) {
        answer = "LIQUID";
    }

    std::cout << answer << '\n';
    return 0;
}
