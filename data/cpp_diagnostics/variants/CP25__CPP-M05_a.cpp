// CP25 - Grade From A Score
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int score = 0;
    if (!(std::cin >> score)) {
        return 0;
    }

    char answer = 'F';
    if (score < 0 || score > 100) {
        answer = 'I';  // INVALID
    } else if (90 <= score <= 100) {
        answer = 'A';
    } else if (80 <= score <= 89) {
        answer = 'B';
    } else if (70 <= score <= 79) {
        answer = 'C';
    } else if (60 <= score <= 69) {
        answer = 'D';
    }

    if (answer == 'I') {
        std::cout << "INVALID" << '\n';
    } else {
        std::cout << answer << '\n';
    }
    return 0;
}
