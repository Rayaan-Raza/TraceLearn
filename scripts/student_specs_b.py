"""Student-style programs for bank problems CP21-CP40 (see student_specs_a.py)."""
from __future__ import annotations

from student_specs_a import AB, AC, LB, MB, OB, OT, RC, SE, UV, WD

SPECS: dict[str, dict] = {}

SPECS["CP21"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cout << v[n - 1];
    for (int i = 0; i < n - 1; i++) {
        cout << " " << v[i];
    }
    cout << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, a[1000], i;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    printf("%d", a[n - 1]);
    for (i = 0; i < n - 1; i++) printf(" %d", a[i]);
    printf("\\n");
    return 0;
}
""",
    "edits": [
        ("A", AB, "cout << v[n - 1];", "cout << v[n];", "reads index n"),
        ("B", AB, 'printf("%d", a[n - 1]);', 'printf("%d", a[n]);', "reads index n"),
        ("A", LB, "i < n - 1; i++) {\n        cout", "i < n; i++) {\n        cout", "prints one value too many"),
        ("B", LB, "i < n - 1; i++) printf", "i <= n - 1; i++) printf", "prints one value too many"),
        ("B", OB, "for (i = 0; i < n - 1; i++) printf", "for (i = 1; i < n - 1; i++) printf", "skips the first value"),
        ("A", OT, '" " << v[i]', '"," << v[i]', "comma separator"),
        ("B", OT, 'printf("%d", a[n - 1]);', 'printf("%d", a[0]);', "moves the wrong value to the front"),
    ],
}

SPECS["CP22"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n, k;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cin >> k;
    int sum = 0;
    for (int i = n - k; i < n; i++) {
        sum += v[i];
    }
    cout << sum << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, k, a[1000], i, total = 0;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &k);
    i = n - k;
    while (i < n) {
        total += a[i];
        i++;
    }
    printf("%d\\n", total);
    return 0;
}
""",
    "edits": [
        ("A", LB, "i < n; i++) {\n        sum", "i <= n; i++) {\n        sum", "adds v[n]"),
        ("B", LB, "while (i < n)", "while (i <= n)", "adds a[n]"),
        ("A", OB, "int i = n - k;", "int i = n - k + 1;", "one value too few"),
        ("B", OB, "i = n - k;", "i = n - k - 1;", "one value too many"),
        ("A", UV, "int sum = 0;", "int sum;", "accumulator never initialised"),
        ("B", UV, "i, total = 0;", "i, total;", "accumulator never initialised"),
        ("A", OT, 'cout << sum << endl;', 'cout << "Sum = " << sum << endl;', "label printed"),
    ],
}

SPECS["CP23"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cout << v[v.size() - 2] << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, a[1000], i;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    printf("%d\\n", a[n - 2]);
    return 0;
}
""",
    "edits": [
        ("A", AB, "v[v.size() - 2]", "v[v.size()]", "reads index size()"),
        ("B", AB, "a[n - 2]", "a[n]", "reads index n"),
        ("A", OB, "v[v.size() - 2]", "v[v.size() - 1]", "prints the last value"),
        ("B", OB, "a[n - 2]", "a[n - 3]", "two values before the last"),
        ("A", OT, "cout << v[v.size() - 2] << endl;", "cout << v[v.size() - 2] + 1 << endl;", "adds one"),
        ("B", OT, 'printf("%d\\n", a[n - 2]);', 'printf("answer: %d\\n", a[n - 2]);', "label printed"),
    ],
}

SPECS["CP24"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n, idx;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cin >> idx;
    if (idx >= 0 && idx < n) {
        cout << v[idx] << endl;
    } else {
        cout << "OUT_OF_RANGE" << endl;
    }
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, i, idx, a[1000];
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &idx);
    if (0 <= idx && idx <= n - 1)
        printf("%d\\n", a[idx]);
    else
        printf("OUT_OF_RANGE\\n");
    return 0;
}
""",
    "edits": [
        ("A", RC, "idx < n", "idx <= n", "accepts index n"),
        ("B", RC, "idx <= n - 1", "idx <= n", "accepts index n"),
        ("A", RC, "idx >= 0 && idx < n", "idx > 0 && idx < n", "rejects index 0"),
        ("A", RC, "idx >= 0 && idx < n", "0 <= idx < n", "mathematical chain"),
        ("B", RC, "0 <= idx &&", "0 < idx &&", "rejects index 0"),
        ("A", OT, '"OUT_OF_RANGE"', '"OUT OF RANGE"', "output text"),
        ("B", OB, "a[idx]);", "a[idx + 1]);", "reads the next value"),
    ],
}

