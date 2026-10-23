// CP40 - First Index With A Value At Least The Target
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

    // The index changes on every pass. The loop also accumulates the sum.
    std::size_t i = 0;
    long long answer = 0;
    while (i < v.size() && v[i] < target) {
        answer += v[i];
    }

    std::cout << i << ' ' << answer << '\n';
    return 0;
}
