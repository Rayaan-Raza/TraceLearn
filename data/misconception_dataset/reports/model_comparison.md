# Model families on the held-out problems

324 rows, unseen problems; fixed hyper-parameters; abstain below 0.6.

| Model | Train set | Mode | Accuracy | False alarm | Precision flagged (n) | Recall | Abstain | Macro-F1 |
|---|---|---|---|---|---|---|---|---|
| always OTHER | all | abstain_rule | 0.688 | 0.0 | None (0) | 0.0 | 0.0 | 0.091 |
| always OTHER | all | argmax | 0.688 | 0.0 | None (0) | 0.0 | 0.0 | 0.091 |
| xgboost | all | best (static+warnings+semantics) | abstain_rule | 0.772 | 0.054 | 0.778 (63) | 0.485 | 0.046 | 0.264 |
| xgboost | all | best (static+warnings+semantics) | argmax | 0.796 | 0.063 | 0.742 (66) | 0.485 | 0.0 | 0.265 |
| xgboost | real | best (static+warnings+semantics) | abstain_rule | 0.806 | 0.045 | 0.814 (59) | 0.475 | 0.003 | 0.192 |
| xgboost | real | best (static+warnings+semantics) | argmax | 0.806 | 0.045 | 0.8 (60) | 0.475 | 0.0 | 0.191 |
| xgboost | all | best+runtime+tests | abstain_rule | 0.784 | 0.054 | 0.774 (62) | 0.475 | 0.031 | 0.354 |
| xgboost | all | best+runtime+tests | argmax | 0.809 | 0.058 | 0.776 (67) | 0.515 | 0.0 | 0.39 |
| xgboost | real | best+runtime+tests | abstain_rule | 0.809 | 0.049 | 0.81 (63) | 0.505 | 0.022 | 0.267 |
| xgboost | real | best+runtime+tests | argmax | 0.818 | 0.049 | 0.791 (67) | 0.525 | 0.0 | 0.294 |
| xgboost | all | all features | abstain_rule | 0.806 | 0.049 | 0.815 (65) | 0.525 | 0.019 | 0.402 |
| xgboost | all | all features | argmax | 0.821 | 0.054 | 0.809 (68) | 0.545 | 0.0 | 0.441 |
| xgboost | real | all features | abstain_rule | 0.818 | 0.045 | 0.828 (64) | 0.525 | 0.012 | 0.294 |
| xgboost | real | all features | argmax | 0.821 | 0.049 | 0.818 (66) | 0.535 | 0.0 | 0.338 |
| random_forest | all | best (static+warnings+semantics) | abstain_rule | 0.207 | 0.004 | 0.5 (2) | 0.01 | 0.698 | 0.12 |
| random_forest | all | best (static+warnings+semantics) | argmax | 0.664 | 0.054 | 0.222 (18) | 0.04 | 0.0 | 0.15 |
| random_forest | real | best (static+warnings+semantics) | abstain_rule | 0.401 | 0.0 | None (0) | 0.0 | 0.426 | 0.071 |
| random_forest | real | best (static+warnings+semantics) | argmax | 0.685 | 0.004 | 0.0 (1) | 0.0 | 0.0 | 0.09 |
| random_forest | all | best+runtime+tests | abstain_rule | 0.491 | 0.049 | 0.774 (53) | 0.406 | 0.414 | 0.159 |
| random_forest | all | best+runtime+tests | argmax | 0.793 | 0.067 | 0.754 (65) | 0.485 | 0.0 | 0.238 |
| random_forest | real | best+runtime+tests | abstain_rule | 0.602 | 0.027 | 0.611 (18) | 0.109 | 0.262 | 0.126 |
| random_forest | real | best+runtime+tests | argmax | 0.806 | 0.045 | 0.814 (59) | 0.475 | 0.0 | 0.191 |
| random_forest | all | all features | abstain_rule | 0.5 | 0.049 | 0.774 (53) | 0.406 | 0.398 | 0.232 |
| random_forest | all | all features | argmax | 0.796 | 0.063 | 0.766 (64) | 0.485 | 0.0 | 0.235 |
| random_forest | real | all features | abstain_rule | 0.667 | 0.031 | 0.778 (36) | 0.277 | 0.198 | 0.163 |
| random_forest | real | all features | argmax | 0.806 | 0.045 | 0.814 (59) | 0.475 | 0.0 | 0.191 |
| extra_trees | all | best (static+warnings+semantics) | abstain_rule | 0.108 | 0.004 | 0.5 (2) | 0.01 | 0.855 | 0.102 |
| extra_trees | all | best (static+warnings+semantics) | argmax | 0.636 | 0.108 | 0.206 (34) | 0.069 | 0.0 | 0.158 |
| extra_trees | real | best (static+warnings+semantics) | abstain_rule | 0.16 | 0.0 | None (0) | 0.0 | 0.781 | 0.039 |
| extra_trees | real | best (static+warnings+semantics) | argmax | 0.676 | 0.027 | 0.182 (11) | 0.02 | 0.0 | 0.168 |
| extra_trees | all | best+runtime+tests | abstain_rule | 0.398 | 0.049 | 0.769 (52) | 0.396 | 0.528 | 0.218 |
| extra_trees | all | best+runtime+tests | argmax | 0.781 | 0.094 | 0.68 (75) | 0.505 | 0.0 | 0.281 |
| extra_trees | real | best+runtime+tests | abstain_rule | 0.546 | 0.022 | 0.5 (12) | 0.059 | 0.346 | 0.11 |
| extra_trees | real | best+runtime+tests | argmax | 0.799 | 0.054 | 0.774 (62) | 0.475 | 0.0 | 0.234 |
| extra_trees | all | all features | abstain_rule | 0.389 | 0.058 | 0.745 (55) | 0.406 | 0.537 | 0.188 |
| extra_trees | all | all features | argmax | 0.79 | 0.081 | 0.708 (72) | 0.505 | 0.0 | 0.304 |
| extra_trees | real | all features | abstain_rule | 0.556 | 0.031 | 0.556 (18) | 0.099 | 0.33 | 0.12 |
| extra_trees | real | all features | argmax | 0.809 | 0.045 | 0.817 (60) | 0.485 | 0.0 | 0.247 |
| logistic_regression | all | best (static+warnings+semantics) | abstain_rule | 0.198 | 0.3 | 0.077 (104) | 0.079 | 0.448 | 0.07 |
| logistic_regression | all | best (static+warnings+semantics) | argmax | 0.346 | 0.605 | 0.117 (206) | 0.238 | 0.0 | 0.112 |
| logistic_regression | real | best (static+warnings+semantics) | abstain_rule | 0.321 | 0.229 | 0.087 (69) | 0.059 | 0.358 | 0.163 |
| logistic_regression | real | best (static+warnings+semantics) | argmax | 0.432 | 0.43 | 0.09 (144) | 0.129 | 0.0 | 0.181 |
| logistic_regression | all | best+runtime+tests | abstain_rule | 0.457 | 0.274 | 0.35 (120) | 0.416 | 0.228 | 0.212 |
| logistic_regression | all | best+runtime+tests | argmax | 0.546 | 0.413 | 0.282 (163) | 0.455 | 0.0 | 0.193 |
| logistic_regression | real | best+runtime+tests | abstain_rule | 0.546 | 0.193 | 0.391 (87) | 0.337 | 0.185 | 0.22 |
| logistic_regression | real | best+runtime+tests | argmax | 0.633 | 0.256 | 0.336 (116) | 0.386 | 0.0 | 0.231 |
| logistic_regression | all | all features | abstain_rule | 0.494 | 0.283 | 0.37 (127) | 0.465 | 0.191 | 0.2 |
| logistic_regression | all | all features | argmax | 0.552 | 0.413 | 0.286 (168) | 0.475 | 0.0 | 0.183 |
| logistic_regression | real | all features | abstain_rule | 0.608 | 0.139 | 0.488 (82) | 0.396 | 0.179 | 0.214 |
| logistic_regression | real | all features | argmax | 0.67 | 0.229 | 0.391 (115) | 0.446 | 0.0 | 0.216 |
| knn | all | best (static+warnings+semantics) | abstain_rule | 0.488 | 0.072 | 0.136 (22) | 0.03 | 0.247 | 0.098 |
| knn | all | best (static+warnings+semantics) | argmax | 0.62 | 0.135 | 0.167 (48) | 0.079 | 0.0 | 0.12 |
| knn | real | best (static+warnings+semantics) | abstain_rule | 0.515 | 0.022 | 0.25 (8) | 0.02 | 0.247 | 0.102 |
| knn | real | best (static+warnings+semantics) | argmax | 0.645 | 0.085 | 0.161 (31) | 0.05 | 0.0 | 0.127 |
| knn | all | best+runtime+tests | abstain_rule | 0.623 | 0.076 | 0.667 (60) | 0.396 | 0.201 | 0.236 |
| knn | all | best+runtime+tests | argmax | 0.756 | 0.121 | 0.605 (81) | 0.485 | 0.0 | 0.245 |
| knn | real | best+runtime+tests | abstain_rule | 0.67 | 0.018 | 0.75 (24) | 0.178 | 0.142 | 0.19 |
| knn | real | best+runtime+tests | argmax | 0.75 | 0.045 | 0.714 (42) | 0.297 | 0.0 | 0.275 |
| knn | all | all features | abstain_rule | 0.682 | 0.094 | 0.689 (74) | 0.505 | 0.142 | 0.253 |
| knn | all | all features | argmax | 0.769 | 0.121 | 0.631 (84) | 0.525 | 0.0 | 0.253 |
| knn | real | all features | abstain_rule | 0.781 | 0.049 | 0.8 (60) | 0.475 | 0.052 | 0.251 |
| knn | real | all features | argmax | 0.806 | 0.058 | 0.785 (65) | 0.505 | 0.0 | 0.306 |
| mlp | all | best (static+warnings+semantics) | abstain_rule | 0.583 | 0.148 | 0.13 (54) | 0.069 | 0.034 | 0.121 |
| mlp | all | best (static+warnings+semantics) | argmax | 0.593 | 0.175 | 0.131 (61) | 0.079 | 0.0 | 0.123 |
| mlp | real | best (static+warnings+semantics) | abstain_rule | 0.633 | 0.054 | 0.24 (25) | 0.059 | 0.04 | 0.128 |
| mlp | real | best (static+warnings+semantics) | argmax | 0.651 | 0.081 | 0.188 (32) | 0.059 | 0.0 | 0.129 |
| mlp | all | best+runtime+tests | abstain_rule | 0.654 | 0.152 | 0.402 (82) | 0.327 | 0.052 | 0.233 |
| mlp | all | best+runtime+tests | argmax | 0.673 | 0.175 | 0.362 (94) | 0.337 | 0.0 | 0.211 |
| mlp | real | best+runtime+tests | abstain_rule | 0.704 | 0.081 | 0.569 (51) | 0.287 | 0.043 | 0.209 |
| mlp | real | best+runtime+tests | argmax | 0.719 | 0.099 | 0.533 (60) | 0.317 | 0.0 | 0.237 |
| mlp | all | all features | abstain_rule | 0.642 | 0.188 | 0.344 (90) | 0.307 | 0.043 | 0.326 |
| mlp | all | all features | argmax | 0.66 | 0.197 | 0.347 (101) | 0.347 | 0.0 | 0.339 |
| mlp | real | all features | abstain_rule | 0.772 | 0.108 | 0.627 (83) | 0.515 | 0.006 | 0.246 |
| mlp | real | all features | argmax | 0.772 | 0.112 | 0.612 (85) | 0.515 | 0.0 | 0.246 |
