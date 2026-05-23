import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from io import StringIO
import re

# ── CONFIG ────────────────────────────────────────────
st.set_page_config(
    page_title="WealthTrack — Samuel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

SHEET_ID = "1ADzYAtCeFpP01eoFOdb2iiwSX3eU9rcbQbS6wQf6sgI"

# ── PALETTE ───────────────────────────────────────────
COLORS = {
    "bg":       "#0D1117",
    "card":     "#161B27",
    "border":   "#21262D",
    "text":     "#E6EDF3",
    "muted":    "#8B949E",
    "green":    "#3FB950",
    "red":      "#F85149",
    "gold":     "#D29922",
    "blue":     "#1F6FEB",
    "purple":   "#8B5CF6",
    "teal":     "#10B981",
    "cyan":     "#58A6FF",
}

# ── GLOBAL CSS ─────────────────────────────────────────
st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@300;400;500;600&display=swap');

    html, body, [class*="css"] {{
        background-color: {COLORS['bg']} !important;
        color: {COLORS['text']} !important;
        font-family: 'DM Sans', sans-serif;
    }}
    .stApp {{ background-color: {COLORS['bg']}; }}
    .main .block-container {{ padding: 1.5rem 2rem; max-width: 1400px; }}
    
    /* Hide streamlit elements */
    #MainMenu, footer, header {{ visibility: hidden; }}
    .stDeployButton {{ display: none; }}
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        background: {COLORS['card']};
        border-radius: 10px;
        padding: 4px;
        gap: 4px;
        border: 1px solid {COLORS['border']};
    }}
    .stTabs [data-baseweb="tab"] {{
        background: transparent;
        color: {COLORS['muted']};
        border-radius: 7px;
        padding: 8px 20px;
        font-family: 'DM Sans', sans-serif;
        font-weight: 500;
        font-size: 13px;
    }}
    .stTabs [aria-selected="true"] {{
        background: {COLORS['blue']} !important;
        color: white !important;
    }}
    .stTabs [data-baseweb="tab-panel"] {{
        padding-top: 1.5rem;
    }}
    
    /* Metrics */
    [data-testid="metric-container"] {{
        background: {COLORS['card']};
        border: 1px solid {COLORS['border']};
        border-radius: 10px;
        padding: 1rem 1.2rem;
    }}
    [data-testid="metric-container"] label {{
        color: {COLORS['muted']} !important;
        font-size: 11px !important;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }}
    [data-testid="metric-container"] [data-testid="stMetricValue"] {{
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 24px !important;
        color: {COLORS['text']} !important;
    }}
    [data-testid="stMetricDelta"] {{
        font-size: 13px !important;
    }}

    /* Divider */
    hr {{ border-color: {COLORS['border']}; }}
    
    /* Dataframe */
    .stDataFrame {{ background: {COLORS['card']}; }}
    
    /* Plotly charts background */
    .js-plotly-plot {{ border-radius: 10px; overflow: hidden; }}
