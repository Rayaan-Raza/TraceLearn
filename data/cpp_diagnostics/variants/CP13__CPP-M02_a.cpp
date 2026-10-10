// CP13 - Second Largest Distinct Value
// Target misconception: CPP-M02 (element value confused with index position)
#include <iostream>
#include <set>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n < 0 ? 0 : n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    std::set<long long> distinct(v.begin(), v.end());
    if (distinct.size() < 2) {
        std::cout << "NONE" << '\n';
        return 0;
    }

    // Walk the set from the largest value down by one position.
    auto it = distinct.rbegin();
    ++it;
    const long long answer = *it;

    long long position = -1;
    for (int i = 0; i < n; ++i) {
        if (v[static_cast<std::size_t>(i)] == answer) {
            position = i;
            break;
        }
    }
    std::cout << position << '\n';
    return 0;
}
