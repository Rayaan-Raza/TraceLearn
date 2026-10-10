"""C++ diagnostic problem definitions: `CPP-M03` and `CPP-M04`.

Naming conventions inside the reference solutions. The generator and the
verifier rely on them:

1. A function that must return a value ends with `return answer;`.
2. A vector of input values is named `v`.
3. A bounds guard compares an index with `v.size()` using `<`.

Author: Agent 4, C++ test author and quality judge.
Standard: ASD-STE100 Simplified Technical English.
"""
from __future__ import annotations

PROBLEMS: list[dict] = [

    # =====================================================================
    # CPP-M03: printing treated as equivalent to returning
    # =====================================================================
    {
        "id": "CP17",
        "slug": "m03_absolute_value",
        "title": "Absolute Value By A Function",
        "misconception": "CPP-M03",
        "secondary": [],
        "difficulty": "Beginner",
        "topic": "Functions",
        "statement_markdown": (
            "Write a function `int absolute_value(int x)` that returns the "
            "absolute value of `x`.\n\n"
            "The function must **return** the value. It must not print it. "
            "Your `main` reads `x` and prints the value that the function "
            "returns."
        ),
        "input_format": "One line that holds one integer `x`.",
        "output_format": "One line that holds one integer: `|x|`.",
        "constraints": "`-1000000000 <= x <= 1000000000`",
        "examples": [
            {"input": "-7", "output": "7",
             "explanation": "The absolute value of -7 is 7."},
            {"input": "0", "output": "0",
             "explanation": "The absolute value of 0 is 0."},
        ],
        "solution": r'''// CP17 - Absolute Value By A Function
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

int absolute_value(int x) {
    // The value travels through the return channel.
    const int answer = x < 0 ? -x : x;
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    std::cout << absolute_value(x) << '\n';
    return 0;
}
''',
        "mutation": [
            ("    return answer;",
             "    std::cout << answer << '\\n';\n    return 0;"),
        ],
        "render": lambda a: f"{a['x']}\n",
        "model": lambda a: f"{abs(a['x'])}\n",
        "cases": [
            {"kind": "visible", "x": -7},
            {"kind": "visible", "boundary": True, "x": 0},
            {"kind": "visible", "x": 42},
            {"kind": "hidden", "x": -1},
            {"kind": "hidden", "x": 999},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "x": -7},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "x": 0},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at what your function does with the result. Does the caller receive it, or does the function send it away?",
             "related_misconception_id": "CPP-M03"},
            {"order": 2, "hint_text": "A function that returns a value uses `return`. Printed text reaches the screen, not the expression that called the function.",
             "related_misconception_id": "CPP-M03"},
            {"order": 3, "hint_text": "Check the last statement of your function. Replace `std::cout << ...` with `return ...`.",
             "related_misconception_id": "CPP-M03"},
        ],
    },
    {
        "id": "CP18",
        "slug": "m03_max_of_three",
        "title": "Largest Of Three Values",
        "misconception": "CPP-M03",
        "secondary": ["CPP-M05"],
        "difficulty": "Beginner",
        "topic": "Functions",
        "statement_markdown": (
            "Write a function `int largest_of_three(int a, int b, int c)` that "
            "returns the largest of the three values.\n\n"
            "The function must **return** the value. Your `main` reads the "
            "three values and prints `largest_of_three(a, b, c) + 1`."
        ),
        "input_format": "One line that holds three integers `a`, `b` and `c`.",
        "output_format": "One line that holds the largest value plus one.",
        "constraints": "Each value is between -1000000000 and 1000000000.",
        "examples": [
            {"input": "3 9 5", "output": "10",
             "explanation": "The largest value is 9. The program prints 9 + 1 = 10."},
            {"input": "-1 -5 -3", "output": "0",
             "explanation": "The largest value is -1. The program prints -1 + 1 = 0."},
        ],
        "solution": r'''// CP18 - Largest Of Three Values
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

int largest_of_three(int a, int b, int c) {
    int answer = a;
    if (b > answer) {
        answer = b;
    }
    if (c > answer) {
        answer = c;
    }
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int a = 0;
    int b = 0;
    int c = 0;
    if (!(std::cin >> a >> b >> c)) {
        return 0;
    }

    std::cout << (largest_of_three(a, b, c) + 1) << '\n';
    return 0;
}
''',
        "mutation": [
            ("    return answer;",
             "    std::cout << answer << '\\n';\n    return 0;"),
        ],
        "render": lambda a: f"{a['a']} {a['b']} {a['c']}\n",
        "model": lambda a: f"{max(a['a'], a['b'], a['c']) + 1}\n",
        "cases": [
            {"kind": "visible", "a": 3, "b": 9, "c": 5},
            {"kind": "visible", "boundary": True, "a": -1, "b": -5, "c": -3},
            {"kind": "visible", "a": 7, "b": 7, "c": 2},
            {"kind": "hidden", "a": 0, "b": 0, "c": 0},
            {"kind": "hidden", "a": -100, "b": 100, "c": 0},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "a": 3, "b": 9, "c": 5},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "a": -1, "b": -5, "c": -3},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the end of your function. What value does the expression in `main` receive?",
             "related_misconception_id": "CPP-M03"},
            {"order": 2, "hint_text": "A function sends a value back with `return`. Printed text does not reach the caller.",
             "related_misconception_id": "CPP-M03"},
            {"order": 3, "hint_text": "Check the last statement of your function. Write `return answer;`.",
             "related_misconception_id": "CPP-M03"},
        ],
    },
    {
        "id": "CP19",
        "slug": "m03_is_even",
        "title": "Even Or Odd By A Function",
        "misconception": "CPP-M03",
        "secondary": [],
        "difficulty": "Beginner",
        "topic": "Functions",
        "statement_markdown": (
            "Write a function `bool is_even(int x)` that returns `true` when "
            "`x` is even.\n\n"
            "The function must **return** the result. Your `main` reads `x` and "
            "prints `1` when the function returns `true`. It prints `0` "
            "otherwise."
        ),
        "input_format": "One line that holds one integer `x`.",
        "output_format": "One line that holds `1` or `0`.",
        "constraints": "`-1000000000 <= x <= 1000000000`",
        "examples": [
            {"input": "4", "output": "1",
             "explanation": "4 is even. The program prints 1."},
            {"input": "7", "output": "0",
             "explanation": "7 is odd. The program prints 0."},
        ],
        "solution": r'''// CP19 - Even Or Odd By A Function
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

bool is_even(int x) {
    // The result travels through the return channel.
    const bool answer = (x % 2 == 0);
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    std::cout << (is_even(x) ? 1 : 0) << '\n';
    return 0;
}
''',
        "mutation": [
            ("    return answer;",
             "    std::cout << (answer ? 1 : 0) << '\\n';\n    return false;"),
        ],
        "render": lambda a: f"{a['x']}\n",
        "model": lambda a: f"{1 if a['x'] % 2 == 0 else 0}\n",
        "cases": [
            {"kind": "visible", "x": 4},
            {"kind": "visible", "boundary": True, "x": 7},
            {"kind": "visible", "x": 0},
            {"kind": "hidden", "x": -6},
            {"kind": "hidden", "x": 13},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "x": 4},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "x": 0},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at what your function returns. Does the caller receive `true`, or a default value?",
             "related_misconception_id": "CPP-M03"},
            {"order": 2, "hint_text": "A bool function returns the result. Printing the result does not fill the return channel.",
             "related_misconception_id": "CPP-M03"},
            {"order": 3, "hint_text": "Check the last statement of your function. Write `return answer;`.",
             "related_misconception_id": "CPP-M03"},
        ],
    },
    {
        "id": "CP20",
        "slug": "m03_greatest_common_divisor",
        "title": "Greatest Common Divisor By A Function",
        "misconception": "CPP-M03",
        "secondary": ["CPP-M07"],
        "difficulty": "Intermediate",
        "topic": "Functions",
        "statement_markdown": (
            "Write a function `int gcd(int a, int b)` that returns the greatest "
            "common divisor of `a` and `b`.\n\n"
            "Use the Euclid loop. The function must **return** the result. Your "
            "`main` reads `a` and `b` and prints `gcd(a, b) + 1`."
        ),
        "input_format": "One line that holds two integers `a` and `b`.",
        "output_format": "One line that holds the greatest common divisor plus one.",
        "constraints": "`1 <= a, b <= 1000000000`",
        "examples": [
            {"input": "12 18", "output": "7",
             "explanation": "The greatest common divisor is 6. The program prints 6 + 1 = 7."},
            {"input": "7 5", "output": "2",
             "explanation": "The greatest common divisor is 1. The program prints 1 + 1 = 2."},
        ],
        "solution": r'''// CP20 - Greatest Common Divisor By A Function
// Target misconception: CPP-M03 (printing treated as equivalent to returning)
#include <iostream>

int gcd(int a, int b) {
    // Each pass makes the pair smaller. The loop reaches the base case.
    while (b != 0) {
        const int remainder = a % b;
        a = b;
        b = remainder;
    }
    const int answer = a;
    return answer;
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int a = 0;
    int b = 0;
    if (!(std::cin >> a >> b)) {
        return 0;
    }

    std::cout << (gcd(a, b) + 1) << '\n';
    return 0;
}
''',
        "mutation": [
            ("    return answer;",
             "    std::cout << answer << '\\n';\n    return 0;"),
        ],
        "render": lambda a: f"{a['a']} {a['b']}\n",
        "model": lambda a: f"{_gcd(a['a'], a['b']) + 1}\n",
        "cases": [
            {"kind": "visible", "a": 12, "b": 18},
            {"kind": "visible", "boundary": True, "a": 7, "b": 5},
            {"kind": "visible", "a": 100, "b": 100},
            {"kind": "hidden", "a": 1, "b": 1},
            {"kind": "hidden", "a": 1071, "b": 462},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "a": 12, "b": 18},
            {"kind": "diagnostic", "tag": "print_in_place_of_return", "a": 7, "b": 5},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at what your function gives back to `main`. Is the divisor in the expression, or on the screen?",
             "related_misconception_id": "CPP-M03"},
            {"order": 2, "hint_text": "The Euclid loop computes the divisor. A separate `return` statement sends it to the caller.",
             "related_misconception_id": "CPP-M03"},
            {"order": 3, "hint_text": "Check the last statement of your function. Write `return answer;`.",
             "related_misconception_id": "CPP-M03"},
        ],
    },

    # =====================================================================
    # CPP-M04: index equal to container size treated as valid
    # =====================================================================
    {
        "id": "CP21",
        "slug": "m04_circular_shift_right",
        "title": "Shift The Values One Place Right",
        "misconception": "CPP-M04",
        "secondary": ["CPP-M01"],
        "difficulty": "Beginner",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n` and then `n` integers. Move every value one place to the "
            "right. The last value moves to the front.\n\n"
            "Print all `n` values on one line, separated by a space. The last "
            "value is read from index `size() - 1`. The index `size()` is "
            "never valid."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers separated by spaces."
        ),
        "output_format": "One line that holds the new order, separated by spaces.",
        "constraints": "`1 <= n <= 100000`",
        "examples": [
            {"input": "4\n1 2 3 4", "output": "4 1 2 3",
             "explanation": "The last value 4 moves to the front. The others move one place right."},
            {"input": "1\n7", "output": "7",
             "explanation": "One value stays in place."},
        ],
        "solution": r'''// CP21 - Shift The Values One Place Right
// Target misconception: CPP-M04 (index equal to container size treated as valid)
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }
    if (n < 1) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    // The last valid index is size() - 1. `at()` reports a wrong index.
    const long long carry = v.at(v.size() - 1);
    for (int i = n - 2; i >= 0; --i) {
        v[static_cast<std::size_t>(i) + 1] = v[static_cast<std::size_t>(i)];
    }
    v[0] = carry;

    for (std::size_t i = 0; i < v.size(); ++i) {
        std::cout << v[i];
        if (i + 1 < v.size()) {
            std::cout << ' ';
        }
    }
    std::cout << '\n';
    return 0;
}
''',
        "mutation": [
            ("v.at(v.size() - 1)", "v.at(v.size())"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n"),
        "model": lambda a: " ".join(
            [str(a["vals"][-1])] + [str(x) for x in a["vals"][:-1]]) + "\n",
        "cases": [
            {"kind": "visible", "vals": [1, 2, 3, 4]},
            {"kind": "visible", "boundary": True, "vals": [7]},
            {"kind": "visible", "vals": [5, 6]},
            {"kind": "hidden", "vals": [10, 20, 30, 40, 50]},
            {"kind": "hidden", "vals": [-1, -2, -3]},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [7]},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [1, 2, 3]},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the index that reads the last value. Is that index inside the vector?",
             "related_misconception_id": "CPP-M04"},
            {"order": 2, "hint_text": "A vector of size N holds the indices 0 to N-1. The index N is one place past the end.",
             "related_misconception_id": "CPP-M04"},
            {"order": 3, "hint_text": "Check your last index. Write `size() - 1`, not `size()`.",
             "related_misconception_id": "CPP-M04"},
        ],
    },
    {
        "id": "CP22",
        "slug": "m04_sum_of_last_k",
        "title": "Sum Of The Last K Values",
        "misconception": "CPP-M04",
        "secondary": ["CPP-M01"],
        "difficulty": "Beginner",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n`, then `n` integers, then one integer `k`. Print the sum "
            "of the last `k` values.\n\n"
            "The first of those values sits at index `size() - k`. The index "
            "`size()` is never valid."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers. Line 3 holds `k`."
        ),
        "output_format": "One line that holds one integer: the sum.",
        "constraints": "`1 <= k <= n <= 100000`",
        "examples": [
            {"input": "5\n10 20 30 40 50\n2", "output": "90",
             "explanation": "The last two values are 40 and 50. The sum is 90."},
            {"input": "1\n7\n1", "output": "7",
             "explanation": "The last one value is 7. The sum is 7."},
        ],
        "solution": r'''// CP22 - Sum Of The Last K Values
// Target misconception: CPP-M04 (index equal to container size treated as valid)
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }
    if (n < 1) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    int k = 1;
    if (!(std::cin >> k)) {
        return 0;
    }

    // The first of the last k values is at index size() - k.
    const std::size_t start = v.size() - static_cast<std::size_t>(k);
    long long answer = 0;
    for (std::size_t i = start; i < v.size(); ++i) {
        answer += v[i];
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("const std::size_t start = v.size() - static_cast<std::size_t>(k);",
             "const std::size_t start = v.size();"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n{a['k']}\n"),
        "model": lambda a: f"{sum(a['vals'][len(a['vals']) - a['k']:])}\n",
        "cases": [
            {"kind": "visible", "vals": [10, 20, 30, 40, 50], "k": 2},
            {"kind": "visible", "boundary": True, "vals": [7], "k": 1},
            {"kind": "visible", "vals": [1, 2, 3], "k": 3},
            {"kind": "hidden", "vals": [5, 5, 5, 5], "k": 2},
            {"kind": "hidden", "vals": [-1, -2, -3, -4], "k": 1},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [7], "k": 1},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [3, 1, 4, 1, 5], "k": 2},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the index where your loop starts. Is that index a member of the vector?",
             "related_misconception_id": "CPP-M04"},
            {"order": 2, "hint_text": "The first of the last k values is at index size() - k. A start index of size() reads nothing.",
             "related_misconception_id": "CPP-M04"},
            {"order": 3, "hint_text": "Check the start index. Subtract `k` from `size()` before you start the loop.",
             "related_misconception_id": "CPP-M04"},
        ],
    },
    {
        "id": "CP23",
        "slug": "m04_second_last_value",
        "title": "Value Before The Last Value",
        "misconception": "CPP-M04",
        "secondary": [],
        "difficulty": "Beginner",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n` and then `n` integers. Print the value that sits one "
            "place before the last value.\n\n"
            "That value is at index `size() - 2`. The index `size()` is never "
            "valid."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers separated by spaces."
        ),
        "output_format": "One line that holds one integer.",
        "constraints": "`2 <= n <= 100000`",
        "examples": [
            {"input": "2\n5 9", "output": "5",
             "explanation": "The value one place before the last is 5."},
            {"input": "5\n1 2 3 4 5", "output": "4",
             "explanation": "The last value is 5. The value before it is 4."},
        ],
        "solution": r'''// CP23 - Value Before The Last Value
