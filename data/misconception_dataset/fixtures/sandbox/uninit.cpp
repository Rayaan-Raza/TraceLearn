#include <stdio.h>
int main() { int n, s; scanf("%d", &n); for (int i = 1; i <= n; i++) s += i; if (s > 5) printf("%d\n", s); else printf("small\n"); return 0; }
