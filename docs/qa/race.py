import uuid, httpx, concurrent.futures as cf, collections
B="http://127.0.0.1:8000"; R=uuid.uuid4().hex[:6]
s=httpx.post(B+"/api/auth/register", json={"email":f"race_{R}@qa.test","password":"Passw0rd!QA","role":"student"}).json()
H={"Authorization":"Bearer "+s["access_token"]}
def go(_): return httpx.post(B+"/api/submissions", headers=H, json={"problem_id":"CP02","source_code":"int main(){}"}).json().get("attempt_number")
with cf.ThreadPoolExecutor(8) as ex: nums=list(ex.map(go, range(8)))
print("attempt numbers:", sorted(nums), "duplicates:", {k:v for k,v in collections.Counter(nums).items() if v>1})
