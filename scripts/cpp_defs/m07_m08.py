"""C++ diagnostic problem definitions: `CPP-M07` and `CPP-M08`.

Naming conventions inside the reference solutions. The generator and the
verifier rely on them:

1. A recursive function reduces its argument by one on the recursive path.
2. A loop that searches for a value changes its index on every iteration.
3. A sentinel loop tests the sentinel in its condition.

Author: Agent 4, C++ test author and quality judge.
Standard: ASD-STE100 Simplified Technical English.
"""
from __future__ import annotations

PROBLEMS: list[dict] = [

    # =====================================================================
    # CPP-M07: recursion or iteration fails to make progress
    # =====================================================================
    {
        "id": "CP33",
        "slug": "m07_sum_to_n_recursive",
        "title": "Sum From One To N By Recursion",
        "misconception": "CPP-M07",
        "secondary": ["CPP-M08"],
        "difficulty": "Beginner",
        "topic": "Recursion",
        "statement_markdown": (
            "Read one integer `n`. Print the sum `1 + 2 + ... + n`.\n\n"
            "Use a recursive function `long long sum_to(int n)`. The base case "
            "is `n <= 0`. Each recursive call must come nearer to the base "
            "case."
        ),
        "input_format": "One line that holds one integer `n`.",
        "output_format": "One line that holds one integer: the sum.",
        "constraints": "`0 <= n <= 1000`",
        "examples": [
            {"input": "5", "output": "15",
             "explanation": "The sum 1 + 2 + 3 + 4 + 5 is 15."},
            {"input": "0", "output": "0",
             "explanation": "The base case gives 0. There is nothing to add."},
        ],
        "solution": r'''// CP33 - Sum From One To N By Recursion
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

long long sum_to(int n) {
    // Base case.
    if (n <= 0) {
        return 0;
    }
    // Each call passes a smaller argument. The state reaches the base case.
    return n + sum_to(n - 1);
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::cout << sum_to(n) << '\n';
    return 0;
}
''',
        "mutation": [
            ("    return n + sum_to(n - 1);", "    return n + sum_to(n);"),
        ],
        "render": lambda a: f"{a['n']}\n",
        "model": lambda a: f"{sum(range(1, a['n'] + 1))}\n",
        "cases": [
            {"kind": "visible", "n": 5},
            {"kind": "visible", "boundary": True, "n": 0},
            {"kind": "visible", "n": 1},
            {"kind": "hidden", "n": 100},
            {"kind": "hidden", "n": 1000},
            {"kind": "diagnostic", "tag": "no_progress", "n": 1},
            {"kind": "diagnostic", "tag": "no_progress", "n": 6},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the argument in your recursive call. Does that argument come nearer to the base case?",
             "related_misconception_id": "CPP-M07"},
            {"order": 2, "hint_text": "A recursive call must change the state. A call with the same argument never reaches the base case.",
             "related_misconception_id": "CPP-M07"},
            {"order": 3, "hint_text": "Check the argument in your call. Write `sum_to(n - 1)`, not `sum_to(n)`.",
             "related_misconception_id": "CPP-M07"},
        ],
    },
    {
        "id": "CP34",
        "slug": "m07_power_recursive",
        "title": "Power By Recursion",
        "misconception": "CPP-M07",
        "secondary": ["CPP-M03"],
        "difficulty": "Beginner",
        "topic": "Recursion",
        "statement_markdown": (
            "Read two integers `base` and `exponent`. Print `base` to the "
            "power of `exponent`.\n\n"
            "Use a recursive function. The base case is `exponent == 0`. Each "
            "recursive call must reduce the exponent."
        ),
        "input_format": "One line that holds `base` and `exponent`.",
        "output_format": "One line that holds one integer.",
        "constraints": "`1 <= base <= 10`, `0 <= exponent <= 18`",
        "examples": [
            {"input": "2 10", "output": "1024",
             "explanation": "2 to the power of 10 is 1024."},
            {"input": "7 0", "output": "1",
             "explanation": "Any number to the power of 0 is 1."},
        ],
        "solution": r'''// CP34 - Power By Recursion
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

long long power(int base, int exponent) {
    // Base case.
    if (exponent == 0) {
        return 1;
    }
    // Each call reduces the exponent by one.
    return base * power(base, exponent - 1);
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int base = 1;
    int exponent = 0;
    if (!(std::cin >> base >> exponent)) {
        return 0;
    }

    std::cout << power(base, exponent) << '\n';
    return 0;
}
''',
        "mutation": [
            ("    return base * power(base, exponent - 1);",
             "    return base * power(base, exponent);"),
        ],
        "render": lambda a: f"{a['base']} {a['exponent']}\n",
        "model": lambda a: f"{a['base'] ** a['exponent']}\n",
        "cases": [
            {"kind": "visible", "base": 2, "exponent": 10},
            {"kind": "visible", "boundary": True, "base": 7, "exponent": 0},
            {"kind": "visible", "base": 3, "exponent": 1},
            {"kind": "hidden", "base": 5, "exponent": 4},
            {"kind": "hidden", "base": 10, "exponent": 6},
            {"kind": "diagnostic", "tag": "no_progress", "base": 3, "exponent": 1},
            {"kind": "diagnostic", "tag": "no_progress", "base": 2, "exponent": 5},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the exponent in your recursive call. Does that value come nearer to zero?",
             "related_misconception_id": "CPP-M07"},
            {"order": 2, "hint_text": "The base case holds exponent == 0. A call must reduce the exponent to reach it.",
             "related_misconception_id": "CPP-M07"},
            {"order": 3, "hint_text": "Check the argument in your call. Write `power(base, exponent - 1)`.",
             "related_misconception_id": "CPP-M07"},
        ],
    },
    {
        "id": "CP35",
        "slug": "m07_fibonacci_recursive",
        "title": "Fibonacci Number By Recursion",
        "misconception": "CPP-M07",
        "secondary": [],
        "difficulty": "Intermediate",
        "topic": "Recursion",
        "statement_markdown": (
            "Read one integer `n`. Print the `n`-th Fibonacci number.\n\n"
            "The series starts with `fib(0) == 0` and `fib(1) == 1`. Use a "
            "recursive function. The two base cases are `n <= 0` and "
            "`n == 1`."
        ),
        "input_format": "One line that holds one integer `n`.",
        "output_format": "One line that holds one integer.",
        "constraints": "`0 <= n <= 30`",
        "examples": [
            {"input": "10", "output": "55",
             "explanation": "The series is 0, 1, 1, 2, 3, 5, 8, 13, 21, 34, 55."},
            {"input": "0", "output": "0",
             "explanation": "The first base case gives 0."},
        ],
        "solution": r'''// CP35 - Fibonacci Number By Recursion
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

long long fibonacci(int n) {
    // Base case one.
    if (n <= 0) {
        return 0;
    }
    // Base case two.
    if (n == 1) {
        return 1;
    }
    // Each call passes a smaller argument.
    return fibonacci(n - 1) + fibonacci(n - 2);
}

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::cout << fibonacci(n) << '\n';
    return 0;
}
''',
        "mutation": [
            ("    return fibonacci(n - 1) + fibonacci(n - 2);",
             "    return fibonacci(n - 1) + fibonacci(n);"),
        ],
        "render": lambda a: f"{a['n']}\n",
        "model": lambda a: f"{_fib(a['n'])}\n",
        "cases": [
            {"kind": "visible", "n": 10},
            {"kind": "visible", "boundary": True, "n": 0},
            {"kind": "visible", "n": 1},
            {"kind": "hidden", "n": 5},
            {"kind": "hidden", "n": 20},
            {"kind": "diagnostic", "tag": "no_progress", "n": 5},
            {"kind": "diagnostic", "tag": "no_progress", "n": 12},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the two arguments in your recursive call. Do both come nearer to a base case?",
             "related_misconception_id": "CPP-M07"},
            {"order": 2, "hint_text": "fib(n) calls fib(n-1) and fib(n-2). Both arguments are smaller than n.",
             "related_misconception_id": "CPP-M07"},
            {"order": 3, "hint_text": "Check the second argument in your call. Write `fibonacci(n - 2)`.",
             "related_misconception_id": "CPP-M07"},
        ],
    },
    {
        "id": "CP36",
        "slug": "m07_halving_steps",
        "title": "Count The Halving Steps",
        "misconception": "CPP-M07",
        "secondary": ["CPP-M08"],
        "difficulty": "Beginner",
        "topic": "Loops",
        "statement_markdown": (
            "Read one integer `n`. Count how many times you must halve `n` "
            "(integer division) before it becomes `0`.\n\n"
            "For example, `8` becomes `4`, then `2`, then `1`, then `0`. That "
            "is 4 steps."
        ),
        "input_format": "One line that holds one integer `n`.",
        "output_format": "One line that holds one integer: the step count.",
        "constraints": "`0 <= n <= 1000000000`",
        "examples": [
            {"input": "8", "output": "4",
             "explanation": "The chain is 8, 4, 2, 1, 0. The count is 4."},
            {"input": "0", "output": "0",
             "explanation": "n is already 0. The count is 0."},
        ],
        "solution": r'''// CP36 - Count The Halving Steps
// Target misconception: CPP-M07 (recursion or iteration fails to make progress)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long answer = 0;
    // Each pass halves n. The state approaches the exit condition.
    while (n > 0) {
        n /= 2;
        ++answer;
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("        n /= 2;\n        ++answer;", "        ++answer;"),
        ],
        "render": lambda a: f"{a['n']}\n",
        "model": lambda a: f"{_halving_steps(a['n'])}\n",
        "cases": [
            {"kind": "visible", "n": 8},
            {"kind": "visible", "boundary": True, "n": 0},
            {"kind": "visible", "n": 1},
            {"kind": "hidden", "n": 100},
            {"kind": "hidden", "n": 1000000000},
            {"kind": "diagnostic", "tag": "no_progress", "n": 1},
            {"kind": "diagnostic", "tag": "no_progress", "n": 64},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your loop body. Which statement changes `n`?",
             "related_misconception_id": "CPP-M07"},
            {"order": 2, "hint_text": "A loop that counts steps must change the value it tests. Otherwise the condition stays true.",
             "related_misconception_id": "CPP-M07"},
            {"order": 3, "hint_text": "Check your loop body. Write `n /= 2;` before you count the step.",
             "related_misconception_id": "CPP-M07"},
        ],
    },

    # =====================================================================
    # CPP-M08: loop fails to update its exit condition
    # =====================================================================
    {
        "id": "CP37",
        "slug": "m08_last_position_of_value",
        "title": "Last Position Of A Value",
        "misconception": "CPP-M08",
        "secondary": ["CPP-M04"],
        "difficulty": "Beginner",
        "topic": "Search",
        "statement_markdown": (
            "Read `n`, then `n` integers, then one target value `t`. Print the "
            "last position of `t`. Print `NOT FOUND` when `t` is absent.\n\n"
            "Scan the list from the end. Your loop must stop when the list "
            "ends."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers. Line 3 holds `t`."
        ),
        "output_format": "One line that holds a position, or `NOT FOUND`.",
        "constraints": "`1 <= n <= 100000`. Each value is between -1000000000 and 1000000000.",
        "examples": [
            {"input": "5\n10 20 30 20 50\n20", "output": "3",
             "explanation": "The value 20 sits at positions 1 and 3. The last position is 3."},
            {"input": "3\n1 2 3\n9", "output": "NOT FOUND",
             "explanation": "The value 9 is absent. The loop scans the full list and stops."},
        ],
        "solution": r'''// CP37 - Last Position Of A Value
// Target misconception: CPP-M08 (loop fails to update its exit condition)
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

    long long target = 0;
    if (!(std::cin >> target)) {
        return 0;
    }

    // Scan from the end. The index changes on every pass.
    for (int i = n - 1; i >= 0; --i) {
        if (v[static_cast<std::size_t>(i)] == target) {
            std::cout << i << '\n';
            return 0;
        }
    }

    std::cout << "NOT FOUND" << '\n';
    return 0;
}
''',
        "mutation": [
            ("    for (int i = n - 1; i >= 0; --i) {",
             "    for (int i = n - 1; i >= 0; ) {"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n{a['t']}\n"),
        "model": lambda a: _last_position(a["vals"], a["t"]) + "\n",
        "cases": [
            {"kind": "visible", "vals": [10, 20, 30, 20, 50], "t": 20},
            {"kind": "visible", "boundary": True, "vals": [1, 2, 3], "t": 9},
            {"kind": "visible", "vals": [5, 5, 5], "t": 5},
            {"kind": "hidden", "vals": [7, 1, 7, 2, 7], "t": 7},
            {"kind": "hidden", "vals": [4, 4], "t": 4},
            {"kind": "diagnostic", "tag": "exit_condition_not_updated", "vals": [1, 2, 3], "t": 9},
            {"kind": "diagnostic", "tag": "exit_condition_not_updated", "vals": [8, 8, 8], "t": 1},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your loop header. Which part of it changes the index?",
             "related_misconception_id": "CPP-M08"},
            {"order": 2, "hint_text": "A `for` loop has three parts. The third part runs after each pass. A missing third part never advances the index.",
             "related_misconception_id": "CPP-M08"},
            {"order": 3, "hint_text": "Check the third part of your `for` header. Write `--i` when you scan from the end.",
             "related_misconception_id": "CPP-M08"},
        ],
    },
    {
        "id": "CP38",
        "slug": "m08_sentinel_count_and_sum",
        "title": "Read Values Until A Sentinel",
        "misconception": "CPP-M08",
        "secondary": ["CPP-M07"],
        "difficulty": "Beginner",
        "topic": "Loops",
        "statement_markdown": (
            "Read integers one by one. The value `-1` is the sentinel. It is "
            "not a data value.\n\n"
            "Print the count of the data values and their sum, separated by a "
            "space. Your loop must stop at the sentinel."
        ),
        "input_format": "One line that holds the data values and then `-1`.",
        "output_format": "One line that holds the count and the sum.",
        "constraints": "Each data value is between 0 and 1000. The input holds 1 to 100 data values.",
        "examples": [
            {"input": "5 3 7 -1", "output": "3 15",
             "explanation": "There are three data values. Their sum is 15."},
            {"input": "1000 0 500 -1", "output": "3 1500",
             "explanation": "The three data values sum to 1500. The sentinel -1 stops the read."},
        ],
        "solution": r'''// CP38 - Read Values Until A Sentinel
