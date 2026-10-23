"""
seed_templates.py — Hand-crafted C++ seed programs for tl-cpp-v2 classes.
Per §9.0-G0c: used when CodeStream seeds lack the structural patterns targeted
by operator_library.json.  Each entry carries _inline_tests so the Verifier
does not need to look up the problem in the CSV.
"""

# Each seed dict:
#   submission_id : unique str (tpl-CLASS-NNN)
#   source_code   : compilable C++ that PASSES _inline_tests when correct
#   _inline_tests : list of {input, output} — mutant must FAIL at least one
#   _hint_class   : informational only

_LB = [  # CPP_LOOP_BOUNDARY  (operators: lb_le_to_lt, lb_while_le_to_lt)
    {
        "submission_id": "tpl-LB-001",
        "_hint_class": "CPP_LOOP_BOUNDARY",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long s=0;\n"
            "    for(int i=1;i<=n;i++) s+=i;\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "3",  "output": "6"},
            {"input": "10", "output": "55"},
        ],
    },
    {
        "submission_id": "tpl-LB-002",
        "_hint_class": "CPP_LOOP_BOUNDARY",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s=0;\n"
            "    for(int i=0;i<=n;i++) s+=i;\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "4",  "output": "10"},
            {"input": "1",  "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-LB-003",
        "_hint_class": "CPP_LOOP_BOUNDARY",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s=0, i=1;\n"
            "    while(i<=n){ s+=i; i++; }\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "15"},
            {"input": "3", "output": "6"},
            {"input": "1", "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-LB-004",
        "_hint_class": "CPP_LOOP_BOUNDARY",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int cnt=0;\n"
            "    for(int i=0;i<=n;i++) cnt++;\n"
            "    cout<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "6"},
            {"input": "0",  "output": "1"},
            {"input": "10", "output": "11"},
        ],
    },
    {
        "submission_id": "tpl-LB-005",
        "_hint_class": "CPP_LOOP_BOUNDARY",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int mx=a[0];\n"
            "    for(int i=0;i<=n-1;i++) if(a[i]>mx) mx=a[i];\n"
            "    cout<<mx<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n1 2 3 4",   "output": "4"},
            {"input": "4\n4 3 2 1",   "output": "4"},
            {"input": "3\n7 2 5",     "output": "7"},
        ],
    },
]

_OBO = [  # CPP_OFF_BY_ONE  (operators: obo_init_1_to_0, obo_bound_n_minus1, obo_index_plus1, obo_index_minus1)
    {
        "submission_id": "tpl-OBO-001",
        "_hint_class": "CPP_OFF_BY_ONE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int s=0;\n"
            "    for(int i=1;i<n;i++) s+=a[i];\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n10 1 2 3",  "output": "6"},
            {"input": "3\n99 5 5",    "output": "10"},
            {"input": "2\n0 7",       "output": "7"},
        ],
    },
    {
        "submission_id": "tpl-OBO-002",
        "_hint_class": "CPP_OFF_BY_ONE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int s=0;\n"
            "    for(int i=0;i<n-1;i++) s+=a[i];\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n1 2 3 4",   "output": "6"},
            {"input": "3\n5 3 2",     "output": "8"},
            {"input": "2\n7 3",       "output": "7"},
        ],
    },
    {
        "submission_id": "tpl-OBO-003",
        "_hint_class": "CPP_OFF_BY_ONE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[106]={};\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int prefix[106]={};\n"
            "    for(int i=0;i<n;i++) prefix[i+1]=prefix[i]+a[i];\n"
            "    cout<<prefix[n]<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n1 2 3 4",   "output": "10"},
            {"input": "3\n5 5 5",     "output": "15"},
            {"input": "1\n8",         "output": "8"},
        ],
    },
    {
        "submission_id": "tpl-OBO-004",
        "_hint_class": "CPP_OFF_BY_ONE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[106]={};\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int s=a[n-1]+a[n-2];\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5\n1 2 3 4 5",  "output": "9"},
            {"input": "3\n10 3 7",     "output": "10"},
            {"input": "2\n6 4",        "output": "10"},
        ],
    },
    {
        "submission_id": "tpl-OBO-005",
        "_hint_class": "CPP_OFF_BY_ONE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[106]={};\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int b[106]={};\n"
            "    for(int i=1;i<n;i++) b[i]=a[i-1]+a[i];\n"
            "    int s=0;\n"
            "    for(int i=0;i<n;i++) s+=b[i];\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 2 3",   "output": "8"},  # b=[0,3,5] sum=8
            {"input": "4\n1 1 1 1", "output": "6"},  # b=[0,2,2,2] sum=6
        ],
    },
]

