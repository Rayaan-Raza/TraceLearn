HINTS = {
    "M01_LOOP_BOUNDARY": {
        1: "Check which values your loop boundary actually includes.",
        2: "Compare the number of iterations with the number of items you intend to process.",
        3: "Review the upper bound supplied to range(). Remember that Python excludes the upper bound.",
        4: "Practice: rewrite the loop using range(n) and confirm it visits exactly n values before moving on.",
    },
    "M02_INDEX_VALUE": {
        1: "Think about whether you need a position or the value stored at that position.",
        2: "When looping, decide if the loop variable is an index or an element value.",
        3: "Use the loop variable directly when you mean the element, not nums[variable] unless variable is an index.",
        4: "Practice: list comprehension exercises that alternate returning positions vs values will make this intuitive.",
    },
    "M03_MISSING_RETURN": {
        1: "Make sure your function sends a result back to the caller.",
        2: "Printing shows output but does not return a value to the caller.",
        3: "Use return with the computed result on every code path that should produce an answer.",
        4: "Practice: write a function and call it in an expression (e.g. x = f(3) * 2) — if print was used, the expression will fail.",
    },
    # C++ templates. A problem-specific hint from the C++ diagnostic bank
    # overrides these, but a diagnosis on a teacher-authored problem reaches
    # only this table, so every scored C++ code needs a fallback here.
    "CPP_LOOP_BOUNDARY": {
        1: "Look at the value your loop condition compares with. Where does the loop actually stop?",
        2: "Count the iterations by hand for a small input. One extra or one missing iteration means the bound is off.",
        3: "A for loop stops when its condition turns false. Check < against <= against the range you intend.",
        4: "Practice: write the same loop with i < n and i <= n and compare the number of iterations for n = 5.",
    },
    "CPP_OFF_BY_ONE": {
        1: "Check the first and the last index your loop touches.",
        2: "The last valid index of n elements is n-1. The index n reads one element too far.",
        3: "Compare the loop condition with size(). Prefer i < n over i <= n when n is the size.",
        4: "Practice: on paper, label elements 0..n-1 and trace which index your loop accesses last.",
    },
    "CPP_ARRAY_BOUNDS": {
        1: "Check every index against the size of the container.",
        2: "The valid indices of n elements run from 0 to n-1. The index n is out of range.",
        3: "Use v.at(i) instead of v[i] while you debug. It reports the index it rejected.",
        4: "Practice: add an assert(i < v.size()) before every subscript access, then run the tests.",
    },
    "CPP_UNINITIALIZED_VAR": {
        1: "Find every variable that is declared without a value and then used.",
        2: "A variable declared without an initialiser holds whatever was already in that memory.",
        3: "Give the variable a starting value where you declare it, for example long long total = 0;",
        4: "Practice: compile with -Wuninitialized and fix every warning before reading program output.",
    },
    "CPP_INT_OVERFLOW": {
        1: "Look at the largest value your computation can reach.",
        2: "An int holds about 2.1 billion. A sum or a product can pass that quickly.",
        3: "Use long long for any value that can grow past the int range.",
        4: "Practice: substitute the maximum input value and compute on paper; if it exceeds 2^31 use long long.",
    },
    "CPP_MISSING_BASE_CASE": {
        1: "Find the condition that stops the recursion.",
        2: "Every recursive function needs a case that returns without calling itself.",
        3: "Write the base case first, and check that it covers the smallest input.",
        4: "Practice: call your function with n = 0 or n = 1 and verify it returns immediately without recursing.",
    },
    "CPP_ASSIGN_VS_COMPARE": {
        1: "Look at every condition that uses a single =.",
        2: "Inside if or while a single = assigns, and it overwrites the value you meant to test.",
        3: "Use == to compare. When the compiler warns about parentheses in a condition, an assignment usually slipped in.",
        4: "Practice: compile with -Wall and treat every -Wparentheses warning as a likely assignment-in-condition bug.",
    },
    "CPP_WRONG_LOOP_DIR": {
        1: "Check the direction the loop variable moves on each pass.",
        2: "The loop variable must move towards the exit condition on every iteration.",
        3: "Use ++i to move forward and --i to move backward, and match the direction to the exit condition.",
        4: "Practice: add a print of i at the top of the loop body and check the first three values match the direction you intended.",
    },
    "CPP_RANGE_CHECK": {
        1: "Look at how the valid range is written. One condition is usually not enough.",
        2: "A range needs a lower bound and an upper bound, joined by &&.",
        3: "Write both bounds out: if (x >= low && x <= high). A chain such as low <= x <= high compiles but compares a boolean, so it is almost always wrong.",
        4: "Practice: test your condition with x = low-1, x = low, x = high, and x = high+1 and confirm it accepts exactly the right values.",
    },
    "CPP_STALE_EXIT": {
        1: "Check what changes the loop variable on each pass.",
        2: "A loop whose state never changes never reaches its exit condition.",
        3: "Move the increment into the body or keep ++i in the for header, and make sure every path updates the state.",
        4: "Practice: add a print of the loop variable at the end of the body; if it stays the same every iteration, it is never updated.",
    },
    # Open-set label: the model is not confident in a specific category.
    # Give general debugging guidance rather than a misconception hint.
    "CPP_OTHER_ERROR": {
        1: "Re-read the problem statement and trace through a small example by hand.",
        2: "Add a print statement after each step to check whether the values match what you expect.",
        3: "Compare your output to the expected output for the smallest test case. Work backwards from the first wrong value.",
        4: "Practice: rubber-duck debug — explain each line aloud and verify that it does exactly what you say.",
    },
}
GENERIC_HINT = "Re-read the problem and trace through a small example by hand."
