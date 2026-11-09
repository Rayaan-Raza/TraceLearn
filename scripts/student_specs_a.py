"""Student-style programs for bank problems CP01-CP20.

Each problem has two base solutions written the way beginners write them (style A:
C++ with cin/vector; style B: C-style scanf/arrays/while) and a list of single-edit
bugs. An edit is (base, label, find, replace, note): `find` must occur exactly once
in the base and `replace` introduces the bug. `scripts/build_student_synthetic.py`
checks by execution that the base passes every test and the edited program fails at
least one, so the single inverse edit is a proof that the bug is what breaks it.

Labels follow `ANNOTATION_GUIDELINE.md`: the cause behind the first failing test.
Bugs the ten misconception classes do not explain (output text, a wrong formula, a
missing special case, printing instead of returning) are CPP_OTHER_ERROR, which the
real CodeStream failures show to be the common case.
"""
from __future__ import annotations

LB, OB, AB = "CPP_LOOP_BOUNDARY", "CPP_OFF_BY_ONE", "CPP_ARRAY_BOUNDS"
UV, OV, MB = "CPP_UNINITIALIZED_VAR", "CPP_INT_OVERFLOW", "CPP_MISSING_BASE_CASE"
AC, WD, RC = "CPP_ASSIGN_VS_COMPARE", "CPP_WRONG_LOOP_DIR", "CPP_RANGE_CHECK"
SE, OT = "CPP_STALE_EXIT", "CPP_OTHER_ERROR"

SPECS: dict[str, dict] = {}

SPECS["CP01"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int n;
    cin >> n;
    int sum = 0;
    for (int i = 0; i < n; i++) {
        sum += i;
    }
    cout << sum << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, i = 0, total = 0;
    scanf("%d", &n);
    while (i < n) {
        total = total + i;
        i++;
    }
    printf("%d\\n", total);
    return 0;
}
""",
    "edits": [
        ("A", LB, "i < n", "i <= n", "loop includes n"),
        ("B", LB, "while (i < n)", "while (i <= n)", "loop includes n"),
        ("A", UV, "int sum = 0;", "int sum;", "accumulator never initialised"),
        ("B", OB, "total = 0;", "total = 1;", "accumulator starts at 1"),
        ("A", OT, "cout << sum << endl;", 'cout << "Sum: " << sum << endl;', "label printed with the answer"),
        ("B", OT, 'printf("%d\\n", total);', 'printf("sum = %d\\n", total);', "label printed with the answer"),
        ("A", OT, "sum += i;", "sum += i * 2;", "wrong formula"),
    ],
}

SPECS["CP02"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    if (n == 0) {
        cout << "NONE" << endl;
        return 0;
    }
    int best = v[0];
    for (int i = 1; i < n; i++) {
        if (v[i] > best) best = v[i];
    }
    cout << best << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, i, x, best = -1000001;
    scanf("%d", &n);
    if (n == 0) { printf("NONE\\n"); return 0; }
    for (i = 0; i < n; i++) {
        scanf("%d", &x);
        if (x > best) best = x;
    }
    printf("%d\\n", best);
    return 0;
}
""",
    "edits": [
        ("A", OT, 'cout << "NONE" << endl;', "cout << 0 << endl;", "no NONE for the empty list"),
        ("A", OT, "if (v[i] > best) best = v[i];", "if (v[i] > best) best = i;", "keeps the position, not the value"),
        ("A", OB, "for (int i = 1; i < n; i++)", "for (int i = 2; i < n; i++)", "scan starts one element late"),
        ("A", LB, "for (int i = 1; i < n; i++)", "for (int i = 1; i <= n; i++)", "scan includes index n"),
        ("B", UV, "x, best = -1000001;", "x, best;", "maximum never initialised"),
        ("B", OT, 'printf("NONE\\n")', 'printf("None\\n")', "output case"),
        ("B", OT, "if (x > best) best = x;", "if (x < best) best = x;", "keeps the minimum"),
    ],
}

