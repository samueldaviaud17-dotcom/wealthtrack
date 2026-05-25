import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="SamInvest", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

SHEET_ID = "1ADzYAtCeFpP01eoFOdb2iiwSX3eU9rcbQbS6wQf6sgI"
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets.readonly"]

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

def sec(txt, icon=""):
    st.markdown(f"""<div style="background:{C['card']};border-left:3px solid {C['blue']};border-radius:6px;
padding:10px 16px;margin:1.5rem 0 1rem 0"><span style="font-family:'Space Grotesk';font-weight:600;font-size:14px">{icon} {txt}</span></div>""", unsafe_allow_html=True)

def base_layout(height=280, legend=False):
    return dict(paper_bgcolor=C['bg'], plot_bgcolor=C['card'],
        font=dict(family="DM Sans", color=C['muted']),
        margin=dict(l=10, r=10, t=30, b=30), height=height, showlegend=legend,
        xaxis=dict(gridcolor=C['border'], linecolor=C['border'], tickfont=dict(color=C['muted'],size=11)),
        yaxis=dict(gridcolor=C['border'], linecolor=C['border'], tickfont=dict(color=C['muted'],size=11)))

# ── Header ─────────────────────────────────────────────
st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding:12px 0;margin-bottom:8px;border-bottom:1px solid {C['border']}">
<div style="display:flex;align-items:center;gap:12px">
<div style="width:36px;height:36px;border-radius:8px;background:linear-gradient(135deg,#1F6FEB,#8B5CF6);
display:flex;align-items:center;justify-content:center;font-size:18px">📊</div>
<div><div style="font-family:'Space Grotesk';font-size:18px;font-weight:700">SamInvest</div>
<div style="font-size:11px;color:{C['muted']}">Samuel · Ingénieur chez Alstom</div></div></div>
<div style="display:flex;align-items:center;gap:8px">
<div style="width:8px;height:8px;border-radius:50%;background:{C['green']};box-shadow:0 0 6px {C['green']}"></div>
<div style="text-align:right"><div style="font-size:12px;color:{C['muted']}">Données live · Refresh auto toutes les 5 min</div><div style="font-size:10px;color:{C['muted']};margin-top:2px" id="synchro-time">🔄 </div>
</div></div>""", unsafe_allow_html=True)

# Display Paris time
from datetime import datetime, timezone, timedelta
_paris = datetime.now(timezone(timedelta(hours=2)))
_now = _paris.strftime("%d/%m/%Y à %H:%M")
st.markdown(f"""<div style="text-align:right;font-size:10px;color:{C['muted']};margin-top:-8px;padding-right:2px">
🔄 Dernière synchro : <b>{_now}</b></div>""", unsafe_allow_html=True)

mois_s = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
mois_f = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Vue d'ensemble", "📈 Bourse", "₿ Crypto", "⚙️ Options", "📊 Performance"])

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
    pvmv_total = n(v(df_pf,9,3)) - n(v(df_pf,9,2)) if df_pf.shape[0]>9 else 0
    for col,(ti,va,su,co,ic,s2) in zip(cols,[
        ("PATRIMOINE TOTAL", fmt(pat),  "",                          C['gold'],   "🏆", ""),
        ("TOTAL INVESTI",    fmt(inv),  "",                          C['blue'],   "💰", ""),
        ("PERFORMANCE",      pct(perf), f"depuis février 2022",      pcol(perf),  "📈", f"+{pvmv_total:,.0f} € de PV/MV" if pvmv_total else ""),
        ("CAGR ANNUALISÉ",   pct(cagr), "depuis fév. 2022",          C['purple'], "⚡", ""),
        ("VARIATION YTD",    fmt(ytd),  pct(ytdp),                   pcol(ytd),   "📅", ""),
        ("DIVIDENDES YTD",   f"{divs_ytd:.2f} €", "net perçu",       C['gold'],   "💰", ""),
        ("PRIMES OPTIONS",   f"{primes_ytd:.2f} €","YTD 2026",        C['purple'], "⚙️", ""),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic,s2), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    L, R = st.columns([2,1])

    with L:
        sec("Évolution mensuelle 2026","📅")
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
            hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'))
        for x_,y_ in zip(xp,yp):
            fig1.add_annotation(x=x_,y=y_,text=f"{y_/1000:.0f}k€",showarrow=False,yshift=14,font=dict(size=10,color=C['text']))
        fig1.update_layout(**base_layout(220))
        fig1.update_yaxes(tickformat=',.0f',ticksuffix=' €')
        st.plotly_chart(fig1,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        sec("Variations mensuelles","📊")
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
                text=[f"{'+' if x>=0 else ''}{x:,.0f}€  {pct_by_month.get(xv[i],'')}" for i,x in enumerate(yv)],
                textposition='outside',textfont=dict(color=C['text'],size=10),
                hovertemplate='<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>'))
            fig2.update_layout(**base_layout(200))
            fig2.update_yaxes(tickformat='+,.0f',ticksuffix=' €')
            st.plotly_chart(fig2,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})



        sec("Évolution annuelle","📈")
        tots=[n(v(df_ea,11+i,9)) for i in range(5)]
        yrs=["2022","2023","2024","2025","2026"]
        tv=[x for x in tots if x>0]; yl=yrs[:len(tv)]
        if tv:
            fig4=go.Figure(go.Scatter(x=yl,y=tv,mode='lines+markers',
                line=dict(color=C['gold'],width=3,shape='spline'),
                marker=dict(color=C['gold'],size=8,line=dict(color=C['bg'],width=2)),
                fill='tozeroy',fillcolor='rgba(210,153,34,0.08)',
                hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'))
            # Annotations évol %
            for i in range(1,len(tv)):
                evol=(tv[i]/tv[i-1]-1)*100
                fig4.add_annotation(x=yl[i],y=tv[i],
                    text=f"{'+' if evol>=0 else ''}{evol:.0f}%",
                    showarrow=False,yshift=16,
                    font=dict(size=9,color=C['green'] if evol>=0 else C['red']))
            fig4.update_layout(**base_layout(180))
            fig4.update_yaxes(tickformat=',.0f',ticksuffix=' €')
            st.plotly_chart(fig4,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})
    with R:
        sec("Répartition","🍩")
        cats=["📈 Bourse","₿ Crypto","⚙️ Options","🏢 PEE","📋 PER","🛡️ AV","💵 Cash"]
        clrs=[C['blue'],C['gold'],C['purple'],C['teal'],"#A855F7","#6B7280","#06B6D4"]
        vals=[n(v(df_p,19+i,2)) for i in range(7)]
        # Sort by value descending
        combined=sorted([(c,cl,v_) for c,cl,v_ in zip(cats,clrs,vals) if v_>0],key=lambda x:-x[2])
        lbl=[x[0] for x in combined]
        vc=[x[1] for x in combined]
        vv=[x[2] for x in combined]
        if vv:
            # Labels with € values
            lbl_with_eur=[f"{l}<br><b>{fmt(v_)}</b>" for l,v_ in zip(lbl,vv)]
            fig3=go.Figure(go.Pie(labels=lbl,values=vv,hole=0.55,
                marker=dict(colors=vc,line=dict(color=C['bg'],width=2)),
                textinfo='percent',textfont=dict(size=11,color='white'),
                customdata=[[fmt(v_)] for v_ in vv],
                hovertemplate='<b>%{label}</b><br>%{customdata[0]}<br>%{percent}<extra></extra>'))
            fig3.add_annotation(text=f"<b>{sum(vv)/1000:.0f}k€</b>",x=0.5,y=0.5,
                font=dict(size=16,color=C['text'],family='Space Grotesk'),showarrow=False)
            # Legend with € values
            fig3.update_traces(
                texttemplate='%{percent}',
            )
            fig3.update_layout(**base_layout(280,True))
            fig3.update_layout(
                legend=dict(
                    orientation='v',x=1.02,y=0.5,
                    font=dict(size=10,color=C['muted']),
                    bgcolor='rgba(0,0,0,0)',
                    itemclick=False,
                ),
                margin=dict(l=0,r=10,t=10,b=10))
            st.plotly_chart(fig3,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # Légende détaillée avec €
        for lbl_,clr_,val_ in zip(lbl,vc,vv):
            pct_=val_/sum(vv)*100
            st.markdown(f"""<div style="display:flex;justify-content:space-between;align-items:center;
            padding:4px 0;border-bottom:1px solid {C['border']}">
            <div style="display:flex;align-items:center;gap:6px">
                <div style="width:8px;height:8px;border-radius:50%;background:{clr_}"></div>
                <span style="font-size:11px;color:{C['muted']}">{lbl_}</span>
            </div>
            <div style="text-align:right">
                <span style="font-size:11px;font-weight:600;color:{clr_}">{fmt(val_)}</span>
                <span style="font-size:10px;color:{C['muted']}"> · {pct_:.1f}%</span>
            </div></div>""", unsafe_allow_html=True)




# ══════════════════════════════════════════════════════
with tab2:
    df_b=fetch("📊 Bourse 2026")
    bi=n(v(df_b,5,1)); bs=n(v(df_b,5,3)); bpv=n(v(df_b,5,6)); bpp=n(v(df_b,5,8))
    bd=n(v(df_b,5,15)); bp=n(v(df_b,5,11))
    bcto=n(v(df_b,5,21)); bpea=n(v(df_b,5,22))  # CTO/PEA split from historique

    # ── 5 KPI cards (same height as tab1) ──────────────
    cols=st.columns(5)
    for col,(ti,va,su,co,ic,s2) in zip(cols,[
        ("TOTAL INVESTI", fmt(bi),       "",                   C['cyan'],  "💰", f"CTO: {fmt(bcto)}  |  PEA: {fmt(bpea)}" if bcto else ""),
        ("SOLDE ACTUEL",  fmt(bs),       "",                   C['blue'],  "💶", f"{'+ ' if bpv>=0 else '- '}{abs(bpv):,.0f} € PV/MV".replace(',',' ')),
        ("PV / MV",       fmt(bpv),      pct(bpp),             pcol(bpp),  "📈", ""),
        ("DIVIDENDES NET",f"{bd:.2f} €", "2026 YTD net",       C['gold'],  "💰", ""),
        ("PARRAINAGE YTD",f"{bp:.2f} €", "",                   C['teal'],  "🤝", ""),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic,s2), unsafe_allow_html=True)

    L2,R2=st.columns(2)

    with L2:
        sec("DCA Mensuel 2026 — CTO & PEA","💸")
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
        st.plotly_chart(fig5,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # DCA cumul ligne
        dca_tot=[n(v(df_b,11+i,4)) for i in range(12)]
        xc=[mois_f[i] for i,x in enumerate(dca_tot) if x>0]
        yc=[x for x in dca_tot if x>0]
        if xc:
            sec("DCA Cumulé 2026","📈")
            figc=go.Figure(go.Scatter(x=xc,y=yc,mode='lines+markers+text',
                line=dict(color=C['cyan'],width=2,shape='spline'),
                marker=dict(color=C['gold'],size=7),fill='tozeroy',fillcolor='rgba(6,182,212,0.08)',
                text=[f"{y:.0f}€" for y in yc],textposition='top center',textfont=dict(size=9,color=C['text']),
                hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'))
            figc.update_layout(**base_layout(180))
            figc.update_yaxes(tickformat=',.0f',ticksuffix=' €')
            st.plotly_chart(figc,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

    with R2:
        sec("Évolution du solde (CTO + PEA)","📊")
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
                hovertemplate='Total: %{y:,.0f} €<extra></extra>'))
            fig6.add_trace(go.Scatter(x=xsol,y=ycto,name='CTO',
                line=dict(color=C['cyan'],width=1.5,dash='dot'),
                hovertemplate='CTO: %{y:,.0f} €<extra></extra>'))
            fig6.add_trace(go.Scatter(x=xsol,y=ypea,name='PEA',
                line=dict(color=C['green'],width=1.5,dash='dot'),
                hovertemplate='PEA: %{y:,.0f} €<extra></extra>'))
            fig6.update_layout(**base_layout(280,True))
            fig6.update_layout(legend=dict(orientation='h',y=-0.12,font=dict(size=11)))
            fig6.update_yaxes(tickformat=',.0f',ticksuffix=' €')
            st.plotly_chart(fig6,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # Dividendes
        sec("Dividendes 2026","💰")
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
        sec("Solde mensuel CTO & PEA","📋")
        solde_rows=[]
        for i in range(12):
            m=mois_f[i]
            scto=n(v(df_b,11+i,7)); spea=n(v(df_b,11+i,8)); stot=n(v(df_b,11+i,9))
            if stot>0:
                solde_rows.append({"Mois":m,"CTO (€)":f"{scto:,.0f} €","PEA (€)":f"{spea:,.0f} €","Total (€)":f"{stot:,.0f} €"})
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
        ("VALEUR PF ($)",  f"{cd:,.2f} $",    "",        C['gold'],  "💵"),
        ("TOTAL INVESTI",  fmt(ci),            "",        C['blue'],  "💰"),
        ("PV / MV",        fmt(cpv),           pct(cp),  pcol(cp),   "📈"),
        ("COURS EUR/$",    f"{ceur:.4f}",      "",        C['muted'], "💱"),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic), unsafe_allow_html=True)

    st.markdown("<br>",unsafe_allow_html=True)
    L3,R3=st.columns([3,2])

    with L3:
        sec("Portefeuille Crypto","₿")
        cdata=[]
        names_c=["Bitcoin","Solana","Ethereum","BinanceCoin","USDC"]
        for i,nm in enumerate(names_c):
            r_=11+i
            cdata.append({"Crypto":nm,"Code":str(v(df_ct,r_,2)),"Montant":str(v(df_ct,r_,3)),
                "Valeur $":f"{n(v(df_ct,r_,5)):,.2f} $","Valeur €":fmt(n(v(df_ct,r_,6))),
                "PV/MV €":f"{'+' if n(v(df_ct,r_,11))>=0 else ''}{n(v(df_ct,r_,11)):,.0f} €",
                "Perf.":f"{'+' if n(v(df_ct,r_,12))>=0 else ''}{n(v(df_ct,r_,12)):.1f} %"})
        st.dataframe(pd.DataFrame(cdata),use_container_width=True,hide_index=True,height=210)

        df_c26=fetch("₿ Crypto 2026")
        sec("DCA Mensuel 2026","💸")
        dca_c=[n(v(df_c26,20+i,2)) for i in range(12)]
        fig7=go.Figure(go.Bar(x=mois_s,y=dca_c,
            marker_color=[C['gold'] if x>0 else C['border'] for x in dca_c],
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_c],
            textposition='outside',textfont=dict(color=C['text'],size=10)))
        fig7.update_layout(**base_layout(200))
        fig7.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig7,use_container_width=True,config={'displayModeBar':False})

    with R3:
        sec("Répartition","🍩")
        clrs_c=["#F7931A","#9945FF","#627EEA","#F3BA2F","#2775CA"]
        pcts_c=[n(v(df_ct,19+i,12)) for i in range(5)]
        # fallback si % non dispo
        if sum(pcts_c)==0: pcts_c=[28.04,33.66,15.15,22.98,0.21]
        vals_c=[cd*p/100 for p in pcts_c]
        fig8=go.Figure(go.Pie(labels=names_c,values=vals_c,hole=0.55,
            marker=dict(colors=clrs_c,line=dict(color=C['bg'],width=2)),
            textinfo='percent',textfont=dict(size=11,color='white'),
            hovertemplate='<b>%{label}</b><br>%{value:,.2f} $<br>%{percent}<extra></extra>'))
        fig8.add_annotation(text=f"<b>{cd/1000:.1f}k$</b>",x=0.5,y=0.5,
            font=dict(size=16,color=C['text'],family='Space Grotesk'),showarrow=False)
        fig8.update_layout(**base_layout(260,True))
        fig8.update_layout(legend=dict(orientation='h',y=-0.05,font=dict(size=10)),margin=dict(l=0,r=0,t=10,b=0))
        st.plotly_chart(fig8,use_container_width=True,config={'displayModeBar':False})

        sec("Gains Staking","🌾")
        staking=[("Bitcoin","#F7931A"),("Solana","#9945FF")]
        st_rows=[]
        for i,(nm,clr) in enumerate(staking):
            g=n(v(df_ct,19+i,9))
            if g!=0: st_rows.append((nm,clr,g))
        for nm,clr,g in st_rows:
            st.markdown(f"""<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid {C['border']}">
