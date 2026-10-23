// CP10 - Count Multiples Of K In A Range
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long n = 0;
    long long k = 0;
    if (!(std::cin >> n >> k)) {
        return 0;
    }

    long long answer = 0;
    // The upper bound is exclusive. `i < n` gives exactly n iterations.
    for (long long i = 0; i <= n; ++i) {
        if (i % k == 0) {
            ++answer;
        }
    }

    std::cout << answer << '\n';
    return 0;
}
