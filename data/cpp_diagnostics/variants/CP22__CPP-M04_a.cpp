// CP22 - Sum Of The Last K Values
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

    int k = 1;
    if (!(std::cin >> k)) {
        return 0;
    }

    // The first of the last k values is at index size() - k.
    const std::size_t start = v.size();
    long long answer = 0;
    for (std::size_t i = start; i < v.size(); ++i) {
        answer += v[i];
    }

    std::cout << answer << '\n';
    return 0;
}