_AB = [  # CPP_ARRAY_BOUNDS  (operators: ab_vector_init_minus1 — throws out_of_range on OOB, no ASAN needed)
    # NOTE: tpl-AB-001..003 rely on ASAN (unreliable on Windows/MinGW); tpl-AB-004+ use
    # vector::at() which throws std::out_of_range — detectable with standard compilation.
    {
        "submission_id": "tpl-AB-001",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int* arr = new int[n];\n"
            "    for(int i=0;i<n;i++) arr[i]=i+1;\n"
            "    long long s=0;\n"
            "    for(int i=0;i<n;i++) s+=arr[i];\n"
            "    cout<<s<<endl;\n"
            "    delete[] arr;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "4",  "output": "10"},
            {"input": "3",  "output": "6"},
        ],
    },
    {
        "submission_id": "tpl-AB-002",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int* a = new int[n];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int mx=a[0];\n"
            "    for(int i=1;i<n;i++) if(a[i]>mx) mx=a[i];\n"
            "    cout<<mx<<endl;\n"
            "    delete[] a;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n3 1 4 2", "output": "4"},
            {"input": "3\n5 9 2",   "output": "9"},
            {"input": "2\n7 3",     "output": "7"},
        ],
    },
    {
        "submission_id": "tpl-AB-003",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int* arr = new int[n];\n"
            "    for(int i=0;i<n;i++) arr[i]=i*2;\n"
            "    cout<<arr[n-1]<<endl;\n"
            "    delete[] arr;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "8"},  # arr[4]=8
            {"input": "3", "output": "4"},  # arr[2]=4
            {"input": "4", "output": "6"},  # arr[3]=6
        ],
    },
    # --- vector::at() templates: throw out_of_range on OOB, no ASAN required ---
    {
        "submission_id": "tpl-AB-004",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> v(n);\n"
            "    for(int i=0;i<n;i++) v[i]=i+1;\n"
            "    cout<<v.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "5"},
            {"input": "3", "output": "3"},
            {"input": "7", "output": "7"},
        ],
    },
    {
        "submission_id": "tpl-AB-005",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> vals(n);\n"
            "    for(int i=0;i<n;i++) cin>>vals[i];\n"
            "    cout<<vals.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n10 20 30 40", "output": "40"},
            {"input": "3\n5 6 7",       "output": "7"},
            {"input": "2\n1 9",         "output": "9"},
        ],
    },
    {
        "submission_id": "tpl-AB-006",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> buf(n);\n"
            "    for(int i=0;i<n;i++) buf[i]=i*3;\n"
            "    long long s=0;\n"
            "    for(int i=0;i<n;i++) s+=buf.at(i);\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4", "output": "18"},  # 0+3+6+9
            {"input": "3", "output": "9"},   # 0+3+6
            {"input": "5", "output": "30"},  # 0+3+6+9+12
        ],
    },
    {
        "submission_id": "tpl-AB-007",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> data(n);\n"
            "    for(int i=0;i<n;i++) cin>>data[i];\n"
            "    int mn=data.at(0);\n"
            "    for(int i=1;i<n;i++) mn=min(mn,data.at(i));\n"
            "    cout<<mn<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n8 2 5 1", "output": "1"},
            {"input": "3\n9 3 6",   "output": "3"},
            {"input": "2\n7 4",     "output": "4"},
        ],
    },
    {
        "submission_id": "tpl-AB-008",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> arr(n);\n"
            "    for(int i=0;i<n;i++) arr[i]=(i+1)*(i+1);\n"
            "    cout<<arr.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "25"},
            {"input": "3", "output": "9"},
            {"input": "4", "output": "16"},
        ],
    },
    # --- 25 more diverse vector::at() templates for scale coverage ---
    {
        "submission_id": "tpl-AB-009",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> nums(n);\n"
            "    for(int i=0;i<n;i++) nums[i]=i*i;\n"
            "    cout<<nums.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "16"}, {"input": "4", "output": "9"}, {"input": "6", "output": "25"},
        ],
    },
    {
        "submission_id": "tpl-AB-010",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> cnt(n);\n"
            "    for(int i=0;i<n;i++) cin>>cnt[i];\n"
            "    int s=0;\n"
            "    for(int i=0;i<n;i++) s+=cnt.at(i);\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n1 2 3 4", "output": "10"}, {"input": "3\n5 5 5", "output": "15"},
            {"input": "2\n7 8", "output": "15"},
        ],
    },
    {
        "submission_id": "tpl-AB-011",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> seq(n);\n"
            "    for(int i=0;i<n;i++) seq[i]=2*i+1;\n"
            "    cout<<seq.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "9"}, {"input": "3", "output": "5"}, {"input": "7", "output": "13"},
        ],
    },
    {
        "submission_id": "tpl-AB-012",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> row(n);\n"
            "    for(int i=0;i<n;i++) cin>>row[i];\n"
            "    cout<<row.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n4 5 6", "output": "6"}, {"input": "5\n1 1 1 1 9", "output": "9"},
            {"input": "2\n3 7", "output": "7"},
        ],
    },
    {
        "submission_id": "tpl-AB-013",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> tab(n);\n"
            "    for(int i=0;i<n;i++) tab[i]=n-i;\n"
            "    cout<<tab.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "1"}, {"input": "4", "output": "1"}, {"input": "3", "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-AB-014",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> prefix(n);\n"
            "    prefix[0]=1;\n"
            "    for(int i=1;i<n;i++) prefix[i]=prefix.at(i-1)*2;\n"
            "    cout<<prefix.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4", "output": "8"}, {"input": "5", "output": "16"}, {"input": "3", "output": "4"},
        ],
    },
    {
        "submission_id": "tpl-AB-015",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> items(n);\n"
            "    for(int i=0;i<n;i++) cin>>items[i];\n"
            "    int even=0;\n"
            "    for(int i=0;i<n;i++) if(items.at(i)%2==0) even++;\n"
            "    cout<<even<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5\n1 2 3 4 5", "output": "2"}, {"input": "4\n2 4 6 8", "output": "4"},
            {"input": "3\n1 3 5", "output": "0"},
        ],
    },
    {
        "submission_id": "tpl-AB-016",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> pts(n);\n"
            "    for(int i=0;i<n;i++) cin>>pts[i];\n"
            "    int mx=pts.at(0);\n"
            "    for(int i=1;i<n;i++) mx=max(mx,pts.at(i));\n"
            "    cout<<mx<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n3 9 2 7", "output": "9"}, {"input": "3\n1 2 3", "output": "3"},
            {"input": "2\n5 5", "output": "5"},
        ],
    },
    {
        "submission_id": "tpl-AB-017",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> scores(n);\n"
            "    for(int i=0;i<n;i++) cin>>scores[i];\n"
            "    int mn=scores.at(0);\n"
            "    for(int i=1;i<n;i++) mn=min(mn,scores.at(i));\n"
            "    cout<<mn<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n5 1 9 3", "output": "1"}, {"input": "3\n7 2 8", "output": "2"},
            {"input": "2\n4 6", "output": "4"},
        ],
    },
    {
        "submission_id": "tpl-AB-018",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> pos(n);\n"
            "    for(int i=0;i<n;i++) pos[i]=i+1;\n"
            "    int last=pos.at(n-1);\n"
            "    cout<<last<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "5"}, {"input": "3", "output": "3"}, {"input": "8", "output": "8"},
        ],
    },
    {
        "submission_id": "tpl-AB-019",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> pairs(n);\n"
            "    for(int i=0;i<n;i++) cin>>pairs[i];\n"
            "    long long prod=1;\n"
            "    for(int i=0;i<n;i++) prod*=pairs.at(i);\n"
            "    cout<<prod<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n2 3 4", "output": "24"}, {"input": "4\n1 2 3 4", "output": "24"},
            {"input": "2\n5 6", "output": "30"},
        ],
    },
    {
        "submission_id": "tpl-AB-020",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> line(n);\n"
            "    for(int i=0;i<n;i++) cin>>line[i];\n"
            "    cout<<line.at(0)<<\" \"<<line.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n10 20 30 40", "output": "10 40"}, {"input": "3\n5 6 7", "output": "5 7"},
            {"input": "2\n1 9", "output": "1 9"},
        ],
    },
    {
        "submission_id": "tpl-AB-021",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> span(n);\n"
            "    for(int i=0;i<n;i++) span[i]=i*2+3;\n"
            "    cout<<span.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4", "output": "9"}, {"input": "3", "output": "7"}, {"input": "5", "output": "11"},
        ],
    },
    {
        "submission_id": "tpl-AB-022",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> grid(n);\n"
            "    for(int i=0;i<n;i++) grid[i]=(i+1)*10;\n"
            "    int s=0;\n"
            "    for(int i=0;i<n;i++) s+=grid.at(i);\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4", "output": "100"}, {"input": "3", "output": "60"}, {"input": "5", "output": "150"},
        ],
    },
    {
        "submission_id": "tpl-AB-023",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> elems(n);\n"
            "    for(int i=0;i<n;i++) cin>>elems[i];\n"
            "    bool found=false;\n"
            "    for(int i=0;i<n;i++) if(elems.at(i)>0) found=true;\n"
            "    cout<<(found?\"YES\":\"NO\")<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n-1 0 2", "output": "YES"}, {"input": "3\n-1 -2 -3", "output": "NO"},
            {"input": "2\n0 1", "output": "YES"},
        ],
    },
    {
        "submission_id": "tpl-AB-024",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> heap(n);\n"
            "    for(int i=0;i<n;i++) heap[i]=100/(i+1);\n"
            "    cout<<heap.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4", "output": "25"}, {"input": "5", "output": "20"}, {"input": "2", "output": "50"},
        ],
    },
    {
        "submission_id": "tpl-AB-025",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> node(n);\n"
            "    for(int i=0;i<n;i++) cin>>node[i];\n"
            "    sort(node.begin(),node.end());\n"
            "    cout<<node.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n3 1 4 2", "output": "4"}, {"input": "3\n9 1 5", "output": "9"},
            {"input": "2\n2 8", "output": "8"},
        ],
    },
    {
        "submission_id": "tpl-AB-026",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> key(n);\n"
            "    for(int i=0;i<n;i++) key[i]=(n-i)*5;\n"
            "    cout<<key.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4", "output": "5"}, {"input": "3", "output": "5"}, {"input": "6", "output": "5"},
        ],
    },
    {
        "submission_id": "tpl-AB-027",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> chunk(n);\n"
            "    for(int i=0;i<n;i++) cin>>chunk[i];\n"
            "    long long mx=chunk.at(0);\n"
            "    for(int i=1;i<n;i++) if(chunk.at(i)>mx) mx=chunk.at(i);\n"
            "    cout<<mx<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n5 9 3 7", "output": "9"}, {"input": "3\n1 1 1", "output": "1"},
            {"input": "2\n100 50", "output": "100"},
        ],
    },
    {
        "submission_id": "tpl-AB-028",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> tier(n);\n"
            "    for(int i=0;i<n;i++) tier[i]=i+10;\n"
            "    cout<<tier.at(0)+tier.at(n-1)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "29"}, {"input": "3", "output": "25"}, {"input": "4", "output": "27"},
        ],
    },
    {
        "submission_id": "tpl-AB-029",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> map(n);\n"
            "    for(int i=0;i<n;i++) cin>>map[i];\n"
            "    long long s2=0;\n"
            "    for(int i=0;i<n;i++) s2+=(long long)map.at(i)*map.at(i);\n"
            "    cout<<s2<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n3 4 5", "output": "50"}, {"input": "2\n10 10", "output": "200"},
            {"input": "4\n1 2 3 4", "output": "30"},
        ],
    },
    {
        "submission_id": "tpl-AB-030",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> list(n);\n"
            "    for(int i=0;i<n;i++) list[i]=3*i;\n"
            "    for(int i=0;i<n;i++) cout<<list.at(i)<<\" \";\n"
            "    cout<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4", "output": "0 3 6 9 "}, {"input": "3", "output": "0 3 6 "},
            {"input": "5", "output": "0 3 6 9 12 "},
        ],
    },
    {
        "submission_id": "tpl-AB-031",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> inv(n);\n"
            "    for(int i=0;i<n;i++) cin>>inv[i];\n"
            "    sort(inv.begin(),inv.end());\n"
            "    cout<<inv.at(0)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n8 3 7 1", "output": "1"}, {"input": "3\n5 2 9", "output": "2"},
            {"input": "2\n4 6", "output": "4"},
        ],
    },
    {
        "submission_id": "tpl-AB-032",
        "_hint_class": "CPP_ARRAY_BOUNDS",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    vector<int> run(n);\n"
            "    for(int i=0;i<n;i++) cin>>run[i];\n"
            "    int cnt=0;\n"
            "    for(int i=0;i<n;i++) if(run.at(i)%3==0) cnt++;\n"
            "    cout<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5\n3 5 6 7 9", "output": "3"}, {"input": "4\n1 2 4 5", "output": "0"},
            {"input": "3\n3 6 9", "output": "3"},
        ],
    },
]

