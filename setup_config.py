import os, requests, unicodedata, re
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
EMAIL = os.getenv("EMAIL")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
JIRA_PROJECT = os.getenv("JIRA_PROJECT")

def normalize(name):
    # Remove acentos, espaços e caracteres especiais
    name = ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn')
    return re.sub(r'[^a-z0-9\-]', '', name.lower().replace(' ','-'))

if __name__=="__main__":
    url = f"https://{JIRA_DOMAIN}/rest/api/3/user/assignable/search?project={JIRA_PROJECT}"
    try:
        res = requests.get(url, auth=HTTPBasicAuth(EMAIL,GITHUB_TOKEN), headers={"Accept":"application/json"}).json()
        nomes = [normalize(u["displayName"]) for u in res if u.get("accountType")=="atlassian"]
        print("Nome dos autores no Jira:")
        print(nomes)
    except Exception as e:
        print("Erro ao buscar nomes do Jira:", e)