SPECS["CP25"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int s;
    cin >> s;
    if (s >= 90 && s <= 100) cout << "A";
    else if (s >= 80 && s <= 89) cout << "B";
    else if (s >= 70 && s <= 79) cout << "C";
    else if (s >= 60 && s <= 69) cout << "D";
    else if (s >= 0 && s <= 59) cout << "F";
    else cout << "INVALID";
    cout << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int score;
    scanf("%d", &score);
    if (score < 0 || score > 100) printf("INVALID\\n");
    else if (score >= 90) printf("A\\n");
    else if (score >= 80) printf("B\\n");
    else if (score >= 70) printf("C\\n");
    else if (score >= 60) printf("D\\n");
    else printf("F\\n");
    return 0;
}
""",
    "edits": [
        ("A", RC, "s >= 90 && s <= 100", "90 <= s <= 100", "mathematical chain"),
        ("A", RC, "s >= 80 && s <= 89", "s > 80 && s <= 89", "80 excluded"),
        ("A", RC, "s >= 0 && s <= 59", "s > 0 && s <= 59", "0 excluded"),
        ("B", RC, "score < 0 || score > 100", "score <= 0 || score > 100", "0 rejected"),
        ("B", RC, "score >= 90", "score > 90", "90 excluded"),
        ("B", RC, "score > 100", "score >= 100", "100 rejected"),
        ("A", OT, '"INVALID"', '"Invalid"', "output case"),
    ],
}

SPECS["CP26"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int w;
    cin >> w;
    int cost;
    if (w >= 1 && w <= 500) cost = 5;
    else if (w >= 501 && w <= 2000) cost = 10;
    else if (w >= 2001 && w <= 10000) cost = 20;
    else cost = -1;
    cout << cost << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int w;
    scanf("%d", &w);
    if (w <= 0) printf("-1\\n");
    else if (w <= 500) printf("5\\n");
    else if (w <= 2000) printf("10\\n");
    else if (w <= 10000) printf("20\\n");
    else printf("-1\\n");
    return 0;
}
""",
    "edits": [
        ("A", RC, "w >= 501 && w <= 2000", "w > 501 && w <= 2000", "501 falls through"),
        ("A", RC, "w >= 1 && w <= 500", "w >= 0 && w <= 500", "0 accepted"),
        ("A", UV, "    else cost = -1;\n", "", "cost unset for invalid weights"),
        ("B", RC, "w <= 0", "w < 0", "0 accepted"),
        ("B", RC, "w <= 500", "w < 500", "500 moves to the next band"),
        ("B", RC, "w <= 10000", "w < 10000", "10000 rejected"),
        ("A", OT, "cost = 10;", "cost = 12;", "wrong price"),
    ],
}

