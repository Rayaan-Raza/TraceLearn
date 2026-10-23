// VARIANT - CP08 - CPP-M08 - loop fails to update its exit condition.
//
// Defect: the while loop tests values[i] but never changes i. The exit
// condition stays unchanged on every iteration.
//
// Observed behaviour, measured on g++ 13.3.0 with `-O2 -Wall -Wextra`:
// The loop body is empty and the condition is loop-invariant. C++ makes a
// side-effect-free loop that does not terminate undefined behaviour, so the
// compiler deletes the loop. The program then prints 0 and exits with status
// 0. Thus this variant fails seven of ten tests with a WRONG OUTPUT. It does
// not reach the wall-clock limit. Its sibling `CP08__CPP-M08_b.cpp` does reach
// the wall-clock limit, because its loop body reads a container.
//
// This difference matters for the judge: a non-progress loop is not always
// caught by a timeout. See docs/PROBLEM_VERIFICATION_REPORT.md.
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::vector<int> values;
    if (n > 0) {
        values.reserve(static_cast<std::size_t>(n));
        for (int i = 0; i < n; ++i) {
            int v = 0;
            if (!(std::cin >> v)) {
                return 0;
            }
            values.push_back(v);
        }
    }

    int target = 0;
    if (!(std::cin >> target)) {
        return 0;
    }

    // BUG: i never changes. The exit condition stays the same.
    int i = 0;
    while (values[static_cast<std::size_t>(i)] != target) {
    }

    std::cout << i << '\n';
    return 0;
}
