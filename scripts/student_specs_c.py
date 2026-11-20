"""Two more beginner-style solutions for every bank problem (CP01-CP40).

`student_specs_a.py` / `student_specs_b.py` hold styles A (cin / vector / for) and B (scanf /
arrays / while) with hand-written single-edit bugs. These are two further styles, written to
look like different students:

- style C: the logic sits in a helper function, C++ streams, fixed global arrays, `for` loops;
- style D: everything in `main`, `cin` for input and `printf` for output, `while` loops with a
  hand-kept counter, and recursion where a beginner might reach for it.

There are no hand-written bugs here. `scripts/build_bank_synthetic.py` checks that each solution
passes every bank test, injects one bug per misconception class with its operators, and keeps a
buggy program only if it fails a test. Nothing here was written from the held-out problems.
"""
from __future__ import annotations

C_HEAD = "#include <iostream>\n#include <string>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n"
D_HEAD = "#include <iostream>\n#include <cstdio>\n#include <string>\n#include <vector>\n#include <algorithm>\nusing namespace std;\n"

SPECS_CD: dict[str, dict[str, str]] = {}


def _add(pid: str, c: str, d: str) -> None:
    SPECS_CD[pid] = {"C": C_HEAD + c.lstrip("\n"), "D": D_HEAD + d.lstrip("\n")}


_add("CP01", r"""
int sum_below(int n) {
    int s = 0;
    for (int k = 0; k < n; k++) {
        s = s + k;
    }
    return s;
}
int main() {
    int n;
    cin >> n;
    cout << sum_below(n) << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    long long total = 0;
    int k = 0;
    while (k < n) {
        total += k;
        k++;
    }
    printf("%lld\n", total);
    return 0;
}
""")

_add("CP02", r"""
int a[1005];
int find_max(int n) {
    int best = a[0];
    for (int i = 1; i < n; i++) {
        if (a[i] > best) {
            best = a[i];
        }
    }
    return best;
}
int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    if (n == 0) {
        cout << "NONE" << endl;
    } else {
        cout << find_max(n) << endl;
    }
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    if (n == 0) {
        printf("NONE\n");
        return 0;
    }
    int best;
    cin >> best;
    int i = 1;
    while (i < n) {
        int x;
        cin >> x;
        if (x > best) {
            best = x;
        }
        i++;
    }
    printf("%d\n", best);
    return 0;
}
""")

_add("CP03", r"""
int twice(int x) {
    int result = x + x;
    return result;
}
int main() {
    int x;
    cin >> x;
    int answer = twice(x) + 1;
    cout << answer << endl;
    return 0;
}
""", r"""
int twice(int x) {
    return 2 * x;
}
int main() {
    int x;
    cin >> x;
    printf("%d\n", twice(x) + 1);
    return 0;
}
""")

_add("CP04", r"""
int a[1005];
int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    if (n == 0) {
        cout << "EMPTY" << endl;
    } else {
        cout << a[n - 1] << endl;
    }
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    int last = 0;
    int i = 0;
    while (i < n) {
        cin >> last;
        i++;
    }
    if (n > 0) {
        printf("%d\n", last);
    } else {
        printf("EMPTY\n");
    }
    return 0;
}
""")

_add("CP05", r"""
bool inside(int x) {
    if (x >= 1 && x <= 10) {
        return true;
    }
    return false;
}
int main() {
    int x;
    cin >> x;
    if (inside(x)) {
        cout << "IN" << endl;
    } else {
        cout << "OUT" << endl;
    }
    return 0;
}
""", r"""
int main() {
    int x;
    cin >> x;
    if (x < 1 || x > 10) {
        printf("OUT\n");
    } else {
        printf("IN\n");
    }
    return 0;
}
""")

_add("CP06", r"""
bool is_zero(int x) {
    if (x == 0) {
        return true;
    }
    return false;
}
int main() {
    int x;
    cin >> x;
    if (is_zero(x)) {
        cout << "ZERO" << endl;
    } else {
        cout << "NONZERO" << endl;
    }
    return 0;
}
""", r"""
int main() {
    int x;
    cin >> x;
    int flag = 0;
    if (x == 0) {
        flag = 1;
    }
    if (flag == 1) {
        printf("ZERO\n");
    } else {
        printf("NONZERO\n");
    }
    return 0;
}
""")

