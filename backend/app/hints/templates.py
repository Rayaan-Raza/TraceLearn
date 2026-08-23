HINTS = {
    "M01_LOOP_BOUNDARY": {
        1: "Check which values your loop boundary actually includes.",
        2: "Compare the number of iterations with the number of items you intend to process.",
        3: "Review the upper bound supplied to range(). Remember that Python excludes the upper bound.",
    },
    "M02_INDEX_VALUE": {
        1: "Think about whether you need a position or the value stored at that position.",
        2: "When looping, decide if the loop variable is an index or an element value.",
        3: "Use the loop variable directly when you mean the element, not nums[variable] unless variable is an index.",
    },
    "M03_MISSING_RETURN": {
        1: "Make sure your function sends a result back to the caller.",
        2: "Printing shows output but does not return a value to the caller.",
        3: "Use return with the computed result on every code path that should produce an answer.",
    },
}
GENERIC_HINT = "Re-read the problem and trace through a small example by hand."
