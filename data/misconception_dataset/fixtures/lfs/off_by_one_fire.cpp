#include <iostream>
using namespace std;
int main() {
    int n, a[105];
    cin >> n;
    for (int i = 0; i < n; i++) cin >> a[i];
    for (int i = 1; i < n; i++) cout << a[i] << " ";
    cout << endl;
}