_UV = [  # CPP_UNINITIALIZED_VAR  (operators: uninit_int_zero, uninit_double_zero, uninit_multi_int, uninit_bool_false)
    {
        "submission_id": "tpl-UV-001",
        "_hint_class": "CPP_UNINITIALIZED_VAR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s = 0;\n"
            "    for(int i=1;i<=n;i++) s+=i;\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "3",  "output": "6"},
            {"input": "10", "output": "55"},
        ],
    },
    {
        "submission_id": "tpl-UV-002",
        "_hint_class": "CPP_UNINITIALIZED_VAR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int s = 0, cnt = 0;\n"
            "    for(int i=0;i<n;i++){ s+=a[i]; cnt++; }\n"
            "    cout<<s<<\" \"<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 2 3", "output": "6 3"},
            {"input": "2\n4 5",   "output": "9 2"},
        ],
    },
    {
        "submission_id": "tpl-UV-003",
        "_hint_class": "CPP_UNINITIALIZED_VAR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    double avg = 0.0;\n"
            "    for(int i=0;i<n;i++) avg+=a[i];\n"
            "    avg/=n;\n"
            "    cout<<fixed<<setprecision(2)<<avg<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n1 2 3 4", "output": "2.50"},
            {"input": "3\n6 6 6",   "output": "6.00"},
        ],
    },
    {
        "submission_id": "tpl-UV-004",
        "_hint_class": "CPP_UNINITIALIZED_VAR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    bool found = false;\n"
            "    for(int i=0;i<n;i++) if(a[i]<0) { found=true; break; }\n"
            "    cout<<(found ? 1 : 0)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 -1 2",  "output": "1"},
            {"input": "3\n1 2 3",   "output": "0"},
        ],
    },
]

