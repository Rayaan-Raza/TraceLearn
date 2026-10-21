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

_AB = [  # CPP_ARRAY_BOUNDS  (operators: ab_array_size_minus1, ab_new_minus1 — caught by ASAN)
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

_IO = [  # CPP_INT_OVERFLOW  (operators: overflow_ll_sum_to_int, overflow_ll_acc_to_int)
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
