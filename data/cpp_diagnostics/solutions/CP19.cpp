// CP19 - Even Or Odd By A Function
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

bool is_even(int x) {
    // The result travels through the return channel.
    const bool answer = (x % 2 == 0);
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    std::cout << (is_even(x) ? 1 : 0) << '\n';
    return 0;
}
