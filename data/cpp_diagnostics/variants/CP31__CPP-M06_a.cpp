// CP31 - Divisible By Two Divisors
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long x = 0;
    long long p = 1;
    long long q = 1;
    if (!(std::cin >> x >> p >> q)) {
        return 0;
    }

    long long remainder_p = x % p;
    long long remainder_q = x % q;
    // A comparison, not an assignment.
    const bool answer = (remainder_p = 0) && (remainder_q == 0);

    std::cout << (answer ? "YES" : "NO") << '\n';
    return 0;
}
