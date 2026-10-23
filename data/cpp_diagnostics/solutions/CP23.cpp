// CP23 - Value Before The Last Value
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
    if (n < 2) {
        // The contract holds at least two values.
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    // The value before the last is at index size() - 2.
    const long long answer = v.at(v.size() - 2);

    std::cout << answer << '\n';
    return 0;
}
