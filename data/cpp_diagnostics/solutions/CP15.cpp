// CP15 - Count The Occurrences Of A Value
// Target misconception: CPP-M02 (element value confused with index position)
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

    long long target = 0;
    if (!(std::cin >> target)) {
        return 0;
    }

    long long answer = 0;
    // Each member of v is a value. Compare the value with the target.
    for (long long value : v) {
        if (value == target) {
            ++answer;
        }
    }

    std::cout << answer << '\n';
    return 0;
}
