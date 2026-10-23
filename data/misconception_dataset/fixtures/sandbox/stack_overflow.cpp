#include <iostream>
long long f(long long n) { return n + f(n - 1); }
int main() { long long n; std::cin >> n; std::cout << f(n) << "\n"; }
