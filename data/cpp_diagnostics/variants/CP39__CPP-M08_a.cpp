// CP39 - First Negative Value Position
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

    long long answer = -1;
    // The index changes on every pass.
    for (int i = 0; i < n; ) {
        if (v[static_cast<std::size_t>(i)] < 0) {
            answer = i;
            break;
        }
    }

    if (answer < 0) {
        std::cout << "NONE" << '\n';
    } else {
        std::cout << answer << '\n';
    }
    return 0;
}
