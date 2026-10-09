// VARIANT - CP08 - CPP-M08 - for loop with a missing update statement.
//
// Defect: the for statement has no update expression. The loop variable i
// stays at 0.
//
// Expected behaviour: when the target sits at index 0 the loop prints 0 and
// returns. When the target is absent the loop runs until the 2000 ms
// wall-clock limit stops it. The static evidence is the missing update
// statement in the for header.
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

    // BUG: the for header has no update expression. i stays at 0.
    for (std::size_t i = 0; i < values.size();) {
        if (values[i] == target) {
            std::cout << i << '\n';
            return 0;
        }
    }

    std::cout << "NOT FOUND" << '\n';
    return 0;
}
