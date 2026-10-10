// CP17 - Absolute Value By A Function
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

int absolute_value(int x) {
    // The value travels through the return channel.
    const int answer = x < 0 ? -x : x;
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    std::cout << absolute_value(x) << '\n';
    return 0;
}
