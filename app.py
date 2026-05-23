import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from io import StringIO
import re
import urllib.parse

st.set_page_config(page_title="WealthTrack", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

SHEET_ID = "1ADzYAtCeFpP01eoFOdb2iiwSX3eU9rcbQbS6wQf6sgI"
C = {"bg":"#0D1117","card":"#161B27","border":"#21262D","text":"#E6EDF3","muted":"#8B949E",
     "green":"#3FB950","red":"#F85149","gold":"#D29922","blue":"#1F6FEB",
     "purple":"#8B5CF6","teal":"#10B981","cyan":"#58A6FF"}

st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&family=DM+Sans:wght@400;500&display=swap');
html,body,[class*="css"]{{background:{C['bg']}!important;color:{C['text']}!important;font-family:'DM Sans',sans-serif}}
.stApp{{background:{C['bg']}}} .main .block-container{{padding:1.5rem 2rem;max-width:1400px}}
#MainMenu,footer,header{{visibility:hidden}} .stDeployButton{{display:none}}
.stTabs [data-baseweb="tab-list"]{{background:{C['card']};border-radius:10px;padding:4px;gap:4px;border:1px solid {C['border']}}}
.stTabs [data-baseweb="tab"]{{background:transparent;color:{C['muted']};border-radius:7px;padding:8px 20px;font-size:13px;font-weight:500}}
.stTabs [aria-selected="true"]{{background:{C['blue']}!important;color:white!important}}
.stTabs [data-baseweb="tab-panel"]{{padding-top:1.5rem}}
[data-testid="metric-container"]{{background:{C['card']};border:1px solid {C['border']};border-radius:10px;padding:1rem 1.2rem}}
[data-testid="metric-container"] label{{color:{C['muted']}!important;font-size:11px!important;text-transform:uppercase;letter-spacing:.08em}}
[data-testid="metric-container"] [data-testid="stMetricValue"]{{font-family:'Space Grotesk',sans-serif!important;font-size:24px!important;color:{C['text']}!important}}
hr{{border-color:{C['border']}}}
</style>""", unsafe_allow_html=True)

# ── Fetch ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def fetch(name):
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&sheet={urllib.parse.quote(name, safe='')}"
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return pd.read_csv(StringIO(r.text), header=None)
    except Exception as e:
        st.warning(f"⚠️ {name}: {e}")
        return pd.DataFrame()

def v(df, r, c, d=0):
    try:
        x = df.iloc[r, c]
        return x if not pd.isna(x) else d
    except: return d

def n(val):
    s = re.sub(r'[€$\s+%\u202f\xa0]', '', str(val)).replace(',', '.')
    if s.count('.') > 1:
        s = s.replace('.', '', s.count('.')-1)
    try: return float(s)
    except: return 0.0

def fmt(x): return f"{x:,.0f} €".replace(",", " ")
def pct(x): return f"{'+' if x>=0 else ''}{x:.2f} %"
def pcol(x): return C['green'] if x >= 0 else C['red']

def card(title, value, sub="", color=C['blue'], icon=""):
    return f"""<div style="background:{C['card']};border:1px solid {C['border']};border-top:2px solid {color};
border-radius:10px;padding:14px 18px;height:100%">
<div style="font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px">{icon} {title}</div>
<div style="font-family:'Space Grotesk';font-size:22px;font-weight:700;color:{C['text']};line-height:1.1">{value}</div>
{"<div style='font-size:12px;color:"+color+";margin-top:4px'>"+sub+"</div>" if sub else ""}
</div>"""

def sec(txt, icon=""):
    st.markdown(f"""<div style="background:{C['card']};border-left:3px solid {C['blue']};border-radius:6px;
padding:10px 16px;margin:1.5rem 0 1rem 0"><span style="font-family:'Space Grotesk';font-weight:600;font-size:14px">{icon} {txt}</span></div>""", unsafe_allow_html=True)

