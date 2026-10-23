// CP09 - Sum Of Squares Of The First N Integers
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long answer = 0;
    // The upper bound is exclusive. `i < n` gives exactly n iterations.
    for (int i = 0; i <= n; ++i) {
        answer += static_cast<long long>(i) * i;
    }

    std::cout << answer << '\n';
    return 0;
}
