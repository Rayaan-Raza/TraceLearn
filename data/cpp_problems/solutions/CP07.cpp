// CP07 - Factorial By Recursion
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
//
// Contract: read n and print n factorial. Use a recursive function
// `long long factorial(int n)`. Each recursive call must approach the base
// case n <= 1.
//
// This solution is the correct control. The recursive call passes `n - 1`,
// so the state approaches the base case. The variant
// `variants/CP07__CPP-M07a.cpp` passes `n` again and never reaches the base
// case. The variant `variants/CP07__CPP-M07b.cpp` loops without updating the
// loop variable.
#include <iostream>

long long factorial(int n) {
    // Base case.
    if (n <= 1) {
        return 1;
    }
    // Each call reduces n by one. The state approaches the base case.
    return static_cast<long long>(n) * factorial(n - 1);
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::cout << factorial(n) << '\n';
    return 0;
}
