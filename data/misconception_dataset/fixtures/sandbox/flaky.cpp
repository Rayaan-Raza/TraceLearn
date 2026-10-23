#include <iostream>
#include <chrono>
int main() { auto t = std::chrono::steady_clock::now().time_since_epoch().count(); std::cout << t << "\n"; }