SPECS["CP03"] = {
    "A": """#include <iostream>
using namespace std;
int twice(int x) {
    return x * 2;
}
int main() {
    int x;
    cin >> x;
    cout << twice(x) + 1 << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int twice(int x) {
    int r = x * 2;
    return r;
}
int main() {
    int x;
    scanf("%d", &x);
    int ans = twice(x);
    printf("%d\\n", ans + 1);
    return 0;
}
""",
    "edits": [
        ("A", OT, "return x * 2;", "cout << x * 2 << endl;\n    return 0;", "prints inside the function instead of returning"),
        ("A", OT, "twice(x) + 1", "twice(x)", "forgets the +1"),
        ("B", OT, "int r = x * 2;", "int r = x + 2;", "wrong formula"),
        ("B", OT, 'printf("%d\\n", ans + 1);', 'printf("%d\\n", ans);', "forgets the +1"),
    ],
}

SPECS["CP04"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    if (v.empty()) {
        cout << "EMPTY" << endl;
    } else {
        cout << v[v.size() - 1] << endl;
    }
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, a[1000], i;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    if (n == 0) {
        printf("EMPTY\\n");
    } else {
        printf("%d\\n", a[n - 1]);
    }
    return 0;
}
""",
    "edits": [
        ("A", AB, "v[v.size() - 1]", "v[v.size()]", "reads index size()"),
        ("B", AB, "a[n - 1]", "a[n]", "reads index n"),
        ("A", OB, "v[v.size() - 1]", "v[v.size() - 2]", "one element too early"),
        ("A", OT, '"EMPTY"', '"Empty"', "output case"),
        ("B", RC, "if (n == 0)", "if (n < 0)", "empty case never detected"),
    ],
}

SPECS["CP05"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int x;
    cin >> x;
    if (x >= 1 && x <= 10) {
        cout << "IN" << endl;
    } else {
        cout << "OUT" << endl;
    }
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int x;
    scanf("%d", &x);
    if (1 <= x && x <= 10)
        printf("IN\\n");
    else
        printf("OUT\\n");
    return 0;
}
""",
    "edits": [
        ("A", RC, "x >= 1 && x <= 10", "1 <= x <= 10", "mathematical chain"),
        ("B", RC, "1 <= x && x <= 10", "1 <= x <= 10", "mathematical chain"),
        ("A", RC, "x >= 1 && x <= 10", "x > 1 && x <= 10", "lower edge excluded"),
        ("B", RC, "x <= 10)", "x < 10)", "upper edge excluded"),
        ("A", OT, '"IN"', '"In"', "output case"),
        ("B", RC, "1 <= x && x <= 10", "1 <= x || x <= 10", "or instead of and"),
    ],
}

SPECS["CP06"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int x;
    cin >> x;
    if (x == 0) {
        cout << "ZERO" << endl;
    } else {
        cout << "NONZERO" << endl;
    }
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int x;
    scanf("%d", &x);
    if (x == 0)
        printf("ZERO\\n");
    else
        printf("NONZERO\\n");
    return 0;
}
""",
    "edits": [
        ("A", AC, "x == 0", "x = 0", "assignment in the condition"),
        ("B", AC, "x == 0", "x = 0", "assignment in the condition"),
        ("A", OT, '"NONZERO"', '"NON-ZERO"', "output text"),
        ("B", OT, '"ZERO\\n"', '"zero\\n"', "output case"),
        ("A", OT, "x == 0", "x != 0", "branches swapped"),
    ],
}

SPECS["CP07"] = {
    "A": """#include <iostream>
