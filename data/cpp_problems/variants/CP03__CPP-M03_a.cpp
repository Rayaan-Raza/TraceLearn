// VARIANT - CP03 - CPP-M03 - printing treated as equivalent to returning.
//
// Defect: the function prints the result and returns 0. The contract
// requires the value through the return channel.
//
// Expected behaviour: this variant fails every test case. Its stdout holds
// the printed text and the wrong value from the expression. The verifier also
// links it into a separate driver. The driver reports returned=0.
#include <iostream>

int twice(int x) {
    // BUG: prints the result instead of returning it.
    std::cout << (x * 2);
    return 0;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // The expression reads the return value, which is 0.
    std::cout << (twice(x) + 1) << '\n';
    return 0;
}