// Target misconception: CPP-M08 (loop fails to update its exit condition)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long answer = 0;
    long long total = 0;
    long long x = 0;
    // The condition tests the sentinel on every pass.
    while (std::cin >> x && x != -1) {
        ++answer;
        total += x;
    }

    std::cout << answer << ' ' << total << '\n';
    return 0;
}
''',
        "mutation": [
            ("    while (std::cin >> x && x != -1) {",
             "    while (std::cin >> x) {"),
        ],
        "render": lambda a: f"{' '.join(str(x) for x in a['vals'])} -1\n",
        "model": lambda a: f"{len(a['vals'])} {sum(a['vals'])}\n",
        "cases": [
            {"kind": "visible", "vals": [5, 3, 7]},
            {"kind": "hidden", "boundary": True, "vals": []},
            {"kind": "visible", "vals": [1000, 0, 500]},            {"kind": "hidden", "vals": [42]},
            {"kind": "hidden", "vals": [1, 1, 1, 1, 1]},
            {"kind": "diagnostic", "tag": "sentinel_not_detected", "vals": [5, 3, 7]},
            {"kind": "diagnostic", "tag": "sentinel_not_detected", "vals": [10, 20]},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the condition of your read loop. Which value stops the loop?",
             "related_misconception_id": "CPP-M08"},
            {"order": 2, "hint_text": "A sentinel loop tests the sentinel on every pass. A condition that only tests the read never sees the sentinel.",
             "related_misconception_id": "CPP-M08"},
            {"order": 3, "hint_text": "Check your loop condition. Write `std::cin >> x && x != -1`.",
             "related_misconception_id": "CPP-M08"},
        ],
    },
    {
        "id": "CP39",
        "slug": "m08_first_negative_position",
        "title": "First Negative Value Position",
        "misconception": "CPP-M08",
        "secondary": ["CPP-M04"],
        "difficulty": "Beginner",
        "topic": "Search",
        "statement_markdown": (
            "Read `n` and then `n` integers. Print the position of the first "
            "negative value. Print `NONE` when there is no negative value.\n\n"
            "Your loop must stop when the list ends."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers separated by spaces."
        ),
        "output_format": "One line that holds a position, or `NONE`.",
        "constraints": "`1 <= n <= 100000`. Each value is between -1000000000 and 1000000000.",
        "examples": [
            {"input": "4\n4 -1 6 -2", "output": "1",
             "explanation": "The first negative value is at position 1."},
            {"input": "3\n1 2 3", "output": "NONE",
             "explanation": "There is no negative value. The loop scans the full list."},
        ],
        "solution": r'''// CP39 - First Negative Value Position
