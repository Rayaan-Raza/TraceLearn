#include <iostream>
using namespace std;
long long fact(long long n) {
    return n * fact(n - 1);
}
int main() {
    long long n;
    cin >> n;
    cout << fact(n) << endl;
}