using namespace std;
long long factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
int main() {
    int n;
    cin >> n;
    cout << factorial(n) << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
long long fact(int n) {
    if (n == 0 || n == 1) {
        return 1;
    }
    return n * fact(n - 1);
}
int main() {
    int n;
    scanf("%d", &n);
    printf("%lld\\n", fact(n));
    return 0;
}
""",
    "edits": [
        ("A", MB, "    if (n <= 1) return 1;\n", "", "no base case"),
        ("B", MB, "n == 0 || n == 1", "n == 1", "base case misses 0"),
        ("A", MB, "factorial(n - 1)", "factorial(n)", "recursive call does not make progress"),
        ("A", OV, "long long factorial(int n)", "int factorial(int n)", "result type too small"),
        ("B", OT, "return n * fact(n - 1);", "return n + fact(n - 1);", "adds instead of multiplying"),
        ("A", OT, "if (n <= 1) return 1;", "if (n <= 1) return 0;", "base case returns 0"),
    ],
}

SPECS["CP08"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n, t;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cin >> t;
    int pos = -1;
    for (int i = 0; i < n; i++) {
        if (v[i] == t) {
            pos = i;
            break;
        }
    }
    if (pos == -1) cout << "NOT FOUND" << endl;
    else cout << pos << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, t, a[1000], i = 0;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &t);
    i = 0;
    while (i < n && a[i] != t) {
        i++;
    }
    if (i == n) printf("NOT FOUND\\n");
    else printf("%d\\n", i);
    return 0;
}
""",
    "edits": [
        ("A", OB, "pos = i;", "pos = i + 1;", "reports a 1-based position"),
        ("A", SE, "for (int i = 0; i < n; i++) {\n        if (v[i] == t) {", "for (int i = 0; i < n; ) {\n        if (v[i] == t) {", "loop index never advances"),
        ("B", SE, "        i++;\n    }\n    if (i == n)", "    }\n    if (i == n)", "loop never advances"),
        ("B", LB, "i < n && a[i] != t", "i <= n && a[i] != t", "loop may run past the list"),
        ("A", WD, "for (int i = 0; i < n; i++) {\n        if (v[i] == t) {", "for (int i = n - 1; i >= 0; i--) {\n        if (v[i] == t) {", "scans from the end, finds the last"),
        ("A", OT, '"NOT FOUND"', '"Not found"', "output case"),
        ("B", OT, "if (i == n)", "if (i > n)", "absent target never reported"),
    ],
}

SPECS["CP09"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    long long n, s = 0;
    cin >> n;
    for (long long i = 0; i < n; i++) {
        s += i * i;
    }
    cout << s << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    long long n, i, sum = 0;
    scanf("%lld", &n);
    for (i = 0; i < n; i++) sum += i * i;
    printf("%lld\\n", sum);
    return 0;
}
""",
    "edits": [
        ("A", LB, "i < n", "i <= n", "loop includes n"),
        ("B", LB, "i < n", "i <= n", "loop includes n"),
        ("A", OV, "long long n, s = 0;", "int n, s = 0;", "sum stored in int"),
        ("B", OV, "long long n, i, sum = 0;", "int n, i, sum = 0;", "sum stored in int"),
        ("A", OT, "s += i * i;", "s += i;", "forgets to square"),
        ("B", UV, "sum = 0;", "sum;", "accumulator never initialised"),
        ("B", OB, "for (i = 0; i < n; i++)", "for (i = 1; i < n + 1; i++)", "range shifted by one"),
    ],
}

SPECS["CP10"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int n, k;
    cin >> n >> k;
    int count = 0;
    for (int i = 0; i < n; i++) {
        if (i % k == 0) count++;
    }
    cout << count << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, k, i, c = 0;
    scanf("%d %d", &n, &k);
    for (i = 0; i < n; i++)
        if (i % k == 0)
            c++;
    printf("%d\\n", c);
    return 0;
}
""",
    "edits": [
        ("A", LB, "i < n", "i <= n", "loop includes n"),
        ("B", LB, "i < n", "i <= n", "loop includes n"),
        ("A", OB, "int i = 0;", "int i = 1;", "range starts at 1, misses 0"),
        ("B", OB, "for (i = 0;", "for (i = 1;", "range starts at 1, misses 0"),
        ("A", AC, "i % k == 0", "i % k = 0", "assignment in the condition"),
        ("A", UV, "int count = 0;", "int count;", "counter never initialised"),
        ("B", OT, 'printf("%d\\n", c);', 'printf("count: %d\\n", c);', "label printed"),
    ],
}

