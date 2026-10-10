// CP37 - Last Position Of A Value
// Target misconception: CPP-M08 (loop fails to update its exit condition)
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

    long long target = 0;
    if (!(std::cin >> target)) {
        return 0;
    }

    // Scan from the end. The index changes on every pass.
    for (int i = n - 1; i >= 0; --i) {
        if (v[static_cast<std::size_t>(i)] == target) {
            std::cout << i << '\n';
            return 0;
        }
    }

    std::cout << "NOT FOUND" << '\n';
    return 0;
}
