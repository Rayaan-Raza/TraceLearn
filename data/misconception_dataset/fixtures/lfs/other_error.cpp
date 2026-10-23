#include <iostream>
using namespace std;
int main() {
    int n;
    long long s = 0, x;
    cin >> n;
    for (int i = 0; i < n; i++) { cin >> x; s += x * 2; }
    cout << s << endl;
}
