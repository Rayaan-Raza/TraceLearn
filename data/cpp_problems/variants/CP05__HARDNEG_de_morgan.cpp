// HARD NEGATIVE - CP05 - CPP-M05 - a range check that is CORRECT.
//
// This control looks like a compound comparison, but it is a correct
// disjunction of two negated comparisons. The taxonomy exclusion criteria
// require that a correct conjunction of two comparisons passes. A naive
// pattern search for the token `<=` next to `<` must not flag this file.
//
// Expected behaviour: this control passes every test case.
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    // Two comparisons joined by ||, both negated. This is correct.
    if (!(x < 1 || 10 < x)) {
        std::cout << "IN" << '\n';
    } else {
        std::cout << "OUT" << '\n';
    }
    return 0;
}
