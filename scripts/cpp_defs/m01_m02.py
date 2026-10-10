"""C++ diagnostic problem definitions: `CPP-M01` and `CPP-M02`.

Each definition carries the statement, the formats, the examples, the
reference solution, the mutation for the misconception variant, the test
cases, and the three scaffolding hints.

Naming conventions inside the reference solutions. The generator and the
verifier rely on them:

1. The answer that the program prints is named `answer`.
2. A vector of input values is named `v`.
3. A loop over the range `0` to `n-1` is written `for (int i = 0; i < n; ++i)`.
4. A recursive call reduces the argument by one.

Author: Agent 4, C++ test author and quality judge.
Standard: ASD-STE100 Simplified Technical English.
"""
from __future__ import annotations

PROBLEMS: list[dict] = [

    # =====================================================================
    # CPP-M01: exclusive upper bound treated as inclusive
    # =====================================================================
    {
        "id": "CP09",
        "slug": "m01_sum_squares_first_n",
        "title": "Sum Of Squares Of The First N Integers",
        "misconception": "CPP-M01",
        "secondary": ["CPP-M08"],
        "difficulty": "Beginner",
        "topic": "Loops",
        "statement_markdown": (
            "Read one integer `n`. Print the sum of the squares of the "
            "integers `0`, `1`, `2`, ... , `n-1`.\n\n"
            "The upper bound `n` is exclusive. The range holds exactly `n` "
            "integers. When `n` is `0` the range is empty and the sum is `0`."
        ),
        "input_format": "One line that holds one integer `n`.",
        "output_format": "One line that holds one integer: the sum.",
        "constraints": "`0 <= n <= 100000`",
        "examples": [
            {"input": "4", "output": "14",
             "explanation": "The range is 0 to 3. The squares are 0, 1, 4 and 9. The sum is 14."},
            {"input": "1", "output": "0",
             "explanation": "The range holds only 0. The square of 0 is 0. The sum is 0."},
        ],
        "solution": r'''// CP09 - Sum Of Squares Of The First N Integers
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long answer = 0;
    // The upper bound is exclusive. `i < n` gives exactly n iterations.
    for (int i = 0; i < n; ++i) {
        answer += static_cast<long long>(i) * i;
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("for (int i = 0; i < n; ++i)", "for (int i = 0; i <= n; ++i)"),
        ],
        "render": lambda a: f"{a['n']}\n",
        "model": lambda a: f"{sum(i * i for i in range(a['n']))}\n",
        "cases": [
            {"kind": "visible", "n": 4},
            {"kind": "visible", "boundary": True, "n": 1},
            {"kind": "visible", "n": 3},
            {"kind": "hidden", "n": 0},
            {"kind": "hidden", "n": 10},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 1},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 6},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your loop exit condition. How many times does the loop body run when n = 1?",
             "related_misconception_id": "CPP-M01"},
            {"order": 2, "hint_text": "The upper bound of this range is exclusive. The valid integers are 0 to n-1.",
             "related_misconception_id": "CPP-M01"},
            {"order": 3, "hint_text": "Check your comparison operator. A bound that excludes n uses `<`, not `<=`.",
             "related_misconception_id": "CPP-M01"},
        ],
    },
    {
        "id": "CP10",
        "slug": "m01_count_multiples_of_k",
        "title": "Count Multiples Of K In A Range",
        "misconception": "CPP-M01",
        "secondary": ["CPP-M06"],
        "difficulty": "Beginner",
        "topic": "Loops",
        "statement_markdown": (
            "Read two integers `n` and `k`. Count the integers `i` in the "
            "range `0` to `n-1` such that `i` is a multiple of `k`.\n\n"
            "The upper bound `n` is exclusive. The value `0` is a multiple of "
            "every `k`. When `n` is `0` the count is `0`."
        ),
        "input_format": "One line that holds `n` and `k`, separated by a space.",
        "output_format": "One line that holds one integer: the count.",
        "constraints": "`0 <= n <= 100000`, `1 <= k <= 100000`",
        "examples": [
            {"input": "5 3", "output": "2",
             "explanation": "The range is 0 to 4. The multiples of 3 are 0 and 3. The count is 2."},
            {"input": "0 4", "output": "0",
             "explanation": "The range is empty. The count is 0."},
        ],
        "solution": r'''// CP10 - Count Multiples Of K In A Range
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long n = 0;
    long long k = 0;
    if (!(std::cin >> n >> k)) {
        return 0;
    }

    long long answer = 0;
    // The upper bound is exclusive. `i < n` gives exactly n iterations.
    for (long long i = 0; i < n; ++i) {
        if (i % k == 0) {
            ++answer;
        }
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("for (long long i = 0; i < n; ++i)", "for (long long i = 0; i <= n; ++i)"),
        ],
        "render": lambda a: f"{a['n']} {a['k']}\n",
        "model": lambda a: f"{sum(1 for i in range(a['n']) if i % a['k'] == 0)}\n",
        "cases": [
            {"kind": "visible", "n": 5, "k": 3},
            {"kind": "visible", "boundary": True, "n": 1, "k": 1},
            {"kind": "visible", "n": 0, "k": 4},
            {"kind": "hidden", "n": 12, "k": 5},
            {"kind": "hidden", "n": 20, "k": 7},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 1, "k": 1},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 9, "k": 4},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your loop exit condition. Does the loop read one value after the range ends?",
             "related_misconception_id": "CPP-M01"},
            {"order": 2, "hint_text": "The range 0 to n-1 holds n integers. The bound n is never a member of the range.",
             "related_misconception_id": "CPP-M01"},
            {"order": 3, "hint_text": "Check your comparison operator. An exclusive bound uses `<`. A bound of `<=` adds one extra iteration.",
             "related_misconception_id": "CPP-M01"},
        ],
    },
    {
        "id": "CP11",
        "slug": "m01_reverse_range",
        "title": "Print A Range In Reverse Order",
        "misconception": "CPP-M01",
        "secondary": ["CPP-M08"],
        "difficulty": "Beginner",
        "topic": "Loops",
        "statement_markdown": (
            "Read one integer `n`. Print the integers `n-1`, `n-2`, ... , `1`, "
            "`0`. Print each integer on its own line.\n\n"
            "The range holds exactly `n` integers. When `n` is `0` the program "
            "prints nothing."
        ),
        "input_format": "One line that holds one integer `n`.",
        "output_format": "`n` lines. Line 1 holds `n-1`. The last line holds `0`.",
        "constraints": "`0 <= n <= 1000`",
        "examples": [
            {"input": "3", "output": "2\n1\n0",
             "explanation": "The range is 0 to 2. The reverse order is 2, 1, 0."},
            {"input": "0", "output": "",
             "explanation": "The range is empty. The program prints no line."},
        ],
        "solution": r'''// CP11 - Print A Range In Reverse Order
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    // The first printed value is n-1. The last printed value is 0.
    for (int i = n - 1; i >= 0; --i) {
        std::cout << i << '\n';
    }
    return 0;
}
''',
        "mutation": [
            ("for (int i = n - 1; i >= 0; --i)", "for (int i = n; i >= 0; --i)"),
        ],
        "render": lambda a: f"{a['n']}\n",
        "model": lambda a: "".join(f"{i}\n" for i in range(a["n"] - 1, -1, -1)),
        "cases": [
            {"kind": "visible", "n": 3},
            {"kind": "visible", "boundary": True, "n": 1},
            {"kind": "visible", "n": 0},
            {"kind": "hidden", "n": 6},
            {"kind": "hidden", "n": 10},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 0},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 5},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the first value that your loop prints. Is that value inside the range?",
             "related_misconception_id": "CPP-M01"},
            {"order": 2, "hint_text": "The largest member of the range is n-1. A loop that starts at n prints one value too many.",
             "related_misconception_id": "CPP-M01"},
            {"order": 3, "hint_text": "Check your start value. Write `n - 1` when you print a range in reverse.",
             "related_misconception_id": "CPP-M01"},
        ],
    },
    {
        "id": "CP12",
        "slug": "m01_product_first_odd",
        "title": "Product Of The First N Odd Integers",
        "misconception": "CPP-M01",
        "secondary": ["CPP-M07"],
        "difficulty": "Beginner",
        "topic": "Loops",
        "statement_markdown": (
            "Read one integer `n`. Print the product of the first `n` odd "
            "positive integers: `1 * 3 * 5 * ... * (2n-1)`.\n\n"
            "The upper bound `n` is exclusive. When `n` is `0` the product of "
            "an empty set is `1`."
        ),
        "input_format": "One line that holds one integer `n`.",
        "output_format": "One line that holds one integer: the product.",
        "constraints": "`0 <= n <= 25`",
        "examples": [
            {"input": "3", "output": "15",
             "explanation": "The first three odd integers are 1, 3 and 5. The product is 15."},
            {"input": "0", "output": "1",
             "explanation": "The set is empty. The product of an empty set is 1."},
        ],
        "solution": r'''// CP12 - Product Of The First N Odd Integers
// Target misconception: CPP-M01 (exclusive upper bound treated as inclusive)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    long long answer = 1;
    // The upper bound is exclusive. The last odd integer is 2*n - 1.
    for (int i = 0; i < n; ++i) {
        answer *= (2 * i + 1);
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("for (int i = 0; i < n; ++i)", "for (int i = 0; i <= n; ++i)"),
        ],
        "render": lambda a: f"{a['n']}\n",
        "model": lambda a: f"{_product(2 * i + 1 for i in range(a['n']))}\n",
        "cases": [
            {"kind": "visible", "n": 3},
            {"kind": "visible", "boundary": True, "n": 1},
            {"kind": "visible", "n": 0},
            {"kind": "hidden", "n": 4},
            {"kind": "hidden", "n": 6},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 1},
            {"kind": "diagnostic", "tag": "inclusive_upper_bound", "n": 5},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at your loop exit condition. How many odd integers does your loop multiply?",
             "related_misconception_id": "CPP-M01"},
            {"order": 2, "hint_text": "The range holds n integers. The last odd integer is 2*n - 1, not 2*n + 1.",
             "related_misconception_id": "CPP-M01"},
            {"order": 3, "hint_text": "Check your comparison operator. `<=` multiplies one extra odd integer.",
             "related_misconception_id": "CPP-M01"},
        ],
    },

    # =====================================================================
    # CPP-M02: element value confused with index position
    # =====================================================================
    {
        "id": "CP13",
        "slug": "m02_second_largest_distinct",
        "title": "Second Largest Distinct Value",
        "misconception": "CPP-M02",
        "secondary": ["CPP-M04"],
        "difficulty": "Beginner",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n` and then `n` integers. Print the second largest "
            "**distinct** value.\n\n"
            "Duplicates count once. When the input holds fewer than two "
            "distinct values, print `NONE`."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers separated by spaces."
        ),
        "output_format": "One line that holds the value, or `NONE`.",
        "constraints": "`0 <= n <= 100000`. Each value is between -1000000000 and 1000000000.",
        "examples": [
            {"input": "4\n5 1 9 3", "output": "5",
             "explanation": "The distinct values are 1, 3, 5 and 9. The second largest is 5."},
            {"input": "4\n4 4 4 1", "output": "1",
             "explanation": "The distinct values are 1 and 4. The second largest is 1."},
        ],
        "solution": r'''// CP13 - Second Largest Distinct Value
// Target misconception: CPP-M02 (element value confused with index position)
#include <iostream>
#include <set>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n < 0 ? 0 : n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    std::set<long long> distinct(v.begin(), v.end());
    if (distinct.size() < 2) {
        std::cout << "NONE" << '\n';
        return 0;
    }

    // Walk the set from the largest value down by one position.
    auto it = distinct.rbegin();
    ++it;
    const long long answer = *it;

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("    std::cout << answer << '\\n';",
             "    long long position = -1;\n"
             "    for (int i = 0; i < n; ++i) {\n"
             "        if (v[static_cast<std::size_t>(i)] == answer) {\n"
             "            position = i;\n"
             "            break;\n"
             "        }\n"
             "    }\n"
             "    std::cout << position << '\\n';"),
        ],
        "render": lambda a: f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n",
        "model": lambda a: (_second_largest(a["vals"]) + "\n"),
        "cases": [
            {"kind": "visible", "vals": [5, 1, 9, 3]},
            {"kind": "visible", "vals": [4, 4, 4, 1]},
            {"kind": "visible", "boundary": True, "vals": [1, 2]},
            {"kind": "hidden", "vals": [9, 9]},
            {"kind": "hidden", "vals": [-5, -1, -5, -9]},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [5, 1, 9, 3]},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [8, 3, 6, 2, 7]},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at what your program prints. Does it print a member of the input, or a location in the input?",
             "related_misconception_id": "CPP-M02"},
            {"order": 2, "hint_text": "An index reaches a value. The answer here is the value itself, not the place where it sits.",
             "related_misconception_id": "CPP-M02"},
            {"order": 3, "hint_text": "Check the expression in your output statement. Print `answer`, not the loop variable `i`.",
             "related_misconception_id": "CPP-M02"},
        ],
    },
    {
        "id": "CP14",
        "slug": "m02_kth_smallest_value",
        "title": "K-th Smallest Value",
        "misconception": "CPP-M02",
        "secondary": ["CPP-M04"],
        "difficulty": "Beginner",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n`, then `n` integers, then one integer `k`. Print the "
            "`k`-th smallest value. Count from `1`.\n\n"
            "You must sort the values first. The input is not sorted."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers. Line 3 holds `k`."
        ),
        "output_format": "One line that holds one integer.",
        "constraints": "`1 <= n <= 100000`, `1 <= k <= n`",
        "examples": [
            {"input": "5\n5 9 1 7 3\n2", "output": "3",
             "explanation": "The sorted values are 1, 3, 5, 7, 9. The second smallest is 3."},
            {"input": "3\n4 4 4\n3", "output": "4",
             "explanation": "The sorted values are 4, 4, 4. The third smallest is 4."},
        ],
        "solution": r'''// CP14 - K-th Smallest Value
// Target misconception: CPP-M02 (element value confused with index position)
#include <algorithm>
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n < 0 ? 0 : n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    int k = 1;
    if (!(std::cin >> k)) {
        return 0;
    }

    std::vector<long long> sorted = v;
    std::sort(sorted.begin(), sorted.end());

    // k counts from 1, so the index is k - 1.
    const long long answer = sorted[static_cast<std::size_t>(k - 1)];

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("const long long answer = sorted[static_cast<std::size_t>(k - 1)];",
             "const long long answer = v[static_cast<std::size_t>(k - 1)];"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n{a['k']}\n"),
        "model": lambda a: f"{sorted(a['vals'])[a['k'] - 1]}\n",
        "cases": [
            {"kind": "visible", "vals": [5, 9, 1, 7, 3], "k": 2},
            {"kind": "visible", "boundary": True, "vals": [8, 3, 6, 1, 9, 2], "k": 1},
            {"kind": "visible", "vals": [4, 4, 4], "k": 3},
            {"kind": "hidden", "vals": [10, 20], "k": 2},
            {"kind": "hidden", "vals": [7, 3, 5, 1], "k": 3},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [5, 9, 1, 7, 3], "k": 2},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [7, 3], "k": 2},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the array that you read the answer from. Is that array sorted?",
             "related_misconception_id": "CPP-M02"},
            {"order": 2, "hint_text": "A position in the unsorted input is not the same as a position in the sorted data.",
             "related_misconception_id": "CPP-M02"},
            {"order": 3, "hint_text": "Check the name inside your brackets. Read from `sorted`, not from `v`.",
             "related_misconception_id": "CPP-M02"},
        ],
    },
    {
        "id": "CP15",
        "slug": "m02_count_occurrences",
        "title": "Count The Occurrences Of A Value",
        "misconception": "CPP-M02",
        "secondary": ["CPP-M08"],
        "difficulty": "Beginner",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n`, then `n` integers, then one target value `t`. Count how "
            "many input values equal `t`.\n\n"
            "The count is a count of values. It is not a count of positions."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers. Line 3 holds `t`."
        ),
        "output_format": "One line that holds one integer: the count.",
        "constraints": "`1 <= n <= 100000`. Each value and `t` are between -1000000000 and 1000000000.",
        "examples": [
            {"input": "6\n0 1 2 0 1 0\n0", "output": "3",
             "explanation": "The value 0 occurs three times. The count is 3."},
            {"input": "3\n1 2 3\n9", "output": "0",
             "explanation": "The value 9 does not occur. The count is 0."},
        ],
        "solution": r'''// CP15 - Count The Occurrences Of A Value
// Target misconception: CPP-M02 (element value confused with index position)
#include <iostream>
#include <vector>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int n = 0;
    if (!(std::cin >> n)) {
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n < 0 ? 0 : n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    long long target = 0;
    if (!(std::cin >> target)) {
        return 0;
    }

    long long answer = 0;
    // Each member of v is a value. Compare the value with the target.
    for (long long value : v) {
        if (value == target) {
            ++answer;
        }
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("    for (long long value : v) {\n        if (value == target) {",
             "    for (int i = 0; i < n; ++i) {\n        if (i == target) {"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n{a['t']}\n"),
        "model": lambda a: f"{a['vals'].count(a['t'])}\n",
        "cases": [
            {"kind": "visible", "vals": [0, 1, 2, 0, 1, 0], "t": 0},
            {"kind": "visible", "boundary": True, "vals": [1, 2, 3], "t": 9},
            {"kind": "visible", "vals": [5, 5, 1, 5], "t": 5},
            {"kind": "hidden", "vals": [0, 0, 0, 1], "t": 1},
            {"kind": "hidden", "vals": [7], "t": 7},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [0, 1, 2, 0, 1, 0], "t": 0},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [4, 4, 2, 4], "t": 4},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the expression in your comparison. Are you comparing a value or a position?",
             "related_misconception_id": "CPP-M02"},
            {"order": 2, "hint_text": "A range-based loop gives you the value. An index loop gives you the position.",
             "related_misconception_id": "CPP-M02"},
            {"order": 3, "hint_text": "Check the left operand of `==`. Compare `v[i]`, not `i`.",
             "related_misconception_id": "CPP-M02"},
        ],
    },
    {
        "id": "CP16",
        "slug": "m02_median_value",
        "title": "Median Value",
        "misconception": "CPP-M02",
        "secondary": ["CPP-M04"],
        "difficulty": "Intermediate",
        "topic": "Arrays",
        "statement_markdown": (
            "Read `n` and then `n` integers. The count `n` is odd. Print the "
            "median value.\n\n"
            "The median is the value in the middle after you sort the values."
        ),
        "input_format": (
            "Line 1 holds `n`. Line 2 holds `n` integers separated by spaces."
        ),
        "output_format": "One line that holds one integer.",
        "constraints": "`1 <= n <= 100000`, `n` is odd",
        "examples": [
            {"input": "5\n5 9 1 7 3", "output": "5",
             "explanation": "The sorted values are 1, 3, 5, 7, 9. The middle value is 5."},
            {"input": "1\n42", "output": "42",
             "explanation": "There is one value. The middle value is 42."},
        ],
        "solution": r'''// CP16 - Median Value
