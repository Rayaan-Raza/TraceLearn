// VARIANT - CP04 - CPP-M04 - index equal to container size treated as valid.
//
// Defect: the program reads index `values.size()`. The last valid index is
// `values.size() - 1`. Index `size()` is out of range.
//
// Expected behaviour: `values.at(size())` throws `std::out_of_range`. Every
// run ends with a non-zero return code. Every test case fails.
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

    // BUG: index size() is never a valid index. `at()` throws here.
    std::cout << values.at(values.size()) << '\n';
    return 0;
}
