// CP30 - Password Length Check
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>
#include <string>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string line;
    if (!std::getline(std::cin, line)) {
        return 0;
    }

    int length = static_cast<int>(line.size());
    // A comparison, not an assignment.
    const bool answer = (length = 8);

    std::cout << (answer ? "OK" : "TOO SHORT") << '\n';
    return 0;
}