// Target misconception: CPP-M02 (element value confused with index position)
#include <algorithm>
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
        // The contract holds an odd count of at least one value.
        return 0;
    }

    std::vector<long long> v(static_cast<std::size_t>(n));
    for (int i = 0; i < n; ++i) {
        if (!(std::cin >> v[static_cast<std::size_t>(i)])) {
            return 0;
        }
    }

    std::vector<long long> sorted = v;
    std::sort(sorted.begin(), sorted.end());

    // n is odd. The middle index is n / 2.
    const long long answer = sorted[static_cast<std::size_t>(n / 2)];

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("const long long answer = sorted[static_cast<std::size_t>(n / 2)];",
             "const long long answer = v[static_cast<std::size_t>(n / 2)];"),
        ],
        "render": lambda a: (
            f"{len(a['vals'])}\n{' '.join(str(x) for x in a['vals'])}\n"),
        "model": lambda a: f"{sorted(a['vals'])[len(a['vals']) // 2]}\n",
        "cases": [
            {"kind": "visible", "vals": [5, 9, 1, 7, 3]},
            {"kind": "visible", "boundary": True, "vals": [42]},
            {"kind": "visible", "vals": [9, 8, 7, 6, 5]},
            {"kind": "hidden", "vals": [1, 2, 3, 4, 5, 6, 7]},
            {"kind": "hidden", "vals": [100, 1, 50, 2, 25]},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [5, 9, 1, 7, 3]},
            {"kind": "diagnostic", "tag": "value_not_position", "vals": [50, 5, 500, 1, 7]},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the array that holds your answer. Did you sort that array, or a different one?",
             "related_misconception_id": "CPP-M02"},
            {"order": 2, "hint_text": "A position in the input is not a position in the sorted data. Sort first, then read the middle.",
             "related_misconception_id": "CPP-M02"},
            {"order": 3, "hint_text": "Check the name inside your brackets. Read from `sorted`, not from `v`.",
             "related_misconception_id": "CPP-M02"},
        ],
    },
]


def _product(values) -> int:
    """Return the product of an iterable. The product of nothing is 1."""
    result = 1
    for value in values:
        result *= value
    return result


def _second_largest(values: list[int]) -> str:
    """Return the second largest distinct value, or the text NONE."""
    distinct = sorted(set(values), reverse=True)
    if len(distinct) < 2:
        return "NONE"
    return str(distinct[1])
