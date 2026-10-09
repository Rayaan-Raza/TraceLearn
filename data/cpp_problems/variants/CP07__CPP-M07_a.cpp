// VARIANT - CP07 - CPP-M07 - recursion that makes no progress.
//
// Defect: the recursive call passes `n` again. The argument never approaches
// the base case n <= 1, so the recursion never stops.
//
// Observed behaviour, measured on g++ 13.3.0:
// * With `-O2 -Wall -Wextra`, the compiler replaces the self call with a
//   self loop (see `objdump`: `jmp .`). The program then never terminates.
//   The sandbox stops it at the 2000 ms wall-clock limit.
// * With `-O1 -g -fsanitize=address,undefined`, the call stays a real call.
//   The program then exhausts the stack and dies from SIGSEGV.
//
// Either way, every test case fails. Both failure modes are evidence for
// CPP-M07: the state does not approach the base case.
#include <iostream>

long long factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    // BUG: passes n again. The state does not approach the base case.
    return static_cast<long long>(n) * factorial(n);
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
