import streamlit as st

def apply_custom_css():
    st.markdown("""
    <style>
        :root {
            --primary: #0052CC;
            --success: #36B37E;
            --warning: #FFAB00;
            --danger: #FF5630;
            --review: #6554C0; 
            --info: #00B8D9;   
            --text-main: #172B4D;
            --text-muted: #6B778C;
        }
        
        .stApp { background-color: #F8F9FA; }

        .saas-header {
            padding: 1.5rem 0;
            margin-bottom: 2rem;
            border-bottom: 1px solid #DFE1E6;
        }
        .saas-header h1 {
            color: var(--text-main);
            font-size: 2.2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }
        .saas-header p { color: var(--text-muted); font-size: 1.1rem; }

        .metric-card {
            background-color: #ffffff;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 4px 12px rgba(9, 30, 66, 0.05);
            border: 1px solid #DFE1E6;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .metric-title {
            color: var(--text-muted); font-size: 0.95rem; font-weight: 600;
            text-transform: uppercase; display: flex; align-items: center; gap: 8px;
        }
        .metric-value { color: var(--text-main); font-size: 2rem; font-weight: 700; line-height: 1; }
        .metric-sub { color: var(--text-muted); font-size: 0.85rem; margin-top: 4px; }
        
        .card-pending { border-top: 4px solid var(--warning); }
        .card-progress { border-top: 4px solid var(--primary); }
        .card-review { border-top: 4px solid var(--review); }
        .card-done { border-top: 4px solid var(--success); }
        .card-hours { border-top: 4px solid var(--info); }
    </style>
    """, unsafe_allow_html=True)

def render_metric_card(title, value, subtitle, icon, custom_class):
    st.markdown(f"""
        <div class="metric-card {custom_class}">
            <div class="metric-title">{icon} {title}</div>
            <div class="metric-value">{value}</div>
            <div class="metric-sub">{subtitle}</div>
        </div>
    """, unsafe_allow_html=True)