// Target misconception: CPP-M08 (loop fails to update its exit condition)
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

    long long answer = -1;
    // The index changes on every pass.
    for (int i = 0; i < n; ++i) {
        if (v[static_cast<std::size_t>(i)] < 0) {
            answer = i;
            break;
        }
    }

    if (answer < 0) {
        std::cout << "NONE" << '\n';
    } else {
        std::cout << answer << '\n';
    }
    return 0;
}
''',
        "mutation": [
            ("    for (int i = 0; i < n; ++i) {\n        if (v[static_cast<std::size_t>(i)] < 0) {",
             "    for (int i = 0; i < n; ) {\n        if (v[static_cast<std::size_t>(i)] < 0) {"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n"),
        "model": lambda a: _first_negative(a["vals"]) + "\n",
        "cases": [
            {"kind": "visible", "vals": [4, -1, 6, -2]},
            {"kind": "visible", "boundary": True, "vals": [1, 2, 3]},
            {"kind": "visible", "vals": [-5, 1, 2]},
            {"kind": "hidden", "vals": [0, 0, -1]},
            {"kind": "hidden", "vals": [9, 9, 9]},
            {"kind": "diagnostic", "tag": "exit_condition_not_updated", "vals": [1, 2, 3]},
            {"kind": "diagnostic", "tag": "exit_condition_not_updated", "vals": [7, 7]},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your loop header. Does the index change on every pass?",
             "related_misconception_id": "CPP-M08"},
            {"order": 2, "hint_text": "A loop must advance its index. A missing update keeps the same position forever.",
             "related_misconception_id": "CPP-M08"},
            {"order": 3, "hint_text": "Check the third part of your `for` header. Write `++i`.",
             "related_misconception_id": "CPP-M08"},
        ],
    },
    {
        "id": "CP40",
        "slug": "m08_first_index_at_least_target",
        "title": "First Index With A Value At Least The Target",
        "misconception": "CPP-M08",
        "secondary": ["CPP-M02"],
        "difficulty": "Intermediate",
        "topic": "Search",
        "statement_markdown": (
            "Read `n`, then `n` integers in ascending order, then one target "
            "value `t`. Print the first index `i` where `v[i] >= t`. Print `n` "
            "when no value reaches `t`.\n\n"
            "Print that index and the sum of the values before it, separated "
            "by a space. Your loop must stop when the list ends."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers in ascending order. "
            "Line 3 holds `t`."
        ),
        "output_format": "One line that holds the index and the sum.",
        "constraints": "`1 <= n <= 100000`. Each value and `t` are between -1000000000 and 1000000000.",
        "examples": [
            {"input": "5\n1 3 5 7 9\n6", "output": "3 9",
             "explanation": "The first value at least 6 is 7 at index 3. The values before it sum to 1 + 3 + 5 = 9."},
            {"input": "5\n1 3 5 7 9\n1", "output": "0 0",
             "explanation": "The value at index 0 is already at least 1. The sum of nothing is 0."},
        ],
        "solution": r'''// CP40 - First Index With A Value At Least The Target
