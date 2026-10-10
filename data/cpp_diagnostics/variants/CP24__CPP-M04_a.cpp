// CP24 - Read A Value At A Given Index
// Target misconception: CPP-M04 (index equal to container size treated as valid)
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }
    if (n < 1) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    long long i = 0;
    if (!(std::cin >> i)) {
        return 0;
    }

    // A valid index is smaller than size(). `at()` reports a wrong index.
    if (i >= 0 && static_cast<std::size_t>(i) <= v.size()) {
        std::cout << v.at(static_cast<std::size_t>(i)) << '\n';
    } else {
        std::cout << "OUT_OF_RANGE" << '\n';
    }
    return 0;
}
