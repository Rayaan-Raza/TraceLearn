# Misconception coverage matrix

Taxonomy version: cpp-taxonomy-0.1
Date: 10 October 2026
Auditor: Agent 2, compliance and taxonomy audit
Scope: C++ misconceptions `CPP-M01` through `CPP-M08`
Standard: ASD-STE100 Simplified Technical English

---

## 1. Purpose

This matrix maps problem topics to the draft C++ taxonomy. It defines the test behaviors that expose each misconception. It defines the inputs that expose each misconception. It states the evidence that each misconception requires. It also states the coverage status of each misconception.

## 2. Taxonomy definitions

| ID | Misconception | Definition | Inclusion criteria | Exclusion criteria |
|---|---|---|---|---|
| `CPP-M01` | Exclusive upper bound treated as inclusive | The student treats an exclusive upper bound as inclusive. | The loop iterates one extra time. The upper boundary test fails. | An off-by-one error from a wrong start index alone. |
| `CPP-M02` | Element value confused with index position | The student confuses an element value with its index. | The code uses a value as an index. The code returns an index where a value is required. | Correct index arithmetic. |
| `CPP-M03` | Printing treated as equivalent to returning | The student prints a value where the contract requires a return. | The function prints the result. The caller receives no return value. | Printing as extra output beside a correct return. |
| `CPP-M04` | Index equal to container size treated as valid | The student treats index `size()` as valid. | The code accesses index `size()`. The loop permits that index. | An access at `size()-1`. That index is valid. |
| `CPP-M05` | Misunderstanding compound boolean comparison | The student chains comparisons as in mathematics. | The condition uses `a < b < c`. The range check gives a wrong result. | A correct conjunction of two comparisons. |
| `CPP-M06` | Confusing assignment and equality comparison | The student uses `=` where `==` is intended, or the reverse. | A condition holds an assignment. A comparison shows an assignment pattern. | An intentional assignment in a condition, with a comment. |
| `CPP-M07` | Recursion or iteration fails to make progress | The recursive call or the loop state does not approach termination. | The state does not change toward the base case. Small inputs time out. | Deep but terminating recursion. |
| `CPP-M08` | Loop fails to update exit condition | The exit condition stays unchanged on some path. | The loop runs after the termination point. The sentinel is never detected. | A correct update on every path. |

Rule: an observable defect is not a misconception. The defect must show the underlying belief. Weak or conflicting evidence receives an unknown outcome.

## 3. Required test behaviors and inputs

Each misconception needs at least two tests. One test must be a boundary test. One test must be a typical test. One negative control must pass for correct code.

### 3.1 `CPP-M01`: exclusive upper bound

| Item | Requirement |
|---|---|
| Test behavior 1 | The loop must iterate exactly n times for a range of n items. |
| Test behavior 2 | The boundary test must fail when the code includes index n. |
| Required input 1 | n = 0. The valid range is empty. |
| Required input 2 | n = 1. The valid range holds one item. |
| Required input 3 | A typical n with distinct values. |
| Exposing input | An array where item n differs from item n-1. A wrong bound changes the answer. |
| Negative control | A correct loop passes all tests. |
| Static evidence | `<=` against an exclusive bound. A `range(n+1)` analogue in C++. |
| Test evidence | The upper boundary test fails. The result holds one extra item. |

### 3.2 `CPP-M02`: element value versus index

| Item | Requirement |
|---|---|
| Test behavior 1 | The returned value must equal the element, not its position. |
| Test behavior 2 | The code must use an index only to reach an element. |
| Required input 1 | An array where no value equals its index. |
| Required input 2 | An array with duplicate values at different positions. |
| Required input 3 | A target value at a known position. |
| Exposing input | The array `{7, 3, 9}`. The maximum value is 9 at index 2. A solution that returns the index gives 2. The expected output is 9. |
| Negative control | A correct search returns the value. |
| Static evidence | A value used as an index. An index returned where a value is required. |
| Test evidence | The result equals a position, not the element. |

### 3.3 `CPP-M03`: printing versus returning

| Item | Requirement |
|---|---|
| Test behavior 1 | The caller must receive the value through the return channel. |
| Test behavior 2 | The standard output must not carry the result when the contract requires a return. |
| Required input 1 | Any input where the expected output is a function result. |
| Required input 2 | A test that captures the standard output and the return value separately. |
| Exposing input | A call inside an expression, such as `f(x) + 1`. A print-only solution yields no return value. |
| Negative control | A correct function returns the value. Extra printing stays absent or separate. |
| Static evidence | A `cout` statement where a `return` statement belongs. No `return` statement in a value function. |
| Test evidence | The caller receives a default value. The result differs from the printed text. |

