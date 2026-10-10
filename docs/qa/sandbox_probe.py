import uuid, httpx
B = "http://127.0.0.1:8000"; R = uuid.uuid4().hex[:6]
s = httpx.post(B + "/api/auth/register", json={"email": f"sb_{R}@qa.test", "password": "Passw0rd!QA", "role": "student"}).json()
S = httpx.Client(base_url=B, timeout=60, headers={"Authorization": "Bearer " + s["access_token"]})
PROBE = r'''#include <fstream>
#include <iostream>
#include <string>
#include <cstdlib>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
int main(){
  const char* ps[]={"/home","/root","/etc/passwd","/etc/hostname","/proc/1/cmdline","tracelearn.db",".env","/mnt/c/Windows/win.ini"};
  for(auto p:ps){ std::ifstream f(p); std::string l; bool ok=(bool)std::getline(f,l); std::cout<<p<<"="<<(ok?"READ":"no")<<" "; }
  std::cout<<"ENV_SECRET="<<(std::getenv("SECRET_KEY")?"present":"absent")<<" ";
  std::cout<<"HOME="<<(std::getenv("HOME")?std::getenv("HOME"):"-")<<" ";
  int sk=socket(AF_INET,SOCK_STREAM,0); sockaddr_in a{}; a.sin_family=AF_INET; a.sin_port=htons(53); inet_pton(AF_INET,"8.8.8.8",&a.sin_addr);
  std::cout<<"NET="<<(connect(sk,(sockaddr*)&a,sizeof a)==0?"CONNECTED":"blocked")<<" ";
  std::cout<<"PID="<<getpid()<<"\n";
}'''
sid = S.post("/api/submissions", json={"problem_id": "CP01", "source_code": PROBE}).json()["id"]
r = S.post(f"/api/submissions/{sid}/run-and-analyze").json()
print("status:", r["execution_status"], r.get("stderr", "")[:300])
for t in r["test_results"]:
    if t["test_type"] == "visible":
        print(t["actual_output_json"]); break
