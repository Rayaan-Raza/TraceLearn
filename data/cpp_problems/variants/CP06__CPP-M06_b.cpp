// VARIANT - CP06 - CPP-M06 - assignment written to the wrong side.
//
// Defect: the condition is `if (0 = x)`. The assignment target is a literal.
// A literal is not an lvalue, so the program is ill-formed.
//
// Expected behaviour: the compiler rejects the source. The verifier records a
// compile error and the diagnostic line. This variant shows the reverse
// direction of CPP-M06.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // BUG: the assignment target is the literal 0. It is not an lvalue.
    if (0 = x) {
        std::cout << "ZERO" << '\n';
    } else {
        std::cout << "NONZERO" << '\n';
    }
    return 0;
}
