#include <stdio.h>
int main() {
    int n, x, s;
    scanf("%d", &n);
    for (int i = 0; i < n; i++) { scanf("%d", &x); s += x; }
    if (s > 0) printf("%d\n", s); else printf("%d\n", 0);
    return 0;
}
