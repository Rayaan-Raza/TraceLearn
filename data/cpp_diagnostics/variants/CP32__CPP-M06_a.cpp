// CP32 - Vowel Or Consonant
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>
#include <string>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string line;
    if (!std::getline(std::cin, line) || line.empty()) {
        return 0;
    }

    char first = line[0];
    const bool is_vowel = (first = 'a') || (first == 'e') || (first == 'i')
        || (first == 'o') || (first == 'u') || (first == 'A')
        || (first == 'E') || (first == 'I') || (first == 'O')
        || (first == 'U');

    std::cout << (is_vowel ? "VOWEL" : "CONSONANT") << '\n';
    return 0;
}
