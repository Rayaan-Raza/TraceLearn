#include <iostream>
using namespace std;
int main() {
    int n;
    cin >> n;
    int a[5];
    long long s = 0;
    for (int i = 0; i < n; i++) { cin >> a[i]; s += a[i]; }
    cout << s << endl;
}