</style>
""", unsafe_allow_html=True)


# ── DATA FETCHING ──────────────────────────────────────
@st.cache_data(ttl=300)  # refresh every 5 min
def fetch_sheet(sheet_name: str) -> pd.DataFrame:
    """Fetch a sheet as CSV from public Google Sheets."""
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={requests.utils.quote(sheet_name)}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        df = pd.read_csv(StringIO(r.text), header=None)
        return df
    except Exception as e:
        st.error(f"Erreur lecture {sheet_name}: {e}")
        return pd.DataFrame()

def clean_num(val) -> float:
    """Parse a French-formatted number string to float."""
    if pd.isna(val) or val == "" or val is None:
        return 0.0
    s = str(val).strip()
    # Remove currency symbols, spaces, +
    s = re.sub(r'[€$\s+%]', '', s).replace('\xa0', '')
    # French format: comma as decimal, space/dot as thousands
    s = s.replace(' ', '').replace('\u202f', '')
    # Handle cases like "1.234,56" → "1234.56"
    if ',' in s and '.' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0

def get_cell(df: pd.DataFrame, row: int, col: int, default=0):
    """Get cell value safely (0-indexed)."""
    try:
        val = df.iloc[row, col]
        if pd.isna(val) or str(val).strip() in ['', 'nan']:
            return default
        return val
    except:
        return default


# ── CHART HELPERS ──────────────────────────────────────
PLOTLY_LAYOUT = dict(
    paper_bgcolor=COLORS['bg'],
    plot_bgcolor=COLORS['card'],
    font=dict(family="DM Sans", color=COLORS['muted']),
    margin=dict(l=10, r=10, t=30, b=10),
    xaxis=dict(
        gridcolor=COLORS['border'],
        linecolor=COLORS['border'],
        tickfont=dict(color=COLORS['muted'], size=11),
    ),
    yaxis=dict(
        gridcolor=COLORS['border'],
        linecolor=COLORS['border'],
        tickfont=dict(color=COLORS['muted'], size=11),
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS['muted'])
    ),
)

def card_html(title: str, value: str, sub: str = "", color: str = "#1F6FEB", icon: str = "") -> str:
    return f"""
    <div style="background:{COLORS['card']};border:1px solid {COLORS['border']};
         border-top:2px solid {color};border-radius:10px;padding:14px 18px;height:100%">
        <div style="font-size:10px;color:{COLORS['muted']};text-transform:uppercase;
             letter-spacing:0.08em;margin-bottom:6px">{icon} {title}</div>
        <div style="font-family:'Space Grotesk',sans-serif;font-size:22px;font-weight:700;
             color:{COLORS['text']};line-height:1.1">{value}</div>
        {"<div style='font-size:12px;color:"+color+";margin-top:4px'>"+sub+"</div>" if sub else ""}
    </div>"""

def section_title(text: str, icon: str = ""):
    st.markdown(f"""
    <div style="background:{COLORS['card']};border-left:3px solid {COLORS['blue']};
         border-radius:6px;padding:10px 16px;margin:1.5rem 0 1rem 0">
        <span style="font-family:'Space Grotesk',sans-serif;font-weight:600;font-size:14px">
            {icon} {text}
        </span>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════
