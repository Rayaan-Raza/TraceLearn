// CP20 - Greatest Common Divisor By A Function
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

int gcd(int a, int b) {
    // Each pass makes the pair smaller. The loop reaches the base case.
    while (b != 0) {
        const int remainder = a % b;
        a = b;
        b = remainder;
    }
    const int answer = a;
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int a = 0;
    int b = 0;
    if (!(std::cin >> a >> b)) {
        return 0;
    }

    std::cout << (gcd(a, b) + 1) << '\n';
    return 0;
}