_IO = [  # CPP_INT_OVERFLOW  (operators: overflow_ll_sum_to_int, overflow_ll_acc_to_int,
        #                              overflow_remove_ll_cast, overflow_1ll_removed)
    {
        "submission_id": "tpl-IO-001",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long sum=0;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        sum+=x;\n"
            "    }\n"
            "    cout<<sum<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1000000000 1000000000 1000000000", "output": "3000000000"},
            {"input": "2\n2000000000 2000000000",            "output": "4000000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-002",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long total = 0;\n"
            "    for(int i=1;i<=n;i++){\n"
            "        long long x; cin>>x;\n"
            "        total+=x;\n"
            "    }\n"
            "    cout<<total<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "2\n1500000000 1500000000", "output": "3000000000"},
            {"input": "1\n2100000000",             "output": "2100000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-003",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    long long n; cin>>n;\n"
            "    long long ans = n*(n+1)/2;\n"
            "    cout<<ans<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000",    "output": "5000050000"},
            {"input": "1000",      "output": "500500"},
        ],
    },
    {
        "submission_id": "tpl-IO-004",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long result = 0;\n"
            "    for(int i=0;i<n;i++){\n"
            "        long long x; cin>>x;\n"
            "        result += x*x;\n"
            "    }\n"
            "    cout<<result<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n100000 100000 100000", "output": "30000000000"},
            {"input": "2\n50000 60000",           "output": "6100000000"},
        ],
    },
    # --- (long long) cast templates (overflow_remove_ll_cast) ---
    {
        "submission_id": "tpl-IO-005",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int a, b; cin>>a>>b;\n"
            "    long long prod = (long long)a * b;\n"
            "    cout<<prod<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000 100000",   "output": "10000000000"},
            {"input": "50000 60000",     "output": "3000000000"},
            {"input": "200000 200000",   "output": "40000000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-006",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long total = (long long)n * (n + 1) / 2;\n"
            "    cout<<total<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000",  "output": "5000050000"},
            {"input": "200000",  "output": "20000100000"},
            {"input": "50000",   "output": "1250025000"},
        ],
    },
    # --- 1LL multiplication templates (overflow_1ll_removed) ---
    {
        "submission_id": "tpl-IO-007",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int a, b; cin>>a>>b;\n"
            "    long long ans = 1LL * a * b;\n"
            "    cout<<ans<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000 100000",   "output": "10000000000"},
            {"input": "80000 90000",     "output": "7200000000"},
            {"input": "150000 150000",   "output": "22500000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-008",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n, m; cin>>n>>m;\n"
            "    long long grid = 1LL * n * m;\n"
            "    cout<<grid<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000 100000",   "output": "10000000000"},
            {"input": "70000 80000",     "output": "5600000000"},
            {"input": "200000 300000",   "output": "60000000000"},
        ],
    },
    # --- Multi-form templates: combine (long long) cast + 1LL + named acc ---
    {
        "submission_id": "tpl-IO-009",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int a, b, c; cin>>a>>b>>c;\n"
            "    long long ans = (long long)a * b + (long long)b * c;\n"
            "    cout<<ans<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000 100000 100000", "output": "20000000000"},
            {"input": "50000 60000 70000",    "output": "7200000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-010",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long ans = 1LL * n * n;\n"
            "    cout<<ans<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "200000", "output": "40000000000"},
            {"input": "100000", "output": "10000000000"},
            {"input": "150000", "output": "22500000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-011",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long total = 0;\n"
            "    for(int i=1;i<=n;i++) total+=i;\n"
            "    cout<<total<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000", "output": "5000050000"},
            {"input": "200000", "output": "20000100000"},
        ],
    },
    {
        "submission_id": "tpl-IO-012",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int h, w; cin>>h>>w;\n"
            "    long long area = 1LL * h * w;\n"
            "    cout<<area<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "200000 200000", "output": "40000000000"},
            {"input": "100000 300000", "output": "30000000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-013",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long ans = (long long)n * (n-1) / 2;\n"
            "    cout<<ans<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000", "output": "4999950000"},
            {"input": "200000", "output": "19999900000"},
        ],
    },
    {
        "submission_id": "tpl-IO-014",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    long long result = 0;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        result += (long long)x * x;\n"
            "    }\n"
            "    cout<<result<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n100000 100000 100000", "output": "30000000000"},
            {"input": "2\n70000 80000",           "output": "11300000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-015",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int a, b; cin>>a>>b;\n"
            "    long long sum = (long long)a * b;\n"
            "    cout<<sum<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100000 200000", "output": "20000000000"},
            {"input": "150000 150000", "output": "22500000000"},
        ],
    },
    {
        "submission_id": "tpl-IO-016",
        "_hint_class": "CPP_INT_OVERFLOW",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    long long n; cin>>n;\n"
            "    long long ans = n*(n+1)*(n+2)/6;\n"
            "    cout<<ans<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "100",   "output": "171700"},
            {"input": "1000",  "output": "167167000"},
        ],
    },
]

