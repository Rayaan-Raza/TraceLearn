// CP28 - Cinema Ticket Price
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int age = 0;
    if (!(std::cin >> age)) {
        return 0;
    }

    long long answer = -1;
    if (age >= 0 <= 5) {
        answer = 0;
    } else if (age >= 6 <= 17) {
        answer = 7;
    } else if (age >= 18 <= 64) {
        answer = 12;
    } else if (age >= 65) {
        answer = 8;
    }

    std::cout << answer << '\n';
    return 0;
}
