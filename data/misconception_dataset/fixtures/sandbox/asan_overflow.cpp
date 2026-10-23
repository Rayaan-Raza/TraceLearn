#include <iostream>
int main() { int n; std::cin >> n; int *a = new int[n]; for (int i = 0; i < n + 3; i++) a[i] = i; std::cout << a[0] << "\n"; delete[] a; }