SPECS["CP27"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int t;
    cin >> t;
    if (t <= 0) cout << "SOLID";
    else if (t >= 1 && t <= 99) cout << "LIQUID";
    else cout << "GAS";
    cout << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int t;
    scanf("%d", &t);
    if (t >= 100) printf("GAS\\n");
    else if (t >= 1) printf("LIQUID\\n");
    else printf("SOLID\\n");
    return 0;
}
""",
    "edits": [
        ("A", RC, "t >= 1 && t <= 99", "1 <= t <= 99", "mathematical chain"),
        ("A", RC, "t <= 0", "t < 0", "0 becomes liquid"),
        ("A", RC, "t <= 99", "t < 99", "99 becomes gas"),
        ("B", RC, "t >= 100", "t > 100", "100 becomes liquid"),
        ("B", RC, "t >= 1)", "t > 1)", "1 becomes solid"),
        ("A", OT, '"GAS"', '"Gas"', "output case"),
        ("B", OT, '"LIQUID\\n"', '"LIQUID WATER\\n"', "output text"),
    ],
}

SPECS["CP28"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int age;
    cin >> age;
    if (age < 0) cout << -1;
    else if (age <= 5) cout << 0;
    else if (age <= 17) cout << 7;
    else if (age <= 64) cout << 12;
    else cout << 8;
    cout << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int age, price;
    scanf("%d", &age);
    if (age < 0) price = -1;
    else if (age >= 65) price = 8;
    else if (age >= 18) price = 12;
    else if (age >= 6) price = 7;
    else price = 0;
    printf("%d\\n", price);
    return 0;
}
""",
    "edits": [
        ("A", RC, "age <= 5", "age < 5", "5 pays the next price"),
        ("A", RC, "age <= 64", "age < 64", "64 pays the senior price"),
        ("A", RC, "age < 0", "age <= 0", "0 becomes invalid"),
        ("B", RC, "age >= 65", "age > 65", "65 pays the adult price"),
        ("B", RC, "age >= 18", "age > 18", "18 pays the child price"),
        ("A", OT, "cout << 12;", "cout << 11;", "wrong price"),
        ("B", UV, "int age, price;", "int age, price;\n    if (age == -1000) price = 0;", "reads age before it is set"),
    ],
}

SPECS["CP29"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int x;
    cin >> x;
    if (x == 0) cout << "ZERO";
    else if (x > 0) cout << "POSITIVE";
    else cout << "NEGATIVE";
    cout << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int x;
    scanf("%d", &x);
    if (x == 0) {
        printf("ZERO\\n");
    } else if (x < 0) {
        printf("NEGATIVE\\n");
    } else {
        printf("POSITIVE\\n");
    }
    return 0;
}
""",
    "edits": [
        ("A", AC, "x == 0", "x = 0", "assignment in the condition"),
        ("B", AC, "x == 0", "x = 0", "assignment in the condition"),
        ("A", OT, '"POSITIVE"', '"Positive"', "output case"),
        ("B", OT, "x < 0", "x <= 0", "zero tested after, but negative branch takes it"),
        ("A", OT, "x > 0", "x < 0", "branches swapped"),
    ],
}

SPECS["CP30"] = {
    "A": """#include <iostream>
#include <string>
using namespace std;
int main() {
    string s;
    getline(cin, s);
    int len = s.length();
    if (len >= 8) {
        cout << "OK" << endl;
    } else {
        cout << "TOO SHORT" << endl;
    }
    return 0;
}
""",
    "B": """#include <stdio.h>
#include <string.h>
int main() {
    char s[200];
    fgets(s, 200, stdin);
    s[strcspn(s, "\\n")] = 0;
    if (strlen(s) >= 8)
        printf("OK\\n");
    else
        printf("TOO SHORT\\n");
    return 0;
}
""",
    "edits": [
        ("A", AC, "len >= 8", "len = 8", "assignment in the condition"),
        ("A", RC, "len >= 8", "len > 8", "8 characters rejected"),
        ("A", RC, "len >= 8", "len >= 7", "7 characters accepted"),
        ("A", OT, "getline(cin, s);", "cin >> s;", "stops reading at the first space"),
        ("B", OT, '    s[strcspn(s, "\\n")] = 0;\n', "", "newline counted in the length"),
        ("B", RC, "strlen(s) >= 8", "strlen(s) > 8", "8 characters rejected"),
        ("B", OT, '"TOO SHORT\\n"', '"too short\\n"', "output case"),
    ],
}

SPECS["CP31"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int x, p, q;
    cin >> x >> p >> q;
    int a = x % p;
    int b = x % q;
    if (a == 0 && b == 0) cout << "YES" << endl;
    else cout << "NO" << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int x, p, q;
    scanf("%d %d %d", &x, &p, &q);
    int r1 = x % p, r2 = x % q;
    if (r1 == 0 && r2 == 0) {
        printf("YES\\n");
    } else {
        printf("NO\\n");
    }
    return 0;
}
""",
    "edits": [
        ("A", AC, "a == 0 &&", "a = 0 &&", "assignment in the condition"),
        ("B", AC, "r2 == 0", "r2 = 0", "assignment in the condition"),
        ("A", OT, "a == 0 && b == 0", "a == 0 || b == 0", "or instead of and"),
        ("B", OT, "r1 == 0 && r2 == 0", "r1 == 0", "second divisor ignored"),
        ("A", OT, '"YES"', '"Yes"', "output case"),
        ("B", OT, "int r1 = x % p, r2 = x % q;", "int r1 = x / p, r2 = x / q;", "quotient instead of remainder"),
    ],
}

