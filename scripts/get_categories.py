import json
import urllib.request
import urllib.parse
import time

API_URL = "https://wiki.biligame.com/sr/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_all_categories():
    accontinue = None
    categories = []
    
    while True:
        params = {
            "action": "query",
            "list": "allcategories",
            "aclimit": "500",
            "format": "json",
            "utf8": "1"
        }
        if accontinue:
            params["accontinue"] = accontinue
            
        url_params = urllib.parse.urlencode(params)
        req_url = f"{API_URL}?{url_params}"
        
        try:
            req = urllib.request.Request(req_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode('utf-8'))
                
            query = data.get("query", {})
            page_categories = query.get("allcategories", [])
            
            for cat in page_categories:
                cat_name = cat.get("*")
                if cat_name:
                    categories.append(cat_name)
                    
            if "continue" in data and "accontinue" in data["continue"]:
                accontinue = data["continue"]["accontinue"]
                time.sleep(0.1)
            else:
                break
        except Exception as e:
            print(f"获取分类出错: {e}")
            break
            
    # 直接在命令行输出，不写文件
    for cat in sorted(categories):
        print(cat)

if __name__ == "__main__":
    get_all_categories()