_MBC = [  # CPP_MISSING_BASE_CASE  (operators: mbc_remove_base_n0, mbc_remove_base_eq1, mbc_remove_return_base)
    {
        "submission_id": "tpl-MBC-001",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int fact(int n){\n"
            "    if(n == 0) { return 1; }\n"
            "    return n * fact(n-1);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<fact(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "120"},
            {"input": "3",  "output": "6"},
            {"input": "0",  "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-MBC-002",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int sum_to(int n){\n"
            "    if(n == 1) return 1;\n"
            "    return n + sum_to(n-1);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<sum_to(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5", "output": "15"},
            {"input": "3", "output": "6"},
            {"input": "1", "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-MBC-003",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int power(int base, int exp){\n"
            "    if(exp == 0) return 1;\n"
            "    return base * power(base, exp-1);\n"
            "}\n"
            "int main(){\n"
            "    int b, e; cin>>b>>e;\n"
            "    cout<<power(b,e)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "2 5",  "output": "32"},
            {"input": "3 3",  "output": "27"},
            {"input": "5 0",  "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-MBC-004",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int fib(int n){\n"
            "    if(n <= 1) { return n; }\n"
            "    return fib(n-1)+fib(n-2);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<fib(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "7",  "output": "13"},
            {"input": "5",  "output": "5"},
            {"input": "0",  "output": "0"},
        ],
    },
    {
        "submission_id": "tpl-MBC-005",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int gcd_r(int a, int b){\n"
            "    if(b == 0) return a;\n"
            "    return gcd_r(b, a%b);\n"
            "}\n"
            "int main(){\n"
            "    int a, b; cin>>a>>b;\n"
            "    cout<<gcd_r(a,b)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "12 8", "output": "4"},
            {"input": "7 3",  "output": "1"},
            {"input": "9 6",  "output": "3"},
        ],
    },
    # --- Multi-form templates: multiple base-case patterns per function ---
    # Each of these matches 2+ MBC operators → more verified mutants per seed
    {
        "submission_id": "tpl-MBC-006",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int fib2(int n){\n"
            "    if(n == 0) { return 0; }\n"
            "    if(n == 1) return 1;\n"
            "    return fib2(n-1) + fib2(n-2);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<fib2(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "7",  "output": "13"},
            {"input": "6",  "output": "8"},
            {"input": "0",  "output": "0"},
            {"input": "1",  "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-MBC-007",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int fact2(int n){\n"
            "    if(n == 0) { return 1; }\n"
            "    if(n == 1) return 1;\n"
            "    return n * fact2(n-1);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<fact2(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "120"},
            {"input": "4",  "output": "24"},
            {"input": "0",  "output": "1"},
            {"input": "1",  "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-MBC-008",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int tri(int n){\n"
            "    if(n <= 1) { return n; }\n"
            "    if(n == 1) return 1;\n"
            "    return n + tri(n-1);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<tri(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "4",  "output": "10"},
            {"input": "0",  "output": "0"},
            {"input": "1",  "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-MBC-009",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int pow2(int n){\n"
            "    if(n == 0) { return 1; }\n"
            "    return 2 * pow2(n-1);\n"
            "}\n"
            "int digitsum(int n){\n"
            "    if(n == 0) { return 0; }\n"
            "    return n%10 + digitsum(n/10);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<pow2(n)<<\" \"<<digitsum(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",   "output": "32 5"},
            {"input": "3",   "output": "8 3"},
            {"input": "10",  "output": "1024 1"},
        ],
    },
    {
        "submission_id": "tpl-MBC-010",
        "_hint_class": "CPP_MISSING_BASE_CASE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int count_steps(int n){\n"
            "    if(n == 0) { return 0; }\n"
            "    if(n == 1) return 1;\n"
            "    if(n == 1) return 1;\n"
            "    return 1 + count_steps(n-1);\n"
            "}\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    cout<<count_steps(n)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "5"},
            {"input": "3",  "output": "3"},
            {"input": "0",  "output": "0"},
        ],
    },
]

_AVC = [  # CPP_ASSIGN_VS_COMPARE  (operators: avc_eq_to_assign_if, avc_ne_to_assign_if)
    {
        "submission_id": "tpl-AVC-001",
        "_hint_class": "CPP_ASSIGN_VS_COMPARE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int target; cin>>target;\n"
            "    int cnt=0;\n"
            "    for(int i=0;i<n;i++)\n"
            "        if(a[i] == target) cnt++;\n"
            "    cout<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5\n1 2 3 2 1\n2",  "output": "2"},
            {"input": "4\n3 3 3 3\n3",    "output": "4"},
            {"input": "3\n1 2 3\n5",      "output": "0"},
        ],
    },
    {
        "submission_id": "tpl-AVC-002",
        "_hint_class": "CPP_ASSIGN_VS_COMPARE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int x; cin>>x;\n"
            "    bool ok=false;\n"
            "    for(int i=0;i<n;i++)\n"
            "        if(a[i] != x) { ok=true; break; }\n"
            "    cout<<(ok?1:0)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 1 1\n1",  "output": "0"},
            {"input": "3\n1 2 3\n1",  "output": "1"},
        ],
    },
    {
        "submission_id": "tpl-AVC-003",
        "_hint_class": "CPP_ASSIGN_VS_COMPARE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105], b[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    for(int i=0;i<n;i++) cin>>b[i];\n"
            "    int cnt=0;\n"
            "    for(int i=0;i<n;i++)\n"
            "        if(a[i] == b[i]) cnt++;\n"
            "    cout<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 2 3\n1 5 3",  "output": "2"},
            {"input": "3\n1 2 3\n4 5 6",  "output": "0"},
        ],
    },
    {
        "submission_id": "tpl-AVC-004",
        "_hint_class": "CPP_ASSIGN_VS_COMPARE",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int q; cin>>q;\n"
            "    while(q--){\n"
            "        int x, y; cin>>x>>y;\n"
            "        if(x == y) cout<<\"EQUAL\"<<endl;\n"
            "        else cout<<\"DIFF\"<<endl;\n"
            "    }\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 1\n2 3\n0 0",  "output": "EQUAL\nDIFF\nEQUAL"},
            {"input": "1\n5 5",             "output": "EQUAL"},
        ],
    },
]

_WLD = [  # CPP_WRONG_LOOP_DIR  (operators: wld_incr_to_decr, wld_start_0_to_n, wld_lt_to_gt, wld_inc_step_to_dec)
    {
        "submission_id": "tpl-WLD-001",
        "_hint_class": "CPP_WRONG_LOOP_DIR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s=0;\n"
            "    for(int i=1;i<=n;i++) s+=i;\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "3",  "output": "6"},
        ],
    },
    {
        "submission_id": "tpl-WLD-002",
        "_hint_class": "CPP_WRONG_LOOP_DIR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s=0;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        s+=x;\n"
            "    }\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n1 2 3 4",  "output": "10"},
            {"input": "3\n5 5 5",    "output": "15"},
        ],
    },
    {
        "submission_id": "tpl-WLD-003",
        "_hint_class": "CPP_WRONG_LOOP_DIR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s=0;\n"
            "    for(int i=0;i<n;i+=1) s+=i;\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "10"},
            {"input": "4",  "output": "6"},
        ],
    },
    {
        "submission_id": "tpl-WLD-004",
        "_hint_class": "CPP_WRONG_LOOP_DIR",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    int s=0;\n"
            "    for(int i=0;i<n;i++) s+=a[i];\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 2 3",  "output": "6"},
            {"input": "4\n1 1 1 1","output": "4"},
        ],
    },
]