### 3.4 `CPP-M04`: index equal to container size

| Item | Requirement |
|---|---|
| Test behavior 1 | An access at index `size()` must be rejected or guarded. |
| Test behavior 2 | A traversal loop must stop before `size()`. |
| Required input 1 | An empty container. The size is 0. |
| Required input 2 | A single-element container. The size is 1. |
| Required input 3 | A traversal that reads the last valid element only. |
| Exposing input | An empty vector. Any access at index 0 fails. A loop with `i <= size()` reads one past the end. |
| Negative control | A correct loop stops at `size()-1`. |
| Static evidence | `i <= vec.size()`. An access at `vec[vec.size()]`. |
| Test evidence | A runtime error on an empty container. A wrong last element. |

### 3.5 `CPP-M05`: compound boolean comparison

| Item | Requirement |
|---|---|
| Test behavior 1 | A range check must use an explicit conjunction of two comparisons. |
| Test behavior 2 | A chained comparison must not act as a mathematical chain. |
| Required input 1 | A value below the range. |
| Required input 2 | A value inside the range. |
| Required input 3 | A value above the range. |
| Required input 4 | A value equal to each limit. |
| Exposing input | The condition `1 <= x <= 10` in C++ evaluates as `(1 <= x) <= 10`. For x = 5, the result is true. For x = -5, the result is also true. The range check fails. |
| Negative control | A correct conjunction `1 <= x && x <= 10` passes all inputs. |
| Static evidence | A chained relational expression. A missing conjunction. |
| Test evidence | An out-of-range value passes the condition. |

### 3.6 `CPP-M06`: assignment versus equality

| Item | Requirement |
|---|---|
| Test behavior 1 | A condition must compare, not assign. |
| Test behavior 2 | The compiler must report warnings for assignment in a condition. |
| Required input 1 | A pair where `x = y` changes the value of `x`. |
| Required input 2 | A condition where the assignment yields a truthy value. |
| Exposing input | The condition `if (x = 0)` against `if (x == 0)`. The input starts with a non-zero x. The assignment form always takes the false branch. |
| Negative control | A correct comparison passes all inputs. |
| Static evidence | An assignment inside a condition. A missing equality operator. |
| Test evidence | The branch differs from the expected branch. The compiler emits a warning. |

### 3.7 `CPP-M07`: recursion or iteration without progress

| Item | Requirement |
|---|---|
| Test behavior 1 | Each recursive call must approach the base case. |
| Test behavior 2 | Each iteration must change the state toward termination. |
| Required input 1 | The smallest input. It is the base case. |
| Required input 2 | An input that needs one step. |
| Required input 3 | An input that needs several steps. |
| Exposing input | `factorial(0)`, `factorial(1)`, and `factorial(5)`. A call with a wrong argument never reaches the base case. The run times out. |
| Negative control | A correct recursion terminates on all inputs. |
| Static evidence | A recursive call with an unchanged argument. A loop body with no state change. |
| Test evidence | A timeout on a small input. A stack overflow. |

### 3.8 `CPP-M08`: loop exit condition not updated

| Item | Requirement |
|---|---|
| Test behavior 1 | The loop variable must change on every iteration. |
| Test behavior 2 | A sentinel-terminated loop must detect the sentinel. |
| Required input 1 | An input that terminates immediately. |
| Required input 2 | An input that needs several iterations. |
| Required input 3 | A sentinel value at the end of the data. |
| Exposing input | A search for an absent element. The loop must end when the search space is exhausted. A loop that never updates its condition times out. |
| Negative control | A correct loop ends at the right point. |
| Static evidence | An exit condition that references an unchanged variable. A missing update statement. |
| Test evidence | A timeout. A result that holds too many items. |

## 4. Topic-to-misconception map

The audit mapped the CodeStream problem topics to the taxonomy. The in-repo problems `P01` to `P06` appear as design templates only. They are Python problems. They must not serve as C++ practice problems.