# Plotly base layout — NO yaxis key here to avoid conflicts
def base_layout(height=280, legend=False):
    return dict(
        paper_bgcolor=C['bg'], plot_bgcolor=C['card'],
        font=dict(family="DM Sans", color=C['muted']),
        margin=dict(l=10, r=10, t=30, b=30),
        height=height, showlegend=legend,
        xaxis=dict(gridcolor=C['border'], linecolor=C['border'], tickfont=dict(color=C['muted'], size=11)),
        yaxis=dict(gridcolor=C['border'], linecolor=C['border'], tickfont=dict(color=C['muted'], size=11)),
    )

# ── Header ─────────────────────────────────────────────
st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding:12px 0;margin-bottom:8px;border-bottom:1px solid {C['border']}">
<div style="display:flex;align-items:center;gap:12px">
<div style="width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#1F6FEB,#8B5CF6);
display:flex;align-items:center;justify-content:center;font-size:18px">📊</div>
<div><div style="font-family:'Space Grotesk';font-size:18px;font-weight:700">WealthTrack</div>
<div style="font-size:11px;color:{C['muted']}">Samuel · Ingénieur chez Alstom</div></div></div>
<div style="display:flex;align-items:center;gap:8px">
<div style="width:8px;height:8px;border-radius:50%;background:{C['green']};box-shadow:0 0 6px {C['green']}"></div>
<span style="font-size:12px;color:{C['muted']}">Données Google Finance · Mis à jour en temps réel</span>
</div></div>""", unsafe_allow_html=True)

tab1, tab2, tab3, tab4 = st.tabs(["🏠 Vue d'ensemble", "📈 Bourse", "₿ Crypto", "⚙️ Options & Perf."])

# ══════════════════════════════════════════════════════
# TAB 1
# ══════════════════════════════════════════════════════
with tab1:
    df_p  = fetch("🏠 Patrimoine")
    df_em = fetch("📅 Évol. Mensuelle")
    df_ea = fetch("📈 Évol. Annuelle")

    pat   = n(v(df_p, 5,1));  inv  = n(v(df_p, 5,3))
    perf  = n(v(df_p, 5,5));  cagr = n(v(df_p, 5,9))
    ytd   = n(v(df_em,5,9));  ytdp = n(v(df_em,5,12))

    cols = st.columns(5)
    for col,(ti,va,su,co,ic) in zip(cols,[
        ("PATRIMOINE TOTAL", fmt(pat), "", C['gold'],"🏆"),
        ("TOTAL INVESTI",    fmt(inv), "", C['blue'],"💰"),
        ("PERFORMANCE",      pct(perf),"depuis ouverture", pcol(perf),"📈"),
        ("CAGR ANNUALISÉ",   pct(cagr),"depuis fév. 2022", C['purple'],"⚡"),
        ("VARIATION YTD",    fmt(ytd), pct(ytdp), pcol(ytd),"📅"),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    L, R = st.columns([2,1])

    with L:
        sec("Évolution mensuelle 2026","📅")
        mois = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
        pats, vars_ = [], []
        for i in range(12):
            pv = n(v(df_em, 13+i, 2)); raw = v(df_em, 13+i, 3, "")
            pats.append(pv if pv > 0 else None)
            vars_.append(n(raw) if str(raw) not in ["—","","nan"] else None)

        xp = [mois[i] for i,v_ in enumerate(pats) if v_]
        yp = [v_ for v_ in pats if v_]
        fig1 = go.Figure(go.Scatter(x=xp, y=yp, mode='lines+markers',
            line=dict(color=C['blue'],width=3,shape='spline'),
            marker=dict(color=C['gold'],size=8,line=dict(color=C['bg'],width=2)),
            fill='tozeroy', fillcolor='rgba(31,111,235,0.08)',
            hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'))
        for x_,y_ in zip(xp,yp):
            fig1.add_annotation(x=x_,y=y_,text=f"{y_/1000:.0f}k€",showarrow=False,yshift=14,font=dict(size=10,color=C['text']))
        fig1.update_layout(**base_layout(220))
        fig1.update_yaxes(tickformat=',.0f', ticksuffix=' €')
        st.plotly_chart(fig1, use_container_width=True, config={'displayModeBar':False})

        sec("Variations mensuelles","📊")
        xv = [mois[i] for i,v_ in enumerate(vars_) if v_ is not None]
        yv = [v_ for v_ in vars_ if v_ is not None]
        fig2 = go.Figure(go.Bar(x=xv, y=yv,
            marker_color=[C['green'] if v_>=0 else C['red'] for v_ in yv],
            text=[f"{'+' if v_>=0 else ''}{v_:,.0f}€" for v_ in yv],
            textposition='outside', textfont=dict(color=C['text'],size=11),
            hovertemplate='<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>'))
        fig2.update_layout(**base_layout(200))
        fig2.update_yaxes(tickformat='+,.0f', ticksuffix=' €')
        st.plotly_chart(fig2, use_container_width=True, config={'displayModeBar':False})

    with R:
        sec("Répartition","🍩")
        cats = ["📈 Bourse","₿ Crypto","⚙️ Options","🏢 PEE","📋 PER","🛡️ AV","💵 Cash"]
        cols_pie = [C['blue'],C['gold'],C['purple'],C['teal'],"#059669","#6B7280","#3B82F6"]
        vals_pie = [n(v(df_p,20+i,2)) for i in range(7)]
        vals_pie = [(c,v_) for c,v_ in zip(cols_pie,vals_pie) if v_>0]
        lbl = [cats[i] for i in range(7) if n(v(df_p,20+i,2))>0]
        if vals_pie:
            fig3 = go.Figure(go.Pie(labels=lbl, values=[v_ for _,v_ in vals_pie], hole=0.55,
                marker=dict(colors=[c for c,_ in vals_pie], line=dict(color=C['bg'],width=2)),
                textinfo='percent', textfont=dict(size=11,color='white'),
                hovertemplate='<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>'))
            total_pie = sum(v_ for _,v_ in vals_pie)
            fig3.add_annotation(text=f"<b>{total_pie/1000:.0f}k€</b>",x=0.5,y=0.5,
                font=dict(size=16,color=C['text'],family='Space Grotesk'),showarrow=False)
            fig3.update_layout(**base_layout(260,True))
            fig3.update_layout(legend=dict(orientation='v',x=1.05,y=0.5,font=dict(size=10),bgcolor='rgba(0,0,0,0)'),
                               margin=dict(l=0,r=10,t=10,b=10))
            st.plotly_chart(fig3, use_container_width=True, config={'displayModeBar':False})

        sec("Évolution annuelle","📈")
        yrs = ["2022","2023","2024","2025","2026"]
        tots = [25813,40915,57485,71057]
        t26 = n(v(df_ea,16,9)); tots.append(t26 if t26>0 else 75285)
        fig4 = go.Figure(go.Scatter(x=yrs,y=tots,mode='lines+markers',
            line=dict(color=C['gold'],width=3,shape='spline'),
            marker=dict(color=C['gold'],size=8,line=dict(color=C['bg'],width=2)),
            fill='tozeroy',fillcolor='rgba(210,153,34,0.08)',
            hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'))
        fig4.update_layout(**base_layout(180))
        fig4.update_yaxes(tickformat=',.0f', ticksuffix=' €')
        st.plotly_chart(fig4, use_container_width=True, config={'displayModeBar':False})

# ══════════════════════════════════════════════════════
# TAB 2
# ══════════════════════════════════════════════════════
with tab2:
    df_b = fetch("📊 Bourse 2026")
    bi=n(v(df_b,1,1)); bs=n(v(df_b,1,3)); bpv=n(v(df_b,1,5)); bpp=n(v(df_b,1,7))
    bd=n(v(df_b,1,15)); bp=n(v(df_b,1,11))

    cols = st.columns(5)
    for col,(ti,va,su,co,ic) in zip(cols,[
        ("TOTAL INVESTI", fmt(bi), "", C['cyan'],"💰"),
        ("SOLDE ACTUEL",  fmt(bs), "", C['blue'],"💶"),
        ("PV / MV",       fmt(bpv), pct(bpp), pcol(bpp),"📈"),
        ("DIVIDENDES NET",f"{bd:.2f} €","2026 YTD",C['gold'],"💰"),
        ("PARRAINAGE YTD",f"{bp:.2f} €","",C['teal'],"🤝"),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    L2, R2 = st.columns(2)
    mois_f = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

    with L2:
        sec("DCA Mensuel 2026","💸")
        dca_cto = [n(v(df_b,11+i,2)) for i in range(12)]
        dca_pea = [n(v(df_b,11+i,3)) for i in range(12)]
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(name='CTO',x=mois_f,y=dca_cto,marker_color=C['blue'],hovertemplate='CTO: %{y:.2f} €<extra></extra>'))
        fig5.add_trace(go.Bar(name='PEA',x=mois_f,y=dca_pea,marker_color=C['green'],hovertemplate='PEA: %{y:.2f} €<extra></extra>'))
        fig5.update_layout(**base_layout(280,True), barmode='stack')
        fig5.update_layout(legend=dict(orientation='h',y=-0.15,font=dict(size=11)))
        fig5.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig5, use_container_width=True, config={'displayModeBar':False})

    with R2:
        sec("Évolution du solde","📊")
        sol = [n(v(df_b,11+i,9)) for i in range(12)]
        xsol = [mois_f[i] for i,s in enumerate(sol) if s>0]
        ysol = [s for s in sol if s>0]
        fig6 = go.Figure(go.Scatter(x=xsol,y=ysol,mode='lines+markers',
            line=dict(color=C['blue'],width=3,shape='spline'),
            marker=dict(color=C['gold'],size=8),fill='tozeroy',fillcolor='rgba(31,111,235,0.08)',
            hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'))
        fig6.update_layout(**base_layout(280))
        fig6.update_yaxes(tickformat=',.0f', ticksuffix=' €')
        st.plotly_chart(fig6, use_container_width=True, config={'displayModeBar':False})

    sec("Dividendes 2026","💰")
    divs = pd.DataFrame({"Action":["TSMC","JP Morgan","Apple","Costco","ASML","Visa","Microsoft","SP Global",
        "Alphabet","Meta","Novo","LVMH","Air Liquide"],"Pays":["Taiwan","USA","USA","USA","Pays-Bas","USA","USA",
        "USA","USA","USA","Danemark","FR","FR"],"Net (€)":[4.53,4.39,0.48,0.74,2.11,1.40,1.13,0.74,0.55,0.30,10.82,12.98,8.77]})
    divs["Net (€)"] = divs["Net (€)"].map(lambda x: f"{x:.2f} €")
    st.dataframe(divs, use_container_width=True, hide_index=True, height=250)

# ══════════════════════════════════════════════════════
# TAB 3
# ══════════════════════════════════════════════════════
with tab3:
    df_ct = fetch("₿ Crypto Total")
    cv=n(v(df_ct,5,1)); cd=n(v(df_ct,5,3)); ci=n(v(df_ct,5,5))
    cpv=n(v(df_ct,5,8)); cp=n(v(df_ct,5,10)); ceur=n(v(df_ct,5,12))

    cols = st.columns(5)
    for col,(ti,va,su,co,ic) in zip(cols,[
        ("VALEUR PF (€)",  fmt(cv), "", C['gold'],"💶"),
        ("VALEUR PF ($)",  f"{cd:,.2f} $","",C['gold'],"💵"),
        ("TOTAL INVESTI",  fmt(ci), "",C['blue'],"💰"),
        ("PV / MV",        fmt(cpv), pct(cp), pcol(cp),"📈"),
        ("COURS EUR/$",    f"{ceur:.4f}","",C['muted'],"💱"),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    L3, R3 = st.columns([3,2])

    with L3:
        sec("Portefeuille Crypto","₿")
        names_ = ["Bitcoin","Solana","Ethereum","BinanceCoin","USDC"]
        cdata = []
        for i,nm in enumerate(names_):
            r_ = 11+i
            cdata.append({"Crypto":nm,"Code":str(v(df_ct,r_,2)),"Montant":str(v(df_ct,r_,3)),
                "Valeur $":f"{n(v(df_ct,r_,5)):,.2f} $","Valeur €":fmt(n(v(df_ct,r_,6))),
                "PV/MV €":f"{'+' if n(v(df_ct,r_,11))>=0 else ''}{n(v(df_ct,r_,11)):,.0f} €",
                "Perf.":f"{'+' if n(v(df_ct,r_,12))>=0 else ''}{n(v(df_ct,r_,12)):.1f} %"})
        st.dataframe(pd.DataFrame(cdata), use_container_width=True, hide_index=True, height=210)

        df_c26 = fetch("₿ Crypto 2026")
        sec("DCA Mensuel 2026","💸")
        mois_s = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
        dca_c = [n(v(df_c26,29+i,2)) for i in range(12)]
        fig7 = go.Figure(go.Bar(x=mois_s,y=dca_c,
            marker_color=[C['gold'] if x>0 else C['border'] for x in dca_c],
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_c],
            textposition='outside',textfont=dict(color=C['text'],size=10),
            hovertemplate='<b>%{x}</b><br>%{y:.2f} €<extra></extra>'))
        fig7.update_layout(**base_layout(200))
        fig7.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig7, use_container_width=True, config={'displayModeBar':False})

    with R3:
        sec("Répartition","🍩")
        pcts = [28.04,33.58,15.17,23.00,0.21]
        clrs_c=["#F7931A","#9945FF","#627EEA","#F3BA2F","#2775CA"]
        fig8 = go.Figure(go.Pie(labels=names_,values=[cd*p/100 for p in pcts],hole=0.55,
            marker=dict(colors=clrs_c,line=dict(color=C['bg'],width=2)),
            textinfo='percent',textfont=dict(size=11,color='white'),
            hovertemplate='<b>%{label}</b><br>%{value:,.2f} $<br>%{percent}<extra></extra>'))
        fig8.add_annotation(text=f"<b>{cd/1000:.1f}k$</b>",x=0.5,y=0.5,
            font=dict(size=16,color=C['text'],family='Space Grotesk'),showarrow=False)
        fig8.update_layout(**base_layout(260,True))
        fig8.update_layout(legend=dict(orientation='h',y=-0.05,font=dict(size=10)),margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig8, use_container_width=True, config={'displayModeBar':False})

        sec("Gains Staking","🌾")
        for nm,g in [("Bitcoin",65.79),("Solana",464.52)]:
            st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid {C['border']}">
<span style="font-weight:600;font-size:13px">{nm}</span>
<span style="font-family:'Space Grotesk';font-weight:700;color:{C['green']}">+{g:.2f} $</span></div>""",unsafe_allow_html=True)
        st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:10px 0">