SPECS["CP32"] = {
    "A": """#include <iostream>
#include <string>
using namespace std;
int main() {
    string s;
    getline(cin, s);
    char c = s[0];
    if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u' ||
        c == 'A' || c == 'E' || c == 'I' || c == 'O' || c == 'U')
        cout << "VOWEL" << endl;
    else
        cout << "CONSONANT" << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    char c;
    scanf("%c", &c);
    int isv = 0;
    if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') isv = 1;
    if (c == 'A' || c == 'E' || c == 'I' || c == 'O' || c == 'U') isv = 1;
    if (isv == 1) printf("VOWEL\\n");
    else printf("CONSONANT\\n");
    return 0;
}
""",
    "edits": [
        ("A", AC, "c == 'a' ||", "c = 'a' ||", "assignment in the condition"),
        ("B", AC, "isv == 1", "isv = 1", "assignment in the condition"),
        ("A", OT, "c == 'u' ||\n        c == 'A' || c == 'E' || c == 'I' || c == 'O' || c == 'U')", "c == 'u')", "uppercase vowels missing"),
        ("B", OT, "    if (c == 'A' || c == 'E' || c == 'I' || c == 'O' || c == 'U') isv = 1;\n", "", "uppercase vowels missing"),
        ("A", OT, '"CONSONANT"', '"Consonant"', "output case"),
        ("B", UV, "int isv = 0;", "int isv;", "flag never initialised"),
    ],
}

SPECS["CP33"] = {
    "A": """#include <iostream>
using namespace std;
long long sum_to(int n) {
    if (n <= 0) return 0;
    return n + sum_to(n - 1);
}
int main() {
    int n;
    cin >> n;
    cout << sum_to(n) << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
long long sum_to(int n) {
    if (n == 0)
        return 0;
    else
        return n + sum_to(n - 1);
}
int main() {
    int n;
    scanf("%d", &n);
    printf("%lld\\n", sum_to(n));
    return 0;
}
""",
    "edits": [
        ("A", MB, "    if (n <= 0) return 0;\n", "", "no base case"),
        ("B", MB, "n == 0", "n == 1", "base case misses 0"),
        ("A", MB, "sum_to(n - 1)", "sum_to(n)", "call does not make progress"),
        ("B", MB, "sum_to(n - 1)", "sum_to(n + 1)", "recursion moves away from the base case"),
        ("A", OT, "return n + sum_to(n - 1);", "return n * sum_to(n - 1);", "multiplies instead of adding"),
        ("B", OT, "return 0;", "return 1;", "base case returns 1"),
    ],
}

SPECS["CP34"] = {
    "A": """#include <iostream>
using namespace std;
long long power(int b, int e) {
    if (e == 0) return 1;
    return b * power(b, e - 1);
}
int main() {
    int b, e;
    cin >> b >> e;
    cout << power(b, e) << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
long long pw(int base, int exponent) {
    if (exponent <= 0) {
        return 1;
    }
    return base * pw(base, exponent - 1);
}
int main() {
    int base, exponent;
    scanf("%d %d", &base, &exponent);
    printf("%lld\\n", pw(base, exponent));
    return 0;
}
""",
    "edits": [
        ("A", MB, "    if (e == 0) return 1;\n", "", "no base case"),
        ("B", MB, "exponent <= 0", "exponent == 1", "base case misses 0"),
        ("A", MB, "power(b, e - 1)", "power(b, e)", "call does not make progress"),
        ("B", MB, "pw(base, exponent - 1)", "pw(base, exponent + 1)", "recursion moves away from the base case"),
        ("A", OT, "return b * power(b, e - 1);", "return b + power(b, e - 1);", "adds instead of multiplying"),
        ("B", OT, "return 1;", "return 0;", "base case returns 0"),
    ],
}