| Problem | Topic | Primary misconception | Secondary misconception |
|---|---|---|---|
| `prob_017`, `prob_046` | Sort n integers by a rule | `CPP-M01` | `CPP-M08` |
| `prob_018`, `prob_045` | Check whether a list is sorted | `CPP-M01` | `CPP-M04` |
| `prob_019`, `prob_041` | Search a sorted list | `CPP-M04` | `CPP-M08` |
| `prob_020`, `prob_043` | Find the mid value when sorted | `CPP-M01` | `CPP-M02` |
| `prob_015`, `prob_042` | Find the unique integer among pairs | `CPP-M01` | `CPP-M02` |
| `prob_012`, `prob_030` | Insert into a linked list at first and last | `CPP-M04` | `CPP-M07` |
| `prob_013` | Evaluate a postfix expression | `CPP-M02` | `CPP-M07` |
| `prob_031` | Insert into a collection, report after each insert | `CPP-M08` | `CPP-M02` |
| `prob_032` | Print all values from two BST roots | `CPP-M07` | `CPP-M02` |
| `prob_033` | Hash function h(x) = x mod k | `CPP-M06` | `CPP-M05` |
| `prob_034` | Circle and point position | `CPP-M05` | `CPP-M06` |
| `prob_035` | Health diagnostic from weight and height | `CPP-M05` | `CPP-M06` |
| `prob_036` | Triangle side determination | `CPP-M05` | `CPP-M06` |
| `prob_025` | Annual income tax | `CPP-M05` | `CPP-M01` |
| `prob_001` to `prob_004` | String cipher and decode | `CPP-M01` | `CPP-M08` |
| `prob_005` | Subsequence check | `CPP-M08` | `CPP-M01` |
| `prob_007` | Robot grid delivery | `CPP-M04` | `CPP-M08` |
| `prob_009` | String calculation | `CPP-M01` | `CPP-M08` |
| `prob_014` | Palindrome check | `CPP-M01` | `CPP-M04` |
| `prob_016`, `prob_044` | Binary conversion | `CPP-M01` | `CPP-M08` |
| `prob_022` | Spell an integer in English words | `CPP-M01` | `CPP-M05` |
| `prob_028` | String with alphabets and digits | `CPP-M01` | `CPP-M08` |
| `prob_029` | Student heights | `CPP-M01` | `CPP-M02` |
| `prob_037` | Timestamp difference | `CPP-M01` | `CPP-M05` |
| `prob_038` | Character task | `CPP-M06` | `CPP-M05` |
| `prob_039`, `prob_040`, `prob_047`, `prob_048`, `prob_049`, `prob_050` | Graph traversal and components | `CPP-M07` | `CPP-M08` |

## 5. Source coverage summary

| Misconception | Practice problem topics | C++ code corpus for features | Label status |
|---|---|---|---|
| `CPP-M01` | CodeStream sorting, search, and string topics | CodeNet C++ corpus | No labels. Requires annotation. |
| `CPP-M02` | CodeStream list, postfix, and BST topics | PROGpedia C++ files | No labels. Requires annotation. |
| `CPP-M03` | No direct topic in the current bank | CodeNet C++ corpus | No labels. Requires new problem design. |
| `CPP-M04` | CodeStream search, list, and grid topics | PROGpedia C++ files | No labels. Requires annotation. |
| `CPP-M05` | CodeStream geometry, tax, and triangle topics | CodeNet C++ corpus | No labels. Requires annotation. |
| `CPP-M06` | CodeStream hash and character topics | CodeNet C++ corpus | No labels. Requires annotation. |
| `CPP-M07` | CodeStream graph and BST topics | PROGpedia C++ files | No labels. Requires annotation. |
| `CPP-M08` | CodeStream sorting and search topics | CodeNet C++ corpus | No labels. Requires annotation. |

## 6. Coverage gaps

1. No source supplies a label for any misconception.
2. The in-repo problems `P01` to `P06` are Python. They serve as design templates only.
3. PROGpedia holds only 659 C++ files. The C++ corpus is small.
4. CodeStream holds only 1,284 C++ submissions. The corpus is small.
5. CodeNet holds the largest C++ corpus but no verdicts.
6. The taxonomy has no C++ diagnostic tests. Each misconception needs its own diagnostic test set.
7. `CPP-M03` has no direct problem topic in the current CodeStream bank. The team must design a new problem with a return contract.

## 7. Rules for label creation

1. A label requires a written definition.
2. A label requires observable evidence.
3. A verdict never becomes a label by itself.
4. A practice problem never becomes a label.
5. Human labels, rule labels, and synthetic labels stay in separate fields.
6. Each label records its taxonomy version and its annotator.
7. Each label records its confidence and its rationale.
8. Weak or conflicting evidence receives an unknown outcome.
9. Each diagnostic test records its target misconception.
10. Each negative control records its expected pass result.

---

## Sign-off

This matrix uses the draft taxonomy `cpp-taxonomy-0.1`. Every mapping states its topic source. Every gap states its required action.
