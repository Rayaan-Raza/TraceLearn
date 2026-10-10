// CP11 - Print A Range In Reverse Order
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    // The first printed value is n-1. The last printed value is 0.
    for (int i = n; i >= 0; --i) {
        std::cout << i << '\n';
    }
    return 0;
}