_add("CP07", r"""
long long factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    long long rest = factorial(n - 1);
    return n * rest;
}
int main() {
    int n;
    cin >> n;
    cout << factorial(n) << endl;
    return 0;
}
""", r"""
long long factorial(int n) {
    if (n == 0 || n == 1) return 1;
    return factorial(n - 1) * n;
}
int main() {
    int n;
    cin >> n;
    printf("%lld\n", factorial(n));
    return 0;
}
""")

_add("CP08", r"""
int a[1005];
int find_first(int n, int t) {
    for (int i = 0; i < n; i++) {
        if (a[i] == t) {
            return i;
        }
    }
    return -1;
}
int main() {
    int n, t;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cin >> t;
    int pos = find_first(n, t);
    if (pos < 0) {
        cout << "NOT FOUND" << endl;
    } else {
        cout << pos << endl;
    }
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    int a[1005];
    int i = 0;
    while (i < n) {
        cin >> a[i];
        i++;
    }
    int t;
    cin >> t;
    int pos = -1;
    i = 0;
    while (i < n && pos == -1) {
        if (a[i] == t) {
            pos = i;
        }
        i++;
    }
    if (pos == -1) {
        printf("NOT FOUND\n");
    } else {
        printf("%d\n", pos);
    }
    return 0;
}
""")

_add("CP09", r"""
long long sum_squares(int n) {
    long long s = 0;
    for (int i = 0; i < n; i++) {
        s += (long long)i * i;
    }
    return s;
}
int main() {
    int n;
    cin >> n;
    cout << sum_squares(n) << endl;
    return 0;
}
""", r"""
int main() {
    long long n;
    cin >> n;
    long long total = 0;
    long long k = 0;
    while (k < n) {
        total = total + k * k;
        k++;
    }
    printf("%lld\n", total);
    return 0;
}
""")

_add("CP10", r"""
int count_multiples(int n, int k) {
    int c = 0;
    for (int i = 0; i < n; i++) {
        if (i % k == 0) {
            c++;
        }
    }
    return c;
}
int main() {
    int n, k;
    cin >> n >> k;
    cout << count_multiples(n, k) << endl;
    return 0;
}
""", r"""
int main() {
    int n, k;
    cin >> n >> k;
    int count = 0;
    int i = 0;
    while (i < n) {
        count++;
        i += k;
    }
    printf("%d\n", count);
    return 0;
}
""")

_add("CP11", r"""
void print_down(int n) {
    for (int i = n - 1; i >= 0; i--) {
        cout << i << endl;
    }
}
int main() {
    int n;
    cin >> n;
    print_down(n);
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    int i = n;
    while (i > 0) {
        i--;
        printf("%d\n", i);
    }
    return 0;
}
""")

_add("CP12", r"""
long long odd_product(int n) {
    long long p = 1;
    for (int i = 1; i <= n; i++) {
        p = p * (2 * i - 1);
    }
    return p;
}
int main() {
    int n;
    cin >> n;
    cout << odd_product(n) << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    long long p = 1;
    long long odd = 1;
    int done = 0;
    while (done < n) {
        p *= odd;
        odd += 2;
        done++;
    }
    printf("%lld\n", p);
    return 0;
}
""")

_add("CP13", r"""
int a[100005];
int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    sort(a, a + n);
    int count = 0;
    int answer = 0;
    for (int i = n - 1; i >= 0; i--) {
        if (i == n - 1 || a[i] != a[i + 1]) {
            count++;
            if (count == 2) {
                answer = a[i];
                break;
            }
        }
    }
    if (count < 2) {
        cout << "NONE" << endl;
    } else {
        cout << answer << endl;
    }
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    bool has1 = false, has2 = false;
    int first = 0, second = 0;
    int i = 0;
    while (i < n) {
        int x;
        cin >> x;
        if (!has1 || x > first) {
            if (has1) {
                second = first;
                has2 = true;
            }
            first = x;
            has1 = true;
        } else if (x < first && (!has2 || x > second)) {
            second = x;
            has2 = true;
        }
        i++;
    }
    if (has2) {
        printf("%d\n", second);
    } else {
        printf("NONE\n");
    }
    return 0;
}
""")