SPECS["CP35"] = {
    "A": """#include <iostream>
using namespace std;
long long fib(int n) {
    if (n <= 0) return 0;
    if (n == 1) return 1;
    return fib(n - 1) + fib(n - 2);
}
int main() {
    int n;
    cin >> n;
    cout << fib(n) << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int fib(int n) {
    if (n == 0 || n == 1)
        return n;
    return fib(n - 1) + fib(n - 2);
}
int main() {
    int n;
    scanf("%d", &n);
    printf("%d\\n", fib(n));
    return 0;
}
""",
    "edits": [
        ("A", MB, "    if (n <= 0) return 0;\n", "", "no base case for 0"),
        ("B", MB, "n == 0 || n == 1", "n == 1", "base case misses 0"),
        ("A", OT, "    if (n == 1) return 1;\n", "", "case n = 1 missing, wrong values"),
        ("A", OT, "fib(n - 1) + fib(n - 2)", "fib(n - 1) + fib(n - 1)", "same call twice"),
        ("B", OB, "fib(n - 2)", "fib(n - 3)", "second call one too deep"),
        ("B", OT, "return n;", "return 1;", "fib(0) returns 1"),
    ],
}

SPECS["CP36"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int n;
    cin >> n;
    int count = 0;
    while (n > 0) {
        n = n / 2;
        count++;
    }
    cout << count << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int steps(int n) {
    if (n == 0) return 0;
    return 1 + steps(n / 2);
}
int main() {
    int n;
    scanf("%d", &n);
    printf("%d\\n", steps(n));
    return 0;
}
""",
    "edits": [
        ("A", SE, "        n = n / 2;\n", "", "n never changes"),
        ("A", LB, "while (n > 0)", "while (n >= 0)", "loop never ends at 0"),
        ("A", UV, "int count = 0;", "int count;", "counter never initialised"),
        ("A", OB, "int count = 0;", "int count = 1;", "counter starts at 1"),
        ("A", OT, "n = n / 2;", "n = n / 3;", "wrong divisor"),
        ("B", MB, "    if (n == 0) return 0;\n", "", "no base case"),
        ("B", MB, "steps(n / 2)", "steps(n)", "call does not make progress"),
    ],
}

SPECS["CP37"] = {
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
    for (int i = n - 1; i >= 0; i--) {
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
    int n, t, a[1000], i;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &t);
    i = n - 1;
    while (i >= 0 && a[i] != t) {
        i--;
    }
    if (i < 0) printf("NOT FOUND\\n");
    else printf("%d\\n", i);
    return 0;
}
""",
    "edits": [
        ("A", WD, "for (int i = n - 1; i >= 0; i--) {", "for (int i = 0; i < n; i++) {", "scans forward, finds the first"),
        ("A", SE, "for (int i = n - 1; i >= 0; i--) {", "for (int i = n - 1; i >= 0; ) {", "index never decreases"),
        ("B", SE, "        i--;\n", "", "index never decreases"),
        ("A", OB, "pos = i;", "pos = i + 1;", "1-based position"),
        ("B", RC, "if (i < 0)", "if (i < -1)", "absent target never reported"),
        ("A", OT, '"NOT FOUND"', '"Not Found"', "output case"),
        ("B", WD, "i = n - 1;\n    while (i >= 0 && a[i] != t) {\n        i--;", "i = 0;\n    while (i < n && a[i] != t) {\n        i++;", "forward scan reports the first position"),
    ],
}