st.markdown(f"""
<div style="display:flex;align-items:center;justify-content:space-between;
     padding:12px 0;margin-bottom:8px;border-bottom:1px solid {COLORS['border']}">
    <div style="display:flex;align-items:center;gap:12px">
        <div style="width:36px;height:36px;border-radius:8px;
             background:linear-gradient(135deg,#1F6FEB,#8B5CF6);
             display:flex;align-items:center;justify-content:center;font-size:18px">📊</div>
        <div>
            <div style="font-family:'Space Grotesk',sans-serif;font-size:18px;font-weight:700">
                WealthTrack</div>
            <div style="font-size:11px;color:{COLORS['muted']}">Samuel · Ingénieur chez Alstom</div>
        </div>
    </div>
    <div style="display:flex;align-items:center;gap:8px">
        <div style="width:8px;height:8px;border-radius:50%;background:{COLORS['green']};
             box-shadow:0 0 6px {COLORS['green']}"></div>
        <span style="font-size:12px;color:{COLORS['muted']}">Données Google Finance · Mis à jour en temps réel</span>
    </div>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs(["🏠 Vue d'ensemble", "📈 Bourse", "₿ Crypto", "⚙️ Options & Perf."])


# ══════════════════════════════════════════════════════
# TAB 1 — VUE D'ENSEMBLE
# ══════════════════════════════════════════════════════
with tab1:
    df_pat = fetch_sheet("🏠 Patrimoine")
    df_em  = fetch_sheet("📅 Évol. Mensuelle")
    df_ea  = fetch_sheet("📈 Évol. Annuelle")

    # ── KPI Cards ────────────────────────────────────
    pat_total   = clean_num(get_cell(df_pat, 5, 1))
    pat_investi = clean_num(get_cell(df_pat, 5, 3))
    pat_perf    = clean_num(get_cell(df_pat, 5, 5))
    pat_cagr    = clean_num(get_cell(df_pat, 5, 9))
    pat_ytd     = clean_num(get_cell(df_em,  5, 9))
    pat_ytd_pct = clean_num(get_cell(df_em,  5, 12))

    def fmt_eur(v): return f"{v:,.0f} €".replace(",", " ")
    def fmt_pct(v): return f"{'+' if v>=0 else ''}{v:.2f} %"
    def pct_color(v): return COLORS['green'] if v >= 0 else COLORS['red']

    cols = st.columns(5)
    cards = [
        ("PATRIMOINE TOTAL",   fmt_eur(pat_total),   "",                            COLORS['gold'],   "🏆"),
        ("TOTAL INVESTI",      fmt_eur(pat_investi),  "",                            COLORS['blue'],   "💰"),
        ("PERFORMANCE TOTALE", fmt_pct(pat_perf),     "depuis ouverture",            pct_color(pat_perf), "📈"),
        ("CAGR ANNUALISÉ",     fmt_pct(pat_cagr),     "depuis fév. 2022",            COLORS['purple'], "⚡"),
        ("VARIATION YTD",      fmt_eur(pat_ytd),      fmt_pct(pat_ytd_pct),          pct_color(pat_ytd), "📅"),
    ]
    for col, (title, val, sub, color, icon) in zip(cols, cards):
        with col:
            st.markdown(card_html(title, val, sub, color, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Layout : charts + répartition ─────────────────
    left, right = st.columns([2, 1])

    with left:
        section_title("Évolution mensuelle 2026", "📅")

        # Monthly data from Évol. Mensuelle
        mois_labels = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
        patrimoine_vals, variation_vals = [], []

        for i in range(12):
            row_idx = 13 + i  # rows 14-25 (0-indexed: 13-24)
            pat_val = clean_num(get_cell(df_em, row_idx, 2))
            var_val = get_cell(df_em, row_idx, 3, "")
            var_num = clean_num(var_val) if str(var_val) not in ["—", "", "nan"] else None
            patrimoine_vals.append(pat_val if pat_val > 0 else None)
            variation_vals.append(var_num)

        # Line chart patrimoine
        fig_line = go.Figure()
        x_vals = [mois_labels[i] for i, v in enumerate(patrimoine_vals) if v]
        y_vals = [v for v in patrimoine_vals if v]

        fig_line.add_trace(go.Scatter(
            x=x_vals, y=y_vals,
            mode='lines+markers',
            line=dict(color=COLORS['blue'], width=3, shape='spline'),
            marker=dict(color=COLORS['gold'], size=8, line=dict(color=COLORS['bg'], width=2)),
            fill='tozeroy',
            fillcolor='rgba(31,111,235,0.08)',
            hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>',
            name='Patrimoine',
        ))

        # Annotations for each point
        for x, y in zip(x_vals, y_vals):
            fig_line.add_annotation(
                x=x, y=y,
                text=f"{y/1000:.0f}k€",
                showarrow=False,
                yshift=14,
                font=dict(size=10, color=COLORS['text']),
            )

        fig_line.update_layout(
            **PLOTLY_LAYOUT,
            height=220,
            showlegend=False,
            yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickformat=',.0f', ticksuffix=' €'),
        )
        st.plotly_chart(fig_line, use_container_width=True, config={'displayModeBar': False})

        # Bar chart variations
        section_title("Variations mensuelles", "📊")
        var_x = [mois_labels[i] for i, v in enumerate(variation_vals) if v is not None]
        var_y = [v for v in variation_vals if v is not None]
        bar_colors = [COLORS['green'] if v >= 0 else COLORS['red'] for v in var_y]

        fig_bar = go.Figure(go.Bar(
            x=var_x, y=var_y,
            marker_color=bar_colors,
            text=[f"{'+' if v>=0 else ''}{v:,.0f}€" for v in var_y],
            textposition='outside',
            textfont=dict(color=COLORS['text'], size=11),
            hovertemplate='<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>',
        ))
        fig_bar.update_layout(
            **PLOTLY_LAYOUT,
            height=200,
            showlegend=False,
            yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickformat='+,.0f', ticksuffix=' €'),
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={'displayModeBar': False})

    with right:
        section_title("Répartition du patrimoine", "🍩")

        # Répartition from Patrimoine sheet (rows 20-26 col B,C)
        categories = []
        values     = []
        cat_colors = [COLORS['blue'], COLORS['gold'], COLORS['purple'],
                      COLORS['teal'], "#059669", "#6B7280", "#3B82F6"]
        cat_icons  = ["📈 Bourse", "₿ Crypto", "⚙️ Options",
                      "🏢 PEE", "📋 PER", "🛡️ AV", "💵 Cash"]

        for i in range(7):
            row = 20 + i
            val = clean_num(get_cell(df_pat, row, 2))
            if val > 0:
                categories.append(cat_icons[i])
                values.append(val)

        if values:
            fig_pie = go.Figure(go.Pie(
                labels=categories,
                values=values,
                hole=0.55,
                marker=dict(
                    colors=cat_colors[:len(values)],
                    line=dict(color=COLORS['bg'], width=2)
                ),
                textinfo='percent',
                textfont=dict(size=11, color='white'),
                hovertemplate='<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>',
            ))
            total_v = sum(values)
            fig_pie.add_annotation(
                text=f"<b>{total_v/1000:.0f}k€</b>",
                x=0.5, y=0.5,
                font=dict(size=16, color=COLORS['text'], family='Space Grotesk'),
                showarrow=False,
            )
            fig_pie.update_layout(
                **PLOTLY_LAYOUT,
                height=280,
                showlegend=True,
                legend=dict(
                    orientation='v',
                    x=1.05, y=0.5,
                    font=dict(size=10, color=COLORS['muted']),
                    bgcolor='rgba(0,0,0,0)',
                ),
                margin=dict(l=0, r=10, t=10, b=10),
            )
            st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})

        # Évol. annuelle mini chart
        section_title("Évolution annuelle", "📈")
        years = ["2022","2023","2024","2025","2026"]
        totals_ea = [25813, 40915, 57485, 71057]
        # Get 2026 from data
        t2026 = clean_num(get_cell(df_ea, 16, 9))
        if t2026 > 0:
            totals_ea.append(t2026)
        else:
            totals_ea.append(75285)

        fig_ea = go.Figure(go.Scatter(
            x=years, y=totals_ea,
            mode='lines+markers',
            line=dict(color=COLORS['gold'], width=3, shape='spline'),
            marker=dict(color=COLORS['gold'], size=8, line=dict(color=COLORS['bg'], width=2)),
            fill='tozeroy',
            fillcolor='rgba(210,153,34,0.08)',
            hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>',
        ))
        fig_ea.update_layout(
            **PLOTLY_LAYOUT,
            height=180,
            showlegend=False,
            yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickformat=',.0f', ticksuffix=' €'),
        )
        st.plotly_chart(fig_ea, use_container_width=True, config={'displayModeBar': False})


# ══════════════════════════════════════════════════════
# TAB 2 — BOURSE
# ══════════════════════════════════════════════════════
with tab2:
    df_b26 = fetch_sheet("📊 Bourse 2026")

    # KPIs
    b_investi  = clean_num(get_cell(df_b26, 1, 1))
    b_solde    = clean_num(get_cell(df_b26, 1, 3))
    b_pvmv_eur = clean_num(get_cell(df_b26, 1, 5))
    b_pvmv_pct = clean_num(get_cell(df_b26, 1, 7))
    b_divs     = clean_num(get_cell(df_b26, 1, 15))
    b_parr     = clean_num(get_cell(df_b26, 1, 11))

    cols = st.columns(5)
    kpis_b = [
        ("TOTAL INVESTI",   fmt_eur(b_investi),      "",                           COLORS['cyan'],  "💰"),
        ("SOLDE ACTUEL",    fmt_eur(b_solde),         "",                           COLORS['blue'],  "💶"),
        ("PV / MV",         fmt_eur(b_pvmv_eur),      fmt_pct(b_pvmv_pct),          pct_color(b_pvmv_pct), "📈"),
        ("DIVIDENDES NET",  f"{b_divs:.2f} €",        "2026 YTD",                   COLORS['gold'],  "💰"),
        ("PARRAINAGE YTD",  f"{b_parr:.2f} €",        "",                           COLORS['teal'],  "🤝"),
    ]
    for col, (title, val, sub, color, icon) in zip(cols, kpis_b):
        with col:
            st.markdown(card_html(title, val, sub, color, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    left2, right2 = st.columns([1, 1])

    with left2:
        section_title("DCA Mensuel 2026", "💸")

        mois_full = ["Janvier","Février","Mars","Avril","Mai","Juin",
                     "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        dca_cto, dca_pea, dca_tot = [], [], []
        solde_cto, solde_pea, solde_tot = [], [], []

        for i in range(12):
            row = 11 + i  # DCA rows
            cto = clean_num(get_cell(df_b26, row, 2))
            pea = clean_num(get_cell(df_b26, row, 3))
            tot = clean_num(get_cell(df_b26, row, 4))
            dca_cto.append(cto); dca_pea.append(pea); dca_tot.append(tot)
            scto = clean_num(get_cell(df_b26, row, 7))
            spea = clean_num(get_cell(df_b26, row, 8))
            stot = clean_num(get_cell(df_b26, row, 9))
            solde_cto.append(scto); solde_pea.append(spea); solde_tot.append(stot)

        fig_dca = go.Figure()
        fig_dca.add_trace(go.Bar(
            name='CTO', x=mois_full, y=dca_cto,
            marker_color=COLORS['blue'],
            hovertemplate='CTO: %{y:.2f} €<extra></extra>',
        ))
        fig_dca.add_trace(go.Bar(
            name='PEA', x=mois_full, y=dca_pea,
            marker_color=COLORS['green'],
            hovertemplate='PEA: %{y:.2f} €<extra></extra>',
        ))
        fig_dca.update_layout(
            **PLOTLY_LAYOUT,
            barmode='stack', height=280,
            legend=dict(orientation='h', y=-0.15, font=dict(size=11)),
            yaxis=dict(**PLOTLY_LAYOUT['yaxis'], ticksuffix=' €'),
        )
        st.plotly_chart(fig_dca, use_container_width=True, config={'displayModeBar': False})

    with right2:
        section_title("Évolution du solde", "📊")

        fig_solde = go.Figure()
        mois_filled = [m for m, v in zip(mois_full, solde_tot) if v > 0]
        solde_filled = [v for v in solde_tot if v > 0]

        if solde_filled:
            fig_solde.add_trace(go.Scatter(
                x=mois_filled, y=solde_filled,
                mode='lines+markers',
                line=dict(color=COLORS['blue'], width=3, shape='spline'),
                marker=dict(color=COLORS['gold'], size=8),
                fill='tozeroy',
                fillcolor='rgba(31,111,235,0.08)',
                hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>',
            ))
        fig_solde.update_layout(
            **PLOTLY_LAYOUT,
            height=280,
            showlegend=False,
            yaxis=dict(**PLOTLY_LAYOUT['yaxis'], tickformat=',.0f', ticksuffix=' €'),
        )
        st.plotly_chart(fig_solde, use_container_width=True, config={'displayModeBar': False})

    # Dividendes table
    section_title("Dividendes 2026", "💰")
    divs_data = {
        "Action": ["TSMC","JP Morgan","Apple","Costco","ASML","Visa","Microsoft","SP Global",
                   "Alphabet","Meta","Novo","TSMC","LVMH","JP Morgan","ASML","Air Liquide"],
        "Pays":   ["Taiwan","USA","USA","USA","Pays-Bas","USA","USA","USA",
                   "USA","USA","Danemark","Taiwan","FR","USA","Pays-Bas","FR"],
        "Net (€)": [4.53,4.39,0.48,0.74,2.11,1.40,1.13,0.74,
                    0.55,0.30,10.82,0,12.98,0,0,8.77],
    }
    df_divs = pd.DataFrame(divs_data)
    df_divs = df_divs[df_divs["Net (€)"] > 0].sort_values("Net (€)", ascending=False)
    df_divs["Net (€)"] = df_divs["Net (€)"].map(lambda x: f"{x:.2f} €")
    st.dataframe(
        df_divs,
        use_container_width=True,
        hide_index=True,
        height=280,
    )


# ══════════════════════════════════════════════════════
# TAB 3 — CRYPTO
# ══════════════════════════════════════════════════════
with tab3:
    df_ct = fetch_sheet("₿ Crypto Total")

    # KPIs
    ct_val_eur  = clean_num(get_cell(df_ct, 5, 1))
    ct_val_usd  = clean_num(get_cell(df_ct, 5, 3))
    ct_investi  = clean_num(get_cell(df_ct, 5, 5))
    ct_pvmv     = clean_num(get_cell(df_ct, 5, 8))
    ct_perf     = clean_num(get_cell(df_ct, 5, 10))
    ct_eur_usd  = clean_num(get_cell(df_ct, 5, 12))

    cols = st.columns(5)
    kpis_c = [
        ("VALEUR PF (€)",  fmt_eur(ct_val_eur),  "",                           COLORS['gold'],   "💶"),
        ("VALEUR PF ($)",  f"{ct_val_usd:,.2f} $", "",                          COLORS['gold'],   "💵"),
        ("TOTAL INVESTI",  fmt_eur(ct_investi),   "",                           COLORS['blue'],   "💰"),
        ("PV / MV",        fmt_eur(ct_pvmv),       fmt_pct(ct_perf),             pct_color(ct_perf), "📈"),
        ("COURS EUR/$",    f"{ct_eur_usd:.4f}",   "",                           COLORS['muted'],  "💱"),
    ]
    for col, (title, val, sub, color, icon) in zip(cols, kpis_c):
        with col:
            st.markdown(card_html(title, val, sub, color, icon), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    left3, right3 = st.columns([3, 2])

    with left3:
        section_title("Portefeuille Crypto — Positions actuelles", "₿")

        # Portfolio table
        cryptos_data = []
        crypto_names = ["Bitcoin","Solana","Ethereum","BinanceCoin","USDC"]
        crypto_colors_map = {
            "Bitcoin": "#F7931A", "Solana": "#9945FF",
            "Ethereum": "#627EEA", "BinanceCoin": "#F3BA2F", "USDC": "#2775CA"
        }
        for i, name in enumerate(crypto_names):
            row = 11 + i
            val_usd = clean_num(get_cell(df_ct, row, 5))
            val_eur = clean_num(get_cell(df_ct, row, 6))
            inv_usd = clean_num(get_cell(df_ct, row, 8))
            pvmv    = clean_num(get_cell(df_ct, row, 11))
            perf    = clean_num(get_cell(df_ct, row, 12))
            pru_usd = clean_num(get_cell(df_ct, row, 10))
            montant = get_cell(df_ct, row, 3, "")
            cryptos_data.append({
                "Crypto": name,
                "Montant": str(montant),
                "Valeur $": f"{val_usd:,.2f} $",
                "Valeur €": fmt_eur(val_eur),
                "Investi €": fmt_eur(inv_usd / ct_eur_usd if ct_eur_usd else 0),
                "PRU $": f"{pru_usd:,.2f}",
                "PV/MV €": f"{'+' if pvmv>=0 else ''}{pvmv:,.0f} €",
                "Perf.": f"{'+' if perf>=0 else ''}{perf:.1f} %",
            })

        df_crypto_table = pd.DataFrame(cryptos_data)
        st.dataframe(df_crypto_table, use_container_width=True, hide_index=True, height=210)

        # DCA chart
        section_title("DCA Mensuel 2026", "💸")
        df_c26 = fetch_sheet("₿ Crypto 2026")
        dca_mois = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
        dca_crypto = [clean_num(get_cell(df_c26, 29+i, 2)) for i in range(12)]

        fig_dca_c = go.Figure(go.Bar(
            x=dca_mois, y=dca_crypto,
            marker_color=[COLORS['gold'] if v > 0 else COLORS['border'] for v in dca_crypto],
            text=[f"{v:.0f}€" if v > 0 else "" for v in dca_crypto],
            textposition='outside',
            textfont=dict(color=COLORS['text'], size=10),
            hovertemplate='<b>%{x}</b><br>%{y:.2f} €<extra></extra>',
        ))
        fig_dca_c.update_layout(
            **PLOTLY_LAYOUT, height=200, showlegend=False,
            yaxis=dict(**PLOTLY_LAYOUT['yaxis'], ticksuffix=' €'),
        )
        st.plotly_chart(fig_dca_c, use_container_width=True, config={'displayModeBar': False})

    with right3:
        section_title("Répartition du portefeuille", "🍩")
        # Répartition from Crypto Total
        rep_names  = ["Bitcoin","Solana","Ethereum","BinanceCoin","USDC"]
        rep_vals   = [ct_val_usd * pct/100 for pct in [28, 33.66, 15.15, 22.98, 0.21]]
        rep_colors = [COLORS['gold'], COLORS['purple'], COLORS['blue'], "#F3BA2F", COLORS['cyan']]

        fig_rep = go.Figure(go.Pie(
            labels=rep_names, values=rep_vals, hole=0.55,
            marker=dict(colors=rep_colors, line=dict(color=COLORS['bg'], width=2)),
            textinfo='percent',
            textfont=dict(size=11, color='white'),
            hovertemplate='<b>%{label}</b><br>%{value:,.2f} $<br>%{percent}<extra></extra>',
        ))
        fig_rep.add_annotation(
            text=f"<b>{ct_val_usd/1000:.1f}k$</b>",
            x=0.5, y=0.5,
            font=dict(size=16, color=COLORS['text'], family='Space Grotesk'),
            showarrow=False,
        )
        fig_rep.update_layout(
            **PLOTLY_LAYOUT, height=260,
            showlegend=True,
            legend=dict(orientation='h', y=-0.05, font=dict(size=10)),
            margin=dict(l=0, r=0, t=10, b=0),
        )
        st.plotly_chart(fig_rep, use_container_width=True, config={'displayModeBar': False})

        # Staking gains
        section_title("Gains Staking", "🌾")
        staking = {
            "Bitcoin": 65.52,
            "Solana":  464.52,
            "Ethereum": 0,
            "BinanceCoin": 0,
        }
        total_staking = sum(staking.values())
        for name, gain in staking.items():
            if gain > 0:
                color = crypto_colors_map.get(name, COLORS['text'])
                pct = gain / total_staking * 100 if total_staking > 0 else 0
                st.markdown(f"""
                <div style="display:flex;justify-content:space-between;align-items:center;
                     padding:8px 0;border-bottom:1px solid {COLORS['border']}">
                    <span style="color:{color};font-weight:600;font-size:13px">{name}</span>
                    <span style="font-family:'Space Grotesk';font-weight:700;color:{COLORS['green']}">
                        +{gain:.2f} $</span>
                </div>""", unsafe_allow_html=True)
        st.markdown(f"""
        <div style="display:flex;justify-content:space-between;padding:10px 0;margin-top:4px">
            <span style="color:{COLORS['muted']};font-size:12px">TOTAL STAKING</span>
            <span style="font-family:'Space Grotesk';font-size:16px;font-weight:700;
                 color:{COLORS['green']}">+{total_staking:.2f} $</span>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
# TAB 4 — OPTIONS & PERFORMANCE
# ══════════════════════════════════════════════════════
with tab4:
    df_opt = fetch_sheet("⚙️ Options 2026")
    df_pf  = fetch_sheet("🏆 Perf. Totale")

    left4, right4 = st.columns([1, 1])

    with left4:
        section_title("Options 2026 — Stratégie de la Roue", "⚙️")

        # KPIs Options
        opt_capital  = clean_num(get_cell(df_opt, 3, 3))  # capital actuel
        opt_investi  = clean_num(get_cell(df_opt, 3, 6))  # capital investi
        opt_roi      = clean_num(get_cell(df_opt, 3, 9))  # ROI
        opt_primes_e = clean_num(get_cell(df_opt, 3, 12)) # primes €
        opt_primes_d = clean_num(get_cell(df_opt, 3, 15)) # primes $

        kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
        with kpi_c1:
            st.markdown(card_html("CAPITAL ACTUEL", fmt_eur(opt_capital), "", COLORS['purple'], "📈"), unsafe_allow_html=True)
        with kpi_c2:
            st.markdown(card_html("ROI TOTAL", fmt_pct(opt_roi), "", pct_color(opt_roi), "🏆"), unsafe_allow_html=True)
        with kpi_c3:
            st.markdown(card_html("PRIMES YTD", f"{opt_primes_e:.2f} €", f"{opt_primes_d:.2f} $", COLORS['gold'], "💰"), unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        # Primes mensuelles chart
        mois_full = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
        primes_eur = []
        roi_mensuel = []
        for i in range(12):
            row = 7 + i
            prime = clean_num(get_cell(df_opt, row, 8))
            roi   = clean_num(get_cell(df_opt, row, 15))
            primes_eur.append(prime)
            roi_mensuel.append(roi)

        fig_opt = go.Figure()
        fig_opt.add_trace(go.Bar(
            name='Prime (€)', x=mois_full, y=primes_eur,
            marker_color=[COLORS['purple'] if v > 0 else COLORS['border'] for v in primes_eur],
            yaxis='y',
            hovertemplate='<b>%{x}</b><br>Prime: %{y:.2f} €<extra></extra>',
        ))
        fig_opt.add_trace(go.Scatter(
            name='ROI %', x=mois_full, y=roi_mensuel,
            line=dict(color=COLORS['gold'], width=2),
            mode='lines+markers',
            marker=dict(size=6),
            yaxis='y2',
            hovertemplate='<b>%{x}</b><br>ROI: %{y:.2f} %<extra></extra>',
        ))
        fig_opt.update_layout(
            **PLOTLY_LAYOUT,
            height=280,
            yaxis=dict(**PLOTLY_LAYOUT['yaxis'], title='Prime (€)', ticksuffix=' €'),
            yaxis2=dict(
                overlaying='y', side='right',
                tickfont=dict(color=COLORS['gold'], size=10),
                ticksuffix=' %',
                gridcolor='rgba(0,0,0,0)',
            ),
            legend=dict(orientation='h', y=-0.15, font=dict(size=11)),
        )
        st.plotly_chart(fig_opt, use_container_width=True, config={'displayModeBar': False})

    with right4:
        section_title("Performance totale & Benchmarks", "🏆")

        # Performance table from Perf. Totale
        poches = [
            {"Poche": "📈 Bourse (CTO+PEA)", "Investi": 23881, "Live": 27285, "PV/MV": 3404, "Perf": 14.3, "color": COLORS['blue']},
            {"Poche": "₿ Crypto (Binance)",  "Investi": 6005,  "Live": 7979,  "PV/MV": 1974, "Perf": 32.9, "color": COLORS['gold']},
            {"Poche": "⚙️ Options (IBK)",     "Investi": 5550,  "Live": 5681,  "PV/MV": 131,  "Perf": 2.4,  "color": COLORS['purple']},
        ]
        total_inv  = sum(p["Investi"] for p in poches)
        total_live = sum(p["Live"]    for p in poches)
        total_pvmv = sum(p["PV/MV"]   for p in poches)
        total_perf = (total_live / total_inv - 1) * 100 if total_inv else 0

        for p in poches:
            col_a, col_b, col_c, col_d = st.columns([2.5, 1.5, 1.5, 1.2])
            with col_a:
                st.markdown(f"<span style='color:{p['color']};font-weight:600;font-size:13px'>{p['Poche']}</span>", unsafe_allow_html=True)
            with col_b:
                st.markdown(f"<span style='font-size:13px'>{fmt_eur(p['Live'])}</span>", unsafe_allow_html=True)
            with col_c:
                color = COLORS['green'] if p['PV/MV'] >= 0 else COLORS['red']
                st.markdown(f"<span style='color:{color};font-size:13px;font-weight:600'>{'+' if p['PV/MV']>=0 else ''}{p['PV/MV']:,.0f} €</span>", unsafe_allow_html=True)
            with col_d:
                color = COLORS['green'] if p['Perf'] >= 0 else COLORS['red']
                st.markdown(f"<span style='color:{color};font-size:13px;font-weight:700'>{'+' if p['Perf']>=0 else ''}{p['Perf']:.1f}%</span>", unsafe_allow_html=True)
            st.divider()

        st.markdown(f"""
        <div style="background:{COLORS['card']};border:1px solid {COLORS['blue']};border-radius:8px;
             padding:12px 16px;display:flex;justify-content:space-between;align-items:center">
            <span style="font-weight:700;font-size:14px">💰 TOTAL</span>
            <span style="font-family:'Space Grotesk';font-size:16px">{fmt_eur(total_live)}</span>
            <span style="color:{COLORS['green']};font-weight:700;font-size:15px">+{total_pvmv:,.0f} €</span>
            <span style="color:{COLORS['green']};font-weight:700;font-size:15px">+{total_perf:.1f}%</span>
        </div>""", unsafe_allow_html=True)

        # Benchmarks CAGR
        st.markdown("<br>", unsafe_allow_html=True)
        section_title("CAGR vs Benchmarks", "⚡")

        benchmarks = [
            ("🏆 Mon Portefeuille", 3.46,  COLORS['gold'], True),
            ("📈 SP500",            13.37, COLORS['cyan'],  False),
            ("🇫🇷 CAC 40 GR",      7.77,  COLORS['cyan'],  False),
            ("🌍 STOXX 600",        7.84,  COLORS['cyan'],  False),
        ]
        max_cagr = max(b[1] for b in benchmarks)

        for name, cagr, color, bold in benchmarks:
            pct_width = cagr / max_cagr * 100
            fw = "700" if bold else "400"
            st.markdown(f"""
            <div style="margin-bottom:12px">
                <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                    <span style="font-size:12px;font-weight:{fw};color:{''+COLORS['gold'] if bold else COLORS['muted']}">{name}</span>
                    <span style="font-family:'Space Grotesk';font-weight:{fw};color:{color};font-size:13px">
                        +{cagr:.2f} %</span>
                </div>
                <div style="height:5px;background:{COLORS['border']};border-radius:3px">
                    <div style="height:100%;width:{pct_width}%;background:{color};border-radius:3px;
                         transition:width 0.8s ease"></div>
                </div>
            </div>""", unsafe_allow_html=True)

        # Note méthodologie
        st.markdown(f"""
        <div style="margin-top:16px;padding:10px 14px;background:{COLORS['card']};
             border-radius:6px;border-left:2px solid {COLORS['muted']}">
            <span style="font-size:10px;color:{COLORS['muted']};font-style:italic">
            ⚠️ CAGR simplifié : (1+PV%)^(1/ans)−1. Delta = CAGR PF − CAGR Indice (pts %).
            Non équivalent à un XIRR.</span>
        </div>""", unsafe_allow_html=True)
