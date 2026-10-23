"""C++ diagnostic problem definitions: `CPP-M05` and `CPP-M06`.

Naming conventions inside the reference solutions. The generator and the
verifier rely on them:

1. A correct range check joins two comparisons with `&&` or `||`.
2. A condition that tests a value uses `==`.
3. A single input value is named `x`.

Author: Agent 4, C++ test author and quality judge.
Standard: ASD-STE100 Simplified Technical English.
"""
from __future__ import annotations

PROBLEMS: list[dict] = [

    # =====================================================================
    # CPP-M05: misunderstanding of a compound boolean comparison
    # =====================================================================
    {
        "id": "CP25",
        "slug": "m05_grade_from_score",
        "title": "Grade From A Score",
        "misconception": "CPP-M05",
        "secondary": ["CPP-M06"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read one integer `score`. Print the grade:\n\n"
            "| Score | Grade |\n|---|---|\n"
            "| 90 to 100 | `A` |\n"
            "| 80 to 89 | `B` |\n"
            "| 70 to 79 | `C` |\n"
            "| 60 to 69 | `D` |\n"
            "| 0 to 59 | `F` |\n\n"
            "A score outside the range 0 to 100 gives `INVALID`. Use an "
            "explicit conjunction of two comparisons for each range."
        ),
        "input_format": "One line that holds one integer `score`.",
        "output_format": "One line that holds one letter, or `INVALID`.",
        "constraints": "`-1000 <= score <= 1000`",
        "examples": [
            {"input": "95", "output": "A",
             "explanation": "95 is inside 90 to 100. The grade is A."},
            {"input": "105", "output": "INVALID",
             "explanation": "105 is above 100. The score is not valid."},
        ],
        "solution": r'''// CP25 - Grade From A Score
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int score = 0;
    if (!(std::cin >> score)) {
        return 0;
    }

    char answer = 'F';
    if (score < 0 || score > 100) {
        answer = 'I';  // INVALID
    } else if (90 <= score && score <= 100) {
        answer = 'A';
    } else if (80 <= score && score <= 89) {
        answer = 'B';
    } else if (70 <= score && score <= 79) {
        answer = 'C';
    } else if (60 <= score && score <= 69) {
        answer = 'D';
    }

    if (answer == 'I') {
        std::cout << "INVALID" << '\n';
    } else {
        std::cout << answer << '\n';
    }
    return 0;
}
''',
        "mutation": [
            ("90 <= score && score <= 100", "90 <= score <= 100"),
            ("80 <= score && score <= 89", "80 <= score <= 89"),
            ("70 <= score && score <= 79", "70 <= score <= 79"),
            ("60 <= score && score <= 69", "60 <= score <= 69"),
        ],
        "render": lambda a: f"{a['score']}\n",
        "model": lambda a: _grade(a["score"]) + "\n",
        "cases": [
            {"kind": "visible", "score": 95},
            {"kind": "visible", "boundary": True, "score": 105},
            {"kind": "visible", "score": 85},
            {"kind": "hidden", "score": 90},
            {"kind": "hidden", "score": 89},
            {"kind": "hidden", "score": 0},
            {"kind": "diagnostic", "tag": "chained_comparison", "score": 85},
            {"kind": "diagnostic", "tag": "chained_comparison", "score": 55},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the condition that selects a grade. Does that condition use one comparison or two?",
             "related_misconception_id": "CPP-M05"},
            {"order": 2, "hint_text": "C++ does not chain comparisons as in mathematics. `a <= x <= b` is `(a <= x) <= b`. That is always true.",
             "related_misconception_id": "CPP-M05"},
            {"order": 3, "hint_text": "Check your condition. Write `90 <= score && score <= 100`.",
             "related_misconception_id": "CPP-M05"},
        ],
    },
    {
        "id": "CP26",
        "slug": "m05_shipping_cost",
        "title": "Shipping Cost By Weight",
        "misconception": "CPP-M05",
        "secondary": ["CPP-M06"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read one integer `weight` in grams. Print the shipping cost:\n\n"
            "| Weight | Cost |\n|---|---|\n"
            "| 1 to 500 | `5` |\n"
            "| 501 to 2000 | `10` |\n"
            "| 2001 to 10000 | `20` |\n"
            "| anything else | `-1` |\n\n"
            "A weight of `0` or less is not valid."
        ),
        "input_format": "One line that holds one integer `weight`.",
        "output_format": "One line that holds the cost.",
        "constraints": "`-1000 <= weight <= 20000`",
        "examples": [
            {"input": "300", "output": "5",
             "explanation": "300 is inside 1 to 500. The cost is 5."},
            {"input": "0", "output": "-1",
             "explanation": "0 is not inside any band. The cost is -1."},
        ],
        "solution": r'''// CP26 - Shipping Cost By Weight
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long weight = 0;
    if (!(std::cin >> weight)) {
        return 0;
    }

    long long answer = -1;
    if (1 <= weight && weight <= 500) {
        answer = 5;
    } else if (501 <= weight && weight <= 2000) {
        answer = 10;
    } else if (2001 <= weight && weight <= 10000) {
        answer = 20;
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("1 <= weight && weight <= 500", "1 <= weight <= 500"),
            ("501 <= weight && weight <= 2000", "501 <= weight <= 2000"),
            ("2001 <= weight && weight <= 10000", "2001 <= weight <= 10000"),
        ],
        "render": lambda a: f"{a['weight']}\n",
        "model": lambda a: f"{_shipping(a['weight'])}\n",
        "cases": [
            {"kind": "visible", "weight": 300},
            {"kind": "visible", "boundary": True, "weight": 0},
            {"kind": "visible", "weight": 600},
            {"kind": "hidden", "weight": 1},
            {"kind": "hidden", "weight": 500},
            {"kind": "hidden", "weight": 5000},
            {"kind": "diagnostic", "tag": "chained_comparison", "weight": 600},
            {"kind": "diagnostic", "tag": "chained_comparison", "weight": -5},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the condition for one band. Does that condition test both limits?",
             "related_misconception_id": "CPP-M05"},
            {"order": 2, "hint_text": "C++ does not chain comparisons as in mathematics. A chain always gives a true result.",
             "related_misconception_id": "CPP-M05"},
            {"order": 3, "hint_text": "Check your condition. Write `501 <= weight && weight <= 2000`.",
             "related_misconception_id": "CPP-M05"},
        ],
    },
    {
        "id": "CP27",
        "slug": "m05_water_state",
        "title": "Water State From A Temperature",
        "misconception": "CPP-M05",
        "secondary": ["CPP-M01"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read one integer `t` in degrees Celsius. Print the state of "
            "water:\n\n"
            "- `SOLID` when `t <= 0`.\n"
            "- `LIQUID` when `t >= 1` and `t <= 99`.\n"
            "- `GAS` when `t >= 100`.\n\n"
            "Print one word in capital letters."
        ),
        "input_format": "One line that holds one integer `t`.",
        "output_format": "One line that holds `SOLID`, `LIQUID` or `GAS`.",
        "constraints": "`-1000 <= t <= 1000`",
        "examples": [
            {"input": "0", "output": "SOLID",
             "explanation": "0 is at the freezing point. The state is SOLID."},
            {"input": "100", "output": "GAS",
             "explanation": "100 is at the boiling point. The state is GAS."},
        ],
        "solution": r'''// CP27 - Water State From A Temperature
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int t = 0;
    if (!(std::cin >> t)) {
        return 0;
    }

    // Two comparisons joined by &&. Each operand is a boolean.
    const char* answer = "GAS";
    if (t <= 0) {
        answer = "SOLID";
    } else if (t >= 1 && t <= 99) {
        answer = "LIQUID";
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("t >= 1 && t <= 99", "t >= 1 <= 99"),
        ],
        "render": lambda a: f"{a['t']}\n",
        "model": lambda a: _water_state(a["t"]) + "\n",
        "cases": [
            {"kind": "visible", "t": 0},
            {"kind": "visible", "boundary": True, "t": 100},
            {"kind": "visible", "t": 50},
            {"kind": "hidden", "t": 1},
            {"kind": "hidden", "t": 99},
            {"kind": "hidden", "t": -10},
            {"kind": "diagnostic", "tag": "chained_comparison", "t": 50},
            {"kind": "diagnostic", "tag": "chained_comparison", "t": 99},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the condition that selects LIQUID. Does that condition use two comparisons?",
             "related_misconception_id": "CPP-M05"},
            {"order": 2, "hint_text": "C++ does not chain comparisons as in mathematics. Join two comparisons with `&&`.",
             "related_misconception_id": "CPP-M05"},
            {"order": 3, "hint_text": "Check your condition. Write `t >= 1 && t <= 99`.",
             "related_misconception_id": "CPP-M05"},
        ],
    },
    {
        "id": "CP28",
        "slug": "m05_ticket_price",
        "title": "Cinema Ticket Price",
        "misconception": "CPP-M05",
        "secondary": ["CPP-M06"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read one integer `age`. Print the cinema ticket price:\n\n"
            "| Age | Price |\n|---|---|\n"
            "| 0 to 5 | `0` |\n"
            "| 6 to 17 | `7` |\n"
            "| 18 to 64 | `12` |\n"
            "| 65 or more | `8` |\n\n"
            "A negative age gives `-1`."
        ),
        "input_format": "One line that holds one integer `age`.",
        "output_format": "One line that holds the price.",
        "constraints": "`-100 <= age <= 120`",
        "examples": [
            {"input": "10", "output": "7",
             "explanation": "10 is inside 6 to 17. The price is 7."},
            {"input": "-3", "output": "-1",
             "explanation": "A negative age is not valid. The price is -1."},
        ],
        "solution": r'''// CP28 - Cinema Ticket Price
// Target misconception: CPP-M05 (misunderstanding of a compound boolean comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int age = 0;
    if (!(std::cin >> age)) {
        return 0;
    }

    long long answer = -1;
    if (age >= 0 && age <= 5) {
        answer = 0;
    } else if (age >= 6 && age <= 17) {
        answer = 7;
    } else if (age >= 18 && age <= 64) {
        answer = 12;
    } else if (age >= 65) {
        answer = 8;
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("age >= 0 && age <= 5", "age >= 0 <= 5"),
            ("age >= 6 && age <= 17", "age >= 6 <= 17"),
            ("age >= 18 && age <= 64", "age >= 18 <= 64"),
        ],
        "render": lambda a: f"{a['age']}\n",
        "model": lambda a: f"{_ticket(a['age'])}\n",
        "cases": [
            {"kind": "visible", "age": 10},
            {"kind": "visible", "boundary": True, "age": -3},
            {"kind": "visible", "age": 30},
            {"kind": "hidden", "age": 5},
            {"kind": "hidden", "age": 65},
            {"kind": "hidden", "age": 17},
            {"kind": "diagnostic", "tag": "chained_comparison", "age": 10},
            {"kind": "diagnostic", "tag": "chained_comparison", "age": 40},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the condition for one age band. Does that condition hold two comparisons?",
             "related_misconception_id": "CPP-M05"},
            {"order": 2, "hint_text": "C++ does not chain comparisons as in mathematics. Join two comparisons with `&&`.",
             "related_misconception_id": "CPP-M05"},
            {"order": 3, "hint_text": "Check your condition. Write `age >= 6 && age <= 17`.",
             "related_misconception_id": "CPP-M05"},
        ],
    },

    # =====================================================================
    # CPP-M06: confusing assignment and equality comparison
    # =====================================================================
    {
        "id": "CP29",
        "slug": "m06_sign_of_number",
        "title": "Sign Of A Number",
        "misconception": "CPP-M06",
        "secondary": ["CPP-M05"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read one integer `x`. Print `ZERO` when `x` equals `0`. Print "
            "`POSITIVE` when `x` is more than `0`. Print `NEGATIVE` "
            "otherwise.\n\n"
            "Compare the value. Do not assign to it."
        ),
        "input_format": "One line that holds one integer `x`.",
        "output_format": "One line that holds `ZERO`, `POSITIVE` or `NEGATIVE`.",
        "constraints": "`-1000000000 <= x <= 1000000000`",
        "examples": [
            {"input": "0", "output": "ZERO",
             "explanation": "x equals 0. The program prints ZERO."},
            {"input": "-4", "output": "NEGATIVE",
             "explanation": "-4 is less than 0. The program prints NEGATIVE."},
        ],
        "solution": r'''// CP29 - Sign Of A Number
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    int x = 0;
    if (!(std::cin >> x)) {
        return 0;
    }

    const char* answer = "NEGATIVE";
    // A comparison, not an assignment.
    if (x == 0) {
        answer = "ZERO";
    } else if (x > 0) {
        answer = "POSITIVE";
    }

    std::cout << answer << '\n';
    return 0;
}
''',
        "mutation": [
            ("    if (x == 0) {", "    if (x = 0) {"),
        ],
        "render": lambda a: f"{a['x']}\n",
        "model": lambda a: _sign(a["x"]) + "\n",
        "cases": [
            {"kind": "visible", "x": 0},
            {"kind": "visible", "boundary": True, "x": -4},
            {"kind": "visible", "x": 9},
            {"kind": "hidden", "x": 1},
            {"kind": "hidden", "x": -1},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "x": 0},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "x": 5},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the condition that tests zero. Does that condition compare, or does it change x?",
             "related_misconception_id": "CPP-M06"},
            {"order": 2, "hint_text": "The operator `=` assigns a value. The operator `==` compares two values.",
             "related_misconception_id": "CPP-M06"},
            {"order": 3, "hint_text": "Check the operator in your condition. Write `x == 0`.",
             "related_misconception_id": "CPP-M06"},
        ],
    },
    {
        "id": "CP30",
        "slug": "m06_password_length",
        "title": "Password Length Check",
        "misconception": "CPP-M06",
        "secondary": ["CPP-M05"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read one line of text. Print `OK` when the line holds 8 or more "
            "characters. Print `TOO SHORT` otherwise.\n\n"
            "Count the space characters. Compare the length with `==`. Do not "
            "assign."
        ),
        "input_format": "One line of text.",
        "output_format": "One line that holds `OK` or `TOO SHORT`.",
        "constraints": "The line holds 1 to 100 characters.",
        "examples": [
            {"input": "abcdefgh", "output": "OK",
             "explanation": "The line holds 8 characters. The program prints OK."},
            {"input": "abc", "output": "TOO SHORT",
             "explanation": "The line holds 3 characters. The program prints TOO SHORT."},
        ],
        "solution": r'''// CP30 - Password Length Check
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>
#include <string>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string line;
    if (!std::getline(std::cin, line)) {
        return 0;
    }

    int length = static_cast<int>(line.size());
    // A comparison, not an assignment.
    const bool answer = (length >= 8);

    std::cout << (answer ? "OK" : "TOO SHORT") << '\n';
    return 0;
}
''',
        "mutation": [
            ("    const bool answer = (length >= 8);",
             "    const bool answer = (length = 8);"),
        ],
        "render": lambda a: f"{a['text']}\n",
        "model": lambda a: ("OK" if len(a["text"]) >= 8 else "TOO SHORT") + "\n",
        "cases": [
            {"kind": "visible", "text": "abcdefgh"},
            {"kind": "visible", "boundary": True, "text": "abc"},
            {"kind": "visible", "text": "12345678901234"},
            {"kind": "hidden", "text": "1234567"},
            {"kind": "hidden", "text": "12345678"},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "text": "abcdefgh"},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "text": "short"},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the expression that gives the answer. Does that expression compare the length, or set it?",
             "related_misconception_id": "CPP-M06"},
            {"order": 2, "hint_text": "The operator `=` assigns a value. The operator `==` compares two values. A comparison gives a bool.",
             "related_misconception_id": "CPP-M06"},
            {"order": 3, "hint_text": "Check the operator in your expression. Write `line.size() >= 8`.",
             "related_misconception_id": "CPP-M06"},
        ],
    },
    {
        "id": "CP31",
        "slug": "m06_divisible_by_both",
        "title": "Divisible By Two Divisors",
        "misconception": "CPP-M06",
        "secondary": ["CPP-M05"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read three integers `x`, `p` and `q`. Print `YES` when `x` is a "
            "multiple of both `p` and `q`. Print `NO` otherwise.\n\n"
            "Compare the remainders with `==`. Do not assign."
        ),
        "input_format": "One line that holds `x`, `p` and `q`.",
        "output_format": "One line that holds `YES` or `NO`.",
        "constraints": "`1 <= p, q <= 1000`, `-1000000 <= x <= 1000000`",
        "examples": [
            {"input": "12 3 4", "output": "YES",
             "explanation": "12 is a multiple of 3 and of 4. The program prints YES."},
            {"input": "12 3 5", "output": "NO",
             "explanation": "12 is not a multiple of 5. The program prints NO."},
        ],
        "solution": r'''// CP31 - Divisible By Two Divisors
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    long long x = 0;
    long long p = 1;
    long long q = 1;
    if (!(std::cin >> x >> p >> q)) {
        return 0;
    }

    long long remainder_p = x % p;
    long long remainder_q = x % q;
    // A comparison, not an assignment.
    const bool answer = (remainder_p == 0) && (remainder_q == 0);

    std::cout << (answer ? "YES" : "NO") << '\n';
    return 0;
}
''',
        "mutation": [
            ("    const bool answer = (remainder_p == 0) && (remainder_q == 0);",
             "    const bool answer = (remainder_p = 0) && (remainder_q == 0);"),
        ],
        "render": lambda a: f"{a['x']} {a['p']} {a['q']}\n",
        "model": lambda a: ("YES" if a["x"] % a["p"] == 0 and a["x"] % a["q"] == 0 else "NO") + "\n",
        "cases": [
            {"kind": "visible", "x": 12, "p": 3, "q": 4},
            {"kind": "visible", "boundary": True, "x": 12, "p": 3, "q": 5},
            {"kind": "visible", "x": 7, "p": 7, "q": 7},
            {"kind": "hidden", "x": 0, "p": 5, "q": 7},
            {"kind": "hidden", "x": 36, "p": 6, "q": 9},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "x": 12, "p": 3, "q": 4},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "x": 9, "p": 3, "q": 2},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the expression that gives the answer. Does that expression compare the remainders, or set one?",
             "related_misconception_id": "CPP-M06"},
            {"order": 2, "hint_text": "The operator `=` assigns a value. The operator `==` compares two values.",
             "related_misconception_id": "CPP-M06"},
            {"order": 3, "hint_text": "Check the operator in your expression. Write `x % p == 0`.",
             "related_misconception_id": "CPP-M06"},
        ],
    },
    {
        "id": "CP32",
        "slug": "m06_character_is_vowel",
        "title": "Vowel Or Consonant",
        "misconception": "CPP-M06",
        "secondary": ["CPP-M05"],
        "difficulty": "Beginner",
        "topic": "Conditions",
        "statement_markdown": (
            "Read one line of text. Take the first character. Print `VOWEL` "
            "when that character is `a`, `e`, `i`, `o`, `u` or `A`, `E`, `I`, "
            "`O`, `U`. Print `CONSONANT` otherwise.\n\n"
            "Compare the characters with `==`. Do not assign."
        ),
        "input_format": "One line of text.",
        "output_format": "One line that holds `VOWEL` or `CONSONANT`.",
        "constraints": "The line holds one letter.",
        "examples": [
            {"input": "a", "output": "VOWEL",
             "explanation": "The first character is a lower-case vowel."},
            {"input": "B", "output": "CONSONANT",
             "explanation": "The first character is a capital consonant."},
        ],
        "solution": r'''// CP32 - Vowel Or Consonant