_RC = [  # CPP_RANGE_CHECK  (operators: rc_ge_to_gt, rc_le_to_lt, rc_lt1_to_le0)
    {
        "submission_id": "tpl-RC-001",
        "_hint_class": "CPP_RANGE_CHECK",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        if(x >= 0) cout<<\"Y\";\n"
            "        else cout<<\"N\";\n"
            "    }\n"
            "    cout<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n-1 0 1",  "output": "NYY"},
            {"input": "2\n0 -5",    "output": "YN"},
        ],
    },
    {
        "submission_id": "tpl-RC-002",
        "_hint_class": "CPP_RANGE_CHECK",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        if(x <= 10) cout<<\"Y\";\n"
            "        else cout<<\"N\";\n"
            "    }\n"
            "    cout<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n9 10 11",  "output": "YYN"},
            {"input": "2\n10 0",     "output": "YY"},
        ],
    },
    {
        "submission_id": "tpl-RC-003",
        "_hint_class": "CPP_RANGE_CHECK",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        if(x < 1) cout<<\"Y\";\n"
            "        else cout<<\"N\";\n"
            "    }\n"
            "    cout<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n0 1 2",    "output": "YNN"},
            {"input": "2\n-1 1",     "output": "YN"},
        ],
    },
    {
        "submission_id": "tpl-RC-004",
        "_hint_class": "CPP_RANGE_CHECK",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int cnt=0;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        if(x >= 1) cnt++;\n"
            "    }\n"
            "    cout<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n0 1 2 3",  "output": "3"},
            {"input": "3\n-1 1 2",   "output": "2"},
        ],
    },
    {
        "submission_id": "tpl-RC-005",
        "_hint_class": "CPP_RANGE_CHECK",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int cnt=0;\n"
            "    for(int i=0;i<n;i++){\n"
            "        int x; cin>>x;\n"
            "        if(x <= 100) cnt++;\n"
            "    }\n"
            "    cout<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "4\n99 100 101 200",  "output": "2"},
            {"input": "3\n100 100 100",      "output": "3"},
        ],
    },
]

