    // HARD NEGATIVE - CP04 - CPP-M04 - a traversal that stops before size().
//
// This control traverses the whole vector with `i < values.size()`. It never
// reads index `size()`. It prints only the last element that it read. The loop
// looks like the buggy loop in `CP04__CPP-M04_b`, but the bound is correct.
//
// Expected behaviour: this control passes every test case.
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

    int last = 0;
    // Correct traversal: `<` stops before index size().
    for (std::size_t i = 0; i < values.size(); ++i) {
        last = values[i];
    }

    std::cout << last << '\n';
    return 0;
}