// Target misconception: CPP-M08 (loop fails to update its exit condition)
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

    long long target = 0;
    if (!(std::cin >> target)) {
        return 0;
    }

    // The index changes on every pass. The loop also accumulates the sum.
    std::size_t i = 0;
    long long answer = 0;
    while (i < v.size() && v[i] < target) {
        answer += v[i];
        ++i;
    }

    std::cout << i << ' ' << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("        answer += v[i];\n        ++i;", "        answer += v[i];"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n{a['t']}\n"),
        "model": lambda a: _lower_bound(a["vals"], a["t"]) + "\n",
        "cases": [
            {"kind": "visible", "vals": [1, 3, 5, 7, 9], "t": 6},
            {"kind": "visible", "boundary": True, "vals": [1, 3, 5, 7, 9], "t": 1},
            {"kind": "visible", "vals": [2, 4, 6], "t": 10},
            {"kind": "hidden", "vals": [10, 20, 30, 40], "t": 25},
            {"kind": "hidden", "vals": [-5, -1, 0, 3], "t": 0},
            {"kind": "diagnostic", "tag": "exit_condition_not_updated", "vals": [1, 3, 5, 7, 9], "t": 100},
            {"kind": "diagnostic", "tag": "exit_condition_not_updated", "vals": [2, 4, 6], "t": 5},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your loop body. Which statement moves the index forward?",
             "related_misconception_id": "CPP-M08"},
            {"order": 2, "hint_text": "A `while` loop needs a statement inside the body that changes the tested value. Otherwise the condition never changes.",
             "related_misconception_id": "CPP-M08"},
            {"order": 3, "hint_text": "Check the last statement of your loop body. Write `++i`.",
             "related_misconception_id": "CPP-M08"},
        ],
    },
]


def _fib(n: int) -> int:
    """Return the n-th Fibonacci number. The helper is outside the trials."""
    a, b = 0, 1
    for _ in range(max(0, n)):
        a, b = b, a + b
    return a


def _halving_steps(n: int) -> int:
    """Return the number of halving steps that reach zero."""
    steps = 0
    while n > 0:
        n //= 2
        steps += 1
    return steps


def _last_position(values: list[int], target: int) -> str:
    """Return the last position of a value, or NOT FOUND."""
    for i in range(len(values) - 1, -1, -1):
        if values[i] == target:
            return str(i)
    return "NOT FOUND"


def _first_negative(values: list[int]) -> str:
    """Return the position of the first negative value, or NONE."""
    for i, value in enumerate(values):
        if value < 0:
            return str(i)
    return "NONE"


def _lower_bound(values: list[int], target: int) -> str:
    """Return the first index with a value at least the target, and the sum."""
    index = 0
    total = 0
    while index < len(values) and values[index] < target:
        total += values[index]
        index += 1
    return f"{index} {total}"
