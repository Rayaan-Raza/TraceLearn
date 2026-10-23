// CP12 - Product Of The First N Odd Integers
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long answer = 1;
    // The upper bound is exclusive. The last odd integer is 2*n - 1.
    for (int i = 0; i <= n; ++i) {
        answer *= (2 * i + 1);
    }

    std::cout << answer << '\n';
    return 0;
}
