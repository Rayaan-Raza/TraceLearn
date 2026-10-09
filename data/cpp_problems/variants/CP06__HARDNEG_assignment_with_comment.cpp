// HARD NEGATIVE - CP06 - CPP-M06 - an INTENTIONAL assignment in a condition.
//
// This control holds an assignment inside a condition, and it carries a
// comment. The taxonomy exclusion criteria require exactly this: an
// intentional assignment in a condition, with a comment, is not CPP-M06. The
// program stores the input in `stored` and then compares `stored` with 0. The
// behaviour is correct.
//
// Expected behaviour: this control passes every test case. The compiler emits
// no warning, because the assignment is wrapped in its own parentheses.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // Intentional assignment inside a condition, with a comment.
    // The value is compared afterwards. This is not a defect.
    int stored = 0;
    if ((stored = x) == 0) {
        std::cout << "ZERO" << '\n';
    } else {
        std::cout << "NONZERO" << '\n';
    }
    return 0;
}