SPECS["CP11"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int n;
    cin >> n;
    for (int i = n - 1; i >= 0; i--) {
        cout << i << "\\n";
    }
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, i;
    scanf("%d", &n);
    i = n - 1;
    while (i >= 0) {
        printf("%d\\n", i);
        i--;
    }
    return 0;
}
""",
    "edits": [
        ("A", LB, "i >= 0", "i >= -1", "loop goes below 0"),
        ("B", LB, "while (i >= 0)", "while (i >= -1)", "loop goes below 0"),
        ("A", WD, "for (int i = n - 1; i >= 0; i--)", "for (int i = 0; i < n; i++)", "counts up instead of down"),
        ("B", SE, "        i--;\n", "", "i never decreases"),
        ("A", OB, "int i = n - 1;", "int i = n;", "starts at n"),
        ("B", OB, "i = n - 1;", "i = n - 2;", "starts at n-2"),
        ("A", OT, '<< "\\n"', '<< " "', "space instead of newline"),
    ],
}

SPECS["CP12"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int n;
    cin >> n;
    long long p = 1;
    for (int i = 0; i < n; i++) {
        p *= (2 * i + 1);
    }
    cout << p << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, i;
    long long prod = 1;
    scanf("%d", &n);
    for (i = 1; i <= n; i++)
        prod = prod * (2 * i - 1);
    printf("%lld\\n", prod);
    return 0;
}
""",
    "edits": [
        ("A", LB, "i < n", "i <= n", "one factor too many"),
        ("B", LB, "i <= n", "i < n", "one factor too few"),
        ("A", OV, "long long p = 1;", "int p = 1;", "product stored in int"),
        ("B", OV, "long long prod = 1;", "int prod = 1;", "product stored in int"),
        ("A", OB, "(2 * i + 1)", "(2 * i - 1)", "odd numbers shifted"),
        ("B", UV, "long long prod = 1;", "long long prod;", "product never initialised"),
        ("A", OT, "p *= (2 * i + 1);", "p += (2 * i + 1);", "adds instead of multiplying"),
    ],
}

SPECS["CP13"] = {
    "A": """#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    sort(v.begin(), v.end());
    v.erase(unique(v.begin(), v.end()), v.end());
    if (v.size() < 2) {
        cout << "NONE" << endl;
    } else {
        cout << v[v.size() - 2] << endl;
    }
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, i, x, first = -2000000, second = -2000000;
    scanf("%d", &n);
    for (i = 0; i < n; i++) {
        scanf("%d", &x);
        if (x > first) {
            second = first;
            first = x;
        } else if (x > second && x < first) {
            second = x;
        }
    }
    if (second == -2000000) printf("NONE\\n");
    else printf("%d\\n", second);
    return 0;
}
""",
    "edits": [
        ("A", OT, "v.erase(unique(v.begin(), v.end()), v.end());", "", "duplicates not removed"),
        ("A", OB, "v[v.size() - 2]", "v[v.size() - 1]", "prints the largest"),
        ("A", AB, "v[v.size() - 2]", "v[v.size() - 3]", "index too small"),
        ("A", OT, '"NONE"', '"None"', "output case"),
        ("A", RC, "v.size() < 2", "v.size() < 1", "one distinct value not rejected"),
        ("B", OT, "x > second && x < first", "x > second", "equal maximum becomes second"),
        ("B", OT, 'printf("NONE\\n")', 'printf("NO\\n")', "output text"),
    ],
}

