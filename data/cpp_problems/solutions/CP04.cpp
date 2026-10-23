// CP04 - Last Element Of A Vector
// Target misconception: CPP-M04 (index equal to container size treated as valid)
//
// Contract: read n and then n integers, print the last element. For n = 0
// print EMPTY. The index size() is never a valid index.
//
// This solution is the correct control. It guards the empty vector and it
// reads the last valid index `values.size() - 1`. The variant
// `variants/CP04__CPP-M04a.cpp` reads index `values.size()`. The variant
// `variants/CP04__CPP-M04b.sanitize-only.cpp` loops with `i <= size()`.
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
        std::cout << "EMPTY" << '\n';
        return 0;
    }

    // The last valid index is size() - 1. Index size() is out of range.
    const std::size_t last = values.size() - 1;
    std::cout << values[last] << '\n';
    return 0;
}
