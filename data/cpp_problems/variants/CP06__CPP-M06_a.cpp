// VARIANT - CP06 - CPP-M06 - confusing assignment and equality comparison.
//
// Defect: the condition is `if (x = 0)`. It assigns 0 to x. The value of the
// assignment expression is 0, which converts to false. The true branch never
// runs.
//
// Expected behaviour: this variant fails every zero input. The inputs 0 fail
// and print NONZERO. The compiler emits a -Wparentheses warning that reports
// the assignment in the condition.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // BUG: `=` assigns. It does not compare.
    if (x = 0) {
        std::cout << "ZERO" << '\n';
    } else {
        std::cout << "NONZERO" << '\n';
    }
    return 0;
}
