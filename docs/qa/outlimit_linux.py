from backend.app.execution.cpp_runner import CppExecutionRunner
src = '#include <iostream>\nint main(){ for(long i=0;i<100000000;i++) std::cout << "xxxxxxxxxx"; }\n'
r = CppExecutionRunner().execute_with_stdin(src, "", 5)
print(r.status, r.error_type, r.stderr[:80])