<span style="font-weight:600;color:{clr}">{nm}</span>
<span style="font-family:'Space Grotesk';font-weight:700;color:{C['green']}">+{g:.2f} $</span></div>""",unsafe_allow_html=True)
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

    c1,c2,c3=st.columns(3)
    with c1: st.markdown(card("CAPITAL ACTUEL",fmt(n(v(df_opt,5,3))),"",C['purple'],"📈"),unsafe_allow_html=True)
    with c2: st.markdown(card("ROI TOTAL",pct(oroi),"",pcol(oroi),"🏆"),unsafe_allow_html=True)
    with c3: st.markdown(card("PRIMES YTD",f"{ope:.2f} €",f"{opd:.2f} $",C['gold'],"💰"),unsafe_allow_html=True)
    st.markdown("<br>",unsafe_allow_html=True)

    sec("Options 2026 — Stratégie de la Roue — Primes mensuelles","⚙️")
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
        yaxis2=dict(overlaying='y',side='right',tickfont=dict(color=C['gold'],size=10),
                    ticksuffix=' %',gridcolor='rgba(0,0,0,0)'),
        legend=dict(orientation='h',y=-0.12,font=dict(size=11)))
    fig9.update_yaxes(ticksuffix=' €')
    st.plotly_chart(fig9,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

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
        sec("Performance par enveloppe","🏆")
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
                st.markdown(f"<span style='color:{clr};font-size:13px;font-weight:600'>{'+' if ppv>=0 else ''}{ppv:,.0f} €</span>",unsafe_allow_html=True)
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
<span style="color:{C['green']};font-weight:700">+{tpv:,.0f} €</span>
<span style="color:{C['green']};font-weight:700">+{tp:.1f}%</span></div>""",unsafe_allow_html=True)

        # Évolution annuelle
        sec("Évolution annuelle du patrimoine","📈")
        tots=[n(v(df_ea,11+i,9)) for i in range(5)]
        yrs=["2022","2023","2024","2025","2026"]
        tv=[x for x in tots if x>0]; yl=yrs[:len(tv)]
        if tv:
            fig_ea=go.Figure(go.Scatter(x=yl,y=tv,mode='lines+markers',
                line=dict(color=C['gold'],width=3,shape='spline'),
                marker=dict(color=C['gold'],size=9,line=dict(color=C['bg'],width=2)),
                fill='tozeroy',fillcolor='rgba(210,153,34,0.08)',
                hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'))
            for i in range(1,len(tv)):
                evol=(tv[i]/tv[i-1]-1)*100
                fig_ea.add_annotation(x=yl[i],y=tv[i],
                    text=f"{'+' if evol>=0 else ''}{evol:.0f}%",
                    showarrow=False,yshift=16,font=dict(size=10,color=C['green'] if evol>=0 else C['red']))
            fig_ea.update_layout(**base_layout(260))
            fig_ea.update_yaxes(tickformat=',.0f',ticksuffix=' €')
            st.plotly_chart(fig_ea,use_container_width=True,config={'displayModeBar':True,'modeBarButtonsToAdd':['resetScale2d'],'modeBarButtonsToRemove':['zoom2d','pan2d','lasso2d','select2d','zoomIn2d','zoomOut2d','autoScale2d'],'displaylogo':False})

    with Rp:
        sec("CAGR vs Benchmarks","⚡")
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
        sec("Alpha vs Benchmarks","📐")
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