_add("CP14", r"""
int a[100005];
int kth(int n, int k) {
    sort(a, a + n);
    return a[k - 1];
}
int main() {
    int n, k;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cin >> k;
    cout << kth(n, k) << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v;
    int i = 0;
    while (i < n) {
        int x;
        cin >> x;
        v.push_back(x);
        i++;
    }
    int k;
    cin >> k;
    sort(v.begin(), v.end());
    printf("%d\n", v[k - 1]);
    return 0;
}
""")

_add("CP15", r"""
int a[100005];
int count_value(int n, int t) {
    int c = 0;
    for (int i = 0; i < n; i++) {
        if (a[i] == t) {
            c = c + 1;
        }
    }
    return c;
}
int main() {
    int n, t;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cin >> t;
    cout << count_value(n, t) << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    int i = 0;
    while (i < n) {
        cin >> v[i];
        i++;
    }
    int t;
    cin >> t;
    int cnt = 0;
    i = 0;
    while (i < n) {
        if (v[i] == t) {
            cnt++;
        }
        i++;
    }
    printf("%d\n", cnt);
    return 0;
}
""")

_add("CP16", r"""
int a[100005];
int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    sort(a, a + n);
    int mid = (n - 1) / 2;
    cout << a[mid] << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    int i = 0;
    while (i < n) {
        cin >> v[i];
        i++;
    }
    sort(v.begin(), v.end());
    int mid = n / 2;
    printf("%d\n", v[mid]);
    return 0;
}
""")

_add("CP17", r"""
int absolute_value(int x) {
    if (x >= 0) {
        return x;
    }
    return -x;
}
int main() {
    int x;
    cin >> x;
    cout << absolute_value(x) << endl;
    return 0;
}
""", r"""
int absolute_value(int x) {
    int r = x;
    if (x < 0) {
        r = 0 - x;
    }
    return r;
}
int main() {
    int x;
    cin >> x;
    printf("%d\n", absolute_value(x));
    return 0;
}
""")

_add("CP18", r"""
int largest_of_three(int a, int b, int c) {
    if (a >= b && a >= c) {
        return a;
    }
    if (b >= a && b >= c) {
        return b;
    }
    return c;
}
int main() {
    int a, b, c;
    cin >> a >> b >> c;
    cout << largest_of_three(a, b, c) + 1 << endl;
    return 0;
}
""", r"""
int largest_of_three(int a, int b, int c) {
    int big;
    if (a > b) {
        big = a;
    } else {
        big = b;
    }
    if (c > big) {
        big = c;
    }
    return big;
}
int main() {
    int a, b, c;
    cin >> a >> b >> c;
    printf("%d\n", largest_of_three(a, b, c) + 1);
    return 0;
}
""")

_add("CP19", r"""
bool is_even(int x) {
    if (x % 2 == 0) {
        return true;
    } else {
        return false;
    }
}
int main() {
    int x;
    cin >> x;
    bool r = is_even(x);
    if (r == true) {
        cout << 1 << endl;
    } else {
        cout << 0 << endl;
    }
    return 0;
}
""", r"""
bool is_even(int x) {
    int rem = x % 2;
    return rem == 0;
}
int main() {
    int x;
    cin >> x;
    printf("%d\n", is_even(x) ? 1 : 0);
    return 0;
}
""")

_add("CP20", r"""
int gcd(int a, int b) {
    while (a % b != 0) {
        int r = a % b;
        a = b;
        b = r;
    }
    return b;
}
int main() {
    int a, b;
    cin >> a >> b;
    cout << gcd(a, b) + 1 << endl;
    return 0;
}
""", r"""
int gcd(int a, int b) {
    if (b == 0) {
        return a;
    }
    return gcd(b, a % b);
}
int main() {
    int a, b;
    cin >> a >> b;
    printf("%d\n", gcd(a, b) + 1);
    return 0;
}
""")

_add("CP21", r"""
int a[100005];
int b[100005];
int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    b[0] = a[n - 1];
    for (int i = 1; i < n; i++) {
        b[i] = a[i - 1];
    }
    for (int i = 0; i < n; i++) {
        if (i > 0) {
            cout << " ";
        }
        cout << b[i];
    }
    cout << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    int i = 0;
    while (i < n) {
        cin >> v[i];
        i++;
    }
    int last = v[n - 1];
    i = n - 1;
    while (i > 0) {
        v[i] = v[i - 1];
        i--;
    }
    v[0] = last;
    i = 0;
    while (i < n) {
        if (i == n - 1) {
            printf("%d\n", v[i]);
        } else {
            printf("%d ", v[i]);
        }
        i++;
    }
    return 0;
}
""")

