from backend.app.execution.cpp_runner import CppExecutionRunner
r = CppExecutionRunner()
A = r'''#include <iostream>
#include <vector>
int main(){ std::vector<char> b(512ULL*1024*1024,1); std::cout<<b.size()<<"\n"; }'''
B = r'''#include <iostream>
#include <vector>
int main(){ std::vector<char> b(512ULL*1024*1024,1); long s=0; for(size_t i=0;i<b.size();i+=4096) s+=b[i]; std::cout<<s<<"\n"; }'''
for name, src in (("probe as written", A), ("probe that reads memory", B)):
    x = r.execute_with_stdin(src, "", 5)
    print(name, "->", x.status, x.error_type, repr(x.stdout[:30]), x.stderr[:80].replace("\n", " "))