SPECS["CP38"] = {
    "A": """#include <iostream>
using namespace std;
int main() {
    int x, count = 0, sum = 0;
    cin >> x;
    while (x != -1) {
        count++;
        sum += x;
        cin >> x;
    }
    cout << count << " " << sum << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int x, count = 0, sum = 0;
    while (1) {
        scanf("%d", &x);
        if (x == -1) break;
        count++;
        sum = sum + x;
    }
    printf("%d %d\\n", count, sum);
    return 0;
}
""",
    "edits": [
        ("A", SE, "        sum += x;\n        cin >> x;\n", "        sum += x;\n", "next value never read"),
        ("A", AC, "while (x != -1)", "while (x = -1)", "assignment in the condition"),
        ("A", UV, "int x, count = 0, sum = 0;", "int x, count = 0, sum;", "sum never initialised"),
        ("A", OB, "count = 0, sum = 0;", "count = 1, sum = 0;", "count starts at 1"),
        ("B", RC, "if (x == -1) break;", "if (x == 0) break;", "wrong sentinel"),
        ("B", OT, "sum = sum + x;", "sum = sum + 1;", "adds one, not the value"),
        ("B", OT, 'printf("%d %d\\n", count, sum);', 'printf("%d %d\\n", sum, count);', "swapped output"),
    ],
}

SPECS["CP39"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    int pos = -1;
    for (int i = 0; i < n; i++) {
        if (v[i] < 0) {
            pos = i;
            break;
        }
    }
    if (pos == -1) cout << "NONE" << endl;
    else cout << pos << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, a[1000], i;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    i = 0;
    while (i < n && a[i] >= 0) {
        i++;
    }
    if (i == n) printf("NONE\\n");
    else printf("%d\\n", i);
    return 0;
}
""",
    "edits": [
        ("A", RC, "v[i] < 0", "v[i] <= 0", "zero counted as negative"),
        ("B", RC, "a[i] >= 0", "a[i] > 0", "zero counted as negative"),
        ("A", RC, "v[i] < 0", "v[i] < -1", "-1 not counted as negative"),
        ("A", OB, "pos = i;", "pos = i + 1;", "1-based position"),
        ("B", SE, "        i++;\n    }\n    if (i == n)", "    }\n    if (i == n)", "index never advances"),
        ("A", OT, '"NONE"', '"None"', "output case"),
        ("B", LB, "i < n && a[i] >= 0", "i <= n && a[i] >= 0", "may read a[n]"),
    ],
}

SPECS["CP40"] = {
    "A": """#include <iostream>
#include <vector>
using namespace std;
int main() {
    int n, t;
    cin >> n;
    vector<int> v(n);
    for (int i = 0; i < n; i++) cin >> v[i];
    cin >> t;
    int i = 0, sum = 0;
    while (i < n && v[i] < t) {
        sum += v[i];
        i++;
    }
    cout << i << " " << sum << endl;
    return 0;
}
""",
    "B": """#include <stdio.h>
int main() {
    int n, t, a[1000], i, sum = 0;
    scanf("%d", &n);
    for (i = 0; i < n; i++) scanf("%d", &a[i]);
    scanf("%d", &t);
    for (i = 0; i < n; i++) {
        if (a[i] >= t) break;
        sum += a[i];
    }
    printf("%d %d\\n", i, sum);
    return 0;
}
""",
    "edits": [
        ("A", RC, "v[i] < t", "v[i] <= t", "stops one value late"),
        ("B", RC, "a[i] >= t", "a[i] > t", "stops one value late"),
        ("A", LB, "i < n && v[i] < t", "i <= n && v[i] < t", "may read v[n]"),
        ("A", SE, "        sum += v[i];\n        i++;\n", "        sum += v[i];\n", "index never advances"),
        ("A", OB, "int i = 0, sum = 0;", "int i = 1, sum = 0;", "starts at index 1"),
        ("B", UV, "i, sum = 0;", "i, sum;", "sum never initialised"),
        ("A", OT, 'cout << i << " " << sum << endl;', 'cout << sum << " " << i << endl;', "swapped output"),
    ],
}