_add("CP22", r"""
int a[100005];
int sum_last(int n, int k) {
    int s = 0;
    for (int i = n - k; i < n; i++) {
        s += a[i];
    }
    return s;
}
int main() {
    int n, k;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cin >> k;
    cout << sum_last(n, k) << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    int i = 0;
    while (i < n) {
        cin >> v[i];
        i++;
    }
    int k;
    cin >> k;
    int sum = 0;
    int taken = 0;
    i = n - 1;
    while (taken < k) {
        sum += v[i];
        i--;
        taken++;
    }
    printf("%d\n", sum);
    return 0;
}
""")

_add("CP23", r"""
int a[100005];
int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cout << a[n - 2] << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    int prev = 0, cur = 0;
    int i = 0;
    while (i < n) {
        prev = cur;
        cin >> cur;
        i++;
    }
    printf("%d\n", prev);
    return 0;
}
""")

_add("CP24", r"""
int a[100005];
bool valid(int idx, int n) {
    if (idx >= 0 && idx < n) {
        return true;
    }
    return false;
}
int main() {
    int n, idx;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cin >> idx;
    if (valid(idx, n)) {
        cout << a[idx] << endl;
    } else {
        cout << "OUT_OF_RANGE" << endl;
    }
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    int i = 0;
    while (i < n) {
        cin >> v[i];
        i++;
    }
    int idx;
    cin >> idx;
    if (idx < 0 || idx >= n) {
        printf("OUT_OF_RANGE\n");
    } else {
        printf("%d\n", v[idx]);
    }
    return 0;
}
""")

_add("CP25", r"""
string grade(int s) {
    if (s < 0 || s > 100) {
        return "INVALID";
    }
    if (s >= 90) {
        return "A";
    }
    if (s >= 80) {
        return "B";
    }
    if (s >= 70) {
        return "C";
    }
    if (s >= 60) {
        return "D";
    }
    return "F";
}
int main() {
    int score;
    cin >> score;
    cout << grade(score) << endl;
    return 0;
}
""", r"""
int main() {
    int s;
    cin >> s;
    if (s >= 0 && s <= 59) {
        printf("F\n");
    } else if (s >= 60 && s <= 69) {
        printf("D\n");
    } else if (s >= 70 && s <= 79) {
        printf("C\n");
    } else if (s >= 80 && s <= 89) {
        printf("B\n");
    } else if (s >= 90 && s <= 100) {
        printf("A\n");
    } else {
        printf("INVALID\n");
    }
    return 0;
}
""")

_add("CP26", r"""
int cost_for(int w) {
    if (w <= 0) {
        return -1;
    }
    if (w <= 500) {
        return 5;
    }
    if (w <= 2000) {
        return 10;
    }
    if (w <= 10000) {
        return 20;
    }
    return -1;
}
int main() {
    int weight;
    cin >> weight;
    cout << cost_for(weight) << endl;
    return 0;
}
""", r"""
int main() {
    int w;
    cin >> w;
    int cost = -1;
    if (w >= 1 && w <= 500) {
        cost = 5;
    }
    if (w >= 501 && w <= 2000) {
        cost = 10;
    }
    if (w >= 2001 && w <= 10000) {
        cost = 20;
    }
    printf("%d\n", cost);
    return 0;
}
""")

_add("CP27", r"""
string state(int t) {
    if (t >= 100) {
        return "GAS";
    }
    if (t >= 1) {
        return "LIQUID";
    }
    return "SOLID";
}
int main() {
    int t;
    cin >> t;
    cout << state(t) << endl;
    return 0;
}
""", r"""
int main() {
    int t;
    cin >> t;
    if (t > 0 && t < 100) {
        printf("LIQUID\n");
    } else if (t <= 0) {
        printf("SOLID\n");
    } else {
        printf("GAS\n");
    }
    return 0;
}
""")