<span style="color:{C['muted']};font-size:12px">TOTAL</span>
<span style="font-family:'Space Grotesk';font-size:16px;font-weight:700;color:{C['green']}">+530.31 $</span></div>""",unsafe_allow_html=True)

# ══════════════════════════════════════════════════════
# TAB 4
# ══════════════════════════════════════════════════════
with tab4:
    df_opt = fetch("⚙️ Options 2026")
    oc=n(v(df_opt,3,3)); oi=n(v(df_opt,3,6)); oroi=n(v(df_opt,3,9))
    ope=n(v(df_opt,3,12)); opd=n(v(df_opt,3,15))

    L4, R4 = st.columns(2)

    with L4:
        sec("Options 2026 — Stratégie de la Roue","⚙️")
        c1,c2,c3 = st.columns(3)
        with c1: st.markdown(card("CAPITAL ACTUEL",fmt(oc),"",C['purple'],"📈"),unsafe_allow_html=True)
        with c2: st.markdown(card("ROI TOTAL",pct(oroi),"",pcol(oroi),"🏆"),unsafe_allow_html=True)
        with c3: st.markdown(card("PRIMES YTD",f"{ope:.2f} €",f"{opd:.2f} $",C['gold'],"💰"),unsafe_allow_html=True)

        st.markdown("<br>",unsafe_allow_html=True)
        mois_s = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
        primes = [n(v(df_opt,7+i,8)) for i in range(12)]
        rois   = [n(v(df_opt,7+i,15)) for i in range(12)]
        fig9 = go.Figure()
        fig9.add_trace(go.Bar(name='Prime (€)',x=mois_s,y=primes,
            marker_color=[C['purple'] if p>0 else C['border'] for p in primes],yaxis='y',
            hovertemplate='<b>%{x}</b><br>%{y:.2f} €<extra></extra>'))
        fig9.add_trace(go.Scatter(name='ROI %',x=mois_s,y=rois,
            line=dict(color=C['gold'],width=2),mode='lines+markers',marker=dict(size=6),yaxis='y2',
            hovertemplate='<b>%{x}</b><br>%{y:.2f} %<extra></extra>'))
        fig9.update_layout(**base_layout(280,True))
        fig9.update_layout(
            yaxis2=dict(overlaying='y',side='right',tickfont=dict(color=C['gold'],size=10),
                        ticksuffix=' %',gridcolor='rgba(0,0,0,0)'),
            legend=dict(orientation='h',y=-0.15,font=dict(size=11)))
        fig9.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig9, use_container_width=True, config={'displayModeBar':False})

    with R4:
        sec("Performance par enveloppe","🏆")
        poches = [
            ("📈 Bourse (CTO+PEA)",23881,27285,3404,14.3,C['blue']),
            ("₿ Crypto (Binance)", 6005, 7999, 1994,33.2,C['gold']),
            ("⚙️ Options (IBK)",   5550, 5681,  131, 2.4,C['purple']),
        ]
        for po,pi,pl,ppv,pp,pc in poches:
            a,b,cc,d = st.columns([2.5,1.5,1.5,1.2])
            with a: st.markdown(f"<span style='color:{pc};font-weight:600;font-size:13px'>{po}</span>",unsafe_allow_html=True)
            with b: st.markdown(f"<span style='font-size:13px'>{fmt(pl)}</span>",unsafe_allow_html=True)
            with cc:
                clr=C['green'] if ppv>=0 else C['red']
                st.markdown(f"<span style='color:{clr};font-size:13px;font-weight:600'>{'+' if ppv>=0 else ''}{ppv:,.0f} €</span>",unsafe_allow_html=True)
            with d:
                clr=C['green'] if pp>=0 else C['red']
                st.markdown(f"<span style='color:{clr};font-size:13px;font-weight:700'>{'+' if pp>=0 else ''}{pp:.1f}%</span>",unsafe_allow_html=True)
            st.divider()

        tl=sum(p[2] for p in poches); ti2=sum(p[1] for p in poches)
        tpv=sum(p[3] for p in poches); tp=(tl/ti2-1)*100 if ti2 else 0
        st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['blue']};border-radius:8px;
padding:12px 16px;display:flex;justify-content:space-between;align-items:center">
<span style="font-weight:700">💰 TOTAL</span><span style="font-family:'Space Grotesk';font-size:16px">{fmt(tl)}</span>
<span style="color:{C['green']};font-weight:700">+{tpv:,.0f} €</span>
<span style="color:{C['green']};font-weight:700">+{tp:.1f}%</span></div>""",unsafe_allow_html=True)

        sec("CAGR vs Benchmarks","⚡")
        benchs = [("🏆 Mon PF",3.46,C['gold'],True),("📈 SP500",13.37,C['cyan'],False),
                  ("🇫🇷 CAC 40",7.77,C['cyan'],False),("🌍 STOXX 600",7.84,C['cyan'],False)]
        mx = max(b[1] for b in benchs)
        for bn,bc_val,bc,bold in benchs:
            fw="700" if bold else "400"; fc=C['gold'] if bold else C['muted']
            st.markdown(f"""<div style="margin-bottom:12px">
<div style="display:flex;justify-content:space-between;margin-bottom:4px">
<span style="font-size:12px;font-weight:{fw};color:{fc}">{bn}</span>
<span style="font-family:'Space Grotesk';font-weight:{fw};color:{bc};font-size:13px">+{bc_val:.2f} %</span></div>
<div style="height:5px;background:{C['border']};border-radius:3px">
<div style="height:100%;width:{bc_val/mx*100:.0f}%;background:{bc};border-radius:3px"></div></div></div>""",unsafe_allow_html=True)
