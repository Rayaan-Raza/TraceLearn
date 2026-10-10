// CP26 - Shipping Cost By Weight
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long weight = 0;
    if (!(std::cin >> weight)) {
        return 0;
    }

    long long answer = -1;
    if (1 <= weight <= 500) {
        answer = 5;
    } else if (501 <= weight <= 2000) {
        answer = 10;
    } else if (2001 <= weight <= 10000) {
        answer = 20;
    }

    std::cout << answer << '\n';
    return 0;
}