_add("CP28", r"""
int price(int age) {
    if (age < 0) {
        return -1;
    }
    if (age >= 65) {
        return 8;
    }
    if (age >= 18) {
        return 12;
    }
    if (age >= 6) {
        return 7;
    }
    return 0;
}
int main() {
    int age;
    cin >> age;
    cout << price(age) << endl;
    return 0;
}
""", r"""
int main() {
    int age;
    cin >> age;
    int p;
    if (age >= 0 && age <= 5) {
        p = 0;
    } else if (age >= 6 && age <= 17) {
        p = 7;
    } else if (age >= 18 && age <= 64) {
        p = 12;
    } else if (age >= 65) {
        p = 8;
    } else {
        p = -1;
    }
    printf("%d\n", p);
    return 0;
}
""")

_add("CP29", r"""
string sign_of(int x) {
    if (x == 0) {
        return "ZERO";
    }
    if (x > 0) {
        return "POSITIVE";
    }
    return "NEGATIVE";
}
int main() {
    int x;
    cin >> x;
    cout << sign_of(x) << endl;
    return 0;
}
""", r"""
int main() {
    int x;
    cin >> x;
    if (x > 0) {
        printf("POSITIVE\n");
    } else if (x == 0) {
        printf("ZERO\n");
    } else {
        printf("NEGATIVE\n");
    }
    return 0;
}
""")

_add("CP30", r"""
bool long_enough(string s) {
    int count = 0;
    for (int i = 0; i < (int)s.size(); i++) {
        count++;
    }
    if (count >= 8) {
        return true;
    }
    return false;
}
int main() {
    string line;
    getline(cin, line);
    if (long_enough(line)) {
        cout << "OK" << endl;
    } else {
        cout << "TOO SHORT" << endl;
    }
    return 0;
}
""", r"""
int main() {
    string s;
    getline(cin, s);
    int len = 0;
    while (s[len] != '\0') {
        len++;
    }
    if (len < 8) {
        printf("TOO SHORT\n");
    } else {
        printf("OK\n");
    }
    return 0;
}
""")

_add("CP31", r"""
bool is_multiple(int x, int d) {
    if (x % d == 0) {
        return true;
    }
    return false;
}
int main() {
    int x, p, q;
    cin >> x >> p >> q;
    if (is_multiple(x, p) && is_multiple(x, q)) {
        cout << "YES" << endl;
    } else {
        cout << "NO" << endl;
    }
    return 0;
}
""", r"""
int main() {
    int x, p, q;
    cin >> x >> p >> q;
    int ok = 1;
    if (x % p != 0) {
        ok = 0;
    }
    if (x % q != 0) {
        ok = 0;
    }
    if (ok == 1) {
        printf("YES\n");
    } else {
        printf("NO\n");
    }
    return 0;
}
""")

_add("CP32", r"""
bool is_vowel(char c) {
    char vowels[10] = {'a', 'e', 'i', 'o', 'u', 'A', 'E', 'I', 'O', 'U'};
    for (int i = 0; i < 10; i++) {
        if (c == vowels[i]) {
            return true;
        }
    }
    return false;
}
int main() {
    string line;
    getline(cin, line);
    if (is_vowel(line[0])) {
        cout << "VOWEL" << endl;
    } else {
        cout << "CONSONANT" << endl;
    }
    return 0;
}
""", r"""
int main() {
    string s;
    getline(cin, s);
    char c = s[0];
    if (c >= 'A' && c <= 'Z') {
        c = c + 32;
    }
    if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u') {
        printf("VOWEL\n");
    } else {
        printf("CONSONANT\n");
    }
    return 0;
}
""")

_add("CP33", r"""
long long sum_to(int n) {
    if (n <= 0) {
        return 0;
    }
    long long rest = sum_to(n - 1);
    return rest + n;
}
int main() {
    int n;
    cin >> n;
    cout << sum_to(n) << endl;
    return 0;
}
""", r"""
long long sum_to(int n) {
    if (n < 1) return 0;
    return sum_to(n - 1) + n;
}
int main() {
    int n;
    cin >> n;
    printf("%lld\n", sum_to(n));
    return 0;
}
""")

_add("CP34", r"""
long long power(long long base, int exponent) {
    if (exponent == 0) {
        return 1;
    }
    long long smaller = power(base, exponent - 1);
    return smaller * base;
}
int main() {
    int base, exponent;
    cin >> base >> exponent;
    cout << power(base, exponent) << endl;
    return 0;
}
""", r"""
long long power(int b, int e) {
    if (e <= 0) return 1;
    if (e == 1) return b;
    return power(b, e - 1) * b;
}
int main() {
    int b, e;
    cin >> b >> e;
    printf("%lld\n", power(b, e));
    return 0;
}
""")

