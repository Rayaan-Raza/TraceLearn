// VARIANT - CP02 - CPP-M02 - element value confused with index position.
//
// Defect: the program tracks the position of the largest value and prints
// that position. The contract requires the largest value itself.
//
// Expected behaviour: this variant fails every test case in which the
// position differs from the value. The exposing input {7, 3, 9} returns 2.
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::vector<int> values;
    if (n > 0) {
        values.reserve(static_cast<std::size_t>(n));
        for (int i = 0; i < n; ++i) {
            int v = 0;
            if (!(std::cin >> v)) {
                return 0;
            }
            values.push_back(v);
        }
    }

    if (values.empty()) {
        std::cout << "NONE" << '\n';
        return 0;
    }

    int best_value = values[0];
    std::size_t best_position = 0;
    for (std::size_t i = 1; i < values.size(); ++i) {
        if (values[i] > best_value) {
            best_value = values[i];
            best_position = i;
        }
    }

    // BUG: prints the position, not the value.
    std::cout << best_position << '\n';
    return 0;
}
