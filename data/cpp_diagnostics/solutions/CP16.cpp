// CP16 - Median Value
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
    if (n < 1) {
        // The contract holds an odd count of at least one value.
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    std::vector<long long> sorted = v;
    std::sort(sorted.begin(), sorted.end());

    // n is odd. The middle index is n / 2.
    const long long answer = sorted[static_cast<std::size_t>(n / 2)];

    std::cout << answer << '\n';
    return 0;
}
