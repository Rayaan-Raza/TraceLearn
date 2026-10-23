// CP18 - Largest Of Three Values
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

int largest_of_three(int a, int b, int c) {
    int answer = a;
    if (b > answer) {
        answer = b;
    }
    if (c > answer) {
        answer = c;
    }
    std::cout << answer << '\n';
    return 0;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int a = 0;
    int b = 0;
    int c = 0;
    if (!(std::cin >> a >> b >> c)) {
        return 0;
    }

    std::cout << (largest_of_three(a, b, c) + 1) << '\n';
    return 0;
}
