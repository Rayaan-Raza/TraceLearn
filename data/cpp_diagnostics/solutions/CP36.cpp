// CP36 - Count The Halving Steps
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long answer = 0;
    // Each pass halves n. The state approaches the exit condition.
    while (n > 0) {
        n /= 2;
        ++answer;
    }

    std::cout << answer << '\n';
    return 0;
}
