#include <stdio.h>
int main() {
    int n, x, p = 1;
    scanf("%d", &n);
    for (int i = 0; i < n; i++) { scanf("%d", &x); p = p * x; }
    printf("%d\n", p);
    return 0;
}
