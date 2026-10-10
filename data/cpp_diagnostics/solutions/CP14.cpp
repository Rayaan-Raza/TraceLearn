// CP14 - K-th Smallest Value
// Target misconception: CPP-M02 (element value confused with index position)
#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n < 0 ? 0 : n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    int k = 1;
    if (!(std::cin >> k)) {
        return 0;
    }

    std::vector<long long> sorted = v;
    std::sort(sorted.begin(), sorted.end());

    // k counts from 1, so the index is k - 1.
    const long long answer = sorted[static_cast<std::size_t>(k - 1)];

    std::cout << answer << '\n';
    return 0;
}
