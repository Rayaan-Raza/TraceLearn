// CP08 - First Position Of A Target
// Target misconception: CPP-M08 (loop fails to update its exit condition)
//
// Contract: read n, then n integers, then a target t. Print the 0-based
// position of the first value that equals t. If t is absent, print NOT FOUND.
// The search loop must stop when the list ends.
//
// This solution is the correct control. The loop variable `i` changes on
// every iteration, and the loop stops at `values.size()`. The variant
// `variants/CP08__CPP-M08a.cpp` uses a while loop with no update. The variant
// `variants/CP08__CPP-M08b.cpp` uses a for loop with a missing update
// statement. Both pass when the target sits at index 0, and both hang when
// the target is absent.
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

    int target = 0;
    if (!(std::cin >> target)) {
        return 0;
    }

    for (std::size_t i = 0; i < values.size(); ++i) {
        if (values[i] == target) {
            std::cout << i << '\n';
            return 0;
        }
    }

    std::cout << "NOT FOUND" << '\n';
    return 0;
}
