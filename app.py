import streamlit as st
import pandas as pd
try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
try:
    from streamlit_autorefresh import st_autorefresh
    AUTOREFRESH_AVAILABLE = True
except ImportError:
    AUTOREFRESH_AVAILABLE = False

st.set_page_config(page_title="SamInvest", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# Hide +/- stepper buttons on number inputs in valorisation scenario table
st.markdown("""<style>
/* Hide steppers globally on number inputs */
input[type=number]::-webkit-inner-spin-button,
input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
input[type=number] { -moz-appearance: textfield; }
/* Hide Streamlit's own +/- buttons */
[data-testid="stNumberInput"] button { display: none !important; }
[data-testid="stNumberInput"] > div { gap: 0 !important; }
</style>""", unsafe_allow_html=True)

SHEET_ID = "1ADzYAtCeFpP01eoFOdb2iiwSX3eU9rcbQbS6wQf6sgI"
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

C = {"bg":"#0D1117","card":"#161B27","border":"#21262D","text":"#E6EDF3","muted":"#8B949E",
     "green":"#6EE7B7","red":"#F85149","gold":"#D29922","blue":"#1F6FEB",
     "purple":"#8B5CF6","teal":"#10B981","cyan":"#58A6FF"}

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=DM+Sans:wght@400;500&display=swap');
html,body,[class*="css"]{{background:{C['bg']}!important;color:{C['text']}!important;font-family:'DM Sans',sans-serif}}
.stApp{{background:{C['bg']}}} .main .block-container{{padding:1.5rem 2rem;max-width:1400px}}
#MainMenu,footer,header{{visibility:hidden}} .stDeployButton{{display:none}}
.stTabs [data-baseweb="tab-list"]{{background:{C['card']};border-radius:10px;padding:4px;gap:4px;border:1px solid {C['border']}}}
.stTabs [data-baseweb="tab"]{{background:transparent;color:{C['muted']};border-radius:7px;padding:8px 20px;font-size:13px;font-weight:500}}
.stTabs [aria-selected="true"]{{background:{C['blue']}!important;color:white!important;color:#0D1117!important}}
/* Per-tab colors */
.stTabs [data-baseweb="tab-list"] button:nth-child(1)[aria-selected="true"]{{background:#818CF8!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(2)[aria-selected="true"]{{background:#6EE7B7!important;color:#0D1117!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(3)[aria-selected="true"]{{background:#7DD3FC!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(4)[aria-selected="true"]{{background:#FCD34D!important;color:#0D1117!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(5)[aria-selected="true"]{{background:#FDA4AF!important}}
/* Hover colors */
.stTabs [data-baseweb="tab-list"] button:nth-child(1):hover{{color:#818CF8!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(2):hover{{color:#6EE7B7!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(3):hover{{color:#7DD3FC!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(4):hover{{color:#FCD34D!important}}
.stTabs [data-baseweb="tab-list"] button:nth-child(5):hover{{color:#FDA4AF!important}}
.stTabs [data-baseweb="tab-panel"]{{padding-top:1.5rem}}
hr{{border-color:{C['border']}}}
</style>""", unsafe_allow_html=True)

# ── Google Sheets connection ───────────────────────────
@st.cache_resource
def get_client():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES)
    return gspread.authorize(creds)

@st.cache_data(ttl=300)
def fetch(sheet_name):
    try:
        client = get_client()
        sh = client.open_by_key(SHEET_ID)
        ws = sh.worksheet(sheet_name)
        return pd.DataFrame(ws.get_all_values())
    except Exception as e:
        st.warning(f"⚠️ Erreur lecture '{sheet_name}': {e}")
        return pd.DataFrame()

# ── Watchlist cours refresh ───────────────────────────
def refresh_watchlist_cours():
    """Re-fetch live price for every ticker in watchlist via yfinance."""
    if not YF_AVAILABLE: return
    wl = st.session_state.get("watchlist", [])
    if not wl: return
    updated = 0
    for w in wl:
        ticker = w.get("ticker", "")
        if not ticker: continue
        try:
            tk = yf.Ticker(ticker)
            fi = tk.fast_info
            price_raw = getattr(fi, "last_price", None) or getattr(fi, "regular_market_price", None)
            cur = getattr(fi, "currency", "USD") or "USD"
            if price_raw:
                try:
                    fx = yf.Ticker("EURUSD=X").fast_info.last_price if cur == "USD" else 1.0
                    if not fx: fx = 1.16
                except: fx = 1.16
                w["cours"] = round(float(price_raw) / fx, 2)
                updated += 1
        except: pass
    from datetime import datetime as _dt; st.session_state["watchlist_last_refresh"] = _dt.now().strftime("%H:%M:%S")
    st.session_state["watchlist_updated_count"] = updated

# ── Helpers ────────────────────────────────────────────
def v(df, r, c, d=0):
    try:
        x = df.iloc[r, c]
        return x if str(x).strip() not in ['', 'nan'] else d
    except: return d

def n(val):
    import re
    s = re.sub(r'[€$\s+%\u202f\xa0]', '', str(val)).replace(',', '.')
    if s.count('.') > 1: s = s.replace('.', '', s.count('.')-1)
    try: return float(s)
    except: return 0.0

def fmt(x): return f"{int(round(x)):,}".replace(",", " ") + " €"
def pct(x): return f"{'+' if x>=0 else ''}{x:.2f} %"
def pcol(x): return C['green'] if x >= 0 else C['red']

def card(title, value, sub="", color=C['blue'], icon="", sub2=""):
    s1 = f"<div style='font-size:12px;color:{color};min-height:17px'>{sub}</div>"
    s2 = "<div style='font-size:11px;color:" + C['muted'] + ";min-height:15px'>" + str(sub2) + "</div>"
    return f"""<div style="background:{C['card']};border:1px solid {C['border']};border-top:2px solid {color};border-radius:10px;padding:14px 18px;height:118px;box-sizing:border-box;display:flex;flex-direction:column">
<div style="font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">{icon} {title}</div>
<div style="font-family:'Space Grotesk';font-size:22px;font-weight:700;color:{C['text']};line-height:1.2;flex:1">{value}</div>
{s1}{s2}
</div>"""

def sec(txt, icon="", color=C['blue'], bg=None):
    bg_col = bg or C['card']
    st.markdown(f"""<div style="background:{bg_col};border-left:4px solid {color};border-radius:6px;
padding:10px 16px;margin:1.5rem 0 1rem 0;border-right:1px solid {color}22;border-top:1px solid {color}22;border-bottom:1px solid {color}22">
<span style="font-family:'Space Grotesk';font-weight:600;font-size:14px;color:{color}">{icon}&nbsp; {txt}</span></div>""", unsafe_allow_html=True)

def base_layout(height=280, legend=False):
    return dict(paper_bgcolor=C['bg'], plot_bgcolor=C['card'],
        font=dict(family="DM Sans", color=C['muted']),
        margin=dict(l=5, r=5, t=25, b=25), height=height, showlegend=legend,
        separators=', ',
        xaxis=dict(gridcolor=C['border'], linecolor=C['border'], tickfont=dict(color=C['muted'],size=11)),
        yaxis=dict(gridcolor=C['border'], linecolor=C['border'], tickfont=dict(color=C['muted'],size=11)))

# ── Header ─────────────────────────────────────────────
from datetime import datetime, timezone, timedelta
_paris = datetime.now(timezone(timedelta(hours=2)))
_now   = _paris.strftime("%d/%m/%Y à %H:%M")

_h1, _h2 = st.columns([8, 1])
with _h1:
    st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding:12px 0;margin-bottom:4px;border-bottom:1px solid {C['border']}">
<div style="display:flex;align-items:center;gap:12px">
<div style="width:40px;height:40px;border-radius:10px;overflow:hidden;flex-shrink:0">
<img src="data:image/png;base64,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" style="width:40px;height:40px;object-fit:cover;border-radius:10px"/>
</div>
<div style="font-family:'Space Grotesk';font-size:18px;font-weight:700;letter-spacing:-0.3px">SamInvest</div></div>
<div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px">
<div style="display:flex;align-items:center;gap:6px">
  <div style="width:7px;height:7px;border-radius:50%;background:{C['green']};box-shadow:0 0 5px {C['green']}"></div>
  <span style="font-size:11px;color:{C['muted']}">Données live · Refresh auto toutes les 5 min</span>
</div>
<div style="font-size:10px;color:{C['muted']}">🔄 Dernière synchro : <b>{_now}</b></div>
</div></div>""", unsafe_allow_html=True)
with _h2:
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    if st.button("↻ Rafraîchir", key="global_refresh_btn", use_container_width=True,
        help="Rafraîchit Google Sheet + cours live"):
        refresh_watchlist_cours()
        st.cache_data.clear()
        st.rerun()

mois_s = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
mois_f = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

tab1, tab5, tab2, tab3, tab4, tab6, tab7 = st.tabs(["🏠 Vue d'ensemble", "📊 Performance", "📈 Bourse", "₿ Crypto", "⚙️ Options", "🔍 Valorisation", "⭐ Watchlist"])

# ══════════════════════════════════════════════════════
# TAB 1 — VUE D'ENSEMBLE
# ══════════════════════════════════════════════════════
with tab1:
    df_p  = fetch("🏠 Patrimoine")
    df_em = fetch("📅 Évol. Mensuelle")
    df_ea = fetch("📈 Évol. Annuelle")
    df_pf = fetch("🏆 Perf. Totale")
    df_b  = fetch("📊 Bourse 2026")
    df_opt= fetch("⚙️ Options 2026")

    pat=n(v(df_p,5,1)); inv=n(v(df_p,5,3)); perf=n(v(df_p,5,5)); cagr=n(v(df_p,5,9))
    ytd=n(v(df_em,5,9)); ytdp=n(v(df_em,5,12))
    divs_ytd = n(v(df_b,5,15))
    primes_ytd = n(v(df_opt,5,12))

    # ── 7 KPI cards ────────────────────────────────────
    cols = st.columns(7)
    for col,(ti,va,su,co,ic,s2) in zip(cols,[
        ("PATRIMOINE TOTAL", fmt(pat),  "",                          C['gold'],   "🏆", ""),
        ("TOTAL INVESTI",    fmt(inv),  "",                          C['blue'],   "💰", ""),
        ("PERFORMANCE",      pct(perf), "depuis février 2022",        pcol(perf),  "📈", ""),
        ("CAGR ANNUALISÉ",   pct(cagr), "depuis fév. 2022",          C['purple'], "⚡", ""),
        ("VARIATION YTD",    fmt(ytd),  pct(ytdp),                   pcol(ytd),   "📅", ""),
        ("DIVIDENDES YTD",   f"{divs_ytd:.2f} €", "net perçu",       C['gold'],   "💰", ""),
        ("PRIMES OPTIONS",   f"{primes_ytd:.2f} €","YTD 2026",        C['purple'], "⚙️", ""),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic,s2), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    L, R = st.columns([2,1])

    with L:
        sec("Évolution mensuelle 2026","📅","#818CF8","#0A0E1A")
        pats=[n(v(df_em,13+i,2)) for i in range(12)]
        vars_=[n(v(df_em,13+i,3)) if str(v(df_em,13+i,3,"")).strip() not in ["—",""] else None for i in range(12)]
        xp=[mois_s[i] for i,x in enumerate(pats) if x>0]
        yp=[x for x in pats if x>0]
        fig1=go.Figure()
        # Area line
        fig1.add_trace(go.Scatter(x=xp,y=yp,mode='lines+markers',name='Patrimoine',
            line=dict(color=C['blue'],width=3,shape='spline'),
            marker=dict(color=C['gold'],size=8,line=dict(color=C['bg'],width=2)),
            fill='tozeroy',fillcolor='rgba(31,111,235,0.08)',
            hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
        for x_,y_ in zip(xp,yp):
            fig1.add_annotation(x=x_,y=y_,text=f"{y_/1000:.0f}k€",showarrow=False,yshift=14,font=dict(size=10,color=C['text']))
        fig1.update_layout(**base_layout(220))
        fig1.update_yaxes(tickformat='.0f',ticksuffix=' €')
        st.plotly_chart(fig1,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        sec("Variations mensuelles","📊","#818CF8","#0A0E1A")
        xv=[mois_s[i] for i,x in enumerate(vars_) if x is not None]
        yv=[x for x in vars_ if x is not None]
        # Get % variations too
        # Build month→% map correctly (skip months with no patrimoine)
        pct_by_month={}
        for i in range(12):
            m_label=mois_s[i]
            pct_str=str(v(df_em,13+i,4,"")).strip()
            if pct_str not in ["—",""]:
                pct_by_month[m_label]=pct_str
        if yv:
            fig2=go.Figure(go.Bar(x=xv,y=yv,
                marker_color=[C['green'] if x>=0 else C['red'] for x in yv],
                text=[f"{'+' if x>=0 else ''}{x:.0f}€  {pct_by_month.get(xv[i],'')}" for i,x in enumerate(yv)],
                textposition='outside',textfont=dict(color=C['text'],size=10),
                hovertemplate='<b>%{x}</b><br>%{y:+.0f} €<extra></extra>'))
            fig2.update_layout(**base_layout(200))
            fig2.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(fig2,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})



        sec("Évolution annuelle","📈","#818CF8","#0A0E1A")
        tots=[n(v(df_ea,11+i,9)) for i in range(5)]
        yrs=["2022","2023","2024","2025","2026"]
        tv=[x for x in tots if x>0]; yl=yrs[:len(tv)]
        if tv:
            fig4=go.Figure(go.Scatter(x=yl,y=tv,mode='lines+markers',
                line=dict(color=C['gold'],width=3,shape='spline'),
                marker=dict(color=C['gold'],size=8,line=dict(color=C['bg'],width=2)),
                fill='tozeroy',fillcolor='rgba(210,153,34,0.08)',
                hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
            # Annotations évol %
            for i in range(1,len(tv)):
                evol=(tv[i]/tv[i-1]-1)*100
                fig4.add_annotation(x=yl[i],y=tv[i],
                    text=f"{'+' if evol>=0 else ''}{evol:.0f}%",
                    showarrow=False,yshift=16,
                    font=dict(size=9,color=C['green'] if evol>=0 else C['red']))
            fig4.update_layout(**base_layout(180))
            fig4.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(fig4,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})
    with R:
        sec("Répartition","🍩","#818CF8","#0A0E1A")
        cats=["📈 Bourse","₿ Crypto","⚙️ Options","🏢 PEE","📋 PER","🛡️ AV","💵 Cash"]
        clrs=[C['blue'],C['gold'],C['purple'],C['teal'],"#A855F7","#6B7280","#06B6D4"]
        vals=[n(v(df_p,19+i,2)) for i in range(7)]
        combined=sorted([(c,cl,v_) for c,cl,v_ in zip(cats,clrs,vals) if v_>0],key=lambda x:-x[2])
        all_lbl=[x[0] for x in combined]
        all_clr=[x[1] for x in combined]
        all_val=[x[2] for x in combined]

        sel=st.multiselect("",all_lbl,default=all_lbl,key="rep_filter",
            help="Cliquez pour afficher/masquer une enveloppe")
        lbl=[l for l in all_lbl if l in sel]
        vc=[all_clr[all_lbl.index(l)] for l in lbl]
        vv=[all_val[all_lbl.index(l)] for l in lbl]
        total_sel=sum(vv) if vv else 0

        if vv:
            fig3=go.Figure(go.Pie(labels=lbl,values=vv,hole=0.55,
                marker=dict(colors=vc,line=dict(color=C['bg'],width=2)),
                textinfo='percent',textfont=dict(size=11,color='white'),
                customdata=[[fmt(v_)] for v_ in vv],
                hovertemplate='<b>%{label}</b><br>%{customdata[0]}<br>%{percent}<extra></extra>'))
            fig3.add_annotation(text=f"<b>{total_sel/1000:.0f}k€</b>",x=0.5,y=0.5,
                font=dict(size=16,color=C['text'],family='Space Grotesk'),showarrow=False)
            fig3.update_layout(**base_layout(260,False))
            fig3.update_layout(showlegend=False,margin=dict(l=0,r=0,t=10,b=10))
            st.plotly_chart(fig3,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        for lbl_,clr_,val_ in zip(all_lbl,all_clr,all_val):
            active = lbl_ in sel
            pct_   = val_/sum(all_val)*100 if sum(all_val) else 0
            op     = "1" if active else "0.3"
            st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding:5px 8px;border-radius:6px;margin-bottom:3px;background:{C['card']};opacity:{op}">
<div style="display:flex;align-items:center;gap:8px">
  <div style="width:12px;height:12px;border-radius:3px;background:{clr_};flex-shrink:0"></div>
  <span style="font-size:12px;color:{C['text']};font-weight:500">{lbl_}</span>
</div>
<span style="font-size:12px;color:{clr_};font-weight:700">{fmt(val_)} · {pct_:.1f}%</span>
</div>""", unsafe_allow_html=True)



# ══════════════════════════════════════════════════════
with tab2:
    df_b=fetch("📊 Bourse 2026")
    bi=n(v(df_b,5,1)); bs=n(v(df_b,5,3)); bpv=n(v(df_b,5,6)); bpp=n(v(df_b,5,8))
    bd=n(v(df_b,5,15)); bp=n(v(df_b,5,11))

    cols=st.columns(5)
    for col,(ti,va,su,co,ic,s2) in zip(cols,[
        ("TOTAL INVESTI", fmt(bi),       "",                   C['cyan'],  "💰", ""),
        ("SOLDE ACTUEL",  fmt(bs),       "",                   C['blue'],  "💶", ""),
        ("PV / MV",       fmt(bpv),      pct(bpp),             pcol(bpp),  "📈", ""),
        ("DIVIDENDES NET",f"{bd:.2f} €", "2026 YTD net",       C['gold'],  "💰", ""),
        ("PARRAINAGE YTD",f"{bp:.2f} €", "",                   C['teal'],  "🤝", ""),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic,s2), unsafe_allow_html=True)

    L2,R2=st.columns(2)

    with L2:
        sec("DCA Mensuel 2026 — CTO & PEA","💸","#7DD3FC","#0A1A1C")
        dca_cto=[n(v(df_b,11+i,2)) for i in range(12)]
        dca_pea=[n(v(df_b,11+i,3)) for i in range(12)]
        fig5=go.Figure()
        fig5.add_trace(go.Bar(name='CTO',x=mois_f,y=dca_cto,marker_color=C['blue'],
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_cto],
            textposition='inside',textfont=dict(color='white',size=9),
            hovertemplate='<b>%{x}</b><br>CTO: %{y:.2f} €<extra></extra>'))
        fig5.add_trace(go.Bar(name='PEA',x=mois_f,y=dca_pea,marker_color=C['green'],
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_pea],
            textposition='inside',textfont=dict(color='white',size=9),
            hovertemplate='<b>%{x}</b><br>PEA: %{y:.2f} €<extra></extra>'))
        fig5.update_layout(**base_layout(280,True),barmode='stack')
        fig5.update_layout(legend=dict(orientation='h',y=-0.12,font=dict(size=11)))
        fig5.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig5,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # DCA cumul ligne
        dca_tot=[n(v(df_b,11+i,4)) for i in range(12)]
        xc=[mois_f[i] for i,x in enumerate(dca_tot) if x>0]
        yc=[x for x in dca_tot if x>0]
        if xc:
            sec("DCA Cumulé 2026","📈","#7DD3FC","#0A1A1C")
            figc=go.Figure(go.Scatter(x=xc,y=yc,mode='lines+markers+text',
                line=dict(color=C['cyan'],width=2,shape='spline'),
                marker=dict(color=C['gold'],size=7),fill='tozeroy',fillcolor='rgba(6,182,212,0.08)',
                text=[f"{y:.0f}€" for y in yc],textposition='top center',textfont=dict(size=9,color=C['text']),
                hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
            figc.update_layout(**base_layout(180))
            figc.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(figc,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

    with R2:
        sec("Évolution du solde (CTO + PEA)","📊","#7DD3FC","#0A1A1C")
        sol=[n(v(df_b,11+i,9)) for i in range(12)]
        sol_cto=[n(v(df_b,11+i,7)) for i in range(12)]
        sol_pea=[n(v(df_b,11+i,8)) for i in range(12)]
        xsol=[mois_f[i] for i,x in enumerate(sol) if x>0]
        ysol=[x for x in sol if x>0]
        ycto=[sol_cto[i] for i,x in enumerate(sol) if x>0]
        ypea=[sol_pea[i] for i,x in enumerate(sol) if x>0]
        if ysol:
            fig6=go.Figure()
            fig6.add_trace(go.Scatter(x=xsol,y=ysol,name='Total',
                line=dict(color=C['blue'],width=3,shape='spline'),
                marker=dict(color=C['gold'],size=7),fill='tozeroy',fillcolor='rgba(31,111,235,0.06)',
                text=[f"{y/1000:.0f}k€" for y in ysol],textposition='top center',mode='lines+markers+text',
                textfont=dict(size=9,color=C['text']),
                hovertemplate='Total: %{y:.0f} €<extra></extra>'))
            fig6.add_trace(go.Scatter(x=xsol,y=ycto,name='CTO',
                line=dict(color=C['cyan'],width=1.5,dash='dot'),
                hovertemplate='CTO: %{y:.0f} €<extra></extra>'))
            fig6.add_trace(go.Scatter(x=xsol,y=ypea,name='PEA',
                line=dict(color=C['green'],width=1.5,dash='dot'),
                hovertemplate='PEA: %{y:.0f} €<extra></extra>'))
            fig6.update_layout(**base_layout(280,True))
            fig6.update_layout(legend=dict(orientation='h',y=-0.12,font=dict(size=11)))
            fig6.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(fig6,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # Dividendes
        sec("Dividendes 2026","💰","#7DD3FC","#0A1A1C")
        div_rows=[]
        for i in range(15):
            r_=11+i
            act=str(v(df_b,r_,15,"")).strip()
            pays=str(v(df_b,r_,16,"")).strip()
            net=n(v(df_b,r_,17,0))
            if act and act not in ["Action",""] and net>0:
                div_rows.append({"Action":act,"Pays":pays,"_net":net})
        if div_rows:
            df_div=pd.DataFrame(div_rows).sort_values("_net",ascending=False).reset_index(drop=True)
            df_div_display=df_div[["Action","Pays","_net"]].rename(columns={"_net":"Net (€)"})
            st.dataframe(df_div_display,use_container_width=True,hide_index=True,height=260,
                column_config={"Net (€)":st.column_config.NumberColumn("Net (€)",format="%.2f €")})

        # Solde mensuel CTO/PEA tableau
        sec("Solde mensuel CTO & PEA","📋","#7DD3FC","#0A1A1C")
        solde_rows=[]
        for i in range(12):
            m=mois_f[i]
            scto=n(v(df_b,11+i,7)); spea=n(v(df_b,11+i,8)); stot=n(v(df_b,11+i,9))
            if stot>0:
                solde_rows.append({"Mois":m,"CTO (€)":f"{scto:.0f} €","PEA (€)":f"{spea:.0f} €","Total (€)":f"{stot:.0f} €"})
        if solde_rows:
            st.dataframe(pd.DataFrame(solde_rows),use_container_width=True,hide_index=True,height=min(280,len(solde_rows)*38+40))

# ══════════════════════════════════════════════════════
with tab3:
    df_ct=fetch("₿ Crypto Total")
    cv=n(v(df_ct,5,1)); cd=n(v(df_ct,5,3)); ci=n(v(df_ct,5,5))
    cpv=n(v(df_ct,5,8)); cp=n(v(df_ct,5,10)); ceur=n(v(df_ct,5,12))

    cols=st.columns(5)
    for col,(ti,va,su,co,ic) in zip(cols,[
        ("VALEUR PF (€)",  fmt(cv),           "",        C['gold'],  "💶"),
        ("VALEUR PF ($)",  f"{cd:.2f} $",    "",        C['gold'],  "💵"),
        ("TOTAL INVESTI",  fmt(ci),            "",        C['blue'],  "💰"),
        ("PV / MV",        fmt(cpv),           pct(cp),  pcol(cp),   "📈"),
        ("COURS EUR/$",    f"{ceur:.4f}",      "",        C['muted'], "💱"),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic), unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    L3,R3=st.columns([3,2])

    with L3:
        sec("Portefeuille Crypto","₿","#FCD34D","#1C100A")
        cdata=[]
        names_c=["Bitcoin","Solana","Ethereum","BinanceCoin","USDC"]
        for i,nm in enumerate(names_c):
            r_=11+i
            cdata.append({"Crypto":nm,"Code":str(v(df_ct,r_,2)),"Montant":str(v(df_ct,r_,3)),
                "Valeur $":f"{n(v(df_ct,r_,5)):.2f} $","Valeur €":fmt(n(v(df_ct,r_,6))),
                "PV/MV €":f"{'+' if n(v(df_ct,r_,11))>=0 else ''}{n(v(df_ct,r_,11)):.0f} €",
                "Perf.":f"{'+' if n(v(df_ct,r_,12))>=0 else ''}{n(v(df_ct,r_,12)):.1f} %"})
        st.dataframe(pd.DataFrame(cdata),use_container_width=True,hide_index=True,height=210)

        df_c26=fetch("₿ Crypto 2026")
        sec("DCA Mensuel 2026","💸","#FCD34D","#1C100A")
        dca_c=[n(v(df_c26,20+i,2)) for i in range(12)]
        fig7=go.Figure(go.Bar(x=mois_s,y=dca_c,
            marker_color=[C['gold'] if x>0 else C['border'] for x in dca_c],
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_c],
            textposition='outside',textfont=dict(color=C['text'],size=10)))
        fig7.update_layout(**base_layout(200))
        fig7.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig7,use_container_width=True,config={'displayModeBar':False})

    with R3:
        sec("Répartition","🍩","#818CF8","#0A0E1A")
        clrs_c=["#FCD34D","#9945FF","#627EEA","#F3BA2F","#2775CA"]
        pcts_c=[n(v(df_ct,19+i,12)) for i in range(5)]
        if sum(pcts_c)==0: pcts_c=[28.04,33.66,15.15,22.98,0.21]
        vals_c=[cd*p/100 for p in pcts_c]

        # ── Tri + multiselect comme vue d'ensemble ───
        combined_c = sorted(
            [(nm, cl, vl) for nm, cl, vl in zip(names_c, clrs_c, vals_c) if vl > 0],
            key=lambda x: -x[2]
        )
        all_lbl_c = [x[0] for x in combined_c]
        all_clr_c = [x[1] for x in combined_c]
        all_val_c = [x[2] for x in combined_c]

        sel_c = st.multiselect("", all_lbl_c, default=all_lbl_c, key="crypto_rep_filter",
            help="Cliquez pour afficher/masquer une crypto")
        lbl_c = [l for l in all_lbl_c if l in sel_c]
        clr_c = [all_clr_c[all_lbl_c.index(l)] for l in lbl_c]
        val_c = [all_val_c[all_lbl_c.index(l)] for l in lbl_c]
        total_c = sum(val_c) if val_c else 0

        if val_c:
            fig8 = go.Figure(go.Pie(
                labels=lbl_c, values=val_c, hole=0.55,
                marker=dict(colors=clr_c, line=dict(color=C['bg'], width=2)),
                textinfo='percent',
                textfont=dict(size=11, color='white'),
                customdata=[[f"{v_:,.0f} $"] for v_ in val_c],
                hovertemplate='<b>%{label}</b><br>%{customdata[0]}<br>%{percent}<extra></extra>'
            ))
            fig8.add_annotation(
                text=f"<b>{total_c/1000:.1f}k$</b>", x=0.5, y=0.5,
                font=dict(size=16, color=C['text'], family='Space Grotesk'), showarrow=False
            )
            fig8.update_layout(**base_layout(260, False))
            fig8.update_layout(showlegend=False, margin=dict(l=0, r=0, t=10, b=10))
            st.plotly_chart(fig8, use_container_width=True, config={
                'displayModeBar': True,
                'modeBarButtonsToRemove': ['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],
                'displaylogo': False
            })

        # ── Légende manuelle style carte ─────────────
        for nm, cl, vl in zip(all_lbl_c, all_clr_c, all_val_c):
            active = nm in sel_c
            pct_   = vl / sum(all_val_c) * 100 if sum(all_val_c) else 0
            op     = "1" if active else "0.3"
            st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding:5px 8px;border-radius:6px;margin-bottom:3px;background:{C['card']};opacity:{op}">
<div style="display:flex;align-items:center;gap:8px">
  <div style="width:12px;height:12px;border-radius:3px;background:{cl};flex-shrink:0"></div>
  <span style="font-size:12px;color:{C['text']};font-weight:500">{nm}</span>
</div>
<span style="font-size:12px;color:{cl};font-weight:700">{vl:,.0f} $ · {pct_:.1f}%</span>
</div>""", unsafe_allow_html=True)

        sec("Gains Staking","🌾","#FCD34D","#1C100A")
        staking_cfg=[("Bitcoin","#F7931A",0),("Solana","#9945FF",1),("Ethereum","#627EEA",2),("BinanceCoin","#F3BA2F",3)]
        st_rows=[]
        for nm,clr,idx in staking_cfg:
            g=n(v(df_ct,19+idx,9))
            if g!=0: st_rows.append((nm,clr,g))
        for nm,clr,g in st_rows:
            gclr=C['green'] if g>=0 else C['red']
            sign='+' if g>=0 else ''
            st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid {C['border']}">
<span style="font-weight:600;color:{clr}">{nm}</span>
<span style="font-family:'Space Grotesk';font-weight:700;color:{gclr}">{sign}{g:.2f} $</span></div>""",unsafe_allow_html=True)
        total_st=sum(x[2] for x in st_rows)
        if total_st:
            st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:10px 0">
<span style="color:{C['muted']};font-size:12px">TOTAL STAKING</span>
<span style="font-family:'Space Grotesk';font-size:16px;font-weight:700;color:{C['green']}">+{total_st:.2f} $</span></div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# TAB 4 — OPTIONS & PERF
# ══════════════════════════════════════════════════════
with tab4:
    df_opt=fetch("⚙️ Options 2026")
    oc=n(v(df_opt,5,0)); oroi=n(v(df_opt,5,9))
    ope=n(v(df_opt,5,12)); opd=n(v(df_opt,5,15))

    roi_pct = oroi*100 if abs(oroi)<5 else oroi
    c1,c2,c3,c4=st.columns(4)
    with c1: st.markdown(card("CAPITAL ACTUEL",fmt(n(v(df_opt,5,3))),"",C['purple'],"📈"),unsafe_allow_html=True)
    with c2: st.markdown(card("CAPITAL INVESTI",fmt(n(v(df_opt,5,6))),"",C['blue'],"💰"),unsafe_allow_html=True)
    with c3: st.markdown(card("ROI TOTAL",f"{roi_pct:+.2f} %","",pcol(roi_pct),"🏆"),unsafe_allow_html=True)
    with c4: st.markdown(card("PRIMES YTD",f"{ope:.2f} €",f"{opd:.2f} $",C['gold'],"💰"),unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)

    sec("Options 2026 — Stratégie de la Roue — Primes mensuelles","⚙️","#FDA4AF","#1C0A12")
    primes=[n(v(df_opt,12+i,9)) for i in range(12)]
    rois=[n(v(df_opt,12+i,15)) for i in range(12)]
    fig9=go.Figure()
    fig9.add_trace(go.Bar(name='Prime (€)',x=mois_s,y=primes,
        marker_color=[C['purple'] if x>0 else C['border'] for x in primes],yaxis='y',
        hovertemplate='<b>%{x}</b><br>%{y:.2f} €<extra></extra>'))
    fig9.add_trace(go.Scatter(name='ROI %',x=mois_s,y=rois,
        line=dict(color=C['gold'],width=2),mode='lines+markers',marker=dict(size=6),yaxis='y2',
        hovertemplate='<b>%{x}</b><br>%{y:.2f} %<extra></extra>'))
    fig9.update_layout(**base_layout(320,True))
    fig9.update_layout(
        yaxis=dict(ticksuffix=' €',gridcolor=C['border'],linecolor=C['border'],tickfont=dict(color=C['muted'],size=11)),
        yaxis2=dict(overlaying='y',side='right',tickfont=dict(color=C['gold'],size=10),tickformat='.2f',ticksuffix=' %',gridcolor='rgba(0,0,0,0)',rangemode='nonnegative'),
        legend=dict(orientation='h',y=-0.12,font=dict(size=11)))
    st.plotly_chart(fig9,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

# ══════════════════════════════════════════════════════
with tab5:
    df_pf  = fetch("🏆 Perf. Totale")
    df_ea  = fetch("📈 Évol. Annuelle")
    df_pat = fetch("🏠 Patrimoine")

    # ── KPIs Performance ───────────────────────────────
    perf_t = n(v(df_pf,5,5))
    cagr_t = n(v(df_pf,5,9)) if df_pf.shape[0]>5 else n(v(df_pat,5,9))
    inv_t  = n(v(df_pf,9,2))
    live_t = n(v(df_pf,9,3))
    pvmv_t = live_t - inv_t
    pp_t   = (live_t/inv_t-1)*100 if inv_t else 0

    c1,c2,c3,c4 = st.columns(4)
    for col,(ti,va,su,co,ic) in zip([c1,c2,c3,c4],[
        ("TOTAL INVESTI",    fmt(inv_t),          "",                   C['blue'],  "💰"),
        ("VALEUR ACTUELLE",  fmt(live_t),          "",                   C['cyan'],  "📈"),
        ("PV / MV TOTAL",    fmt(pvmv_t),          pct(pp_t),            pcol(pp_t), "💹"),
        ("CAGR ANNUALISÉ",   pct(n(v(df_pat,5,9))),"depuis fév. 2022",  C['purple'],"⚡"),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic),unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    Lp, Rp = st.columns([3,2])

    with Lp:
        sec("Performance par enveloppe","🏆","#6EE7B7","#0A1C0F")
        poches=[
            ("📈 Bourse (CTO+PEA)", n(v(df_pf,6,2)), n(v(df_pf,6,3)), C['blue']),
            ("₿ Crypto (Binance)",  n(v(df_pf,7,2)), n(v(df_pf,7,3)), C['gold']),
            ("⚙️ Options (IBK)",    n(v(df_pf,8,2)), n(v(df_pf,8,3)), C['purple']),
        ]
        for po,pi,pl,pc in poches:
            ppv=pl-pi; pp=(pl/pi-1)*100 if pi else 0
            a,b,cc,d=st.columns([2.5,1.5,1.5,1.2])
            with a: st.markdown(f"<span style='color:{pc};font-weight:600;font-size:13px'>{po}</span>",unsafe_allow_html=True)
            with b: st.markdown(f"<span style='font-size:13px'>{fmt(pl)}</span>",unsafe_allow_html=True)
            with cc:
                clr=C['green'] if ppv>=0 else C['red']
                st.markdown(f"<span style='color:{clr};font-size:13px;font-weight:600'>{'+' if ppv>=0 else ''}{int(round(abs(ppv))):,} €</span>".replace(',', ' '),unsafe_allow_html=True)
            with d:
                clr=C['green'] if pp>=0 else C['red']
                st.markdown(f"<span style='color:{clr};font-size:13px;font-weight:700'>{'+' if pp>=0 else ''}{pp:.1f}%</span>",unsafe_allow_html=True)
            st.divider()

        tl=sum(p[2] for p in poches); ti2=sum(p[1] for p in poches)
        tpv=tl-ti2; tp=(tl/ti2-1)*100 if ti2 else 0
        st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['blue']};border-radius:8px;
padding:12px 16px;display:flex;justify-content:space-between;align-items:center">
<span style="font-weight:700">💰 TOTAL</span>
<span style="font-family:'Space Grotesk';font-size:16px">{fmt(tl)}</span>
<span style="color:{C['green']};font-weight:700">+{str(int(round(tpv))).replace(',', ' ')} €</span>
<span style="color:{C['green']};font-weight:700">+{tp:.1f}%</span></div>""",unsafe_allow_html=True)

        # Évolution annuelle
        sec("Évolution annuelle du patrimoine","📈","#6EE7B7","#0A1C0F")
        tots=[n(v(df_ea,11+i,9)) for i in range(5)]
        yrs=["2022","2023","2024","2025","2026"]
        tv=[x for x in tots if x>0]; yl=yrs[:len(tv)]
        if tv:
            fig_ea=go.Figure(go.Scatter(x=yl,y=tv,mode='lines+markers',
                line=dict(color=C['gold'],width=3,shape='spline'),
                marker=dict(color=C['gold'],size=9,line=dict(color=C['bg'],width=2)),
                fill='tozeroy',fillcolor='rgba(210,153,34,0.08)',
                hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
            for i in range(1,len(tv)):
                evol=(tv[i]/tv[i-1]-1)*100
                fig_ea.add_annotation(x=yl[i],y=tv[i],
                    text=f"{'+' if evol>=0 else ''}{evol:.0f}%",
                    showarrow=False,yshift=16,font=dict(size=10,color=C['green'] if evol>=0 else C['red']))
            fig_ea.update_layout(**base_layout(260))
            fig_ea.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(fig_ea,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

    with Rp:
        sec("CAGR vs Benchmarks","⚡","#6EE7B7","#0A1C0F")
        benchs=[
            ("🏆 Mon PF",    n(v(df_pf,13,2)), C['gold'], True),
            ("📈 SP500",     n(v(df_pf,14,2)), C['cyan'], False),
            ("🇫🇷 CAC 40",  n(v(df_pf,15,2)), C['cyan'], False),
            ("🌍 STOXX 600", n(v(df_pf,16,2)), C['cyan'], False),
        ]
        if all(b[1]==0 for b in benchs):
            benchs=[("🏆 Mon PF",3.64,C['gold'],True),("📈 SP500",13.37,C['cyan'],False),
                    ("🇫🇷 CAC 40",7.77,C['cyan'],False),("🌍 STOXX 600",7.84,C['cyan'],False)]
        mx=max(b[1] for b in benchs) or 1
        for bn,bv,bc,bold in benchs:
            fw="700" if bold else "400"; fc=C['gold'] if bold else C['muted']
            st.markdown(f"""<div style="margin-bottom:14px">
<div style="display:flex;justify-content:space-between;margin-bottom:5px">
<span style="font-size:13px;font-weight:{fw};color:{fc}">{bn}</span>
<span style="font-family:'Space Grotesk';font-weight:{fw};color:{bc};font-size:14px">+{bv:.2f} %</span></div>
<div style="height:6px;background:{C['border']};border-radius:3px">
<div style="height:100%;width:{bv/mx*100:.0f}%;background:{bc};border-radius:3px"></div></div></div>""",unsafe_allow_html=True)

        # Alpha vs benchmarks
        mon_pf = benchs[0][1]
        st.markdown(f"<div style='margin-top:16px'>",unsafe_allow_html=True)
        sec("Alpha vs Benchmarks","📐","#6EE7B7","#0A1C0F")
        for bn,bv,bc,bold in benchs[1:]:
            alpha = mon_pf - bv
            clr = C['green'] if alpha>=0 else C['red']
            st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid {C['border']}">
<span style="font-size:12px;color:{C['muted']}">{bn}</span>
<span style="font-weight:700;color:{clr};font-size:13px">{'+' if alpha>=0 else ''}{alpha:.2f} pts %</span></div>""",unsafe_allow_html=True)

        # Méthode note
        st.markdown(f"""<div style="margin-top:16px;padding:10px 14px;background:{C['card']};
border-radius:6px;border-left:2px solid {C['muted']}">
<span style="font-size:10px;color:{C['muted']};font-style:italic">
⚠️ CAGR simplifié : (1+PV%)^(1/ans)−1. Delta = CAGR PF − CAGR Indice (pts %).</span></div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
with tab6:
    C_VAL = "#A78BFA"
    C_VAL_DIM = "#1E1530"

    # ── Session state — 3 listes distinctes ─────────
    for _k in ["wl_portefeuille", "wl_options", "wl_surveillance"]:
        if _k not in st.session_state:
            st.session_state[_k] = []
    if "wl_sort_asc" not in st.session_state:
        st.session_state.wl_sort_asc = False
    # watchlist = vue plate pour KPI hint uniquement
    st.session_state.watchlist = (st.session_state.wl_portefeuille +
                                   st.session_state.wl_options +
                                   st.session_state.wl_surveillance)

    # ── Layout ───────────────────────────────────────
    col_form, col_res = st.columns([1, 1.6])

    with col_form:
        sec("Simulateur de valorisation", "🔍", C_VAL, C_VAL_DIM)
        add_wl = False  # default — overridden by button if visible

        # Method selector
        method = st.selectbox("Méthode de projection", 
            ["EPS / PER","FCF / PER","DCF (Discounted Cash Flow)"], 
            label_visibility="collapsed", key="valo_method")

        # Company info — auto-fetch via yfinance
        st.markdown(f"<div style='font-size:10px;color:{C_VAL};text-transform:uppercase;letter-spacing:.08em;margin:8px 0 4px'>Ticker (ex: MC.PA, ADBE, MSFT)</div>", unsafe_allow_html=True)
        ticker_input = st.text_input("", placeholder="Ex: MC.PA pour LVMH, ADBE pour Adobe...", label_visibility="collapsed", key="valo_ticker")

        # Auto-fetch on ticker entry
        action_name = st.session_state.get("valo_name_auto", "")
        cours_auto  = st.session_state.get("valo_cours_auto", 0.0)
        currency    = st.session_state.get("valo_currency", "€")

        if ticker_input and len(ticker_input) >= 2:
            # Auto-fetch when ticker changes
            last_ticker = st.session_state.get("valo_last_ticker", "")
            if ticker_input.strip().upper() != last_ticker:
                st.session_state["valo_last_ticker"] = ticker_input.strip().upper()
                st.session_state["valo_do_fetch"] = True

            if st.session_state.get("valo_do_fetch", False):
                st.session_state["valo_do_fetch"] = False
                if YF_AVAILABLE:
                    with st.spinner(f"📡 Récupération {ticker_input.upper()}..."):
                        try:
                            tk   = yf.Ticker(ticker_input.strip().upper())

                            # fast_info est plus robuste pour les tickers EU (.PA, .AS, etc.)
                            fi = tk.fast_info
                            price_raw = getattr(fi, "last_price", None) or getattr(fi, "regular_market_price", None) or 0
                            cur_raw   = getattr(fi, "currency", "USD") or "USD"
                            nb_sh_raw = getattr(fi, "shares", None) or 0

                            # Fallback sur info si fast_info incomplet
                            info = {}
                            try:
                                info = tk.info or {}
                            except: pass
                            if not price_raw:
                                price_raw = info.get("currentPrice") or info.get("regularMarketPrice") or 0
                            if not nb_sh_raw:
                                nb_sh_raw = info.get("sharesOutstanding", 0) or 0

                            price = float(price_raw) if price_raw else 0
                            cur   = cur_raw
                            nb_sh = float(nb_sh_raw) if nb_sh_raw else 0
                            name  = info.get("longName") or info.get("shortName") or ticker_input.upper()

                            if price == 0:
                                raise ValueError(f"Cours introuvable pour {ticker_input.upper()} — vérifie le ticker (ex: MC.PA, ADBE)")

                            # FX conversion
                            try:
                                fx = yf.Ticker("EURUSD=X").fast_info.last_price if cur=="USD" else 1.0
                                if not fx: fx = 1.16
                            except: fx = 1.16
                            price_eur = round(price/fx, 2)
                            currency_label = "€ (converti USD)" if cur=="USD" else cur
                            st.session_state["valo_fx"] = fx if cur=="USD" else 1.0

                            # ── Historical financials — 5 dernières années ──
                            hist_data = {}
                            try:
                                # income_stmt = jusqu'à 5 ans, financials = 4 ans max
                                # On prend le plus complet des deux
                                try:
                                    inc_5 = tk.income_stmt   # nouveau nom yfinance ≥ 0.2
                                except: inc_5 = None
                                try:
                                    inc_4 = tk.financials    # ancienne API, 4 ans
                                except: inc_4 = None
                                # Garde celui qui a le plus de colonnes
                                if inc_5 is not None and not inc_5.empty:
                                    if inc_4 is not None and not inc_4.empty:
                                        inc = inc_5 if len(inc_5.columns) >= len(inc_4.columns) else inc_4
                                    else:
                                        inc = inc_5
                                else:
                                    inc = inc_4

                                # Même logique pour le cashflow
                                try:
                                    cf_5 = tk.cash_flow      # nouveau nom yfinance ≥ 0.2
                                except: cf_5 = None
                                try:
                                    cf_4 = tk.cashflow       # ancienne API
                                except: cf_4 = None
                                if cf_5 is not None and not cf_5.empty:
                                    if cf_4 is not None and not cf_4.empty:
                                        cf = cf_5 if len(cf_5.columns) >= len(cf_4.columns) else cf_4
                                    else:
                                        cf = cf_5
                                else:
                                    cf = cf_4

                                def get_row(df, keys):
                                    if df is None or df.empty: return None
                                    for k in keys:
                                        if k in df.index: return df.loc[k]
                                    return None

                                rev_row = get_row(inc, ["Total Revenue","Revenue","TotalRevenue"])
                                ni_row  = get_row(inc, ["Net Income","NetIncome","Net Income Common Stockholders"])
                                eps_row = get_row(inc, ["Diluted EPS","Basic EPS","EPS","DilutedEPS"])
                                fcf_row = get_row(cf,  ["Free Cash Flow","FreeCashFlow"])

                                if rev_row is not None:
                                    # Prend jusqu'à 5 ans selon ce que Yahoo Finance fournit
                                    # inc.columns donne les vraies dates disponibles
                                    N = min(5, len(inc.columns), len(rev_row))

                                    def safe_float(row, i, scale=1e9):
                                        try:
                                            v = row.iloc[i]
                                            return float(v) / scale if v and str(v) not in ["None","nan","0"] else 0.0
                                        except: return 0.0

                                    # Colonnes = dates réelles des bilans → noms auto (2024, 2023...)
                                    # Affiche l'année fiscale (ex: juin 2025 → "2025")
                                    years_inc = [str(c.year) for c in inc.columns[:N]]

                                    rev_vals = [safe_float(rev_row, i) for i in range(N)]
                                    ni_vals  = [safe_float(ni_row,  i) if ni_row  is not None else 0.0 for i in range(N)]
                                    fcf_vals = [safe_float(fcf_row, i) if fcf_row is not None and i < len(fcf_row) else 0.0 for i in range(N)]
                                    eps_vals = [safe_float(eps_row, i, scale=1.0) if eps_row is not None and i < len(eps_row) else 0.0 for i in range(N)]

                                    margin_vals = [ni_vals[i]/rev_vals[i]*100 if rev_vals[i] != 0 else 0.0 for i in range(N)]
                                    fcf_margin  = [fcf_vals[i]/rev_vals[i]*100 if rev_vals[i] != 0 else 0.0 for i in range(N)]

                                    def cagr_5y(vals):
                                        """CAGR sur les données disponibles.
                                        vals[0] = année la plus récente, vals[-1] = la plus ancienne.
                                        CAGR = (recent/ancien)^(1/n_ans) - 1
                                        n_ans = nombre d'années entre le premier et le dernier point non nul.
                                        """
                                        v = [(i, x) for i, x in enumerate(vals) if x != 0]
                                        if len(v) < 2: return None
                                        idx_recent, val_recent = v[0]
                                        idx_ancien, val_ancien = v[-1]
                                        n_ans = idx_ancien - idx_recent  # ex: 0 à 4 = 4 ans
                                        if n_ans <= 0: return None
                                        try:
                                            return ((abs(val_recent) / abs(val_ancien)) ** (1 / n_ans) - 1) * 100
                                        except: return None

                                    hist_data = {
                                        "years":    years_inc,
                                        "n":        N,
                                        "revenue":  rev_vals,
                                        "ni":       ni_vals,
                                        "margin":   margin_vals,
                                        "eps":      eps_vals,
                                        "fcf":      fcf_vals,
                                        "fcf_m":    fcf_margin,
                                        "cagr_rev": cagr_5y(rev_vals),
                                        "cagr_ni":  cagr_5y(ni_vals),
                                        "cagr_eps": cagr_5y(eps_vals),
                                        "cagr_fcf": cagr_5y(fcf_vals),
                                        "nb_shares": nb_sh / 1e6,
                                    }
                            except Exception as fe:
                                hist_data = {}

                            st.session_state["valo_name_auto"]   = name
                            st.session_state["valo_cours_auto"]  = price_eur
                            st.session_state["valo_cours"]       = price_eur  # pre-fill the input field
                            st.session_state["valo_currency"]    = currency_label
                            st.session_state["valo_hist_data"]   = hist_data
                            st.session_state["valo_nb_auto"]     = round(nb_sh/1e6,1) if nb_sh else 0
                            st.session_state["valo_nb"]          = round(nb_sh/1e6,1) if nb_sh else 0
                            # Pre-fill hist metric with latest EPS or FCF
                            if hist_data.get("eps") and hist_data["eps"][0]!=0:
                                st.session_state["valo_hist"]    = abs(hist_data["eps"][0])
                            action_name = name; cours_auto = price_eur
                            st.success(f"✅ {name} — {price_eur:.2f} {currency_label}")
                        except Exception as e:
                            st.error(f"❌ {str(e) if str(e) else f"Ticker {ticker_input.upper()} introuvable — vérifie le format (ex: MC.PA, ADBE)"}")
                else:
                    st.warning("yfinance non disponible")

            # ── Display historical data table ──────────
            hist_data = st.session_state.get("valo_hist_data",{})
            if hist_data and hist_data.get("years"):
                yrs   = hist_data["years"]
                n     = len(yrs)
                GR    = C['green']; RE = C['red']; GO = C['gold']

                st.markdown(f"<div style='background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:12px;margin:8px 0'>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:10px;font-weight:700;color:{C_VAL};text-transform:uppercase;letter-spacing:.08em;margin-bottom:8px'>📊 Données historiques</div>", unsafe_allow_html=True)

                # Build table
                rows = {
                    "CA (Md)"          : hist_data["revenue"],
                    "Bénéfice net (Md)": hist_data["ni"],
                    "Marge nette (%)"  : hist_data["margin"],
                    "EPS ($)"          : hist_data["eps"],
                    "FCF (Md)"         : hist_data["fcf"],
                    "Marge FCF (%)"    : hist_data["fcf_m"],
                }
                cagrs = {
                    "CA (Md)"          : hist_data["cagr_rev"],
                    "Bénéfice net (Md)": hist_data["cagr_ni"],
                    "Marge nette (%)"  : None,
                    "EPS ($)"          : hist_data["cagr_eps"],
                    "FCF (Md)"         : hist_data["cagr_fcf"],
                    "Marge FCF (%)"    : None,
                }

                # Header
                hdr = "<div style='display:grid;grid-template-columns:110px " + " ".join(["1fr"]*n) + " 70px;gap:4px;font-size:9px;color:"+C['muted']+";border-bottom:1px solid "+C['border']+";padding-bottom:4px;margin-bottom:4px'>"
                hdr += "<span></span>"
                for yr in yrs: hdr += f"<span style='text-align:right'>{yr}</span>"
                n_cols = hist_data.get("n", 5)
                cagr_hdr_label = f"CAGR {n_cols}A" if n_cols == 5 else f"CAGR {n_cols}A*"
                hdr += f"<span style='text-align:right;color:{GO}'>{cagr_hdr_label}</span></div>"
                st.markdown(hdr, unsafe_allow_html=True)

                for metric, vals in rows.items():
                    is_pct = "%" in metric
                    cagr_v = cagrs.get(metric)
                    row_html = "<div style='display:grid;grid-template-columns:110px " + " ".join(["1fr"]*n) + " 70px;gap:4px;font-size:10px;padding:3px 0;border-bottom:1px solid #1C2333'>"
                    row_html += f"<span style='color:{C['muted']}'>{metric}</span>"
                    for i,val in enumerate(vals):
                        fmt_v = f"{val:.1f}%" if is_pct else f"{val:.2f}"
                        # Color trend: green if increasing (first = most recent)
                        if i < len(vals)-1 and vals[i+1] != 0:
                            clr = GR if vals[i] >= vals[i+1] else RE
                        else:
                            clr = C['text']
                        row_html += f"<span style='text-align:right;color:{clr};font-family:monospace'>{fmt_v}</span>"
                    n_yrs = hist_data.get("n", len(vals))
                    if cagr_v is not None:
                        cclr = GR if cagr_v >= 0 else RE
                        cagr_label = f"CAGR {n_yrs}A" if n_yrs == 5 else f"CAGR {n_yrs}A*"
                        row_html += f"<span style='text-align:right;color:{cclr};font-weight:700;font-family:monospace' title='{cagr_label}'>{cagr_v:+.1f}%</span>"
                    else:
                        moy = sum(vals)/len(vals) if vals else 0
                        row_html += f"<span style='text-align:right;color:{GO};font-family:monospace'>moy {moy:.1f}%</span>"
                    row_html += "</div>"
                    st.markdown(row_html, unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size:9px;color:{C["muted"]};margin-bottom:8px;font-style:italic'>⚠️ Données Yahoo Finance · Vérifier avant utilisation · Colonnes = années les plus récentes en premier</div>", unsafe_allow_html=True)
                st.selectbox("Ajouter dans :", ["📈 Actions en Portefeuille", "⚙️ Actions en Option", "👀 Actions à Surveiller"], key="valo_wl_target")
                add_wl = st.button("⭐ Ajouter à la Watchlist", use_container_width=True, key="valo_add")
            else:
                st.selectbox("Ajouter dans :", ["📈 Actions en Portefeuille", "⚙️ Actions en Option", "👀 Actions à Surveiller"], key="valo_wl_target_2")
                add_wl = st.button("⭐ Ajouter à la Watchlist", use_container_width=True, key="valo_add_no_hist")



        # Display auto-fetched or manual values
        if action_name:
            st.markdown(f"<div style='font-size:11px;color:{C_VAL};margin:4px 0'>📌 {action_name}</div>", unsafe_allow_html=True)

        # Cours auto-rempli depuis yfinance, éditable manuellement
        cours = st.number_input(
            "Cours actuel (€)",
            min_value=0.0,
            value=float(cours_auto) if cours_auto else 0.0,
            format="%.2f",
            key="valo_cours",
            help="Rempli automatiquement depuis Yahoo Finance — modifiable manuellement"
        )
        # PRU — stocké pour la watchlist
        pru = st.number_input("Mon PRU (€)", min_value=0.0, value=0.0, format="%.2f", key="valo_pru",
            help="Prix de Revient Unitaire — affiché dans la colonne PRU de la watchlist")
        
        if not action_name:
            action_name = ticker_input.upper() if ticker_input else ""

        nb_auto = st.session_state.get("valo_nb_auto", 0.0) or 0.0
        nb_input = st.number_input(
            "Nb actions (M)",
            min_value=0.0,
            value=float(nb_auto) if nb_auto else 0.0,
            format="%.1f",
            key="valo_nb",
            help="Rempli automatiquement depuis Yahoo Finance (sharesOutstanding)"
        )
        if nb_auto and nb_auto != st.session_state.get("valo_nb", 0):
            st.session_state["valo_nb"] = nb_auto

        st.markdown("---")

        # ── Dynamic labels per method ──────────────────
        if method == "EPS / PER":
            metric_label = "EPS annuel (€ ou $)"
            metric_help  = "Bénéfice net par action de la dernière année connue"
            growth_label = "Croissance CA (%)"
            growth_help  = "Taux de croissance annuel du chiffre d'affaires"
            margin_label = "Marge nette (%)"
            margin_help  = "Bénéfice net / CA — détermine le bénéfice projeté"
            mult_label   = "PER cible"
            mult_help    = "Price/Earnings cible selon le scénario"
            hist_label   = "EPS actuel (€/$)"
        elif method == "FCF / PER":
            metric_label = "FCF/action (€ ou $)"
            metric_help  = "Free Cash Flow par action de la dernière année connue"
            growth_label = "Croissance FCF (%)"
            growth_help  = "Taux de croissance annuel du Free Cash Flow"
            margin_label = "Marge FCF (%)"
            margin_help  = "FCF / CA — conversion du CA en cash réellement généré"
            mult_label   = "P/FCF cible"
            mult_help    = "Price/FCF cible — multiple appliqué au FCF projeté"
            hist_label   = "FCF/action actuel (€/$)"
        else:
            metric_label = "FCF total ($M)"
            hist_label   = "FCF total actuel ($M)"

        if method in ["EPS / PER", "FCF / PER"]:
            st.number_input(hist_label, min_value=0.0, value=0.0, format="%.2f",
                help=metric_help, key="valo_hist")

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

            # ── Entêtes colonnes ─────────────────────
            hcols = st.columns([1.1, 1, 1, 1])
            with hcols[0]:
                st.markdown(f"<div style='font-size:10px;color:{C_VAL};text-transform:uppercase;letter-spacing:.06em;padding:4px 0'>Paramètre</div>", unsafe_allow_html=True)
            for col, (scen, emoji, color) in zip(hcols[1:], [("BASE","📊","#7DD3FC"),("BEAR","🐻","#F85149"),("BULL","🐂","#3FB950")]):
                with col:
                    st.markdown(f"<div style='font-size:11px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:.08em;padding:4px 0;text-align:center'>{emoji} {scen}</div>", unsafe_allow_html=True)

            st.markdown(f"<div style='height:1px;background:{C['border']};margin:4px 0 8px'></div>", unsafe_allow_html=True)

            # ── Rachat d'actions (commun aux 3 scénarios) ──
            rac_cols = st.columns([1.1, 2.9])
            with rac_cols[0]:
                st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>Rachat actions/an (%)</div>", unsafe_allow_html=True)
            with rac_cols[1]:
                st.number_input("Rachat d'actions annuel (%)", value=-1.5, format="%.1f",
                    help="Taux de rachat annuel — réduit le nb d'actions et augmente l'EPS",
                    key="valo_rachat2", label_visibility="collapsed")
            st.markdown(f"<div style='height:1px;background:{C['border']}55;margin:4px 0 8px'></div>", unsafe_allow_html=True)

            # ── Ligne 1 : Croissance CA ──────────────
            r1 = st.columns([1.1, 1, 1, 1])
            with r1[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>{growth_label}</div>", unsafe_allow_html=True)
            with r1[1]: st.number_input(growth_label, value=9.0,  format="%.1f", help=growth_help, key="valo_g_BASE",  label_visibility="collapsed")
            with r1[2]: st.number_input(growth_label, value=5.0,  format="%.1f", help=growth_help, key="valo_g_BEAR",  label_visibility="collapsed")
            with r1[3]: st.number_input(growth_label, value=13.0, format="%.1f", help=growth_help, key="valo_g_BULL",  label_visibility="collapsed")

            # ── Ligne 2 : Marge nette ────────────────
            r2 = st.columns([1.1, 1, 1, 1])
            with r2[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>{margin_label}</div>", unsafe_allow_html=True)
            with r2[1]: st.number_input(margin_label, value=28.5, format="%.1f", help=margin_help, key="valo_m_BASE",  label_visibility="collapsed")
            with r2[2]: st.number_input(margin_label, value=24.0, format="%.1f", help=margin_help, key="valo_m_BEAR",  label_visibility="collapsed")
            with r2[3]: st.number_input(margin_label, value=32.0, format="%.1f", help=margin_help, key="valo_m_BULL",  label_visibility="collapsed")

            # ── Ligne 3 : PER cible ──────────────────
            r3 = st.columns([1.1, 1, 1, 1])
            with r3[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>{mult_label}</div>", unsafe_allow_html=True)
            with r3[1]: st.number_input(mult_label, value=25, help=mult_help, key="valo_per_BASE", label_visibility="collapsed")
            with r3[2]: st.number_input(mult_label, value=18, help=mult_help, key="valo_per_BEAR", label_visibility="collapsed")
            with r3[3]: st.number_input(mult_label, value=32, help=mult_help, key="valo_per_BULL", label_visibility="collapsed")

            st.markdown(f"<div style='height:1px;background:{C['border']}55;margin:6px 0'></div>", unsafe_allow_html=True)

            # ── Ligne 4 : Perf. annuelle ─────────────
            r4 = st.columns([1.1, 1, 1, 1])
            with r4[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>Perf. annuelle (%)</div>", unsafe_allow_html=True)
            with r4[1]: st.number_input("Perf. annuelle (%)", value=10.0, format="%.1f", help="Rendement annuel exigé", key="valo_perf_BASE", label_visibility="collapsed")
            with r4[2]: st.number_input("Perf. annuelle (%)", value=10.0, format="%.1f", help="Rendement annuel exigé", key="valo_perf_BEAR", label_visibility="collapsed")
            with r4[3]: st.number_input("Perf. annuelle (%)", value=10.0, format="%.1f", help="Rendement annuel exigé", key="valo_perf_BULL", label_visibility="collapsed")

            # ── Ligne 5 : Marge sécu ─────────────────
            r5 = st.columns([1.1, 1, 1, 1])
            with r5[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>Marge sécu. (%)</div>", unsafe_allow_html=True)
            with r5[1]: st.number_input("Marge sécu. (%)", value=10.0, format="%.1f", help="Décote sur prix à payer", key="valo_ms_BASE", label_visibility="collapsed")
            with r5[2]: st.number_input("Marge sécu. (%)", value=15.0, format="%.1f", help="Décote sur prix à payer", key="valo_ms_BEAR", label_visibility="collapsed")
            with r5[3]: st.number_input("Marge sécu. (%)", value=10.0, format="%.1f", help="Décote sur prix à payer", key="valo_ms_BULL", label_visibility="collapsed")

            # ── Ligne 6 : Nb années ──────────────────
            r6 = st.columns([1.1, 1, 1, 1])
            with r6[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>Nb années</div>", unsafe_allow_html=True)
            with r6[1]: st.number_input("Nb années", value=5, min_value=1, max_value=10, key="valo_ny_BASE", label_visibility="collapsed")
            with r6[2]: st.number_input("Nb années", value=5, min_value=1, max_value=10, key="valo_ny_BEAR", label_visibility="collapsed")
            with r6[3]: st.number_input("Nb années", value=5, min_value=1, max_value=10, key="valo_ny_BULL", label_visibility="collapsed")

        else:  # DCF
            st.number_input("FCF total actuel ($M)", min_value=0.0, value=0.0, format="%.0f",
                help="Free Cash Flow total de l'entreprise en millions", key="valo_fcf")
            c1,c2 = st.columns(2)
            with c1: st.number_input("Taux d'actualisation (%)", value=10.0, format="%.1f",
                help="Ton taux de rendement exigé (WACC ou rendement cible)", key="valo_dr")
            with c2: st.number_input("Croissance terminale (%)", value=3.0, format="%.1f",
                help="Croissance perpétuelle après la période de projection (≈ inflation)", key="valo_tg")

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            hcols = st.columns([1.1, 1, 1, 1])
            with hcols[0]:
                st.markdown(f"<div style='font-size:10px;color:{C_VAL};text-transform:uppercase;padding:4px 0'>Paramètre</div>", unsafe_allow_html=True)
            for col, (scen, emoji, color) in zip(hcols[1:], [("BASE","📊","#7DD3FC"),("BEAR","🐻","#F85149"),("BULL","🐂","#3FB950")]):
                with col:
                    st.markdown(f"<div style='font-size:11px;font-weight:700;color:{color};text-align:center;padding:4px 0'>{emoji} {scen}</div>", unsafe_allow_html=True)
            st.markdown(f"<div style='height:1px;background:{C['border']};margin:4px 0 8px'></div>", unsafe_allow_html=True)

            d1 = st.columns([1.1, 1, 1, 1])
            with d1[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>Croissance FCF (%)</div>", unsafe_allow_html=True)
            with d1[1]: st.number_input("Croissance FCF (%)", value=9.0,  format="%.1f", key="valo_gfcf_BASE", label_visibility="collapsed")
            with d1[2]: st.number_input("Croissance FCF (%)", value=4.0,  format="%.1f", key="valo_gfcf_BEAR", label_visibility="collapsed")
            with d1[3]: st.number_input("Croissance FCF (%)", value=14.0, format="%.1f", key="valo_gfcf_BULL", label_visibility="collapsed")

            d2 = st.columns([1.1, 1, 1, 1])
            with d2[0]: st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 0 0'>Marge sécu. (%)</div>", unsafe_allow_html=True)
            with d2[1]: st.number_input("Marge de sécurité (%)", value=10.0, format="%.1f", key="valo_ms_BASE", label_visibility="collapsed")
            with d2[2]: st.number_input("Marge de sécurité (%)", value=15.0, format="%.1f", key="valo_ms_BEAR", label_visibility="collapsed")
            with d2[3]: st.number_input("Marge de sécurité (%)", value=10.0, format="%.1f", key="valo_ms_BULL", label_visibility="collapsed")

        st.markdown("---")
        calc = True  # calcul permanent, plus besoin de bouton

    # ── RESULTS ──────────────────────────────────────
    with col_res:
        sec("Résultats", "🎯", C_VAL, C_VAL_DIM)

        # ── 4 KPI synthèse en haut ────────────────────
        r_base_kpi = st.session_state.get("valo_results_base", None)
        cours_kpi  = st.session_state.get("valo_cours", 0)
        hist_eps_kpi = st.session_state.get("valo_hist", 0)
        conv_kpi   = st.session_state.get("valo_conviction", 0)

        # Upside BASE vs cours
        pp_base_kpi = r_base_kpi.get("price_pay", 0) if r_base_kpi else 0
        vi_base_kpi = r_base_kpi.get("price", 0) if r_base_kpi else 0
        upside_kpi  = (pp_base_kpi - cours_kpi) / cours_kpi * 100 if cours_kpi > 0 and pp_base_kpi > 0 else None
        marge_eff   = (pp_base_kpi - cours_kpi) / cours_kpi * 100 if cours_kpi > 0 and pp_base_kpi > 0 else None

        kpi_r = st.columns(4)
        kpi_valo = [
            ("PRIX À PAYER BASE",
             f"{pp_base_kpi:,.0f} €" if pp_base_kpi else "—",
             "avec marge de sécurité",
             C["green"] if upside_kpi and upside_kpi > 0 else C["red"] if upside_kpi else C_VAL, "💰"),
            ("UPSIDE BASE",
             f"{upside_kpi:+.1f}%" if upside_kpi is not None else "—",
             "vs cours actuel",
             C["green"] if upside_kpi and upside_kpi > 0 else C["red"] if upside_kpi is not None else C["muted"], "📈"),
            ("VALEUR INTRINSÈQUE",
             f"{vi_base_kpi:,.0f} €" if vi_base_kpi else "—",
             "scénario BASE",
             "#7DD3FC", "🔍"),
            ("EPS ACTUEL",
             f"{hist_eps_kpi:.2f}" if hist_eps_kpi else "—",
             "€/$ par action",
             C["gold"], "📊"),
        ]
        for col, (ti, va, su, co, ic) in zip(kpi_r, kpi_valo):
            with col: st.markdown(card(ti, va, su, co, ic), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        # ── Calculation engine ────────────────────────
        results = {}

        def calc_eps_per(g_pct, m_pct, per, hist_eps, nb_act, rachat_pct, n_years=5):
            """Project EPS/FCF over n years and compute price."""
            if hist_eps <= 0 or nb_act <= 0: return None
            rev = hist_eps  # base metric
            for i in range(n_years):
                rev = rev * (1 + g_pct/100)
            nb_est = nb_act * (1 + rachat_pct/100)**n_years
            eps_final = rev  # already per-share if hist is per-share
            price = eps_final * per
            return price

        def calc_dcf(fcf_m, g_pct, dr_pct, tg_pct, ms_pct, nb_act, n_years=5):
            """Simple DCF: PV of FCF + terminal value."""
            if fcf_m <= 0 or nb_act <= 0: return None
            dr = dr_pct / 100
            tg = tg_pct / 100
            pv = 0
            fcf = fcf_m
            for i in range(1, n_years+1):
                fcf = fcf * (1 + g_pct/100)
                pv += fcf / (1+dr)**i
            # Terminal value (Gordon Growth)
            tv = fcf * (1+tg) / (dr - tg) if dr > tg else 0
            pv_tv = tv / (1+dr)**n_years
            equity_val = (pv + pv_tv) * 1e6  # back to full €
            price_per_share = equity_val / (nb_act * 1e6) if nb_act > 0 else 0
            return price_per_share

        # n_years is now per-scenario, fetched inside loop
        rachat  = st.session_state.get("valo_rachat2", -1.5)
        nb_act  = st.session_state.get("valo_nb_auto", 0) or st.session_state.get("valo_nb", 0)
        hist_d  = st.session_state.get("valo_hist_data", {})
        cours_v = st.session_state.get("valo_cours", 0)

        if method in ["EPS / PER", "FCF / PER"]:
            hist_eps = st.session_state.get("valo_hist", 0)
            # Get last revenue from hist_data if available
            rev_last = hist_d.get("revenue", [0])[0] * 1e9 if hist_d.get("revenue") else 0
            for scen in ["BASE","BEAR","BULL"]:
                g    = st.session_state.get(f"valo_g_{scen}", 0)
                m    = st.session_state.get(f"valo_m_{scen}", 0)
                per  = st.session_state.get(f"valo_per_{scen}", 0)
                perf    = st.session_state.get(f"valo_perf_{scen}", 10.0)
                ms      = st.session_state.get(f"valo_ms_{scen}", 10.0)
                n_years = int(st.session_state.get(f"valo_ny_{scen}", 5))

                if hist_eps <= 0 and rev_last <= 0:
                    results[scen] = None; continue

                if rev_last > 0 and nb_act > 0 and m > 0:
                    # ── Proper chain: Revenue → BN → EPS ──
                    rev = rev_last
                    for _ in range(n_years):
                        rev = rev * (1 + g/100)
                    bn = rev * m/100
                    nb_est = (nb_act * 1e6) * (1 + rachat/100)**n_years
                    eps_final = bn / nb_est if nb_est > 0 else 0
                elif hist_eps > 0:
                    # Fallback: project EPS directly with CA growth (no revenue data)
                    # Note: margin% not applicable when projecting EPS directly
                    eps_final = hist_eps * (1 + g/100)**n_years
                    st.session_state[f"valo_warn_{scen}"] = "⚠️ Données revenue non dispo — EPS projeté directement (marge non appliquée)"
                else:
                    results[scen] = None; continue

                # ── Formules alignées Google Sheet ──
                # Valeur intrinsèque = EPS_final × PER
                valeur_intrinseque = eps_final * per
                # Prix avec perf = VI / (1+perf%)^n  → prix à payer aujourd'hui pour avoir VI dans n ans
                prix_avec_perf = valeur_intrinseque / (1 + perf/100)**n_years if perf > 0 else valeur_intrinseque
                # Prix à payer = prix_avec_perf × (1 - marge_secu%)
                prix_a_payer = prix_avec_perf * (1 - ms/100)
                results[scen] = {
                    "price":       valeur_intrinseque,   # valeur intrinsèque dans n ans
                    "price_pay":   prix_a_payer,          # prix max à payer aujourd'hui
                    "price_perf":  prix_avec_perf,         # prix avec perf (avant marge sécu)
                    "eps_final":   eps_final,
                    "per":         per,
                    "n_years":     n_years,
                }
        else:
            fcf = st.session_state.get("valo_fcf", 0)
            dr  = st.session_state.get("valo_dr", 10)
            tg  = st.session_state.get("valo_tg", 3)
            nb  = st.session_state.get("valo_nb", 0)
            for scen in ["BASE","BEAR","BULL"]:
                g  = st.session_state.get(f"valo_gfcf_{scen}", 0)
                ms = st.session_state.get(f"valo_ms_{scen}", 10)
                if fcf > 0 and nb > 0:
                    price = calc_dcf(fcf, g, dr, tg, ms, nb)
                    price_pay = price * (1 - ms/100) if price else None
                    results[scen] = {"price": price, "price_pay": price_pay}
                else:
                    results[scen] = None

        cours_v = st.session_state.get("valo_cours", 0)

        # Store BASE result for top KPI cards
        if results.get("BASE") and results["BASE"].get("price"):
            st.session_state["valo_results_base"] = results["BASE"]

        # ── 3 scenario cards ──────────────────────────
        s_cols = st.columns(3)
        scen_styles = {
            "BASE": ("#0A1A2E","#7DD3FC","📊 Base"),
            "BEAR": ("#1C0A0A","#F85149","🐻 Bear"),
            "BULL": ("#0A1C0A","#3FB950","🐂 Bull"),
        }
        conv_score = 0
        for col, scen in zip(s_cols, ["BASE","BEAR","BULL"]):
            bg, color, label = scen_styles[scen]
            r = results.get(scen)
            with col:
                if r and r.get("price"):
                    p   = r["price"]; pp = r["price_pay"]
                    pperf = r.get("price_perf", pp)
                    eps_f = r.get("eps_final", 0)
                    ny    = r.get("n_years", 5)
                    upside_pay = (pp/cours_v - 1)*100 if cours_v > 0 else 0
                    upside_val = (p/cours_v  - 1)*100 if cours_v > 0 else 0
                    up_color = C['green'] if upside_pay >= 0 else C['red']
                    up_arrow = "▲" if upside_pay >= 0 else "▼"
                    r["upside_pay"] = upside_pay
                    r["upside_val"] = upside_val
                    per_v = r.get("per",0)
                    # Show $ price too if USD stock
                    cur_label = st.session_state.get("valo_currency","€")
                    fx_rate   = st.session_state.get("valo_fx", 1.0)
                    is_usd    = "USD" in cur_label
                    pp_usd    = pp * fx_rate if is_usd and fx_rate>1 else None
                    pperf_usd = pperf * fx_rate if is_usd and fx_rate>1 else None
                    p_usd     = p * fx_rate if is_usd and fx_rate>1 else None
                    
                    usd_line = f"<div style='font-size:9px;color:{color};font-family:monospace;margin-bottom:3px'>≈ <b>${pp_usd:,.0f}</b> · {pperf_usd:,.0f} $ avec perf · {p_usd:,.0f} $ intrinsèque</div>" if pp_usd else ""
                    ms_v   = st.session_state.get(f"valo_ms_{scen}", 10.0)
                    perf_v = st.session_state.get(f"valo_perf_{scen}", 10.0)
                    formula_line = f"<div style='font-size:8px;color:{C["muted"]};font-family:monospace;margin-top:4px;padding-top:4px;border-top:1px solid {C["border"]}'>VI={p:,.0f}€ ÷ (1+{perf_v:.0f}%)^{ny} × (1−{ms_v:.0f}%) = {pp:,.0f}€</div>"

                    st.markdown(f"""<div style="background:{bg};border:1px solid {color}44;border-radius:10px;padding:16px;margin-bottom:4px">
<div style="font-size:11px;font-weight:700;color:{color};text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">{label}</div>
<div style="font-size:11px;color:{C['muted']};margin-bottom:2px">💰 Prix à payer (avec marge sécu)</div>
<div style="font-family:'Space Grotesk';font-size:28px;font-weight:700;color:{color};margin-bottom:3px">{pp:,.0f} €</div>
{usd_line}
<div style="font-size:12px;color:{C['muted']};margin-bottom:2px">Prix avec perf {r.get('n_years',5)}ans : <span style="color:{C['text']};font-weight:600">{pperf:,.0f} €</span></div>
<div style="font-size:12px;color:{C['muted']};margin-bottom:2px">Valeur intrinsèque : <span style="color:{C['text']};font-weight:600">{p:,.0f} €</span></div>
<div style="font-size:11px;color:{C['muted']}">EPS {2025+ny} : <span style="color:{color};font-weight:600">{eps_f:.2f}</span> · PER : <span style="color:{color};font-weight:600">{per_v}x</span></div>
{formula_line}
<div style="font-size:14px;font-weight:700;color:{up_color};margin-top:8px">{up_arrow} {upside_pay:+.1f}% vs cours</div>
</div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""<div style="background:{bg};border:1px solid {C['border']};border-radius:8px;padding:14px;margin-bottom:4px;opacity:.5">
<div style="font-size:10px;font-weight:700;color:{color};margin-bottom:6px">{label}</div>
<div style="font-size:18px;color:{C['muted']}">— €</div>
<div style="font-size:11px;color:{C['muted']}">Saisir les données</div>
</div>""", unsafe_allow_html=True)

        # ── Tableau projections EPS ───────────────────
        if any(r for r in results.values() if r and r.get("price")):
            from datetime import datetime as _dt2
            current_year = _dt2.now().year
            proj_years   = [str(current_year + i) for i in range(1, 7)]

            sec("Tableau des projections EPS (€)", "📋", C_VAL, C_VAL_DIM)

            scen_cfg = {
                "BASE": ("🏠", "#7DD3FC"),
                "BEAR": ("🐻", "#F85149"),
                "BULL": ("🐂", "#3FB950"),
            }

            # Build per-scenario EPS projections
            proj_rows = []
            for scen, (icon, color) in scen_cfg.items():
                r = results.get(scen)
                if not r or not r.get("price"): continue
                g        = st.session_state.get(f"valo_g_{scen}", 9)
                m        = st.session_state.get(f"valo_m_{scen}", 0)
                hist_eps_v = st.session_state.get("valo_hist", 0)
                rev_last_v = hist_d.get("revenue", [0])[0] * 1e9 if hist_d.get("revenue") else 0
                nb_act_v   = st.session_state.get("valo_nb_auto", 0) or st.session_state.get("valo_nb", 0)
                rachat_v   = st.session_state.get("valo_rachat2", -1.5)
                # Convert to EUR if needed
                try:
                    fx_t = st.session_state.get("valo_fx", 1.0)
                except: fx_t = 1.0

                eps_proj = []
                for yr in range(1, 7):
                    if rev_last_v > 0 and nb_act_v > 0 and m > 0:
                        rev_y = rev_last_v * (1 + g/100)**yr
                        bn_y  = rev_y * m/100
                        nb_y  = (nb_act_v * 1e6) * (1 + rachat_v/100)**yr
                        eps_y = bn_y / nb_y if nb_y > 0 else 0
                    else:
                        eps_y = hist_eps_v * (1 + g/100)**yr
                    eps_proj.append(eps_y / fx_t if fx_t > 1 else eps_y)

                # CAGR EPS sur les 5 ans projetés
                eps_start = eps_proj[0] if eps_proj[0] != 0 else None
                eps_end   = eps_proj[-1] if eps_proj[-1] != 0 else None
                cagr_eps  = ((eps_end / eps_start) ** (1/5) - 1) * 100 if eps_start and eps_end and eps_start > 0 else None

                proj_rows.append((scen, icon, color, eps_proj, cagr_eps))

            if proj_rows:
                # Header
                tbl_p  = f"""<div style="overflow-x:auto;margin-bottom:8px">
<table style="width:100%;border-collapse:collapse;font-size:12px;font-family:'DM Sans'">
<thead>
<tr style="background:#1C2333;color:{C['muted']};font-size:10px;text-transform:uppercase;letter-spacing:.06em">
  <th style="padding:8px 12px;text-align:left;border-bottom:1px solid {C['border']}">Scénario</th>"""
                for yr_lbl in proj_years:
                    tbl_p += f"<th style='padding:8px 12px;text-align:right;border-bottom:1px solid {C['border']}'>{yr_lbl}</th>"
                tbl_p += f"<th style='padding:8px 12px;text-align:right;border-bottom:1px solid {C['border']}'>CAGR</th>"
                tbl_p += "</tr></thead><tbody>"

                for scen, icon, color, eps_proj, cagr_eps in proj_rows:
                    tbl_p += f"<tr style='border-bottom:1px solid {C['border']}22'>"
                    tbl_p += f"<td style='padding:7px 12px;font-weight:700;color:{color}'>{icon} {scen.capitalize()}</td>"
                    fx_rate  = st.session_state.get("valo_fx", 1.0)
                    is_usd   = fx_rate > 1.0
                    for i, eps_v in enumerate(eps_proj):
                        fw = "700" if i == len(eps_proj)-1 else "400"
                        # eps_v is already in €; eps_usd = original USD value
                        eps_usd = eps_v * fx_rate if is_usd else None
                        sub = f"<div style='font-size:9px;color:{C["muted"]};font-family:monospace;margin-top:1px'>${eps_usd:.1f}</div>" if is_usd else ""
                        tbl_p += f"<td style='padding:6px 12px;text-align:right;color:{color};font-weight:{fw}'>{eps_v:.1f}€{sub}</td>"
                    # CAGR cell
                    if cagr_eps is not None:
                        cagr_col = C['green'] if cagr_eps >= 0 else C['red']
                        tbl_p += f"<td style='padding:7px 12px;text-align:right;color:{cagr_col};font-weight:700;font-family:monospace'>{cagr_eps:+.1f}%</td>"
                    else:
                        tbl_p += f"<td style='padding:7px 12px;text-align:right;color:{C['muted']}'>—</td>"
                    tbl_p += "</tr>"

                tbl_p += "</tbody></table></div>"
                st.markdown(tbl_p, unsafe_allow_html=True)

        # ── Conviction score ──────────────────────────
        if any(r for r in results.values() if r and r.get("price")):
            # ── Weighted conviction score ──────────────
            # Criteria:
            # 40% → Upside BASE prix à payer vs cours (key entry point)
            # 20% → Upside BULL prix à payer (potential upside)
            # 25% → Marge de sécurité disponible (BASE: cours < prix à payer)
            # 15% → BEAR positif (downside protection)
            def norm(val, low, high):
                """Normalize val between low and high → 0 to 1"""
                return max(0, min(1, (val - low) / (high - low))) if high != low else 0

            r_base = results.get("BASE"); r_bear = results.get("BEAR"); r_bull = results.get("BULL")
            up_base = r_base.get("upside_pay",0) if r_base else 0
            up_bull = r_bull.get("upside_pay",0) if r_bull else 0
            up_bear = r_bear.get("upside_pay",0) if r_bear else 0
            # Marge sécu = how much below prix à payer the cours is (positive = good)
            marge_secu = -up_base  # if cours below prix à payer, upside_pay is negative

            s1 = norm(up_base,  -30, 40) * 40   # 40% weight
            s2 = norm(up_bull,  -20, 60) * 20   # 20% weight
            s3 = norm(marge_secu, -10, 30) * 25 # 25% weight
            s4 = norm(up_bear,  -50, 10) * 15   # 15% weight
            score = int(s1 + s2 + s3 + s4)

            score_color = C['green'] if score >= 65 else (C['gold'] if score >= 40 else C['red'])
            score_text = "💪 Conviction FORTE — Bon point d'entrée" if score >= 65 else ("🤔 Conviction MODÉRÉE — Attendre repli" if score >= 40 else "⚠️ Prudence — Cours trop élevé")
            # Detail breakdown
            score_detail = f"BASE: {up_base:+.1f}% · BULL: {up_bull:+.1f}% · BEAR: {up_bear:+.1f}%"
            st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:12px 16px;display:flex;align-items:center;gap:16px;margin-top:8px">
<div style="font-family:'Space Grotesk';font-size:28px;font-weight:700;color:{score_color}">{score}<span style="font-size:14px;color:{C['muted']}">/100</span></div>
<div style="flex:1">
<div style="font-size:10px;color:{C['muted']};margin-bottom:4px">Score pondéré · BASE 40% · BULL 20% · Marge sécu 25% · BEAR 15%</div>
<div style="height:5px;background:{C['border']};border-radius:3px;margin-bottom:5px">
<div style="height:100%;width:{score}%;background:linear-gradient(90deg,#F85149,#F0883E,#D29922,#3FB950);border-radius:3px"></div>
</div>
<div style="font-size:12px;font-weight:600;color:{score_color};margin-bottom:3px">{score_text}</div>
<div style="font-size:10px;color:{C['muted']}">{score_detail}</div>
</div>
</div>""", unsafe_allow_html=True)

        # Add to watchlist logic
        if add_wl and action_name and cours_v > 0:
            r_base = results.get("BASE")
            upside = (r_base["price"]/cours_v - 1)*100 if r_base and r_base.get("price") else 0
            statut = "buy" if upside > 10 else ("avoid" if upside < -5 else "wait")
            pru_v  = st.session_state.get("valo_pru", 0)

            # Résolution de la liste cible depuis le selectbox
            target_label = st.session_state.get("valo_wl_target") or st.session_state.get("valo_wl_target_2") or "👀 Actions à Surveiller"
            if "Portefeuille" in target_label:
                target_key, target_icon = "wl_portefeuille", "📈"
            elif "Option" in target_label:
                target_key, target_icon = "wl_options", "⚙️"
            else:
                target_key, target_icon = "wl_surveillance", "👀"

            entry = {
                "name":    action_name,
                "ticker":  ticker_input.strip().upper() if ticker_input else "",
                "cours":   cours_v,
                "pru":     pru_v,
                "cible":   r_base["price"] if r_base else 0,
                "a_payer": r_base["price_pay"] if r_base else 0,
                "upside":  upside,
                "statut":  statut,
                "method":  method,
                "liste":   target_key,
            }
            # Remove from all lists if already present, then add to target
            for k in ["wl_portefeuille", "wl_options", "wl_surveillance"]:
                st.session_state[k] = [w for w in st.session_state.get(k, []) if w["name"] != action_name]
            st.session_state[target_key].append(entry)
            # Keep flat watchlist in sync (used by KPI hint)
            st.session_state.watchlist = (st.session_state.wl_portefeuille +
                                           st.session_state.wl_options +
                                           st.session_state.wl_surveillance)
            st.success(f"✅ {action_name} ajouté dans {target_icon} {target_label.split(' ', 1)[1]} !")

    # ── Hint to go to Watchlist tab ───────────────────
    if st.session_state.watchlist:
        nb_wl = len(st.session_state.watchlist)
        st.markdown(f"""<div style="background:#1C2333;border:1px solid {C_VAL}44;border-radius:8px;padding:12px 16px;margin-top:8px;display:flex;align-items:center;gap:10px">
<span style="font-size:18px">⭐</span>
<span style="color:{C_VAL};font-weight:600">{nb_wl} action(s) dans ta watchlist</span>
<span style="color:{C['muted']};font-size:12px">— consulte l'onglet <b style='color:{C_VAL}'>⭐ Watchlist</b> pour voir le tableau complet</span>
</div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# TAB 7 — WATCHLIST
# ════════════════════════════════════════════════════════════
with tab7:
    C_WL     = "#A78BFA"
    C_WL_DIM = "#1E1530"

    # ── Session state guards ──────────────────────────
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = []
    # Migrate old flat watchlist → new structure on first load
    if st.session_state.watchlist and "liste" not in (st.session_state.watchlist[0] if st.session_state.watchlist else {}):
        for w in st.session_state.watchlist:
            w.setdefault("liste", "surveillance")
    if "wl_portefeuille" not in st.session_state:
        st.session_state.wl_portefeuille = []
    if "wl_options" not in st.session_state:
        st.session_state.wl_options = []
    if "wl_surveillance" not in st.session_state:
        st.session_state.wl_surveillance = []
    if "wl_sort_asc" not in st.session_state:
        st.session_state.wl_sort_asc = False

    wl = st.session_state.watchlist

    # ── Shared helpers (also used by tab6) ───────────
    def ecart_ifs(w):
        cours_w   = w.get("cours", 0)
        a_payer_w = w.get("a_payer", 0)
        if cours_w <= 0 or a_payer_w <= 0: return 0, "wait"
        e = (a_payer_w - cours_w) / cours_w * 100
        if e > 0:         return e, "achat_ideal"
        elif e >= -10.01: return e, "achat_sans_marge"
        elif e >= -13:    return e, "proche"
        elif e >= -20:    return e, "wait"
        else:             return e, "surcote"

    def get_statut_info(w):
        cours_w   = w.get("cours", 0)
        a_payer_w = w.get("a_payer", 0)
        if cours_w <= 0 or a_payer_w <= 0:
            return "wait", C["gold"], "😴 ATTENDRE", C["gold"]
        ecart = (a_payer_w - cours_w) / cours_w * 100
        if ecart > 0:
            return "buy",   C["green"], "💎 ACHAT IDÉAL 💎",      C["green"]
        elif ecart >= -10.01:
            return "buy",   "#F0883E",  "🔥 ACHAT SANS MARGE 🔥",  "#F0883E"
        elif ecart >= -13:
            return "watch", "#60A5FA",  "👀 PROCHE 👀",             "#60A5FA"
        elif ecart >= -20:
            return "wait",  C["gold"],  "😴 ATTENDRE 😴",           C["gold"]
        else:
            return "avoid", C["red"],   "🚫 SURCOTE 🚫",            C["red"]

    wl = (st.session_state.get("wl_portefeuille", []) +
          st.session_state.get("wl_options", []) +
          st.session_state.get("wl_surveillance", []))

    if not wl:
        st.markdown(f'''<div style="background:{C["card"]};border:1px solid {C_WL}44;border-radius:12px;padding:40px;text-align:center;color:{C["muted"]};margin-top:16px">
<div style="font-size:32px;margin-bottom:12px">⭐</div>
<div style="font-size:16px;font-weight:600;color:{C_WL};margin-bottom:8px">Ta watchlist est vide</div>
<div style="font-size:13px">Calcule une valorisation dans l'onglet <b>🔍 Valorisation</b>, choisis une liste et clique sur <b>⭐ Watchlist</b></div>
</div>''', unsafe_allow_html=True)
    else:
        # ── KPI row ──────────────────────────────────
        nb_total      = len(wl)
        nb_ideal      = sum(1 for w in wl if ecart_ifs(w)[1] == "achat_ideal")
        nb_sans_marge = sum(1 for w in wl if ecart_ifs(w)[1] == "achat_sans_marge")
        nb_proche     = sum(1 for w in wl if ecart_ifs(w)[1] == "proche")
        nb_surcote    = sum(1 for w in wl if ecart_ifs(w)[1] == "surcote")
        nb_wait_real  = sum(1 for w in wl if ecart_ifs(w)[1] == "wait")
        avg_ecart_all = sum(ecart_ifs(w)[0] for w in wl) / len(wl) if wl else 0

        kc = st.columns(6)
        kpi_data = [
            ("💎 ACHAT IDÉAL",  str(nb_ideal)      if nb_total else "—", f"{nb_ideal} action(s)",      C["green"],  "💎"),
            ("🔥 SANS MARGE",   str(nb_sans_marge) if nb_total else "—", f"{nb_sans_marge} action(s)", "#F0883E",   "🔥"),
            ("👀 PROCHE",       str(nb_proche)     if nb_total else "—", f"{nb_proche} action(s)",     "#60A5FA",   "👀"),
            ("😴 ATTENDRE",     str(nb_wait_real)  if nb_total else "—", f"{nb_wait_real} action(s)",  C["gold"],   "😴"),
            ("🚫 SURCOTE",      str(nb_surcote)    if nb_total else "—", f"{nb_surcote} action(s)",    C["red"],    "🚫"),
            ("📊 ÉCART MOYEN",  f"{avg_ecart_all:+.1f}%" if wl else "—", f"{nb_total} analysées",
             C["green"] if avg_ecart_all >= 0 else C["red"], "📊"),
        ]
        for col, (ti, va, su, co, ic) in zip(kc, kpi_data):
            with col: st.markdown(card(ti, va, su, co, ic), unsafe_allow_html=True)

        # ── Info cours + bouton tri ───────────────────
        last_refresh = st.session_state.get("watchlist_last_refresh", "—")
        upd_count    = st.session_state.get("watchlist_updated_count", 0)
        asc_now      = st.session_state.get("wl_sort_asc", False)
        txt_refresh  = f"🕐 {last_refresh}" + (f" · {upd_count} ticker(s) MAJ" if last_refresh != "—" else "")

        # Info à gauche, bouton tri juste après
        st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:2px 0 2px'>{txt_refresh}</div>", unsafe_allow_html=True)
        _bc = st.columns([1, 5])
        with _bc[0]:
            if st.button("Écart ↑" if asc_now else "Écart ↓", key="wl_sort_btn", use_container_width=True):
                st.session_state.wl_sort_asc = not asc_now
                st.rerun()

        def get_ecart(w):
            c = w.get("cours", 0); p = w.get("a_payer", 0)
            return (p - c) / c * 100 if c > 0 and p > 0 else -999

        asc = st.session_state.get("wl_sort_asc", False)

        # ── 3 sous-tableaux distincts ─────────────────
        SUB_LISTS = [
            ("wl_portefeuille", "📈 Actions en Portefeuille", "#3FB950"),
            ("wl_options",      "⚙️ Actions en Option",       "#F0883E"),
            ("wl_surveillance", "👀 Actions à Surveiller",    "#60A5FA"),
        ]

        # Largeurs fixes identiques pour tous les tableaux
        _ths = "font-size:10px;color:{m};text-transform:uppercase;letter-spacing:.06em;border-bottom:1px solid {b};padding:8px 12px;white-space:nowrap".format(m=C["muted"], b=C["border"])
        THL = lambda col, w: f"<th style='text-align:left;width:{w};{_ths}'>{col}</th>"
        TH  = lambda col, w: f"<th style='text-align:right;width:{w};{_ths}'>{col}</th>"
        THC = lambda col, w: f"<th style='text-align:center;width:{w};{_ths}'>{col}</th>"

        for list_key, list_label, list_color in SUB_LISTS:
            entries = st.session_state.get(list_key, [])
            sec(f"{list_label}  ({len(entries)})", "⭐", list_color, "#0A0E1A")

            if not entries:
                st.markdown(f"<div style='font-size:11px;color:{C["muted"]};padding:8px 12px;margin-bottom:16px;font-style:italic'>Aucune action dans cette liste</div>", unsafe_allow_html=True)
                continue

            sorted_e = sorted(entries, key=get_ecart, reverse=not asc)
            tbl  = f"<div style='overflow-x:auto;margin-bottom:20px'>"
            tbl += f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;font-size:12px;font-family:DM Sans'>"
            tbl += f"<thead><tr style='background:#1C2333'>"
            tbl += (THL("Action",          "28%") +
                    THC("Ticker",           "8%") +
                    TH ("PRU",              "9%") +
                    TH ("Prix Actuel",     "11%") +
                    TH ("Prix d'Achat avec Marge", "16%") +
                    TH ("Écart (%) ▼▲",   "13%") +
                    THC("Verdict",         "15%"))
            tbl += "</tr></thead><tbody>"

            for w in sorted_e:
                _, _, verdict_txt, verdict_col = get_statut_info(w)
                cours_w   = w.get("cours", 0)
                pru_w     = w.get("pru", 0)
                a_payer_w = w.get("a_payer", 0)
                ticker_w  = w.get("ticker", "")
                ecart_w   = (a_payer_w - cours_w) / cours_w * 100 if cours_w > 0 else 0

                if ecart_w > 0:        ecart_col="#3FB950"; ecart_bg="#0D2A0D"
                elif ecart_w>=-10.01:  ecart_col="#F0883E"; ecart_bg="#2A1800"
                elif ecart_w>=-13:     ecart_col="#60A5FA"; ecart_bg="#0D1A2A"
                elif ecart_w>=-20:     ecart_col=C["gold"]; ecart_bg="#2A2000"
                else:                  ecart_col=C["red"];  ecart_bg="#2A0D0D"
                cours_bg = "#0D2A0D" if pru_w>0 and cours_w<=pru_w else ("#2A0D0D" if pru_w>0 and cours_w>pru_w else "transparent")

                tbl += f"<tr style='border-bottom:1px solid {C["border"]}22'>"
                tbl += f"<td style='padding:7px 12px;font-weight:600;color:{C["text"]}'>{w['name']}</td>"
                tbl += f"<td style='padding:7px 12px;text-align:center;font-family:monospace;font-size:10px;color:{list_color}'>{ticker_w or '—'}</td>"
                tbl += f"<td style='padding:7px 12px;text-align:right;color:{C["muted"]}'>{f'{pru_w:,.2f} €' if pru_w else '—'}</td>"
                tbl += f"<td style='padding:7px 12px;text-align:right;font-weight:700;color:{C["text"]};background:{cours_bg};border-radius:4px'>{cours_w:,.2f} €</td>"
                tbl += f"<td style='padding:7px 12px;text-align:right;color:{C["cyan"]};font-weight:700'>{a_payer_w:,.0f} €</td>"
                tbl += f"<td style='padding:7px 12px;text-align:right;background:{ecart_bg};color:{ecart_col};font-weight:700;border-radius:4px'>{ecart_w:+.2f}%</td>"
                tbl += f"<td style='padding:7px 12px;text-align:center;color:{verdict_col};font-weight:700;white-space:nowrap'>{verdict_txt}</td>"
                tbl += "</tr>"

            tbl += "</tbody></table></div>"
            st.markdown(tbl, unsafe_allow_html=True)

                # ── Delete controls ───────────────────────────
        st.markdown(f"<div style='font-size:10px;color:{C['muted']};margin-top:4px;margin-bottom:4px'>Supprimer une action :</div>", unsafe_allow_html=True)
        all_names = [w["name"] for w in wl]
        del_cols  = st.columns([3, 1])
        with del_cols[0]:
            to_delete = st.selectbox("", all_names, label_visibility="collapsed", key="valo_del_sel")
        with del_cols[1]:
            if st.button("🗑️ Supprimer", key="valo_del_btn", use_container_width=True):
                for k in ["wl_portefeuille", "wl_options", "wl_surveillance"]:
                    st.session_state[k] = [w for w in st.session_state.get(k, []) if w["name"] != to_delete]
                st.rerun()
        if st.button("🗑️ Vider toutes les listes", key="valo_clear"):
            for k in ["wl_portefeuille", "wl_options", "wl_surveillance"]:
                st.session_state[k] = []
            st.session_state.watchlist = []
            st.rerun()
