// CP02 - Largest Value, Not Position
// Target misconception: CPP-M02 (element value confused with index position)
//
// Contract: read n and then n integers, print the largest value. Print the
// value, not its position. For n = 0 print NONE.
//
// This solution is the correct control. It returns `best`, which holds a
// value from the vector. The variant `variants/CP02__CPP-M02a.cpp` prints
// `best_index`, which holds a position.
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

    int best = values[0];
    for (std::size_t i = 1; i < values.size(); ++i) {
        if (values[i] > best) {
            best = values[i];
        }
    }

    std::cout << best << '\n';
    return 0;
}