// Target misconception: CPP-M04 (index equal to container size treated as valid)
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }
    if (n < 2) {
        // The contract holds at least two values.
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    // The value before the last is at index size() - 2.
    const long long answer = v.at(v.size() - 2);

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("v.at(v.size() - 2)", "v.at(v.size())"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n"),
        "model": lambda a: f"{a['vals'][-2]}\n",
        "cases": [
            {"kind": "visible", "vals": [5, 9]},
            {"kind": "visible", "boundary": True, "vals": [1, 2, 3, 4, 5]},
            {"kind": "visible", "vals": [-7, 3]},
            {"kind": "hidden", "vals": [10, 20, 30]},
            {"kind": "hidden", "vals": [100, 200, 300, 400]},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [5, 9]},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [9, 8, 7, 6]},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the index in your access. Does that index point at a member of the vector?",
             "related_misconception_id": "CPP-M04"},
            {"order": 2, "hint_text": "The last member is at size() - 1. The member before it is at size() - 2.",
             "related_misconception_id": "CPP-M04"},
            {"order": 3, "hint_text": "Check your index. Write `size() - 2` for this task.",
             "related_misconception_id": "CPP-M04"},
        ],
    },
    {
        "id": "CP24",
        "slug": "m04_index_guard",
        "title": "Read A Value At A Given Index",
        "misconception": "CPP-M04",
        "secondary": ["CPP-M01"],
        "difficulty": "Beginner",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n`, then `n` integers, then one index `i`. Print the value "
            "at index `i`. When `i` is not a valid index, print "
            "`OUT_OF_RANGE`.\n\n"
            "A valid index is in the range `0` to `size() - 1`. The index "
            "`size()` is **not** valid."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers. Line 3 holds `i`."
        ),
        "output_format": "One line that holds the value, or `OUT_OF_RANGE`.",
        "constraints": "`1 <= n <= 100000`, `-1 <= i <= n`",
        "examples": [
            {"input": "5\n10 20 30 40 50\n4", "output": "50",
             "explanation": "Index 4 is the last valid index. The value is 50."},
            {"input": "5\n10 20 30 40 50\n5", "output": "OUT_OF_RANGE",
             "explanation": "Index 5 equals size(). It is not valid."},
        ],
        "solution": r'''// CP24 - Read A Value At A Given Index
// Target misconception: CPP-M04 (index equal to container size treated as valid)
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }
    if (n < 1) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    long long i = 0;
    if (!(std::cin >> i)) {
        return 0;
    }

    // A valid index is smaller than size(). `at()` reports a wrong index.
    if (i >= 0 && static_cast<std::size_t>(i) < v.size()) {
        std::cout << v.at(static_cast<std::size_t>(i)) << '\n';
    } else {
        std::cout << "OUT_OF_RANGE" << '\n';
    }
    return 0;
}
''',
        "mutation": [
            ("static_cast<std::size_t>(i) < v.size()",
             "static_cast<std::size_t>(i) <= v.size()"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n{a['i']}\n"),
        "model": lambda a: (
            f"{a['vals'][a['i']]}\n" if 0 <= a['i'] < len(a['vals']) else "OUT_OF_RANGE\n"),
        "cases": [
            {"kind": "visible", "vals": [10, 20, 30, 40, 50], "i": 4},
            {"kind": "visible", "boundary": True, "vals": [10, 20, 30, 40, 50], "i": 5},
            {"kind": "visible", "vals": [10, 20, 30, 40, 50], "i": 0},
            {"kind": "hidden", "vals": [7], "i": 1},
            {"kind": "hidden", "vals": [1, 2, 3], "i": -1},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [10, 20, 30, 40, 50], "i": 5},
            {"kind": "diagnostic", "tag": "index_equal_to_size", "vals": [7, 8, 9], "i": 3},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your guard. Which index does your condition accept as the largest valid index?",
             "related_misconception_id": "CPP-M04"},
            {"order": 2, "hint_text": "A valid index is smaller than size(). The index size() is one place past the end.",
             "related_misconception_id": "CPP-M04"},
            {"order": 3, "hint_text": "Check the comparison in your guard. Use `<`, not `<=`.",
             "related_misconception_id": "CPP-M04"},
        ],
    },
]


def _gcd(a: int, b: int) -> int:
    """Return the greatest common divisor. The helper is outside the trials."""
    while b:
        a, b = b, a % b
    return abs(a)
