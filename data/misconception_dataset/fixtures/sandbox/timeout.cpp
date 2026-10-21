#include <iostream>
int main() { int n; std::cin >> n; int i = 0; volatile long spin = 0; while (i < n) { spin = spin + 1; } std::cout << i << "\n"; }