// Target misconception: CPP-M06 (confusing assignment and equality comparison)
#include <iostream>
#include <string>

int main() {
    std::ios::sync_with_stdio(false);
    std::cin.tie(nullptr);

    std::string line;
    if (!std::getline(std::cin, line) || line.empty()) {
        return 0;
    }

    char first = line[0];
    const bool is_vowel = (first == 'a') || (first == 'e') || (first == 'i')
        || (first == 'o') || (first == 'u') || (first == 'A')
        || (first == 'E') || (first == 'I') || (first == 'O')
        || (first == 'U');

    std::cout << (is_vowel ? "VOWEL" : "CONSONANT") << '\n';
    return 0;
}
''',
        "mutation": [
            ("    const bool is_vowel = (first == 'a')",
             "    const bool is_vowel = (first = 'a')"),
        ],
        "render": lambda a: f"{a['text']}\n",
        "model": lambda a: ("VOWEL" if a["text"][:1].lower() in "aeiou" else "CONSONANT") + "\n",
        "cases": [
            {"kind": "visible", "text": "a"},
            {"kind": "visible", "boundary": True, "text": "B"},
            {"kind": "visible", "text": "E"},
            {"kind": "hidden", "text": "u"},
            {"kind": "hidden", "text": "z"},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "text": "a"},
            {"kind": "diagnostic", "tag": "assignment_in_condition", "text": "E"},
        ],
        "hints": [
            {"order": 1, "hint_text": "Look at the expression that tests the first character. Does that expression compare, or does it overwrite?",
             "related_misconception_id": "CPP-M06"},
            {"order": 2, "hint_text": "The operator `=` assigns a value. The operator `==` compares two values.",
             "related_misconception_id": "CPP-M06"},
            {"order": 3, "hint_text": "Check the operator in your expression. Write `first == 'a'`.",
             "related_misconception_id": "CPP-M06"},
        ],
    },
]


def _grade(score: int) -> str:
    """Return the letter grade for a score."""
    if score < 0 or score > 100:
        return "INVALID"
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _shipping(weight: int) -> int:
    """Return the shipping cost for a weight in grams."""
    if 1 <= weight <= 500:
        return 5
    if 501 <= weight <= 2000:
        return 10
    if 2001 <= weight <= 10000:
        return 20
    return -1


def _water_state(t: int) -> str:
    """Return the state of water at a temperature."""
    if t <= 0:
        return "SOLID"
    if 1 <= t <= 99:
        return "LIQUID"
    return "GAS"


def _ticket(age: int) -> int:
    """Return the cinema ticket price for an age."""
    if age < 0:
        return -1
    if age <= 5:
        return 0
    if age <= 17:
        return 7
    if age <= 64:
        return 12
    return 8


def _sign(x: int) -> str:
    """Return the sign of a number."""
    if x == 0:
        return "ZERO"
    return "POSITIVE" if x > 0 else "NEGATIVE"
