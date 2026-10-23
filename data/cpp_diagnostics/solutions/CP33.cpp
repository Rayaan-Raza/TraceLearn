// CP33 - Sum From One To N By Recursion
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

long long sum_to(int n) {
    // Base case.
    if (n <= 0) {
        return 0;
    }
    // Each call passes a smaller argument. The state reaches the base case.
    return n + sum_to(n - 1);
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::cout << sum_to(n) << '\n';
    return 0;
}