SPECS["CP14"] = {
    "A": """#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;
int main() {
    int n, k;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cin >> k;
    sort(v.begin(), v.end());
    cout << v[k - 1] << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
#include <stdlib.h>
int cmp(const void *a, const void *b) { return *(int *)a - *(int *)b; }
int main() {
    int n, k, i;
    static int a[100005];
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &k);
    qsort(a, n, sizeof(int), cmp);
    printf("%d\\n", a[k - 1]);
    return 0;
}
""",
    "edits": [
        ("A", OB, "v[k - 1]", "v[k]", "counts from 0"),
        ("B", OB, "a[k - 1]", "a[k]", "counts from 0"),
        ("A", OT, "    sort(v.begin(), v.end());\n", "", "never sorts"),
        ("B", OT, "qsort(a, n, sizeof(int), cmp);", "", "never sorts"),
        ("A", OT, "sort(v.begin(), v.end());", "sort(v.rbegin(), v.rend());", "sorts descending"),
        ("B", AB, "static int a[100005];", "static int a[100];", "array smaller than the input"),
        ("A", OT, "cout << v[k - 1] << endl;", "cout << v[n - k] << endl;", "k-th largest"),
    ],
}

SPECS["CP15"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n, t, cnt = 0;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cin >> t;
    for (int i = 0; i < n; i++) {
        if (v[i] == t) cnt++;
    }
    cout << cnt << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, t, i, x, c = 0;
    scanf("%d", &n);
    int a[n];
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &t);
    for (i = 0; i < n; i++) {
        x = a[i];
        if (x == t) c = c + 1;
    }
    printf("%d\\n", c);
    return 0;
}
""",
    "edits": [
        ("A", AC, "v[i] == t", "v[i] = t", "assignment in the condition"),
        ("B", AC, "x == t", "x = t", "assignment in the condition"),
        ("A", LB, "for (int i = 0; i < n; i++) {\n        if", "for (int i = 0; i <= n; i++) {\n        if", "loop includes index n"),
        ("A", OT, "if (v[i] == t) cnt++;", "if (v[i] == t) cnt = i;", "keeps the position"),
        ("B", UV, "i, x, c = 0;", "i, x, c;", "counter never initialised"),
        ("B", OT, "if (x == t) c = c + 1;", "if (x == t) { c = 1; }", "counts presence, not occurrences"),
        ("A", OB, "int n, t, cnt = 0;", "int n, t, cnt = 1;", "counter starts at 1"),
    ],
}

SPECS["CP16"] = {
    "A": """#include <iostream>
#include <vector>
#include <algorithm>
using namespace std;
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    sort(v.begin(), v.end());
    cout << v[n / 2] << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
#include <stdlib.h>
int cmp(const void *a, const void *b) { return *(int *)a - *(int *)b; }
int main() {
    int n, i;
    scanf("%d", &n);
    int a[n];
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    qsort(a, n, sizeof(int), cmp);
    printf("%d\\n", a[(n - 1) / 2]);
    return 0;
}
""",
    "edits": [
        ("A", OB, "v[n / 2]", "v[n / 2 + 1]", "one place above the middle"),
        ("B", OB, "a[(n - 1) / 2]", "a[(n + 1) / 2]", "one place above the middle"),
        ("A", OT, "    sort(v.begin(), v.end());\n", "", "never sorts"),
        ("B", OT, "qsort(a, n, sizeof(int), cmp);", "", "never sorts"),
        ("A", AB, "v[n / 2]", "v[n]", "index n"),
        ("A", OT, "cout << v[n / 2] << endl;", "cout << v[0] << endl;", "prints the smallest"),
        ("B", OT, "a[(n - 1) / 2]", "a[n / 2 - 1] + 0", "lower-middle slip"),
    ],
}

SPECS["CP17"] = {
    "A": """#include <iostream>
