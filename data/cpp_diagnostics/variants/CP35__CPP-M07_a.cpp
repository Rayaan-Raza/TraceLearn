// CP35 - Fibonacci Number By Recursion
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

long long fibonacci(int n) {
    // Base case one.
    if (n <= 0) {
        return 0;
    }
    // Base case two.
    if (n == 1) {
        return 1;
    }
    // Each call passes a smaller argument.
    return fibonacci(n - 1) + fibonacci(n);
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::cout << fibonacci(n) << '\n';
    return 0;
}
