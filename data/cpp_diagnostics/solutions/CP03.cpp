// CP03 - Return, Do Not Print
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
//
// Contract: write `int twice(int x)` that returns x * 2. The function must
// return the value. It must not print the value. `main` reads x and prints
// twice(x) + 1.
//
// This solution is the correct control. `twice` uses a return statement. The
// variant `variants/CP03__CPP-M03a.cpp` prints inside `twice` and returns 0.
// The verifier links that variant into a separate driver to observe the
// return channel on its own.
#include <iostream>

int twice(int x) {
    // The value travels through the return channel.
    return x * 2;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // The expression reads the return value. It does not read printed text.
    std::cout << (twice(x) + 1) << '\n';
    return 0;
}