_SE = [  # CPP_STALE_EXIT  (operators: se_remove_incr_in_while, se_frozen_counter, se_remove_flag_update, se_remove_break_condition)
    {
        "submission_id": "tpl-SE-001",
        "_hint_class": "CPP_STALE_EXIT",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s=0, i=1;\n"
            "    while(i<=n){\n"
            "        s+=i;\n"
            "        i++;\n"
            "    }\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "3",  "output": "6"},
        ],
    },
    {
        "submission_id": "tpl-SE-002",
        "_hint_class": "CPP_STALE_EXIT",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int i=0, s=0;\n"
            "    while(i<n){\n"
            "        s+=i;\n"
            "        i++;\n"
            "    }\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "10"},
            {"input": "4",  "output": "6"},
        ],
    },
    {
        "submission_id": "tpl-SE-003",
        "_hint_class": "CPP_STALE_EXIT",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int s=0;\n"
            "    for(int i=1;;i++){\n"
            "        if(i>n) break;\n"
            "        s+=i;\n"
            "    }\n"
            "    cout<<s<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "15"},
            {"input": "3",  "output": "6"},
        ],
    },
    {
        "submission_id": "tpl-SE-004",
        "_hint_class": "CPP_STALE_EXIT",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int a[105];\n"
            "    for(int i=0;i<n;i++) cin>>a[i];\n"
            "    bool flag=false;\n"
            "    int i=0;\n"
            "    while(!flag && i<n){\n"
            "        if(a[i]<0) flag=true;\n"
            "        i++;\n"
            "    }\n"
            "    cout<<(flag?1:0)<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "3\n1 -1 2",   "output": "1"},
            {"input": "3\n1 2 3",    "output": "0"},
        ],
    },
    {
        "submission_id": "tpl-SE-005",
        "_hint_class": "CPP_STALE_EXIT",
        "source_code": (
            "#include<bits/stdc++.h>\nusing namespace std;\n"
            "int main(){\n"
            "    int n; cin>>n;\n"
            "    int cnt=0, i=n;\n"
            "    while(i>0){\n"
            "        cnt++;\n"
            "        i--;\n"
            "    }\n"
            "    cout<<cnt<<endl;\n"
            "}"
        ),
        "_inline_tests": [
            {"input": "5",  "output": "5"},
            {"input": "3",  "output": "3"},
        ],
    },
]

SEED_TEMPLATES = {
    "CPP_LOOP_BOUNDARY":    _LB,
    "CPP_OFF_BY_ONE":       _OBO,
    "CPP_ARRAY_BOUNDS":     _AB,
    "CPP_UNINITIALIZED_VAR":_UV,
    "CPP_INT_OVERFLOW":     _IO,
    "CPP_MISSING_BASE_CASE":_MBC,
    "CPP_ASSIGN_VS_COMPARE":_AVC,
    "CPP_WRONG_LOOP_DIR":   _WLD,
    "CPP_RANGE_CHECK":      _RC,
    "CPP_STALE_EXIT":       _SE,
}
