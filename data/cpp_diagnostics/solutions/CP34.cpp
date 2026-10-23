// CP34 - Power By Recursion
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

long long power(int base, int exponent) {
    // Base case.
    if (exponent == 0) {
        return 1;
    }
    // Each call reduces the exponent by one.
    return base * power(base, exponent - 1);
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int base = 1;
    int exponent = 0;
    if (!(std::cin >> base >> exponent)) {
        return 0;
    }

    std::cout << power(base, exponent) << '\n';
    return 0;
}
