// VARIANT - CP04 - CPP-M04 - loop bound uses `<=` against `size()`.
//
// Defect: the loop condition is `i <= values.size()`. The loop therefore
// reads one element past the end of the vector. `operator[]` does no bounds
// check, so the read is undefined behaviour and the result is not reliable.
//
// Expected behaviour: `-O2` without a sanitizer may return a plausible value.
// The AddressSanitizer build reports a heap-buffer-overflow. This file is a
// sanitizer-only control, so the verifier asserts the sanitizer report.
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

    if (values.empty()) {
        std::cout << "EMPTY" << '\n';
        return 0;
    }

    int last = 0;
    // BUG: `<= size()` permits the index size(). That index is invalid.
    for (std::size_t i = 0; i <= values.size(); ++i) {
        last = values[i];
    }

    std::cout << last << '\n';
    return 0;
}