using namespace std;
int absolute_value(int x) {
    if (x < 0) return -x;
    return x;
}
int main() {
    int x;
    cin >> x;
    cout << absolute_value(x) << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int absolute_value(int x) {
    int r = x;
    if (x < 0) r = 0 - x;
    return r;
}
int main() {
    int x;
    scanf("%d", &x);
    printf("%d\\n", absolute_value(x));
    return 0;
}
""",
    "edits": [
        ("A", OT, "    if (x < 0) return -x;\n    return x;", "    if (x < 0) cout << -x << endl;\n    return x;", "prints instead of returning"),
        ("A", RC, "x < 0", "x < -1", "-1 not made positive"),
        ("A", OT, "return -x;", "return x;", "never negates"),
        ("B", RC, "if (x < 0)", "if (x <= 0 && x != 0)", "kept for symmetry"),
        ("B", OT, "r = 0 - x;", "r = x - 0;", "never negates"),
        ("B", UV, "int r = x;", "int r;", "result never set for non-negative x"),
    ],
}

SPECS["CP18"] = {
    "A": """#include <iostream>
using namespace std;
int largest_of_three(int a, int b, int c) {
    int m = a;
    if (b > m) m = b;
    if (c > m) m = c;
    return m;
}
int main() {
    int a, b, c;
    cin >> a >> b >> c;
    cout << largest_of_three(a, b, c) + 1 << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int largest_of_three(int a, int b, int c) {
    if (a >= b && a >= c) return a;
    if (b >= a && b >= c) return b;
    return c;
}
int main() {
    int a, b, c;
    scanf("%d %d %d", &a, &b, &c);
    printf("%d\\n", largest_of_three(a, b, c) + 1);
    return 0;
}
""",
    "edits": [
        ("A", OT, "return m;", "cout << m << endl;\n    return m;", "prints inside the function"),
        ("A", OT, "if (c > m) m = c;", "if (c > b) m = c;", "compares with the wrong variable"),
        ("A", OT, "largest_of_three(a, b, c) + 1", "largest_of_three(a, b, c)", "forgets +1"),
        ("B", OT, "if (b >= a && b >= c) return b;", "if (b >= a && b >= c) return a;", "returns the wrong value"),
        ("B", OT, "+ 1);", "+ 2);", "wrong constant"),
        ("B", AC, "a >= b && a >= c", "a = b && a >= c", "assignment in the condition"),
    ],
}

SPECS["CP19"] = {
    "A": """#include <iostream>
using namespace std;
bool is_even(int x) {
    return x % 2 == 0;
}
int main() {
    int x;
    cin >> x;
    if (is_even(x)) cout << 1 << endl;
    else cout << 0 << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
#include <stdbool.h>
bool is_even(int x) {
    if (x % 2 == 0) {
        return true;
    }
    return false;
}
int main() {
    int x;
    scanf("%d", &x);
    printf("%d\\n", is_even(x) ? 1 : 0);
    return 0;
}
""",
    "edits": [
        ("A", AC, "x % 2 == 0", "x % 2 = 0", "assignment in the condition"),
        ("A", OT, "return x % 2 == 0;", "return x % 2 == 1;", "tests odd"),
        ("B", AC, "if (x % 2 == 0)", "if (x % 2 = 0)", "assignment in the condition"),
        ("B", OT, "return true;", "return false;", "returns false for even"),
        ("A", OT, "cout << 1 << endl;", 'cout << "yes" << endl;', "output text"),
        ("B", OT, "is_even(x) ? 1 : 0", "is_even(x) ? 0 : 1", "branches swapped"),
    ],
}

SPECS["CP20"] = {
    "A": """#include <iostream>
using namespace std;
int gcd(int a, int b) {
    while (b != 0) {
        int t = a % b;
        a = b;
        b = t;
    }
    return a;
}
int main() {
    int a, b;
    cin >> a >> b;
    cout << gcd(a, b) + 1 << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int gcd(int a, int b) {
    int r;
    while (b > 0) {
        r = a % b;
        a = b;
        b = r;
    }
    return a;
}
int main() {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d\\n", gcd(a, b) + 1);
    return 0;
}
""",
    "edits": [
        ("A", SE, "        b = t;\n", "", "b never changes, loop never ends"),
        ("B", SE, "        b = r;\n", "", "b never changes, loop never ends"),
        ("A", OT, "int t = a % b;", "int t = a / b;", "division instead of remainder"),
        ("A", OT, "gcd(a, b) + 1", "gcd(a, b)", "forgets +1"),
        ("B", RC, "while (b > 0)", "while (b > 1)", "stops one step early"),
        ("B", UV, "    int r;\n    while", "    int r;\n    a = a + r * 0;\n    while", "reads r before it is set"),
        ("A", OT, "return a;", "return b;", "returns the remainder side"),
    ],
}
