// CP38 - Read Values Until A Sentinel
// Target misconception: CPP-M08 (loop fails to update its exit condition)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long answer = 0;
    long long total = 0;
    long long x = 0;
    // The condition tests the sentinel on every pass.
    while (std::cin >> x && x != -1) {
        ++answer;
        total += x;
    }

    std::cout << answer << ' ' << total << '\n';
    return 0;
}