_add("CP35", r"""
long long fib(int n) {
    if (n <= 0) {
        return 0;
    }
    if (n == 1) {
        return 1;
    }
    long long a = fib(n - 1);
    long long b = fib(n - 2);
    return a + b;
}
int main() {
    int n;
    cin >> n;
    cout << fib(n) << endl;
    return 0;
}
""", r"""
long long fib(int n) {
    if (n < 2) {
        if (n <= 0) return 0;
        return 1;
    }
    return fib(n - 2) + fib(n - 1);
}
int main() {
    int n;
    cin >> n;
    printf("%lld\n", fib(n));
    return 0;
}
""")

_add("CP36", r"""
int steps(int n) {
    int c = 0;
    while (n > 0) {
        n /= 2;
        c++;
    }
    return c;
}
int main() {
    int n;
    cin >> n;
    cout << steps(n) << endl;
    return 0;
}
""", r"""
int steps(int n) {
    if (n == 0) {
        return 0;
    }
    return 1 + steps(n / 2);
}
int main() {
    int n;
    cin >> n;
    printf("%d\n", steps(n));
    return 0;
}
""")

_add("CP37", r"""
int a[100005];
int find_last(int n, int t) {
    int pos = -1;
    for (int i = 0; i < n; i++) {
        if (a[i] == t) {
            pos = i;
        }
    }
    return pos;
}
int main() {
    int n, t;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cin >> t;
    int pos = find_last(n, t);
    if (pos == -1) {
        cout << "NOT FOUND" << endl;
    } else {
        cout << pos << endl;
    }
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    int i = 0;
    while (i < n) {
        cin >> v[i];
        i++;
    }
    int t;
    cin >> t;
    i = n - 1;
    while (i >= 0 && v[i] != t) {
        i--;
    }
    if (i < 0) {
        printf("NOT FOUND\n");
    } else {
        printf("%d\n", i);
    }
    return 0;
}
""")

_add("CP38", r"""
int main() {
    int count = 0;
    int sum = 0;
    int x;
    while (cin >> x) {
        if (x == -1) {
            break;
        }
        count++;
        sum += x;
    }
    cout << count << " " << sum << endl;
    return 0;
}
""", r"""
int main() {
    int x = 0, n = 0, total = 0;
    do {
        cin >> x;
        if (x != -1) {
            n++;
            total += x;
        }
    } while (x != -1);
    printf("%d %d\n", n, total);
    return 0;
}
""")

_add("CP39", r"""
int a[100005];
int first_negative(int n) {
    for (int i = 0; i < n; i++) {
        if (a[i] < 0) {
            return i;
        }
    }
    return -1;
}
int main() {
    int n;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    int pos = first_negative(n);
    if (pos == -1) {
        cout << "NONE" << endl;
    } else {
        cout << pos << endl;
    }
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    int pos = -1;
    int i = 0;
    while (i < n) {
        int x;
        cin >> x;
        if (x < 0 && pos == -1) {
            pos = i;
        }
        i++;
    }
    if (pos == -1) {
        printf("NONE\n");
    } else {
        printf("%d\n", pos);
    }
    return 0;
}
""")

_add("CP40", r"""
int a[100005];
int main() {
    int n, t;
    cin >> n;
    for (int i = 0; i < n; i++) {
        cin >> a[i];
    }
    cin >> t;
    int idx = n;
    for (int i = 0; i < n; i++) {
        if (a[i] >= t) {
            idx = i;
            break;
        }
    }
    long long sum = 0;
    for (int i = 0; i < idx; i++) {
        sum += a[i];
    }
    cout << idx << " " << sum << endl;
    return 0;
}
""", r"""
int main() {
    int n;
    cin >> n;
    vector<int> v(n);
    int i = 0;
    while (i < n) {
        cin >> v[i];
        i++;
    }
    int t;
    cin >> t;
    long long total = 0;
    i = 0;
    while (i < n) {
        if (v[i] >= t) {
            break;
        }
        total += v[i];
        i++;
    }
    printf("%d %lld\n", i, total);
    return 0;
}
""")
