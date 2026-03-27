import os
import re
import json
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

# ==========================================
# 1. CONFIGURAÇÕES DA PÁGINA E UI/UX DESIGN
# ==========================================
st.set_page_config(page_title="Sprint Dashboard", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stApp { background-color: #F8FAFC; }
    
    .metric-card { 
        background-color: #ffffff; 
        border-radius: 16px; 
        padding: 24px; 
        border: 1px solid #E2E8F0; 
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03); 
        margin-bottom: 1rem;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
    }
    .metric-title { color: #64748B; font-size: 0.85rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;}
    .metric-value { font-size: 2.2rem; font-weight: 800; line-height: 1; }
    .metric-sub { color: #94A3B8; font-size: 0.85rem; margin-top: 8px; font-weight: 500;}
    
    .badge { 
        padding: 4px 12px; 
        border-radius: 9999px; 
        font-size: 0.75rem; 
        font-weight: 700; 
        display: inline-block; 
        letter-spacing: 0.02em;
    }
    .bg-done { background-color: #DEF7EC; color: #03543F; border: 1px solid #31C48D;} 
    .bg-review { background-color: #FEF08A; color: #713F12; border: 1px solid #FDE047;} 
    .bg-progress { background-color: #E1EFFE; color: #1E429F; border: 1px solid #3F83F8;} 
    .bg-pending { background-color: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;} 
    
    h1, h2, h3 { color: #0F172A; font-weight: 700 !important; }
</style>
""", unsafe_allow_html=True)

def render_metric(title, value, sub, color="#0F172A"):
    st.markdown(f'''
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value" style="color: {color};">{value}</div>
        <div class="metric-sub">{sub}</div>
    </div>
    ''', unsafe_allow_html=True)

def render_badge(status):
    cores = {"Concluída": "bg-done", "Em Review": "bg-review", "Em Andamento": "bg-progress", "Pendente": "bg-pending"}
    classe = cores.get(status, "bg-pending")
    return f'<span class="badge {classe}">{status}</span>'

# ==========================================
# 2. VARIÁVEIS E CONFIGURAÇÕES EXTERNAS
# ==========================================
load_dotenv()
TOKEN = os.getenv("TOKEN")
EMAIL = os.getenv("EMAIL")
JIRA_DOMAIN = os.getenv("JIRA_DOMAIN")
BOARD_ID = os.getenv("BOARD_ID")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

auth = HTTPBasicAuth(EMAIL, TOKEN) if EMAIL and TOKEN else None
HEADERS = {"Accept": "application/json"}

# Lendo o arquivo de configuração para tornar o app universal
with open('config.json', 'r', encoding='utf-8') as f:
    config = json.load(f)

GITHUB_ORG = config["github"]["org"]
GITHUB_REPOS = config["github"]["repos"]
REGEX_CFG = config["regex"]
MAPEAMENTO_DEV = config.get("dev_mapping", {})

def normalizar_usuario(nome_bruto):
    if not nome_bruto or pd.isna(nome_bruto): return "nenhum"
    nome_limpo = str(nome_bruto).lower().strip().replace(" ", "-")
    # Busca o "De-Para" no config.json (ex: "gustasvos" -> "gustavo-ribeiro")
    return MAPEAMENTO_DEV.get(nome_limpo, nome_limpo)


# ==========================================
# 3. EXTRATORES DE DADOS
# ==========================================
@st.cache_data(ttl=3600)
def process_jira_data():
    if not auth: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    url_stories = f"https://{JIRA_DOMAIN}/rest/agile/1.0/board/{BOARD_ID}/issue?jql=issuetype='Story'&maxResults=1000"
    res_stories = requests.get(url_stories, auth=auth, headers=HEADERS)
    stories_raw = res_stories.json().get("issues", []) if res_stories.status_code == 200 else []

    subtasks_data, worklogs_data, changelog_data, stories_data = [], [], [], []

    for story in stories_raw:
        story_key = story["key"]
        story_summary = story.get("fields", {}).get("summary", f"User Story ({story_key})")
        
        sprint_info = story.get("fields", {}).get("sprint")
        if isinstance(sprint_info, dict):
            sprint_name = sprint_info.get("name", "Sem Sprint")
            sprint_start = sprint_info.get("startDate", "")
            sprint_end = sprint_info.get("endDate", "")
        else:
            sprint_name, sprint_start, sprint_end = "Sem Sprint", "", ""
            
        stories_data.append({
            "story_key": story_key, "story_summary": story_summary, "sprint": sprint_name,
            "sprint_start": sprint_start, "sprint_end": sprint_end
        })

        # Extrai ID da Story com base no Regex do config.json
        match_us = re.search(REGEX_CFG["us_summary_pattern"], story_summary, re.IGNORECASE)
        story_index = int(match_us.group(1)) if match_us else 0

        for st_item in story.get("fields", {}).get("subtasks", []):
            st_key = st_item["key"]
            res_st = requests.get(f"https://{JIRA_DOMAIN}/rest/api/3/issue/{st_key}?expand=worklog,changelog", auth=auth, headers=HEADERS)
            if res_st.status_code != 200: continue
            
            fields = res_st.json().get("fields", {})
            st_summary = fields.get("summary", f"Subtask ({st_key})")
            
            # Define ID Canônico
            canonical_id = None
            if REGEX_CFG["use_jira_key_as_canonical"]:
                canonical_id = st_key
            elif story_index > 0:
                match_task = re.search(REGEX_CFG["subtask_summary_pattern"], st_summary, re.IGNORECASE)
                if match_task:
                    task_index = int(match_task.group(1))
                    canonical_id = REGEX_CFG["us_format"].format(story=story_index, task=task_index)
            
            assignee_raw = fields.get("assignee", {}).get("displayName", "Nenhum") if fields.get("assignee") else "Nenhum"
            assignee_norm = normalizar_usuario(assignee_raw)
            
            labels = fields.get("labels", [])
            label = labels[0] if labels else "Sem Tag"
            
            status_raw = fields.get("status", {}).get("name", "").lower()
            if "concluíd" in status_raw or "done" in status_raw: status_group = "Concluída"
            elif "review" in status_raw: status_group = "Em Review"
            elif "andamento" in status_raw or "progress" in status_raw: status_group = "Em Andamento"
            else: status_group = "Pendente"

            time_spent_h = (fields.get("timespent", 0) or 0) / 3600

            subtasks_data.append({
                "subtask_key": st_key, "subtask_summary": st_summary, "story_key": story_key, "story_summary": story_summary,
                "assignee": assignee_norm, "label": label, "status_group": status_group, "time_spent_h": time_spent_h, 
                "sprint": sprint_name, "canonical_id": canonical_id  
            })

            for w in fields.get("worklog", {}).get("worklogs", []):
                worklogs_data.append({
                    "subtask_key": st_key, "story_key": story_key, 
                    "author": normalizar_usuario(w["author"]["displayName"]), 
                    "date": w["started"][:10], "time_spent_h": w["timeSpentSeconds"] / 3600
                })

            for h in res_st.json().get("changelog", {}).get("histories", []):
                date = h["created"][:10]
                author_log = normalizar_usuario(h.get("author", {}).get("displayName", "Desconhecido"))
                
                for item in h["items"]:
                    if item["field"] == "status":
                        changelog_data.append({
                            "subtask_key": st_key, 
                            "author": author_log, 
                            "date": date, 
                            "from_status": str(item.get("fromString")).lower(), 
                            "to_status": str(item.get("toString")).lower()
                        })

    df_subtasks = pd.DataFrame(subtasks_data).drop_duplicates(subset=['subtask_key'])
    df_worklogs = pd.DataFrame(worklogs_data)
    df_changelogs = pd.DataFrame(changelog_data)
    
    if not df_worklogs.empty: df_worklogs['date'] = pd.to_datetime(df_worklogs['date'])
    if not df_changelogs.empty: df_changelogs['date'] = pd.to_datetime(df_changelogs['date'])

    return pd.DataFrame(stories_data), df_subtasks, df_worklogs, df_changelogs

@st.cache_data(ttl=3600)
def fetch_github_commits():
    if not GITHUB_TOKEN: return pd.DataFrame()
    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    all_commits = []

    for repo in GITHUB_REPOS:
        res_branches = requests.get(f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/branches", headers=headers)
        if res_branches.status_code != 200: continue
        
        for branch in res_branches.json():
            res_commits = requests.get(f"https://api.github.com/repos/{GITHUB_ORG}/{repo}/commits?sha={branch['name']}&per_page=100", headers=headers)
            if res_commits.status_code == 200:
                for c in res_commits.json():
                    msg = c.get("commit", {}).get("message", "")
                    sha = c.get("sha")
                    author_login = c.get("author", {}).get("login") or c.get("commit", {}).get("author", {}).get("name", "")
                    
                    canonical_id = None
                    if REGEX_CFG["use_jira_key_as_canonical"]:
                        match = re.search(REGEX_CFG["commit_pattern"], msg, re.IGNORECASE)
                        if match:
                            canonical_id = match.group(0).upper()
                    else:
                        match = re.search(REGEX_CFG["commit_pattern"], msg, re.IGNORECASE)
                        if match:
                            story_index, task_index = int(match.group(1)), int(match.group(2))
                            canonical_id = REGEX_CFG["us_format"].format(story=story_index, task=task_index)

                    all_commits.append({
                        "sha": sha, "url": f"https://github.com/{GITHUB_ORG}/{repo}/commit/{sha}", "repo": repo,
                        "author": normalizar_usuario(author_login), 
                        "date": c.get("commit", {}).get("author", {}).get("date", "")[:10],
                        "message": msg, "canonical_id": canonical_id 
                    })
    
    df_commits = pd.DataFrame(all_commits)
    if not df_commits.empty: df_commits.drop_duplicates(subset=['sha'], inplace=True)
    return df_commits


# ==========================================
# FUNÇÃO DO POPUP (MODAL) DE DETALHES
# ==========================================
@st.dialog("🔍 Detalhes da Tarefa", width="large")
def modal_detalhes_tarefa(subtask, df_all_commits, dict_retornos):
    id_legivel = subtask['canonical_id'] if pd.notna(subtask['canonical_id']) else subtask['subtask_key']
    st.subheader(f"{id_legivel}: {subtask['subtask_summary']}")
    st.caption(f"Pertence a: {subtask['story_summary']}")
    
    badge_html = render_badge(subtask['status_group'])
    dev_nome = subtask['assignee']
    qtd_voltou = dict_retornos.get(subtask['subtask_key'], 0)
    
    if qtd_voltou > 0:
        st.markdown(f"""
        <div style='background-color: #FFFBEB; border-left: 4px solid #F59E0B; padding: 12px; margin-bottom: 16px; border-radius: 6px; color: #92400E; font-size: 0.85rem;'>
            <b>⚠️ Atenção:</b> Esta tarefa já retornou <b>{qtd_voltou} vezes</b> da etapa de Code Review. Pode haver ajustes pendentes.
        </div>
        """, unsafe_allow_html=True)

    col_info, col_commits = st.columns([1, 1.5])
    
    with col_info:
        st.markdown(f"{badge_html}", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.write(f"**Desenvolvedor:** 👨‍💻 {dev_nome}")
        st.write(f"**Esforço Registrado:** ⏳ {subtask['time_spent_h']:.1f} horas")
        st.write(f"**Tag / Tipo:** `{subtask['label']}`")
        
        jira_url = f"https://{JIRA_DOMAIN}/browse/{subtask['subtask_key']}"
        st.write(f"**Jira:** [Visualizar Ticket no Jira]({jira_url})")

    with col_commits:
        st.markdown("**🔗 Código e Commits (GitHub):**")
        commits_vinculados = df_all_commits[df_all_commits['canonical_id'] == subtask['canonical_id']] if pd.notna(subtask['canonical_id']) and not df_all_commits.empty else pd.DataFrame()
        
        if not commits_vinculados.empty:
            commits_do_dev = commits_vinculados[commits_vinculados['author'] == dev_nome]
            outros_commits = commits_vinculados[commits_vinculados['author'] != dev_nome]
            
            if not commits_do_dev.empty:
                st.markdown(f"✅ **{dev_nome}:**")
                for _, commit in commits_do_dev.iterrows():
                    msg_curta = commit['message'][:45] + '...' if len(commit['message']) > 45 else commit['message']
                    st.markdown(f"- 🕒 {commit['date']} | [{msg_curta}]({commit['url']})")
            else:
                st.caption(f"👻 Nenhum commit direto de {dev_nome} mapeado.")
                
            if not outros_commits.empty:
                st.markdown(f"🔄 **Outros membros nesta Task:**")
                for _, commit in outros_commits.iterrows():
                    msg_curta = commit['message'][:45] + '...' if len(commit['message']) > 45 else commit['message']
                    st.markdown(f"- 🕒 {commit['date']} | 👤 *{commit['author']}* | [{msg_curta}]({commit['url']})")
        else:
            st.caption("👻 Sem commits mapeados via padrão definido nesta task.")

# ==========================================
# 4. DASHBOARD E FILTROS VISUAIS
# ==========================================

col_logo, col_btn = st.sidebar.columns([3, 1])
with col_logo:
    st.image("https://cdn-icons-png.flaticon.com/512/732/732214.png", width=40) 
with col_btn:
    if st.button("🔄", help="Limpar cache e buscar dados novos"):
        process_jira_data.clear()
        fetch_github_commits.clear()
        st.rerun()

st.sidebar.header("🎛️ Filtros do Dashboard")
st.sidebar.markdown("---")

st.title("🎯 Dashboard de Acompanhamento (Sprint)")
st.markdown("Acompanhe o progresso das metas, esforço do time e commits integrados de forma simples e visual.")
st.markdown("<br>", unsafe_allow_html=True)

with st.spinner('Sincronizando Jira e GitHub...'):
    df_stories, df_subtasks, df_worklogs, df_changelogs = process_jira_data()
    df_commits = fetch_github_commits()

if df_subtasks.empty:
    st.error("Nenhum dado encontrado. Verifique seu .env")
    st.stop()

# Dicionário para resgatar nomes bonitos (USXX-YY) baseados na chave (JH-XX)
dict_info_tasks = df_subtasks.set_index('subtask_key').to_dict('index')

dict_retornos_review = {}
if not df_changelogs.empty:
    df_retornos = df_changelogs[(df_changelogs['from_status'].str.contains('review', na=False)) & (df_changelogs['to_status'].str.contains('andamento|progress', na=False))]
    dict_retornos_review = df_retornos.groupby('subtask_key').size().to_dict()

sprints = ["Todas"] + df_subtasks['sprint'].dropna().unique().tolist()
sprint_selecionada = st.sidebar.selectbox("1. Sprint Atual", sprints)

df_stories_filtrado = df_stories[df_stories['sprint'] == sprint_selecionada] if sprint_selecionada != "Todas" else df_stories

st.sidebar.markdown("<br>", unsafe_allow_html=True)
st.sidebar.subheader("2. Definir Meta da Sprint")

opcoes_meta = {row['story_summary']: row['story_key'] for _, row in df_stories_filtrado.iterrows()}

with st.sidebar.popover("⚙️ Selecionar User Stories", use_container_width=True):
    st.markdown("**Escolha as histórias que farão parte da meta:**")
    meta_selecionada_titulos = st.multiselect(
        "Histórias",
        options=list(opcoes_meta.keys()),
        default=list(opcoes_meta.keys())[:5] if len(opcoes_meta) > 5 else list(opcoes_meta.keys()),
        label_visibility="collapsed" 
    )

chaves_meta_manual = [opcoes_meta[titulo] for titulo in meta_selecionada_titulos]
st.sidebar.caption(f"_{len(chaves_meta_manual)} histórias selecionadas._")

df_meta = df_subtasks[df_subtasks['story_key'].isin(chaves_meta_manual)].copy()

# ==========================================
# RECURSO NOVO: BURNDOWN CHART NA SIDEBAR
# ==========================================
st.sidebar.markdown("---")
if not df_meta.empty and chaves_meta_manual:
    with st.sidebar.popover("📉 Abrir Burndown Chart", use_container_width=True):
        st.markdown("### Burndown de Entregas da Meta")
        
        s_start = df_stories_filtrado['sprint_start'].dropna().max() if 'sprint_start' in df_stories_filtrado else ""
        s_end = df_stories_filtrado['sprint_end'].dropna().max() if 'sprint_end' in df_stories_filtrado else ""
        
        todas_datas = pd.to_datetime(df_worklogs['date'].dropna().tolist() + df_changelogs['date'].dropna().tolist())
        
        if pd.notna(s_start) and s_start != "": data_min = pd.to_datetime(s_start[:10])
        else: data_min = todas_datas.min() if not todas_datas.empty else pd.to_datetime('today') - pd.Timedelta(days=7)
            
        if pd.notna(s_end) and s_end != "": data_max = pd.to_datetime(s_end[:10])
        else: data_max = pd.to_datetime('today') + pd.Timedelta(days=1)
        
        dias_sprint = pd.date_range(start=data_min, end=data_max)
        df_bd = pd.DataFrame({'data': dias_sprint})
        
        entregas_bd = pd.DataFrame()
        if not df_changelogs.empty:
            entregas_bd = df_changelogs[(df_changelogs['subtask_key'].isin(df_meta['subtask_key'])) & (df_changelogs['to_status'].str.contains('concluíd|done', na=False))]
        
        if not entregas_bd.empty:
            df_primeiras_entregas = entregas_bd.groupby('subtask_key')['date'].min().reset_index()
            entregas_dia = df_primeiras_entregas.groupby('date').size().reset_index(name='concluidas')
            entregas_dia['date'] = pd.to_datetime(entregas_dia['date'])
            df_bd = df_bd.merge(entregas_dia, left_on='data', right_on='date', how='left').fillna(0)
            df_bd['cumulativo'] = df_bd['concluidas'].cumsum()
        else:
            df_bd['cumulativo'] = 0
            
        total_tasks_meta = len(df_meta)
        df_bd['restantes'] = total_tasks_meta - df_bd['cumulativo']
        
        passo = total_tasks_meta / (len(df_bd) - 1) if len(df_bd) > 1 else 0
        df_bd['ideal'] = [max(0, total_tasks_meta - (i * passo)) for i in range(len(df_bd))]
        
        fig_bd = go.Figure()
        fig_bd.add_trace(go.Scatter(x=df_bd['data'], y=df_bd['ideal'], mode='lines', name='Linha Ideal', line=dict(dash='dash', color='gray')))
        fig_bd.add_trace(go.Scatter(x=df_bd['data'], y=df_bd['restantes'], mode='lines+markers', name='Tarefas Restantes', line=dict(color='#EF4444', width=3)))
        
        fig_bd.update_layout(xaxis_title="Dias da Sprint", yaxis_title="Qtd. Subtasks", hovermode="x unified",
                             legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        
        st.plotly_chart(fig_bd, use_container_width=True)
        st.caption("📥 Dica: Passe o mouse sobre o gráfico e clique no ícone de câmera para baixar a imagem ou na setinha para abrir em Tela Cheia.")

st.sidebar.markdown("---")
devs_disponiveis = df_subtasks['assignee'].dropna().unique().tolist()
dev_selecionado = st.sidebar.selectbox("3. Visão do Desenvolvedor", ["Todos"] + devs_disponiveis)

# ==========================================
# RECURSO NOVO: LOGS DE ATIVIDADE NA SIDEBAR COM POPUP
# ==========================================
if dev_selecionado != "Todos":
    df_meta = df_meta[df_meta['assignee'] == dev_selecionado]
    
    st.sidebar.markdown("---")
    st.sidebar.subheader(f"👤 Últimos Registros: {dev_selecionado}")
    
    def obter_nomes_legiveis(task_key):
        info = dict_info_tasks.get(task_key, {})
        id_bonito = info.get('canonical_id')
        if pd.isna(id_bonito) or not id_bonito:
            id_bonito = task_key
        us_summary = info.get('story_summary', 'User Story Desconhecida')
        return id_bonito, us_summary

    st.sidebar.markdown("**Última ação no Jira:**")
    wl_dev = df_worklogs[df_worklogs['author'] == dev_selecionado] if not df_worklogs.empty else pd.DataFrame()
    cl_dev = df_changelogs[df_changelogs['author'] == dev_selecionado] if not df_changelogs.empty else pd.DataFrame()
    
    ultimo_wl = wl_dev.sort_values(by='date', ascending=False).iloc[0] if not wl_dev.empty else None
    ultimo_cl = cl_dev.sort_values(by='date', ascending=False).iloc[0] if not cl_dev.empty else None
    
    if ultimo_wl is not None:
        id_legivel, us_titulo = obter_nomes_legiveis(ultimo_wl['subtask_key'])
        st.sidebar.markdown(f"**Worklog ({ultimo_wl['date'].strftime('%d/%m')}):**<br>Lançou {ultimo_wl['time_spent_h']:.1f}h em **{id_legivel}**<br><span style='font-size: 0.8rem; color: #64748B;'>({us_titulo})</span>", unsafe_allow_html=True)
        
        row_tarefa_wl = df_subtasks[df_subtasks['subtask_key'] == ultimo_wl['subtask_key']]
        if not row_tarefa_wl.empty:
            if st.sidebar.button(f"Abrir 📖 {id_legivel}", key="btn_wl", use_container_width=True):
                modal_detalhes_tarefa(row_tarefa_wl.iloc[0], df_commits, dict_retornos_review)

    if ultimo_cl is not None:
        st.sidebar.markdown("<br>", unsafe_allow_html=True)
        id_legivel, us_titulo = obter_nomes_legiveis(ultimo_cl['subtask_key'])
        st.sidebar.markdown(f"**Status ({ultimo_cl['date'].strftime('%d/%m')}):**<br>Moveu **{id_legivel}** para *{ultimo_cl['to_status']}*<br><span style='font-size: 0.8rem; color: #64748B;'>({us_titulo})</span>", unsafe_allow_html=True)
        
        row_tarefa_cl = df_subtasks[df_subtasks['subtask_key'] == ultimo_cl['subtask_key']]
        if not row_tarefa_cl.empty:
            if st.sidebar.button(f"Abrir 📖 {id_legivel}", key="btn_cl", use_container_width=True):
                modal_detalhes_tarefa(row_tarefa_cl.iloc[0], df_commits, dict_retornos_review)

    if ultimo_wl is None and ultimo_cl is None:
        st.sidebar.caption("Sem ações recentes no Jira.")

    st.sidebar.markdown("**Últimos Commits no GitHub:**")
    if not df_commits.empty:
        commits_dev = df_commits[df_commits['author'] == dev_selecionado].sort_values(by='date', ascending=False).head(3)
        if not commits_dev.empty:
            for _, c in commits_dev.iterrows():
                msg_curta = c['message'][:35] + '...' if len(c['message']) > 35 else c['message']
                st.sidebar.markdown(f"- 🕒 {c['date']} | [{msg_curta}]({c['url']})")
        else:
            st.sidebar.caption("Sem commits mapeados.")

# ==========================================
# 5. VISÃO GERAL E GRÁFICO DE TAGS (COM POPUPS)
# ==========================================
if not chaves_meta_manual:
    st.info("👋 Selecione pelo menos uma User Story no menu lateral para visualizar os dados da Meta.")
else:
    total_sub = len(df_meta)
    qtd_concluida = len(df_meta[df_meta['status_group'] == 'Concluída'])
    qtd_review = len(df_meta[df_meta['status_group'] == 'Em Review'])
    qtd_andamento = len(df_meta[df_meta['status_group'] == 'Em Andamento'])
    qtd_pendente = len(df_meta[df_meta['status_group'] == 'Pendente'])

    esf_concluida = df_meta[df_meta['status_group'] == 'Concluída']['time_spent_h'].sum()
    esf_review = df_meta[df_meta['status_group'] == 'Em Review']['time_spent_h'].sum()
    esf_andamento = df_meta[df_meta['status_group'] == 'Em Andamento']['time_spent_h'].sum()
    esf_total = df_meta['time_spent_h'].sum()

    st.markdown(f"<h3 style='margin-bottom: 20px;'>📊 Resumo Executivo: <span style='color: #3B82F6;'>{sprint_selecionada}</span></h3>", unsafe_allow_html=True)
    
    # --- FUNÇÃO ATUALIZADA QUE ABRE O POPUP AO CLICAR NO BOTÃO ---
    def render_task_list(df_subset, prefix_key):
        if df_subset.empty:
            st.caption("Nenhuma tarefa neste status.")
        else:
            for _, row in df_subset.iterrows():
                id_legivel = row['canonical_id'] if pd.notna(row['canonical_id']) else "Tarefa Avulsa"
                
                st.markdown(f"""
                <div style='font-size: 0.85rem; line-height: 1.4; margin-bottom: 4px;'>
                    <b>👨‍💻 {row['assignee']}</b> | ⏳ {row['time_spent_h']:.1f}h<br>
                    <span style='color: #3B82F6; font-weight: 600;'>{id_legivel}</span>: <span style='color: #475569;'>{row['subtask_summary']}</span><br>
                    <span style='color: #94A3B8; font-size: 0.75rem;'>{row['story_summary']}</span>
                </div>
                """, unsafe_allow_html=True)
                
                # Botão que ativa o Popup/Modal
                if st.button(f"Detalhes 🔍", key=f"btn_{prefix_key}_{row['subtask_key']}", use_container_width=True):
                    modal_detalhes_tarefa(row, df_commits, dict_retornos_review)

                st.markdown("<div style='border-bottom: 1px solid #E2E8F0; margin-bottom: 12px; margin-top: 4px;'></div>", unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1: 
        render_metric("Total da Meta", f"{total_sub} Task", f"{esf_total:.1f}h de Esforço", color="#0F172A")
        with st.expander("Ver tarefas"):
            render_task_list(df_meta, "todas")
            
    with col2: 
        render_metric("Concluídas", f"{qtd_concluida}", f"{esf_concluida:.1f}h de Esforço", color="#059669")
        with st.expander("Ver tarefas"):
            render_task_list(df_meta[df_meta['status_group'] == 'Concluída'], "concluida")
            
    with col3: 
        render_metric("Em Review", f"{qtd_review}", f"{esf_review:.1f}h de Esforço", color="#D97706")
        with st.expander("Ver tarefas"):
            render_task_list(df_meta[df_meta['status_group'] == 'Em Review'], "review")
            
    with col4: 
        render_metric("Andamento", f"{qtd_andamento}", f"{esf_andamento:.1f}h de Esforço", color="#2563EB")
        with st.expander("Ver tarefas"):
            render_task_list(df_meta[df_meta['status_group'] == 'Em Andamento'], "andamento")
            
    with col5: 
        render_metric("Pendentes", f"{qtd_pendente}", "Aguardando início", color="#64748B")
        with st.expander("Ver tarefas"):
            render_task_list(df_meta[df_meta['status_group'] == 'Pendente'], "pendente")

    st.markdown("<br>", unsafe_allow_html=True)
    st.subheader("📈 Métricas de Média por Subtask")
    
    df_meta_concluidas = df_meta[df_meta['status_group'] == 'Concluída']
    if not df_meta_concluidas.empty:
        media_geral = df_meta_concluidas['time_spent_h'].mean()
        st.caption(f"**Média geral da equipe:** {media_geral:.2f}h por subtask concluída.")

        df_media_tag = df_meta_concluidas.groupby('label')['time_spent_h'].mean().reset_index()
        df_media_tag = df_media_tag.sort_values(by='time_spent_h', ascending=False)
        
        fig_tags = px.bar(
            df_media_tag, x='label', y='time_spent_h', 
            text_auto='.1f', color_discrete_sequence=['#6366F1'],
            labels={'label': 'Categoria (TAG)', 'time_spent_h': 'Média de Horas'}
        )
        fig_tags.update_layout(plot_bgcolor="white", xaxis_title="", yaxis_title="Média (Horas)")
        st.plotly_chart(fig_tags, use_container_width=True)
    else:
        st.info("Ainda não há tarefas concluídas nesta meta para gerar as métricas de média.")

    # ==========================================
    # 6. HIERARQUIA VISUAL AGRUPADA
    # ==========================================
    st.markdown("---")
    
    st.subheader("📋 Execução: User Stories e Subtasks")
    st.markdown("Clique na User Story para expandir e visualizar as tarefas vinculadas.")

    for titulo_us in sorted(meta_selecionada_titulos):
        story_key = opcoes_meta[titulo_us]
        subs_da_us = df_meta[df_meta['story_key'] == story_key].sort_values(by='subtask_summary')
        
        if subs_da_us.empty: continue 

        with st.expander(f"📖 {titulo_us} — ({len(subs_da_us)} subtasks)", expanded=False):
            st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
            
            for _, sub in subs_da_us.iterrows():
                badge_html = render_badge(sub['status_group'])
                dev_nome = sub['assignee']
                
                qtd_voltou = dict_retornos_review.get(sub['subtask_key'], 0)
                aviso_review_titulo = f" | ⚠️ Voltou {qtd_voltou}x" if qtd_voltou > 0 else ""

                commits_vinculados = df_commits[df_commits['canonical_id'] == sub['canonical_id']] if pd.notna(sub['canonical_id']) and not df_commits.empty else pd.DataFrame()
                
                if commits_vinculados.empty:
                    icone_commit = "👻 Sem Commit"
                else:
                    icone_commit = f"🔗 {len(commits_vinculados)} Commits"
                
                if sub['status_group'] == 'Pendente' and commits_vinculados.empty: 
                    icone_commit = "Aguardando"

                with st.expander(f"⚙️ {sub['subtask_summary']} | 👨‍💻 {dev_nome} | ⏳ {sub['time_spent_h']:.1f}h | {icone_commit}{aviso_review_titulo}"):
                    
                    if qtd_voltou > 0:
                        st.markdown(f"""
                        <div style='background-color: #FFFBEB; border-left: 4px solid #F59E0B; padding: 12px; margin-bottom: 16px; border-radius: 6px; color: #92400E; font-size: 0.85rem;'>
                            <b>⚠️ Atenção:</b> Esta tarefa já retornou <b>{qtd_voltou} vezes</b> da etapa de Code Review. Pode haver ajustes pendentes.
                        </div>
                        """, unsafe_allow_html=True)

                    col_info, col_commits = st.columns([1, 2])
                    
                    with col_info:
                        st.markdown(f"{badge_html}", unsafe_allow_html=True)
                        st.markdown("<br>", unsafe_allow_html=True)
                        st.write(f"**Esforço Registrado:** {sub['time_spent_h']:.1f} horas")
                        st.write(f"**Tag / Tipo:** `{sub['label']}`")
                        
                        jira_url = f"https://{JIRA_DOMAIN}/browse/{sub['subtask_key']}"
                        st.write(f"**Jira:** [Visualizar `{sub['subtask_key']}`]({jira_url})")

                    with col_commits:
                        st.markdown("**🔗 Código e Commits (GitHub):**")
                        
                        if not commits_vinculados.empty:
                            commits_do_dev = commits_vinculados[commits_vinculados['author'] == dev_nome]
                            outros_commits = commits_vinculados[commits_vinculados['author'] != dev_nome]
                            
                            if not commits_do_dev.empty:
                                st.markdown(f"✅ **{dev_nome}:**")
                                for _, commit in commits_do_dev.iterrows():
                                    st.markdown(f"- 🕒 {commit['date']} | [{commit['message']}]({commit['url']})")
                            else:
                                st.caption(f"👻 Nenhum commit direto de {dev_nome} mapeado.")
                                
                            if not outros_commits.empty:
                                st.markdown(f"🔄 **Outros membros nesta Task:**")
                                for _, commit in outros_commits.iterrows():
                                    st.markdown(f"- 🕒 {commit['date']} | 👤 *{commit['author']}* | [{commit['message']}]({commit['url']})")
                        else:
                            st.caption("👻 Sem commits mapeados via padrão definido nesta task.")

# ==========================================
# 7. GRÁFICOS DO DESENVOLVEDOR (Com Toggle)
# ==========================================
if dev_selecionado != "Todos" and chaves_meta_manual:
    st.markdown("---")
    st.subheader(f"📈 Gráfico de Esforço Diário: {dev_selecionado}")
    
    mostrar_estrelas = st.toggle("⭐ Mostrar marcações de entregas no gráfico", value=True)
    
    df_dev_worklogs = df_worklogs[df_worklogs['author'] == dev_selecionado].copy() if not df_worklogs.empty else pd.DataFrame()
    
    if not df_dev_worklogs.empty:
        df_diario = df_dev_worklogs.groupby('date')['time_spent_h'].sum().reset_index()
        fig_linha = go.Figure()
        
        fig_linha.add_trace(go.Scatter(
            x=df_diario['date'], 
            y=df_diario['time_spent_h'], 
            mode='lines+markers', 
            name='Horas Trabalhadas', 
            line=dict(color='#3B82F6', width=3),
            hovertemplate="<b>%{x}</b><br>%{y}h trabalhadas<extra></extra>"
        ))
        
        subtasks_entregues = df_meta[df_meta['status_group'] == 'Concluída']['subtask_key'].tolist()
        
        if mostrar_estrelas and not df_changelogs.empty and subtasks_entregues:
            entregas_historico = df_changelogs[
                (df_changelogs['subtask_key'].isin(subtasks_entregues)) & 
                (df_changelogs['to_status'].str.contains('concluíd|done', na=False))
            ]
            
            if not entregas_historico.empty:
                df_ultimas_datas = entregas_historico.groupby('subtask_key')['date'].max().reset_index()
                entregas_por_dia = df_ultimas_datas.groupby('date').size().reset_index(name='qtd')
                
                for _, row in entregas_por_dia.iterrows():
                    dt_data = pd.to_datetime(row['date'])
                    qtd = row['qtd']
                    
                    if dt_data in df_diario['date'].values:
                        y_val = df_diario.loc[df_diario['date'] == dt_data, 'time_spent_h'].values[0]
                    else:
                        y_val = 0
                        
                    texto_label = f"⭐ {qtd} Entregue(s)"
                    texto_hover = f"<b>{dt_data.strftime('%d/%m/%Y')}</b><br>✅ {qtd} tarefa(s) concluída(s)<br>⏱️ {y_val}h registradas neste dia"
                    
                    fig_linha.add_trace(go.Scatter(
                        x=[dt_data], 
                        y=[y_val], 
                        mode='markers+text', 
                        marker=dict(color='#10B981', size=16, symbol='star', line=dict(color='white', width=1)), 
                        text=[texto_label], 
                        textposition='top center', 
                        hoverinfo='text',
                        hovertext=[texto_hover],
                        showlegend=False
                    ))

        fig_linha.update_layout(
            plot_bgcolor="white", xaxis_title="Dias", yaxis_title="Horas Trabalhadas", hovermode="x unified"
        )
        fig_linha.update_yaxes(rangemode="tozero")
        st.plotly_chart(fig_linha, use_container_width=True)
    else:
        st.info("Não há horas registradas (worklogs) para este desenvolvedor mapeadas nesta sprint.")

# ==========================================
# 8. DEBUG DE MAPEAMENTO OBRIGATÓRIO
# ==========================================
st.markdown("---")
with st.expander("🧪 Debug de Mapeamento Relacional (Logs)"):
    st.caption("Validação das Chaves Canônicas criadas pelo Regex para garantir a amarração.")
    col_dbg1, col_dbg2 = st.columns(2)
    with col_dbg1:
        st.markdown("**Subtasks Mapeadas**")
        if not df_subtasks.empty:
            df_sub_dbg = df_subtasks[['subtask_key', 'subtask_summary', 'canonical_id', 'assignee']].dropna(subset=['canonical_id'])
            st.dataframe(df_sub_dbg, use_container_width=True)

    with col_dbg2:
        st.markdown("**Commits Mapeados**")
        if not df_commits.empty:
            df_com_dbg = df_commits[['message', 'canonical_id', 'author']].dropna(subset=['canonical_id'])
            st.dataframe(df_com_dbg, use_container_width=True)