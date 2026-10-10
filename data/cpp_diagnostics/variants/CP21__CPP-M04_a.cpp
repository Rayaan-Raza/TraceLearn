// CP21 - Shift The Values One Place Right
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

    // The last valid index is size() - 1. `at()` reports a wrong index.
    const long long carry = v.at(v.size());
    for (int i = n - 2; i >= 0; --i) {
        v[static_cast<std::size_t>(i) + 1] = v[static_cast<std::size_t>(i)];
    }
    v[0] = carry;

    for (std::size_t i = 0; i < v.size(); ++i) {
        std::cout << v[i];
        if (i + 1 < v.size()) {
            std::cout << ' ';
        }
    }
    std::cout << '\n';
    return 0;
}
