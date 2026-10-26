# 🎯 Sprint Dashboard (Jira + GitHub)

Um dashboard interativo e **plug & play** construído com Streamlit para acompanhamento de Sprints.
Ele integra dados do Jira Software com commits do GitHub.

---

# 🧠 Como funciona a integração?

O sistema conecta tarefas e commits usando um **ID canônico (Canonical ID)** via Regex.

### ✅ Padrão utilizado (Customizado)

* **Jira:**

  * `User Story 01`
  * `Task - 02`
    → ID: `US01-02`

* **GitHub:**

  ```
  US01-02: implementação login
  ```

✔ O dashboard faz o match automaticamente.

---

# ⚙️ Pré-requisitos

Antes de começar, você precisa ter instalado:

* 🐍 Python (3.8+)
* 🔧 Git

---

# 🚀 Setup completo (do zero)

## 1️⃣ Clonar o repositório

```bash
git clone https://github.com/kakashinho/dashboard-jira-github.git
cd dashboard-jira-github
```

---

## 2️⃣ Criar e ativar ambiente virtual

### Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / Mac:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3️⃣ Instalar dependências

```bash
pip install -r requirements.txt
```

---

# 🔑 4️⃣ Criar arquivo `.env`

```env
# Jira
EMAIL=joao@gmail.com
TOKEN=SEU_TOKEN_JIRA
JIRA_DOMAIN=joao.atlassian.net
BOARD_ID=34
JIRA_PROJECT=JH

# GitHub
GITHUB_TOKEN=SEU_TOKEN_GITHUB
GITHUB_ORG=fatec
```

---

## 🔍 O que é `JIRA_PROJECT`?

É a **sigla do projeto no Jira**.

Exemplo:

* Projeto: *Java The Hutt*
* Sigla: `JH`

---

# 🔐 Como gerar os tokens

### Jira

https://id.atlassian.com/manage-profile/security/api-tokens

### GitHub

https://github.com/settings/personal-access-tokens

---

# 🤖 5️⃣ Gerar nomes do Jira automaticamente

Use o script auxiliar do projeto:

```bash
python setup_config.py
```

Ele vai retornar algo como:

```
Nome dos autores no Jira:
['joao-silva', 'maria-souza']
```

---

## 💡 Por que isso é importante?

No:

* **GitHub** → usuários usam nick (ex: `lukitta013`)
* **Jira** → nomes formais (ex: `Lucas Carvalho`)

Esse script normaliza os nomes automaticamente, facilitando o `dev_mapping`.

---

# ⚙️ 6️⃣ Configurar `config.json`

```json
{
  "github": {
    "org": "lucasfisioramos-cmyk",
    "repos": [
      "Zip-Coders"
    ]
  },
  "regex": {
    "us_summary_pattern": "User\\s*Story\\s*0*(\\d+)",
    "subtask_summary_pattern": "(?:Task|Tarefa|Subtask)\\s*[-]*\\s*0*(\\d+)",
    "commit_pattern": "US[-]*(\\d+)[-]*(\\d+)",
    "us_format": "US{story:02d}-{task:02d}",
    "use_jira_key_as_canonical": false
  },
  "dev_mapping": {
    "kakashinho": "joao-siqueira"
  }
}
```

---

## 👥 `dev_mapping`

Formato:

```json
"github_user": "jira_user"
```

✔ Use o resultado do `setup_config.py`
✔ Foque no username do GitHub (mais fácil)

---

# ▶️ 7️⃣ Rodar aplicação

```bash
streamlit run app.py
```

---

# 🧪 Debug

Se algo não funcionar:

### ✔ Verifique commits:

```
US01-02: mensagem
```

### ✔ Use no dashboard:

```
🧪 Debug de Mapeamento Relacional
```

---

# 🔄 Alternativa: usar chave do Jira

Se quiser usar:

```
PROJ-123
```

Mude:

```json
"use_jira_key_as_canonical": true
```

E:

```json
"commit_pattern": "PROJ-\\d+"
```

---

# 🎉 Pronto!

Agora é só rodar e acompanhar sua sprint com integração completa 🚀
