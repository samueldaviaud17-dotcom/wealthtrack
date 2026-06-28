import streamlit as st
import pandas as pd
from pathlib import Path
import json, base64, requests

# ── GitHub persistence ─────────────────────────────────────────────────────
_GH_TOKEN  = st.secrets.get("GITHUB_TOKEN", "")
_GH_REPO   = st.secrets.get("GITHUB_REPO",  "samueldaviaud17-dotcom/wealthtrack")
_GH_BRANCH = st.secrets.get("GITHUB_BRANCH","main")
_GH_API    = "https://api.github.com"

def _gh_headers():
    return {"Authorization": f"token {_GH_TOKEN}", "Accept": "application/vnd.github+json"}

def gh_read(path):
    """Lit un fichier depuis GitHub. Retourne (contenu_bytes, sha) ou (None, None)."""
    if not _GH_TOKEN: return None, None
    try:
        r = requests.get(f"{_GH_API}/repos/{_GH_REPO}/contents/{path}",
                         headers=_gh_headers(), params={"ref": _GH_BRANCH}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return base64.b64decode(data["content"]), data["sha"]
        return None, None
    except Exception:
        return None, None

def gh_write(path, content_bytes, commit_msg, sha=None):
    """Écrit un fichier sur GitHub (crée ou met à jour). Retourne True si succès."""
    if not _GH_TOKEN: return False
    try:
        payload = {
            "message": commit_msg,
            "content": base64.b64encode(content_bytes).decode(),
            "branch":  _GH_BRANCH,
        }
        if sha: payload["sha"] = sha
        r = requests.put(f"{_GH_API}/repos/{_GH_REPO}/contents/{path}",
                         headers=_gh_headers(), json=payload, timeout=15)
        return r.status_code in (200, 201)
    except Exception:
        return False

def gh_list(prefix):
    """Liste les fichiers dans un dossier GitHub. Retourne liste de {'name','path','sha'} ou []."""
    if not _GH_TOKEN: return []
    try:
        r = requests.get(f"{_GH_API}/repos/{_GH_REPO}/contents/{prefix}",
                         headers=_gh_headers(), params={"ref": _GH_BRANCH}, timeout=10)
        if r.status_code == 200:
            return [{"name": f["name"], "path": f["path"], "sha": f["sha"]}
                    for f in r.json() if isinstance(f, dict)]
        return []
    except Exception:
        return []

# ── Watchlist persistence ─────────────────────────────────────────────────
_WL_PATH = "ibkr_data/watchlist.json"

def load_watchlist_gh():
    """Charge la watchlist depuis GitHub. Retourne dict ou {}."""
    content, _ = gh_read(_WL_PATH)
    if content:
        try: return json.loads(content)
        except Exception: pass
    return {"wl_portefeuille": [], "wl_options": [], "wl_surveillance": []}

def save_watchlist_gh():
    """Sauvegarde la watchlist sur GitHub."""
    data = {
        "wl_portefeuille":  st.session_state.get("wl_portefeuille", []),
        "wl_options":       st.session_state.get("wl_options", []),
        "wl_surveillance":  st.session_state.get("wl_surveillance", []),
    }
    _, sha = gh_read(_WL_PATH)
    gh_write(_WL_PATH, json.dumps(data, ensure_ascii=False, indent=2).encode(),
             "update watchlist", sha)

# ── Capital réel persistence ──────────────────────────────────────────────
_CR_PATH = "ibkr_data/capital_reel.json"

try:
    import yfinance as yf
    YF_AVAILABLE = True
except ImportError:
    YF_AVAILABLE = False
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="SamInvest", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

# ── Capital réel persistant (saisie manuelle) ──
_CAPITAL_REEL_FILE = Path(__file__).parent / "ibkr_data" / "capital_reel.json"

def load_capital_reel():
    # 1. GitHub (priorité)
    content, _ = gh_read(_CR_PATH)
    if content:
        try: return float(json.loads(content)['capital_reel'])
        except Exception: pass
    # 2. Fallback filesystem local
    try:
        return float(json.loads(_CAPITAL_REEL_FILE.read_text())['capital_reel'])
    except Exception: return 0.0

def save_capital_reel(val):
    data = json.dumps({'capital_reel': val})
    _, sha = gh_read(_CR_PATH)
    gh_write(_CR_PATH, data.encode(), f"update capital_reel={val}", sha)
    try:
        _CAPITAL_REEL_FILE.parent.mkdir(exist_ok=True)
        _CAPITAL_REEL_FILE.write_text(data)
    except Exception: pass

# ── Objectifs persistants (saisie manuelle) ───────────────────────────────
_OBJ_PATH = "ibkr_data/objectifs.json"

def load_objectifs():
    content, _ = gh_read(_OBJ_PATH)
    if content:
        try: return json.loads(content)
        except Exception: pass
    return {"obj_patrimoine": 80000, "obj_dca": 600}

def save_objectifs(obj_pat, obj_dca):
    data = json.dumps({"obj_patrimoine": obj_pat, "obj_dca": obj_dca})
    _, sha = gh_read(_OBJ_PATH)
    gh_write(_OBJ_PATH, data.encode(), f"update objectifs pat={obj_pat} dca={obj_dca}", sha)

# ── Snapshots mensuels (PV/MV + TRI) ─────────────────────────────────────
_SNAP_PATH = "ibkr_data/snapshots.json"

def load_snapshots():
    content, _ = gh_read(_SNAP_PATH)
    if content:
        try: return json.loads(content)
        except Exception: pass
    return {"snapshots": []}

def save_snapshot(pvmv, tri_global):
    """Ajoute ou met à jour le snapshot du mois en cours."""
    data = load_snapshots()
    snaps = data.get("snapshots", [])
    mois_key = datetime.now().strftime("%Y-%m")
    # Remplacer si déjà existant pour ce mois, sinon ajouter
    snaps = [s for s in snaps if s.get("date","")[:7] != mois_key]
    snaps.append({"date": datetime.now().strftime("%Y-%m-%d"), "pvmv": pvmv, "tri": tri_global})
    snaps.sort(key=lambda x: x["date"])
    payload = json.dumps({"snapshots": snaps}, ensure_ascii=False, indent=2)
    _, sha = gh_read(_SNAP_PATH)
    return gh_write(_SNAP_PATH, payload.encode(), f"snapshot {mois_key} pvmv={pvmv:.0f}", sha)

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
.stApp{{background:{C['bg']}}} 
.main .block-container{{padding:0 2rem 1.5rem 2rem !important;max-width:1400px}}
section[data-testid="stSidebar"]{{display:none}}
#MainMenu,footer,header{{visibility:hidden}} .stDeployButton{{display:none}}
div[data-testid="stDecoration"]{{display:none !important}}
div[data-testid="stHeader"]{{display:none !important}}
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
    from datetime import datetime as _dt; st.session_state["watchlist_last_refresh"] = _dt.now(__import__("zoneinfo").ZoneInfo("Europe/Paris")).strftime("%H:%M:%S")
    st.session_state["watchlist_updated_count"] = updated

# ── Taux EUR/USD live ────────────────────────────────
def get_eurusd_live():
    """Récupère le taux EUR/USD en temps réel via yfinance."""
    if not YF_AVAILABLE: return None
    try:
        fx = yf.Ticker("EURUSD=X").fast_info.last_price
        if fx and 0.8 < fx < 2.0:
            st.session_state['eurusd_live'] = fx
            return fx
    except: pass
    return st.session_state.get('eurusd_live', None)

# ── Refresh cours sous-jacents options ───────────────
def refresh_options_cours():
    """Récupère le cours live (yfinance) pour chaque sous-jacent des options ouvertes.
    Stocke 2 dicts :
      - options_cours_live_usd : {ticker: prix_usd}  → pour affichage et calcul marge
      - options_cours_live     : {ticker: prix_eur}  → pour compatibilité autres parties
    """
    if not YF_AVAILABLE: return
    ibkr_data = st.session_state.get('ibkr_data', {})
    if not ibkr_data: return
    tickers_set = set()
    for yr_data in ibkr_data.values():
        # Positions options ouvertes
        for t in yr_data.get('trades', []):
            if t.get('statut') == 'Ouverte':
                tickers_set.add(t.get('ticker', ''))
        # Actions détenues (pour tableau PRU ajusté)
        for ticker in yr_data.get('actions_detenues', {}).keys():
            tickers_set.add(ticker)
    tickers_set.discard('')
    if not tickers_set: return
    # Taux EUR/USD live
    try:
        _fx = yf.Ticker('EURUSD=X').fast_info.last_price or 1.16
    except: _fx = 1.16
    updated_usd = {}
    updated_eur = {}
    for ticker in tickers_set:
        try:
            tk  = yf.Ticker(ticker)
            fi  = tk.fast_info
            price_raw = getattr(fi, 'last_price', None) or getattr(fi, 'regular_market_price', None)
            cur = getattr(fi, 'currency', 'USD') or 'USD'
            if price_raw:
                price_usd = float(price_raw) if cur == 'USD' else float(price_raw) * _fx
                price_eur = price_usd / _fx
                updated_usd[ticker] = round(price_usd, 4)
                updated_eur[ticker] = round(price_eur, 4)
        except: pass
    if updated_usd:
        st.session_state['options_cours_live_usd'] = updated_usd
        st.session_state['options_cours_live']     = updated_eur
        from datetime import datetime as _dt
        from zoneinfo import ZoneInfo as _ZI
        st.session_state['options_cours_last_refresh'] = _dt.now(_ZI('Europe/Paris')).strftime('%H:%M:%S')

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

def sv(df, row, col):
    """Lecture sécurisée d'une cellule DataFrame — retourne 0.0 si indisponible."""
    try: return n(v(df, row, col))
    except Exception: return 0.0


def fmt(x): return f"{int(round(x)):,}".replace(",", " ") + " €"
def fmt2(x): return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", " ") + " €"

def xirr(cashflows):
    """cashflows: liste de (date: datetime, montant: float).
    Convention : versements = négatifs, valeur finale = positive.
    Retourne le taux annuel (en %) ou None si non résolvable."""
    if len(cashflows) < 2: return None
    t0 = cashflows[0][0]
    def npv(rate):
        total = 0.0
        for d, cf in cashflows:
            yrs = (d - t0).days / 365.25
            try:
                total += cf / (1 + rate) ** yrs
            except (OverflowError, ZeroDivisionError):
                return float('inf')
        return total
    lo, hi = -0.9999, 10.0
    f_lo, f_hi = npv(lo), npv(hi)
    if f_lo * f_hi > 0:
        return None
    for _ in range(100):
        mid = (lo + hi) / 2
        f_mid = npv(mid)
        if abs(f_mid) < 1e-6:
            return mid * 100
        if f_lo * f_mid < 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return ((lo + hi) / 2) * 100
def pct(x): return f"{'+' if x>=0 else ''}{x:.2f} %"
def pcol(x): return C['green'] if x >= 0 else C['red']

# ── Benchmarks indices (config + helpers mutualisés TRI vs indices) ──
BENCH_TICKERS = {
    "SP500":    ["^SP500TR", "^GSPC", "SPY"],
    "CAC 40":   ["PX1GR.PA", "^FCHI", "CAC.PA"],
    "STOXX 600":["^STOXX", "^SXXP", "MEUD.PA"],
}
BENCH_START = {"SP500": datetime(2022,2,4), "CAC 40": datetime(2022,2,4), "STOXX 600": datetime(2022,2,4)}

def dca_months(start_date, today):
    """Liste des dates DCA (le 4 de chaque mois) entre start_date et today inclus."""
    months = []
    d = start_date
    while d <= today:
        months.append(d)
        d = datetime(d.year + (1 if d.month == 12 else 0),
                     1 if d.month == 12 else d.month + 1, 4)
    return months

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_index_history(tickers_try, start_str, end_str):
    """Essaie plusieurs tickers jusqu'à en trouver un avec assez de données. Retourne (ticker_utilisé, DataFrame) ou (None, None)."""
    if not YF_AVAILABLE:
        return None, None
    for tk in tickers_try:
        try:
            df_h = yf.Ticker(tk).history(start=start_str, end=end_str, interval="1d")
            if df_h is not None and len(df_h) >= 100:
                return tk, df_h
        except Exception:
            continue
    return None, None

def price_at_or_before(df_h, target_date):
    """Renvoie le Close le plus proche disponible à target_date (ou juste avant)."""
    if df_h is None or len(df_h) == 0:
        return None
    idx = df_h.index
    target = pd.Timestamp(target_date)
    try:
        target = target.tz_localize(idx.tz) if idx.tz is not None else target
    except Exception:
        pass
    sub = df_h[df_h.index <= target]
    if len(sub) == 0:
        return float(df_h['Close'].iloc[0])
    return float(sub['Close'].iloc[-1])

MARKET_TICKERS = [
    ("SP500",    "^GSPC",  "🇺🇸"),
    ("CAC 40",   "^FCHI",  "🇫🇷"),
    ("STOXX 600","^STOXX", "🇪🇺"),
    ("BTC",      "BTC-USD","₿"),
]

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fear_greed():
    """Récupère le Fear & Greed Index CNN. Retourne dict {score, rating, prev_close} ou None."""
    try:
        import requests as _req
        _headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://edition.cnn.com/markets/fear-and-greed',
            'Accept': 'application/json',
        }
        _r = _req.get('https://production.dataviz.cnn.io/index/fearandgreed/graphdata', headers=_headers, timeout=6)
        if _r.status_code == 200:
            _d = _r.json()
            _fg = _d.get('fear_and_greed', {})
            return {
                'score': round(float(_fg.get('score', 0)), 0),
                'rating': _fg.get('rating', ''),
                'prev_close': round(float(_fg.get('previous_close', 0)), 0),
            }
    except Exception:
        pass
    return None

@st.cache_data(ttl=3600, show_spinner=False)
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_analyst_data(ticker: str):
    """Récupère le consensus analystes + dividendes pour un ticker via yfinance.
    Retourne dict {rec_mean, rec_label, rec_col, target_price, nb_analysts,
                   div_yield, div_rate, ex_div_date, last_div_date} ou None."""
    if not YF_AVAILABLE or not ticker:
        return None
    try:
        from datetime import date as _date
        tk = yf.Ticker(ticker)
        info = tk.info
        rec_mean = info.get('recommendationMean', None)
        target   = info.get('targetMeanPrice', None)
        nb       = info.get('numberOfAnalystOpinions', None)

        # Dividendes
        div_yield = info.get('dividendYield', None)      # float ex 0.008
        div_rate  = info.get('dividendRate', None)       # montant annuel $
        _ex_ts    = info.get('exDividendDate', None)     # timestamp UNIX
        _last_ts  = info.get('lastDividendDate', None)
        ex_div_date   = _date.fromtimestamp(int(_ex_ts))   if _ex_ts   else None
        last_div_date = _date.fromtimestamp(int(_last_ts)) if _last_ts else None

        if rec_mean is None and div_yield is None:
            return None

        # Label + couleur selon score 1→5
        if rec_mean is None:
            lbl, col = None, None
        elif rec_mean <= 1.5:   lbl, col = 'Strong Buy',   '#22C55E'
        elif rec_mean <= 2.5:   lbl, col = 'Buy',           '#84CC16'
        elif rec_mean <= 3.5:   lbl, col = 'Hold',          '#EAB308'
        elif rec_mean <= 4.5:   lbl, col = 'Underperform',  '#F97316'
        else:                    lbl, col = 'Sell',          '#EF4444'

        return {
            'rec_mean':     round(rec_mean, 1) if rec_mean else None,
            'rec_label':    lbl,
            'rec_col':      col,
            'target_price': round(float(target), 2) if target else None,
            'nb_analysts':  int(nb) if nb else None,
            'div_yield':    round((div_yield if div_yield > 1 else div_yield * 100), 2) if div_yield else None,   # en %
            'div_rate':     round(float(div_rate), 2) if div_rate else None,    # $ annuel
            'ex_div_date':  ex_div_date,
            'last_div_date': last_div_date,
        }
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dividend_calendar(tickers: tuple):
    """Retourne liste de dicts {ticker, ex_date, yield_pct, rate} triés par ex_date."""
    if not YF_AVAILABLE:
        return []
    from datetime import date as _date
    results = []
    today = _date.today()
    for tk_str in tickers:
        if not tk_str:
            continue
        try:
            data = fetch_analyst_data(tk_str)
            if data and data.get('ex_div_date') and data['ex_div_date'] >= today:
                results.append({
                    'ticker':    tk_str,
                    'ex_date':   data['ex_div_date'],
                    'yield_pct': data.get('div_yield'),
                    'rate':      data.get('div_rate'),
                })
        except Exception:
            continue
    results.sort(key=lambda x: x['ex_date'])
    return results


def fetch_earnings_calendar(tickers: tuple):
    """Récupère les prochains earnings pour une liste de tickers.
    Retourne liste de dicts {ticker, date, eps_est, rev_est} triés par date."""
    if not YF_AVAILABLE:
        return []
    results = []
    for tk_str in tickers:
        if not tk_str:
            continue
        try:
            tk = yf.Ticker(tk_str)
            # Méthode 1 : calendar dict
            cal = tk.calendar
            if cal and isinstance(cal, dict):
                ed = cal.get('Earnings Date')
                if ed:
                    # Peut être une liste ou une valeur unique
                    dates = ed if isinstance(ed, list) else [ed]
                    for d in dates:
                        try:
                            if hasattr(d, 'date'):
                                d = d.date()
                            elif isinstance(d, str):
                                from datetime import date as _date
                                d = _date.fromisoformat(d[:10])
                            from datetime import date as _date
                            if d >= _date.today():
                                results.append({
                                    'ticker': tk_str,
                                    'date': d,
                                    'eps_est': cal.get('Earnings Average', None),
                                    'rev_est': cal.get('Revenue Average', None),
                                })
                                break
                        except Exception:
                            continue
            # Méthode 2 : earnings_dates
            if not any(r['ticker'] == tk_str for r in results):
                ed2 = tk.earnings_dates
                if ed2 is not None and len(ed2) > 0:
                    from datetime import date as _date, timezone
                    for idx_d, row in ed2.iterrows():
                        try:
                            if hasattr(idx_d, 'date'):
                                d2 = idx_d.date()
                            else:
                                d2 = _date.fromisoformat(str(idx_d)[:10])
                            if d2 >= _date.today():
                                results.append({
                                    'ticker': tk_str,
                                    'date': d2,
                                    'eps_est': row.get('EPS Estimate', None),
                                    'rev_est': None,
                                })
                                break
                        except Exception:
                            continue
        except Exception:
            continue
    # Trier par date
    results.sort(key=lambda x: x['date'])
    return results


@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_history(ticker, period, interval):
    """Retourne {"prix": dernier close, "var_pct": variation sur la période, "serie": liste de closes} ou None."""
    if not YF_AVAILABLE:
        return None
    try:
        if period == "1d":
            tk_obj = yf.Ticker(ticker)
            # previous_close = clôture officielle J-1, exactement comme Yahoo Finance
            try:
                fi = tk_obj.fast_info
                prix_veille = float(fi.previous_close)
                prix_actuel = float(fi.last_price)
            except Exception:
                prix_veille = None
                prix_actuel = None

            # Fallback si fast_info échoue
            if not prix_veille or not prix_actuel:
                h_day = tk_obj.history(period="5d", interval="1d")
                if h_day is None or len(h_day) < 2: return None
                closes_day = h_day['Close'].dropna().tolist()
                prix_veille  = closes_day[-2]
                prix_actuel  = closes_day[-1]

            # Série intraday pour sparkline
            _intr_interval = "15m" if ticker == "BTC-USD" else "5m"
            h_intr = tk_obj.history(period="1d", interval=_intr_interval)
            if h_intr is not None and len(h_intr) >= 2:
                serie = h_intr['Close'].dropna().tolist()
            else:
                serie = [prix_veille, prix_actuel]

            var_pct = (prix_actuel / prix_veille - 1) * 100 if prix_veille else 0
            return {"prix": prix_actuel, "var_pct": var_pct, "serie": serie, "ref": prix_veille}

        h = yf.Ticker(ticker).history(period=period, interval=interval)
        if h is None or len(h) < 2:
            return None
        closes = h['Close'].dropna().tolist()
        if len(closes) < 2:
            return None
        prix_actuel = closes[-1]
        prix_debut  = closes[0]
        var_pct = (prix_actuel / prix_debut - 1) * 100 if prix_debut else 0
        return {"prix": prix_actuel, "var_pct": var_pct, "serie": closes}
    except Exception:
        return None


def card(title, value, sub="", color=C['blue'], icon="", sub2=""):
    s1 = f"<div style='font-size:12px;color:{color};min-height:17px'>{sub}</div>"
    s2 = "<div style='font-size:11px;color:" + C['muted'] + ";min-height:15px'>" + str(sub2) + "</div>"
    return f"""<div style="background:{C['card']};border:1px solid {C['border']};border-top:2px solid {color};border-radius:10px;padding:14px 18px;height:118px;box-sizing:border-box;display:flex;flex-direction:column">
<div style="font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px">{icon} {title}</div>
<div style="font-family:'Space Grotesk';font-size:22px;font-weight:700;color:{C['text']};line-height:1.2;flex:1">{value}</div>
{s1}{s2}
</div>"""


def card_editable(title, value, sub="", color=C['teal'], icon=""):
    """Carte KPI identique à card() mais avec un espace pour le popover crayon."""
    return (
        f"<div style='background:{C['card']};border:1px solid {C['border']};"
        f"border-top:2px solid {color};border-radius:10px;padding:14px 18px;"
        f"height:118px;box-sizing:border-box;display:flex;flex-direction:column'>"
        f"<div style='font-size:10px;color:{C['muted']};text-transform:uppercase;"
        f"letter-spacing:.08em;margin-bottom:4px'>{icon} {title}</div>"
        f"<div style='font-family:Space Grotesk;font-size:22px;font-weight:700;"
        f"color:{C['text']};line-height:1.2;flex:1'>{value}</div>"
        f"<div style='font-size:12px;color:{color};min-height:17px'>{sub}</div>"
        f"</div>"
    )

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

# ── Header bannière ─────────────────────────────────────
from zoneinfo import ZoneInfo as _ZI
_TZ_PARIS = _ZI("Europe/Paris")
_paris_h  = datetime.now(_TZ_PARIS)
_hnow     = _paris_h.strftime("%H:%M")
_YR = _paris_h.year

_BNR = "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"

st.markdown(f'''<style>
.block-container{{padding-top:0!important}}
section.main > div{{padding-top:0!important}}
</style>
<div style="position:relative;width:calc(100% + 4rem);margin-left:-2rem;height:140px;overflow:hidden;margin-bottom:8px">
<img src="data:image/png;base64,{_BNR}" style="width:100%;height:100%;object-fit:cover;object-position:center 40%;display:block"/>
<div style="position:absolute;top:0;left:0;height:100%;width:30%;background:linear-gradient(to right,rgba(10,14,23,0.88) 40%,transparent)"></div>
<div style="position:absolute;top:0;right:0;height:100%;width:40%;background:linear-gradient(to left,rgba(10,14,23,0.85) 40%,transparent)"></div>
<div style="position:absolute;left:16px;bottom:14px;display:flex;align-items:center;gap:10px">
<img src="data:image/png;base64,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" style="width:36px;height:36px;object-fit:cover;border-radius:8px"/>
<span style="font-family:Space Grotesk,sans-serif;font-size:20px;font-weight:700;color:#e6edf3">SamInvest</span>
</div>
<div style="position:absolute;right:140px;bottom:10px;display:flex;align-items:center;gap:12px">
<div style="display:flex;align-items:center;gap:5px">
<div style="width:7px;height:7px;border-radius:50%;background:#3FB950;box-shadow:0 0 7px #3FB950"></div>
<span style="font-size:11px;color:#cdd9e5;font-weight:600;letter-spacing:.04em">Live Data</span>
</div>
<div style="width:1px;height:20px;background:rgba(255,255,255,0.2)"></div>
<div>
<div style="font-size:9px;color:#8b949e;text-transform:uppercase;letter-spacing:.06em">Données synchronisées</div>
<div style="font-size:14px;font-weight:700;color:#e6edf3;font-family:Space Grotesk,sans-serif">{_hnow}</div>
</div>
</div>
</div>''', unsafe_allow_html=True)

_rbtn = st.columns([8, 1, 1, 1])
with _rbtn[1]:
    # ── Backup JSON ──
    _backup = {
        "export_date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "capital_reel": st.session_state.get("capital_reel", 0.0),
        "objectifs": {
            "obj_patrimoine": st.session_state.get("obj_patrimoine", 80000),
            "obj_dca":        st.session_state.get("obj_dca", 600),
        },
        "watchlist": {
            "wl_portefeuille": st.session_state.get("wl_portefeuille", []),
            "wl_options":      st.session_state.get("wl_options", []),
            "wl_surveillance": st.session_state.get("wl_surveillance", []),
        },
        "ibkr_annees": list(st.session_state.get("ibkr_data", {}).keys()),
        "ibkr_kpis": {
            k: v for k, v in st.session_state.get("ibkr_kpis", {}).items()
            if isinstance(v, (int, float, str, list, dict, type(None)))
               and k not in ("dernier_depot",)
        },
    }
    st.download_button("💾 Backup", data=json.dumps(_backup, ensure_ascii=False, indent=2),
        file_name=f"saminvest_backup_{datetime.now().strftime('%Y%m%d')}.json",
        mime="application/json", use_container_width=True,
        help="Télécharge un backup JSON de toutes tes données persistantes")
with _rbtn[2]:
    # ── Snapshot mensuel ──
    _snap_label = "📸 Snapshot"
    _snaps_exist = load_snapshots().get("snapshots", [])
    _mois_actuel = datetime.now().strftime("%Y-%m")
    _deja_snap = any(s.get("date","")[:7] == _mois_actuel for s in _snaps_exist)
    if st.button(f"{'✅' if _deja_snap else '📸'} Snapshot", key="snapshot_btn",
                  use_container_width=True,
                  help=f"Enregistre la PV/MV + TRI du mois{' (déjà fait ce mois-ci)' if _deja_snap else ''}"):
        _pvmv_snap = st.session_state.get('tri_global', {}).get('valeur_actuelle_totale', 0) - \
                     st.session_state.get('tri_global', {}).get('valeur_investie_totale', 0)
        _tri_snap  = st.session_state.get('tri_global', {}).get('tri_global')
        if save_snapshot(_pvmv_snap, _tri_snap):
            st.toast(f"✅ Snapshot {_mois_actuel} sauvegardé !", icon="📸")
            st.session_state.pop('_snaps_cache', None)
            st.rerun()
        else:
            st.toast("⚠️ Erreur lors du snapshot", icon="⚠️")
with _rbtn[3]:
    if st.button("↻ Rafraîchir", key="global_refresh_btn", use_container_width=True,
        help="Rafraîchit Google Sheet + cours live"):
        refresh_watchlist_cours()
        refresh_options_cours()
        get_eurusd_live()
        st.cache_data.clear()
        st.rerun()


# ══════════════════════════════════════════════════════
# PARSING & DONNÉES IBKR (défini AVANT les onglets pour
# que tab1/tab5 voient ibkr_data et ibkr_kpis dès le 1er run)
# ══════════════════════════════════════════════════════
def parse_ibkr_html(content_bytes):
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None

    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try: text = content_bytes.decode(enc); break
        except: continue
    else: text = content_bytes.decode('latin-1', errors='replace')

    soup = BeautifulSoup(text, 'html.parser')
    tables = soup.find_all('table')

    def sf(val):
        """safe float"""
        v = str(val).strip().replace('\xa0','').replace(',','').replace(' ','')
        if not v or v in ('--','-',''):  return 0.0
        try: return float(v)
        except: return 0.0

    def get_rows(tbl):
        """Retourne toutes les lignes comme listes de strings."""
        rows = []
        for tr in tbl.find_all('tr'):
            cells = [td.get_text(separator=' ', strip=True).replace('\xa0',' ')
                     for td in tr.find_all(['td','th'])]
            if any(c.strip() for c in cells):
                rows.append(cells)
        return rows

    def find_table(keyword_row):
        """Trouve une table dont une des premières lignes contient tous les mots-clés."""
        for tbl in tables:
            rows = get_rows(tbl)
            for row in rows[:3]:
                joined = '|'.join(row)
                if all(kw in joined for kw in keyword_row):
                    return tbl, rows
        return None, []

    # ── Initialisation ──────────────────────────────────
    year             = None
    trades           = []
    positions_ouvertes = []
    actif_net        = None
    depots           = 0.0
    synthese_realise   = {}   # {sym: total réalisé €}
    synthese_profit_ct = {}   # {sym: profit CT €}
    synthese_perte_ct  = {}   # {sym: perte CT €}
    synthese_prime_enc = {}   # {sym: prime encaissée EUR (Profit ou Perte C/T selon signe)}
    synthese_nonrealise= {}   # {sym: non-réalisé total €}
    cours_sous_jacents = {}   # {ticker: cours €}

    # ── Année depuis table infos compte ─────────────────
    for tbl in tables:
        rows = get_rows(tbl)
        for row in rows[:3]:
            joined = '|'.join(row)
            # "May 29, 2026" ou "December 31, 2025"
            import re as _re
            m = _re.search(r'(\d{4})', joined)
            if m and 'January' in joined or 'February' in joined or \
               'March' in joined or 'April' in joined or 'May' in joined or \
               'June' in joined or 'July' in joined or 'August' in joined or \
               'September' in joined or 'October' in joined or 'November' in joined or \
               'December' in joined:
                years_found = _re.findall(r'(20\d\d)', joined)
                if years_found:
                    year = int(max(years_found))  # année la plus récente
                    break
        if year: break

    # ── Synthèse réalisée/non-réalisée ──────────────────
    # Table avec "Realisé" dans les premières lignes
    # Colonnes identifiées par leur NOM dans le header → robuste à tous les formats IBKR
    tbl_synth, rows_synth = find_table(['Realisé'])
    if tbl_synth:
        for hrow in rows_synth[:3]:
            joined = '|'.join(hrow)
            if 'Profit C/T' in joined or 'Total' in joined:
                # Chercher les indices par position dans la section Réalisé
                # Structure stable : [Sym, Aj.coût, ProfitCT, PerteC T, ProfitLT, PerteLT, Total_Réal, ...]
                # col[2]=ProfitCT, col[3]=PerteCT, col[6]=TotalRéal sont TOUJOURS aux mêmes positions
                # car ils sont dans la PREMIÈRE moitié (section Réalisé)
                # Le Non-Réalisé est dans la DEUXIÈME moitié → col[-2] = avant-dernier (hors Code)
                break

        in_options = False
        for row in rows_synth[2:]:  # skip 2 lignes d'en-tête
            if not row or not row[0].strip(): continue
            sym = row[0].strip()
            if sym == 'Options sur actions et indices': in_options = True; continue
            if sym in ('Actions','Forex','Total (Tous les actifs)','Total Actions',
                       'Total Forex','Total Options sur actions et indices'):
                if sym != 'Options sur actions et indices': in_options = False
                continue
            if not in_options: continue
            if sym.startswith('Total'): continue
            n = len(row)
            if n < 7: continue
            # Positions stables dans TOUS les formats IBKR :
            profit_ct  = sf(row[2])   # col[2] = Profit C/T réalisé
            perte_ct   = sf(row[3])   # col[3] = Perte C/T réalisé
            total_real = sf(row[6])   # col[6] = Total Réalisé
            nonreal    = sf(row[-2]) if n >= 9 else 0.0
            # Prime encaissée EUR par symbole = valeur non-nulle (Profit ou Perte C/T)
            # Positif = trades gagnants (prime > coût rachat)
            # Négatif = trades perdants/roulés (coût rachat > prime reçue)
            prime_enc_eur = profit_ct if profit_ct != 0.0 else perte_ct
            synthese_realise[sym]      = total_real
            synthese_profit_ct[sym]    = profit_ct
            synthese_perte_ct[sym]     = perte_ct
            synthese_nonrealise[sym]   = nonreal
            synthese_prime_enc[sym]    = prime_enc_eur

    # ── Cours sous-jacents depuis synthèse évaluée ──────
    # Table avec "Quantité|Prix|Pertes et profits"
    tbl_eval, rows_eval = find_table(['Quantité','Prix','Pertes et profits'])
    if tbl_eval:
        in_actions = False
        for row in rows_eval[2:]:
            if not row: continue
            sym = row[0].strip()
            if sym == 'Actions': in_actions = True; continue
            if sym in ('Options sur actions et indices','Forex','Total Actions',
                       'Total (Tous les actifs)','Total Forex','Other Fees',
                       'P/L Total pour période relevé de compte'): in_actions = False; continue
            if not in_actions or sym.startswith('Total') or not sym: continue
            # Cours actuel = col[4] (prix courant)
            if len(row) > 4:
                cours = sf(row[4])
                if cours > 0:
                    cours_sous_jacents[sym] = cours

    # ── Taux EUR/USD depuis transactions Forex ──────────────────────────────
    fx_eur_usd = 1.10  # fallback
    tbl_tx_all, rows_tx_all = find_table(['Symbole','Date/Heure','Quantité','Prix trans.'])
    if tbl_tx_all:
        _fx_list = [sf(_r[3]) for _r in rows_tx_all if _r[0].strip() == 'EUR.USD' and len(_r) > 3]
        _fx_list = [x for x in _fx_list if 0.8 < x < 2.0]
        if _fx_list: fx_eur_usd = sum(_fx_list)/len(_fx_list)

    # ── Transactions (trades) ────────────────────────────
    # Table avec "Symbole|Date/Heure|Quantité|Prix trans."
    tbl_tx, rows_tx = find_table(['Symbole','Date/Heure','Quantité','Prix trans.'])
    if tbl_tx:
        import re as _re
        OPT_SECTION = False
        for row in rows_tx[1:]:
            if not row: continue
            sym = row[0].strip()
            # Détection section Options
            if sym == 'Options sur actions et indices': OPT_SECTION = True; continue
            if sym in ('Actions','Forex','Contrats à terme'): OPT_SECTION = False; continue
            if not OPT_SECTION: continue
            # Sauter les lignes Total et les en-têtes
            if sym.startswith('Total') or sym == 'Symbole' or not sym: continue
            if len(row) < 9: continue

            date_str = row[1].split(',')[0].strip() if len(row) > 1 else ''
            qty      = sf(row[2])
            prix     = sf(row[3])
            produit  = sf(row[5])
            comm     = sf(row[6])
            code     = row[10].strip() if len(row) > 10 else ''

            if 'Ep' in code:              statut = 'Expirée'
            elif 'A' in code:             statut = 'Assignée'
            elif qty > 0 and 'C' in code: statut = 'Fermée'
            elif qty < 0:                 statut = 'Ouverte'
            else:                         statut = 'Clôturée'

            sp = sym.split()
            cp = sp[-1] if sp else ''
            lbl = 'Put' if cp == 'P' else 'Call'
            type_trade = f"{'Vente' if qty < 0 else 'Achat'} {lbl}" if cp in ('P','C') else ''

            trades.append({
                'symbole':    sym,
                'ticker':     sp[0] if sp else sym,
                'call_put':   cp,
                'strike':     sp[-2] if len(sp) >= 3 else '',
                'expiration': sp[1]  if len(sp) >= 2 else '',
                'date':       date_str,
                'quantite':   qty,
                'prix':       prix,
                'produit':    produit,
                'produit_eur':abs(produit)/fx_eur_usd if qty < 0 and produit != 0 else 0.0,
                'frais':      comm,
                'pl_realise': 0.0,  # sera rempli depuis synthèse
                'statut':     statut,
                'code':       code,
                'type_trade': type_trade,
                'annee':      year,
            })

    # ── Frais par symbole depuis synthèse évaluée (Table 3, col Commissions) ──
    # C'est la source de vérité : frais nets en EUR par option
    frais_par_sym = {}  # {sym: frais_eur}
    tbl_eval2, rows_eval2 = find_table(['Quantité','Prix','Pertes et profits'])
    if tbl_eval2:
        in_opts2 = False
        for row in rows_eval2[2:]:
            if not row: continue
            sym = row[0].strip()
            if sym == 'Options sur actions et indices': in_opts2 = True; continue
            if sym in ('Actions','Forex','Total (Tous les actifs)','Total Actions',
                       'Total Forex','Total Options sur actions et indices',
                       'Other Fees','P/L Total pour période relevé de compte'):
                if 'Total Options' in sym:
                    in_opts2 = False; continue
            if not in_opts2 or sym.startswith('Total') or not sym: continue
            if len(row) > 7:
                comm = abs(sf(row[7]))  # col[7] = Commissions
                if comm > 0:
                    frais_par_sym[sym] = comm

    # ── Détecter les roulages (fermeture + ouverture le même jour) ─────────
    # Une option est ROULÉE si elle a été rachetée (code='C') et qu'une nouvelle
    # option a été ouverte (code contient 'O') le même jour dans ce relevé
    _ouvertures_par_date = {}  # {date: [sym]}
    _fermetures_C = {}         # {sym: date_rachat}
    for t in trades:
        date = t['date']
        code = t['code']
        qty  = t['quantite']
        sym  = t['symbole']
        if qty < 0 and 'O' in code:
            _ouvertures_par_date.setdefault(date, []).append(sym)
        elif qty > 0 and code.strip() == 'C':
            _fermetures_C[sym] = date

    # Symboles roulés = rachetés ET remplacés le même jour
    _syms_roules = set()
    for sym, date_close in _fermetures_C.items():
        nouvelles = [s for s in _ouvertures_par_date.get(date_close, []) if s != sym]
        if nouvelles:
            _syms_roules.add(sym)

    # ── Injecter P/L, frais ET statut définitif depuis Synthèse ──────────
    # La Synthèse est la source de vérité absolue pour le statut :
    #   réal_total ≠ 0  → option clôturée dans ce relevé
    #   nonreal_total ≠ 0 → option encore ouverte dans ce relevé
    # Cela résout le problème cross-year : une option vendue en 2025 et
    # expirée en 2026 sera "Ouverte" dans HTML 2025 et "Clôturée" dans HTML 2026.
    by_sym = {}
    for t in trades:
        by_sym.setdefault(t['symbole'], []).append(t)

    for sym, sym_trades in by_sym.items():
        real_pl   = synthese_realise.get(sym)
        nonreal   = synthese_nonrealise.get(sym)   # None si absent (≠ 0.0)
        frais_sym = frais_par_sym.get(sym, 0.0)

        # Pré-détection des assignées via code 'A' dans transactions
        # IBKR ne les met pas dans la Synthèse Options → pl_option=0 par convention
        _has_assignment = any('A' in t.get('code','') for t in sym_trades)

        # Statut définitif depuis Synthèse + détection roulages
        # Assignées : code 'A' présent ET pas dans Synthèse Options (real_pl=None)
        if _has_assignment and real_pl is None:
            statut_final = 'Assignée'
        elif real_pl is not None and real_pl != 0.0:
            # Option clôturée → déterminer le type exact
            close_t = next((t for t in sym_trades if t['quantite'] > 0), None)
            if close_t:
                code_close = close_t.get('code','')
                if 'Ep' in code_close:
                    statut_final = 'Expirée'
                elif 'A' in code_close:
                    statut_final = 'Assignée'
                elif sym in _syms_roules:
                    statut_final = 'Roulée'
                elif code_close.strip() == 'C':
                    statut_final = 'Fermée'
                else:
                    statut_final = 'Clôturée'
            else:
                # Pas de trade de fermeture dans ce relevé (cross-year)
                statut_final = 'Expirée' if real_pl >= 0 else 'Fermée'
        elif nonreal != 0.0 or (real_pl == 0.0 and nonreal == 0.0 and real_pl is not None):
            statut_final = 'Ouverte'
        else:
            # Pas dans la synthèse → code transaction
            close_t = next((t for t in sym_trades if t['quantite'] > 0), None)
            if close_t:
                code_close = close_t.get('code','')
                if 'Ep' in code_close:    statut_final = 'Expirée'
                elif 'A'  in code_close:  statut_final = 'Assignée'
                elif sym in _syms_roules: statut_final = 'Roulée'
                else:                     statut_final = 'Fermée'
            else:
                statut_final = 'Ouverte'

        # Prime encaissée EUR depuis Synthèse (Profit ou Perte C/T selon signe)
        prime_enc_sym = synthese_prime_enc.get(sym, 0.0)
        # Mettre à jour tous les trades du symbole
        for t in sym_trades:
            t['statut']        = statut_final
            t['frais']         = frais_sym
            t['prime_enc_eur'] = prime_enc_sym

        # P/L sur le dernier trade de fermeture (tous statuts clôturés)
        if real_pl is not None:
            close_trades = [t for t in sym_trades
                            if t['statut'] in ('Expirée','Fermée','Assignée','Clôturée','Roulée')]
            if close_trades:
                close_trades[-1]['pl_realise'] = real_pl

    # ── Positions ouvertes options + actions détenues ────────
    actions_detenues = {}  # {ticker: {quantite, pru_classique, valeur}}
    tbl_pos, rows_pos = find_table(['Symbole','Quantité','Mult','Coût'])
    if tbl_pos:
        in_opts = False
        in_actions = False
        for row in rows_pos:
            if not row: continue
            sym = row[0].strip()
            if sym == 'Actions': in_actions = True; in_opts = False; continue
            if sym == 'Options sur actions et indices': in_opts = True; in_actions = False; continue
            if sym in ('Total','Total en EUR','Symbole','USD','EUR','Forex',
                       'Total Actions','Total Options sur actions et indices'): continue
            if sym.startswith('Total') or not sym: continue
            if len(row) < 7: continue
            if in_actions:
                qty      = sf(row[1])
                pru_ibkr = sf(row[3])   # col[3] = prix unitaire (Coût moyen IBKR)
                prix     = sf(row[5])   # col[5] = cours de clôture
                valeur   = sf(row[6])
                if qty != 0 and pru_ibkr > 0:
                    actions_detenues[sym] = {
                        'ticker':        sym,
                        'quantite':      qty,
                        'pru_classique': pru_ibkr,
                        'cours':         prix,
                        'valeur':        valeur,
                        'annee':         year,
                    }
            if in_opts:
                positions_ouvertes.append({
                    'symbole':   sym,
                    'quantite':  sf(row[1]),
                    'cours':     sf(row[5]),
                    'valeur':    sf(row[6]),
                    'pl_unreal': sf(row[7]) if len(row) > 7 else 0.0,
                    'annee':     year,
                })

    # ── Actif net (depuis table infos compte) ─────────────
    for tbl in tables:
        rows = get_rows(tbl)
        for row in rows:
            if 'Total' in row[0] and len(row) >= 4:
                v = sf(row[3]) if len(row) > 3 else 0.0
                if v > 1000: actif_net = v; break

    # ── Achats actions (pour PRU classique réel) ─────────────
    # Source : table transactions (Symbole/Date/Heure/Quantité/Prix trans.)
    # On prend qty > 0 dans la section Actions = achats réels au prix de marché
    achats_actions = {}  # {ticker: {'qty_total': x, 'cout_total': y}}
    tbl_tx2, rows_tx2 = find_table(['Symbole','Date/Heure','Quantité','Prix trans.'])
    if tbl_tx2:
        in_act2 = False
        for row in rows_tx2[1:]:
            sym2 = row[0].strip() if row else ''
            if sym2 == 'Actions': in_act2 = True; continue
            if sym2 in ('Options sur actions et indices','Forex','Contrats à terme'): in_act2 = False; continue
            if not in_act2 or not sym2 or sym2 == 'Symbole': continue
            if sym2.startswith('Total'): continue
            # Ignorer les options (leur symbole contient des espaces ex: "MARA 23JAN26 8 P")
            if ' ' in sym2: continue
            if len(row) < 4: continue
            qty2   = sf(row[2])
            prix2  = sf(row[3])
            comm2  = abs(sf(row[6])) if len(row) > 6 else 0.0  # Comm/Tarif (toujours négatif dans IBKR)
            if qty2 != 0 and prix2 > 0:
                if sym2 not in achats_actions:
                    achats_actions[sym2] = {'qty_total': 0.0, 'cout_total': 0.0}
                achats_actions[sym2]['qty_total']  += qty2
                # Coût = prix × qty + commissions (comme IBKR dans "Coût d'acquisition")
                achats_actions[sym2]['cout_total'] += qty2 * prix2 + (comm2 if qty2 > 0 else -comm2)
    tbl_dep, rows_dep = find_table(['Date', 'Description', 'Montant'])
    depots_detail = []
    if tbl_dep:
        in_eur = False
        for row in rows_dep[1:]:
            if not row: continue
            label = row[0].strip()
            if label == 'EUR':   in_eur = True;  continue
            if label == 'USD':   in_eur = False; continue
            if label.startswith('Total'): in_eur = False; continue
            if in_eur and len(row) >= 3:
                v = sf(row[-1])
                if v > 0:
                    depots += v
                    depots_detail.append((label, v))

    return {
        'year':               year,
        'trades':             trades,
        'positions':          positions_ouvertes,
        'actif_net':          actif_net,
        'frais':              sum(frais_par_sym.values()),  # frais options en EUR
        'fx':                 fx_eur_usd,  # taux EUR/USD du relevé
        'depots':             depots,
        'depots_detail':      depots_detail,
        'synthese_realise':   synthese_realise,
        'synthese_profit_ct': synthese_profit_ct,
        'synthese_prime_enc': synthese_prime_enc,
        'syms_in_synthese':  set(synthese_realise.keys()) | set(synthese_nonrealise.keys()),
        'synthese_perte_ct':  synthese_perte_ct,
        'synthese_nonrealise':synthese_nonrealise,
        'cours_sous_jacents': cours_sous_jacents,
        'frais_par_sym':     frais_par_sym,
        'actions_detenues':  actions_detenues,
        'achats_actions':     achats_actions,
    }



def get_trade_statut_final(sym, all_trades):
    """Détermine le statut final d'une option à partir de tous ses trades."""
    sym_trades = [t for t in all_trades if t['symbole'] == sym]
    codes = ' '.join(t.get('code','') for t in sym_trades)
    if 'Ep' in codes: return 'Expirée'
    net_qty = sum(t['quantite'] for t in sym_trades)
    if abs(net_qty) < 0.01:
        close_trades = [t for t in sym_trades if t['quantite'] > 0 and 'Ep' not in t.get('code','')]
        if close_trades: return 'Roulée'
        return 'Fermée'
    return 'Ouverte'


def get_type_trade(sym, all_trades):
    """Retourne le type du trade d'ouverture (Vente Put / Vente Call / etc.)."""
    sym_trades = [t for t in all_trades if t['symbole'] == sym]
    # Trade d'ouverture = qty < 0
    open_trade = next((t for t in sym_trades if t['quantite'] < 0), None)
    if open_trade:
        return open_trade.get('type_trade', '')
    # Fallback depuis le symbole
    sp = sym.split()
    cp = sp[-1] if sp else ''
    label = 'Put' if cp == 'P' else 'Call'
    return f"Vente {label}"


# ── Dossier de stockage persistant des fichiers IBKR ──
IBKR_DIR = Path(__file__).parent / "ibkr_data"
IBKR_DIR.mkdir(exist_ok=True)

def _ensure_ibkr_dir_on_github():
    """Crée le dossier ibkr_data/ sur GitHub s'il n'existe pas (via .gitkeep)."""
    if not _GH_TOKEN: return
    files = gh_list("ibkr_data")
    if not files:
        gh_write("ibkr_data/.gitkeep", b"", "init ibkr_data folder")

_ensure_ibkr_dir_on_github()

def restore_ibkr_from_github():
    """Télécharge les HTML IBKR depuis GitHub vers le filesystem local si manquants."""
    if not _GH_TOKEN: return
    files = gh_list("ibkr_data")
    for f in files:
        if not (f["name"].endswith(".htm") or f["name"].endswith(".html")):
            continue
        local = IBKR_DIR / f["name"]
        if not local.exists():
            content, _ = gh_read(f["path"])
            if content:
                local.write_bytes(content)

def load_all_ibkr():
    """Charge et parse tous les fichiers HTML présents sur le disque."""
    data = {}
    for html_file in sorted(list(IBKR_DIR.glob("*.htm")) + list(IBKR_DIR.glob("*.html"))):
        try:
            parsed = parse_ibkr_html(html_file.read_bytes())
            if parsed and parsed['year']:
                data[parsed['year']] = parsed
        except Exception:
            pass
    return data

def compute_ibkr_kpis(ibkr_data, **kwargs):
    """Calcule tous les KPIs globaux depuis l ensemble des CSV chargés.
    Toutes les valeurs sont en EUR (les HTML IBKR sont déjà en EUR via Synthèse)."""
    all_trades = []
    for yr_data in ibkr_data.values():
        all_trades.extend(yr_data.get('trades', []))

    # Capital investi = somme de tous les dépôts EUR
    capital_investi = sum(d.get('depots', 0.0) for d in ibkr_data.values())

    # Dernier versement de cash (date + montant), tous fichiers confondus
    _all_depots_detail = []
    for yr_data in ibkr_data.values():
        _all_depots_detail.extend(yr_data.get('depots_detail', []))
    dernier_depot = None
    if _all_depots_detail:
        from datetime import datetime as _dt_dep
        _parsed_depots = []
        for _lbl, _amt in _all_depots_detail:
            _dm = None
            for _fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    _dm = _dt_dep.strptime(_lbl[:10], _fmt)
                    break
                except ValueError:
                    continue
            if _dm:
                _parsed_depots.append((_dm, _amt))
        if _parsed_depots:
            _parsed_depots.sort(key=lambda x: x[0])
            _last_dt, _last_amt = _parsed_depots[-1]
            _MOIS_F_LOCAL = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
            dernier_depot = {"date": _last_dt, "montant": _last_amt,
                             "mois": _MOIS_F_LOCAL[_last_dt.month-1], "annee": _last_dt.year}

    # Primes nettes EUR = P&L réalisé net (gains - pertes)
    primes_nettes_eur = sum(t['pl_realise'] for t in all_trades)

    # Taux FX moyen des CSV (calculé avant le fallback)
    fx_rates = [d.get('fx', 1.16) for d in ibkr_data.values() if 0.8 <= d.get('fx', 0) <= 1.8]
    fx = sum(fx_rates) / len(fx_rates) if fx_rates else 1.16

    # Taux EUR/USD : live si disponible, sinon taux moyen des CSV
    fx_live = kwargs.get('fx_live', None)
    fx_historique = fx_live if fx_live and 0.8 < fx_live < 2.0 else fx

    # Primes brutes encaissées = somme des Profit C/T > 0 de la Synthèse IBKR
    # = primes des trades gagnants uniquement (hors rachats perdants des roulements)
    primes_brutes_eur = sum(
        v for d in ibkr_data.values()
        for v in d.get('synthese_profit_ct', {}).values()
        if v > 0
    )
    primes_brutes_usd = primes_brutes_eur * fx_historique

    # Capital actuel = capital investi + primes nettes
    capital_actuel = capital_investi + primes_nettes_eur

    # ROI = primes nettes / capital investi
    roi = (primes_nettes_eur / capital_investi * 100) if capital_investi > 0 else 0.0

    return {
        'capital_investi':  capital_investi,
        'primes_nettes_eur':primes_nettes_eur,
        'primes_brutes_eur':primes_brutes_eur,  # EUR brut Profit C/T
        'primes_brutes_usd':primes_brutes_usd,  # USD ≈ valeur Google Sheet
        'capital_actuel':   capital_actuel,
        'roi':              roi,
        'fx':               fx,
        'dernier_depot':    dernier_depot,
    }

# ── Chargement initial depuis disque (persistant entre sessions) ──
# Forcer le rechargement si la version du parser a changé
if 'ibkr_data' not in st.session_state:
    restore_ibkr_from_github()  # restaure les HTML depuis GitHub si filesystem vide
    st.session_state['ibkr_data'] = load_all_ibkr()
    st.session_state.pop('options_auto_refreshed', None)

# ── Auto-refresh cours live au premier chargement de la session ──
if not st.session_state.get('options_auto_refreshed', False) and YF_AVAILABLE:
    if st.session_state.get('ibkr_data'):
        refresh_options_cours()
        get_eurusd_live()
        st.session_state['options_auto_refreshed'] = True



if 'capital_reel' not in st.session_state:
    st.session_state['capital_reel'] = load_capital_reel()

# Resync depuis GitHub au démarrage de session (une seule fois)
if st.session_state.get('_cr_loaded') is None:
    st.session_state['capital_reel'] = load_capital_reel()
    _obj = load_objectifs()
    st.session_state.setdefault('obj_patrimoine', _obj.get('obj_patrimoine', 80000))
    st.session_state.setdefault('obj_dca',        _obj.get('obj_dca', 600))
    st.session_state['_cr_loaded'] = True

# ── Chargement watchlist depuis GitHub (une seule fois par session) ──
if st.session_state.get('_wl_loaded') is None:
    _wl_gh_init = load_watchlist_gh()
    st.session_state['wl_portefeuille']  = _wl_gh_init.get('wl_portefeuille', [])
    st.session_state['wl_options']       = _wl_gh_init.get('wl_options', [])
    st.session_state['wl_surveillance']  = _wl_gh_init.get('wl_surveillance', [])
    st.session_state['watchlist'] = (st.session_state['wl_portefeuille'] +
                                     st.session_state['wl_options'] +
                                     st.session_state['wl_surveillance'])
    st.session_state['_wl_loaded'] = True


# Calcul des KPIs IBKR dès l'init → disponibles dans tous les onglets au 1er run
st.session_state['ibkr_kpis'] = compute_ibkr_kpis(
    st.session_state['ibkr_data'],
    fx_live=st.session_state.get('eurusd_live', None))

# ── Calcul TRI Global (Bourse+Crypto+Options) + benchmarks indices — une seule fois ──
def _compute_tri_global_et_benchmarks():
    _df_pf = fetch("🏆 Perf. Totale")
    _pi_bourse = sv(_df_pf,6,2); _pl_bourse = sv(_df_pf,6,3)
    _pi_crypto = sv(_df_pf,7,2); _pl_crypto = sv(_df_pf,7,3)
    _pi_options = st.session_state['ibkr_kpis'].get('capital_investi', sv(_df_pf,8,2))
    _pl_options = st.session_state.get('capital_reel', 0.0) or sv(_df_pf,8,3)

    _now = datetime.now(_TZ_PARIS).replace(tzinfo=None)
    _start_bourse = BENCH_START["SP500"]   # 2022-02-04
    _start_crypto = datetime(2022, 8, 4)

    _months_b = dca_months(_start_bourse, _now)
    _months_c = dca_months(_start_crypto, _now)
    _montant_b = _pi_bourse / len(_months_b) if _months_b else 0
    _montant_c = _pi_crypto / len(_months_c) if _months_c else 0

    # Flux Options = vrais dépôts IBKR
    _options_cfs = []
    for _yd in st.session_state['ibkr_data'].values():
        for _lbl, _amt in _yd.get('depots_detail', []):
            for _f in ("%Y-%m-%d","%d/%m/%Y","%m/%d/%Y","%d-%m-%Y"):
                try:
                    _options_cfs.append((datetime.strptime(_lbl[:10], _f), _amt)); break
                except ValueError: continue
    _options_cfs.sort(key=lambda x: x[0])

    _all_cfs_in = sorted(
        [(m, _montant_b) for m in _months_b]
        + [(m, _montant_c) for m in _months_c]
        + _options_cfs,
        key=lambda x: x[0])

    _val_actuelle = _pl_bourse + _pl_crypto + _pl_options
    _val_investie = _pi_bourse + _pi_crypto + _pi_options

    _cfs_pf = [(d, -m) for d, m in _all_cfs_in] + [(_now, _val_actuelle)]
    _tri_global = xirr(_cfs_pf) if _val_investie > 0 and _val_actuelle > 0 else None

    # Benchmarks
    _end_str = (_now + __import__('datetime').timedelta(days=1)).strftime("%Y-%m-%d")
    _bench_results = {}
    _bench_debug = []
    for idx_name, tk_list in BENCH_TICKERS.items():
        used_tk, df_h = fetch_index_history(tuple(tk_list), _start_bourse.strftime("%Y-%m-%d"), _end_str)
        disp_name = {"SP500":"SP500 TR","CAC 40":"CAC40 GR","STOXX 600":"STOXX 600"}[idx_name]
        if df_h is None:
            _bench_results[idx_name] = {"display": disp_name, "tri": None, "valeur": None, "note": "données indisponibles"}
            _bench_debug.append({"Indice": disp_name, "Ticker utilisé": "—", "Lignes": 0,
                                  "Première date": "—", "Dernière date": "—",
                                  "Statut": f"❌ Échec (testés: {', '.join(tk_list)})"})
            continue
        if idx_name == "CAC 40" and used_tk != "PX1GR.PA": disp_name = "CAC40"
        if idx_name == "SP500" and used_tk == "^GSPC": disp_name = "SP500"
        _bench_debug.append({"Indice": disp_name, "Ticker utilisé": used_tk, "Lignes": len(df_h),
                              "Première date": df_h.index[0].strftime("%Y-%m-%d"),
                              "Dernière date": df_h.index[-1].strftime("%Y-%m-%d"), "Statut": "✅ OK"})
        parts = 0.0; n_ok = 0; cfs = []
        for d, montant in _all_cfs_in:
            px = price_at_or_before(df_h, d)
            if px and px > 0:
                parts += montant / px; cfs.append((d, -montant)); n_ok += 1
        px_now = price_at_or_before(df_h, _now)
        if px_now and parts > 0 and n_ok >= 2:
            val_finale = parts * px_now
            cfs.append((_now, val_finale))
            tri = xirr(cfs)
            _bench_results[idx_name] = {"display": disp_name, "tri": tri, "valeur": val_finale,
                                         "note": f"{n_ok}/{len(_all_cfs_in)} flux OK (ticker {used_tk})"}
        else:
            _bench_results[idx_name] = {"display": disp_name, "tri": None, "valeur": None,
                                         "note": f"pas assez de données ({n_ok} flux OK)"}

    return {
        "tri_global": _tri_global,
        "valeur_actuelle_totale": _val_actuelle,
        "valeur_investie_totale": _val_investie,
        "nb_flux": len(_all_cfs_in),
        "benchmarks": _bench_results,
        "debug_rows": _bench_debug,
    }

st.session_state['tri_global'] = _compute_tri_global_et_benchmarks()

tab1, tab5, tab_marche, tab2, tab3, tab4, tab8, tab6, tab7, tab9 = st.tabs(["🏠 Vue d'ensemble", "📊 Performance", "🌍 Contexte Marché", "📈 Bourse", "₿ Crypto", "⚙️ Options", "📊 IBKR Analyse", "🔍 Valorisation", "⭐ Watchlist", "🚧 Chantier"])

# ── Constantes globales ───────────────────────────────
mois_s = ["Jan","Fév","Mar","Avr","Mai","Juin","Juil","Aoû","Sep","Oct","Nov","Déc"]
mois_f = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

# ══════════════════════════════════════════════════════
# TAB 1 — VUE D'ENSEMBLE
# ══════════════════════════════════════════════════════
with tab1:
    df_p  = fetch("🏠 Patrimoine")
    df_em = fetch("📅 Évol. Mensuelle")
    df_ea = fetch("📈 Évol. Annuelle")
    df_pf = fetch("🏆 Perf. Totale")
    df_b  = fetch("📊 Bourse")
    df_opt= fetch("⚙️ Options")

    pat=sv(df_p,5,1); inv=sv(df_p,5,3); perf=sv(df_p,5,5)
    _tri_g = st.session_state['tri_global']['tri_global']
    # Options : UNIQUEMENT depuis session_state (déjà chargé depuis GitHub à l'init)
    _ibkr_cr  = st.session_state.get('capital_reel', 0.0) or load_capital_reel()
    _ibkr_inv = st.session_state.get('ibkr_kpis', {}).get('capital_investi', 0.0)
    # pat et inv viennent du Sheet SANS la partie IBKR
    # On soustrait ce que le Sheet a pour IBKR et on met la vraie valeur app
    # sv(df_pf,8,3) = valeur IBKR dans Sheet, sv(df_pf,8,2) = investi IBKR dans Sheet
    _sh_ibkr_val = sv(df_pf, 8, 3)
    _sh_ibkr_inv = sv(df_pf, 8, 2)
    pat = pat - _sh_ibkr_val + _ibkr_cr
    inv = inv - _sh_ibkr_inv + _ibkr_inv
    ytd=sv(df_em,5,9); ytdp=sv(df_em,5,12)
    divs_ytd = sv(df_b,5,15)
    # Primes YTD depuis HTML parsé (ibkr_data) — filtre sur l'année courante
    _primes_ytd_ibkr = 0.0
    if 'ibkr_data' in st.session_state and st.session_state['ibkr_data']:
        _yr_data_now = st.session_state['ibkr_data'].get(_YR, {})
        _primes_ytd_ibkr = sum(_yr_data_now.get('synthese_realise', {}).values())
    primes_ytd = _primes_ytd_ibkr if _primes_ytd_ibkr != 0.0 else sv(df_opt, 5, 12)

    # ── 7 KPI cards ────────────────────────────────────
    cols = st.columns(7)
    for col,(ti,va,su,co,ic,s2) in zip(cols,[
        ("PATRIMOINE TOTAL", fmt(pat),  "",                          C['gold'],   "🏆", ""),
        ("TOTAL INVESTI",    fmt(inv),  "",                          C['blue'],   "💰", ""),
        ("PERFORMANCE",      pct(perf), "depuis février 2022",        pcol(perf),  "📈", ""),
        ("TRI ANNUALISÉ",     pct(_tri_g) if _tri_g is not None else "—", "global, XIRR",  C['purple'], "⚡", ""),
        ("VARIATION YTD",    fmt(ytd),  pct(ytdp),                   pcol(ytd),   "📅", ""),
        ("DIVIDENDES YTD",   f"{divs_ytd:.2f} €", "net perçu",       C['gold'],   "💰", ""),
        ("PRIMES OPTIONS",   f"{primes_ytd:.2f} €",f"YTD {_YR}",        C['purple'], "⚙️", ""),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic,s2), unsafe_allow_html=True)


    _today     = datetime.now()
    _day_of_yr = _today.timetuple().tm_yday
    _days_yr   = 366 if _today.year % 4 == 0 else 365
    _pct_yr    = _day_of_yr / _days_yr * 100

    # ── Objectifs + progression — expander avec popovers ─────────────
    with st.expander("🎯 Objectifs & progression de l'année", expanded=True):
        _o1, _o2, _o3, _o4 = st.columns(4)

        # Card 1 — Objectif patrimoine
        with _o1:
            _obj_pat = st.session_state.get('obj_patrimoine', 80000)
            _pct_obj = (pat / _obj_pat * 100) if _obj_pat > 0 else 0
            _diff    = pat - _obj_pat
            _diff_col = C['green'] if _diff >= 0 else C['gold']
            _bar_col  = C['green'] if _pct_obj >= 100 else (C['gold'] if _pct_obj >= _pct_yr else C['red'])
            st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:12px 14px">
  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
    <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em">🎯 Objectif patrimoine</div>
  </div>
  <div style="font-family:'Space Grotesk';font-size:26px;font-weight:700;color:{_bar_col}">{_pct_obj:.1f}%</div>
  <div style="font-size:10px;color:{C['muted']};margin:2px 0 6px">Actuel <b style="color:{C['text']}">{fmt(pat)}</b></div>
  <div style="background:{C['border']};border-radius:3px;height:4px;margin-bottom:4px">
    <div style="background:{_bar_col};height:100%;width:{min(_pct_obj,100):.0f}%;border-radius:3px"></div>
  </div>
  <div style="font-size:10px;color:{C['muted']}">objectif {fmt(_obj_pat)}</div>
</div>""", unsafe_allow_html=True)
            with st.popover("✏️", use_container_width=False):
                st.markdown("**Modifier l'objectif patrimoine**")
                _obj_pat_new = st.number_input("Objectif (€)", min_value=0,
                    value=_obj_pat, step=1000, key="obj_patrimoine_input")
                if st.button("💾 Sauvegarder", key="save_obj_pat"):
                    st.session_state['obj_patrimoine'] = _obj_pat_new
                    save_objectifs(_obj_pat_new, st.session_state.get('obj_dca', 600))
                    st.rerun()

        # Card 2 — DCA mensuel
        with _o2:
            _dca_mois_obj = st.session_state.get('obj_dca', 600)
            # Bourse mois en cours
            _now_mois = datetime.now(_TZ_PARIS).replace(tzinfo=None)
            _mois_idx = _now_mois.month - 1
            _dca_b_ce_mois = n(v(df_b, 11+_mois_idx, 2)) + n(v(df_b, 11+_mois_idx, 3))
            # Crypto mois en cours
            try:
                _df_c_dca = fetch("₿ Crypto")
                _dca_c_ce_mois = n(v(_df_c_dca, 20+_mois_idx, 2))
            except Exception:
                _dca_c_ce_mois = 0.0
            # Options (dernier dépôt si mois en cours)
            _dca_o_real = 0.0
            if 'ibkr_data' in st.session_state:
                _yr_data_now2 = st.session_state['ibkr_data'].get(_YR, {})
                _depots_yr2 = _yr_data_now2.get('depots_detail', [])
                if _depots_yr2:
                    _parsed_deps2 = []
                    for _lbl2, _amt2 in _depots_yr2:
                        for _f2 in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                            try:
                                _parsed_deps2.append((datetime.strptime(_lbl2[:10], _f2), _amt2)); break
                            except ValueError: continue
                    if _parsed_deps2:
                        _last_dt2, _last_amt2 = max(_parsed_deps2, key=lambda x: x[0])
                        if _last_dt2.year == _now_mois.year and _last_dt2.month == _now_mois.month:
                            _dca_o_real = _last_amt2
            _dca_ce_mois = _dca_b_ce_mois + _dca_c_ce_mois + _dca_o_real
            _pct_dca = min((_dca_ce_mois / _dca_mois_obj * 100), 150) if _dca_mois_obj > 0 else 0
            _dca_col = C['green'] if _pct_dca >= 100 else (C['gold'] if _pct_dca >= 80 else C['red'])
            _mois_nom = mois_f[_now_mois.month-1]
            st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:12px 14px">
  <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">💸 DCA mensuel</div>
  <div style="display:flex;justify-content:space-between;align-items:flex-start">
    <div style="flex:1;min-width:0">
      <div style="font-family:'Space Grotesk';font-size:26px;font-weight:700;color:{_dca_col}">{fmt(_dca_ce_mois)}</div>
      <div style="font-size:10px;color:{C['muted']};margin-top:1px">{_mois_nom} · <span style="color:{_dca_col};font-weight:700">{_pct_dca:.0f}%</span> objectif {fmt(_dca_mois_obj)}</div>
    </div>
    <div style="text-align:right;font-size:12px;line-height:2.0;margin-left:8px;flex-shrink:0">
      <div>📈 Bourse <b style="color:{C['blue']}">{fmt(_dca_b_ce_mois)}</b></div>
      <div>₿ Crypto <b style="color:{C['gold']}">{fmt(_dca_c_ce_mois)}</b></div>
      <div>⚙️ Options <b style="color:{C['purple']}">{fmt(_dca_o_real)}</b></div>
    </div>
  </div>
  <div style="background:{C['border']};border-radius:3px;height:4px;margin-top:6px">
    <div style="background:{_dca_col};height:100%;width:{min(_pct_dca,100):.0f}%;border-radius:3px"></div>
  </div>
</div>""", unsafe_allow_html=True)
            with st.popover("✏️", use_container_width=False):
                st.markdown("**Modifier l'objectif DCA mensuel**")
                _obj_dca_new = st.number_input("Objectif DCA (€)", min_value=0,
                    value=_dca_mois_obj, step=50, key="obj_dca_input")
                if st.button("💾 Sauvegarder", key="save_obj_dca"):
                    st.session_state['obj_dca'] = _obj_dca_new
                    save_objectifs(st.session_state.get('obj_patrimoine', 80000), _obj_dca_new)
                    st.rerun()

        # Card 3 — Année écoulée
        with _o3:
            st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:12px 14px">
  <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">📅 Année {_YR} écoulée</div>
  <div style="font-family:'Space Grotesk';font-size:26px;font-weight:700;color:{C['blue']}">{_pct_yr:.1f}%</div>
  <div style="font-size:10px;color:{C['muted']};margin:3px 0 6px">Jour {_day_of_yr} / {_days_yr}</div>
  <div style="background:{C['border']};border-radius:3px;height:4px">
    <div style="background:{C['blue']};height:100%;width:{_pct_yr:.0f}%;border-radius:3px"></div>
  </div>
</div>""", unsafe_allow_html=True)

        # Card 4 — Reste à atteindre
        with _o4:
            _reste = _obj_pat - pat
            _reste_col = C['green'] if _reste <= 0 else C['gold']
            _reste_label = "Objectif atteint ! 🎉" if _reste <= 0 else f"Il reste {fmt(_reste)} à atteindre"
            _reste_pct = min((pat / _obj_pat * 100), 100) if _obj_pat else 0
            st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:12px 14px">
  <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;margin-bottom:6px">🏁 Reste à atteindre</div>
  <div style="font-family:'Space Grotesk';font-size:26px;font-weight:700;color:{_reste_col}">{fmt(abs(_reste)) if _reste > 0 else fmt(0)}</div>
  <div style="font-size:10px;color:{C['muted']};margin:3px 0 6px"><span style="color:{_reste_col};font-weight:700">{_reste_label}</span></div>
  <div style="background:{C['border']};border-radius:3px;height:4px">
    <div style="background:{_reste_col};height:100%;width:{_reste_pct:.0f}%;border-radius:3px"></div>
  </div>
</div>""", unsafe_allow_html=True)


    with st.expander("📅 Évolution mensuelle & Répartition", expanded=True):
        L, R = st.columns([2,1])

        with L:
            sec("Évolution mensuelle","📅","#818CF8","#0A0E1A")
            pats=[n(v(df_em,13+i,2)) for i in range(12)]
            vars_=[n(v(df_em,13+i,3)) if str(v(df_em,13+i,3,"")).strip() not in ["—",""] else None for i in range(12)]
            xp=[mois_s[i] for i,x in enumerate(pats) if x>0]
            yp=[x for x in pats if x>0]
            fig1=go.Figure(go.Bar(
                x=xp, y=yp,
                marker_color='#818CF8',
                marker_line=dict(color=C['bg'], width=1),
                text=[f"{y/1000:.0f}k€" for y in yp],
                textposition='outside', textfont=dict(color=C['text'], size=10),
                hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
            # Annotations % variation vs mois précédent
            for i in range(1, len(yp)):
                _evol1 = (yp[i]/yp[i-1]-1)*100 if yp[i-1] else 0
                _col1  = C['green'] if _evol1 >= 0 else C['red']
                fig1.add_annotation(x=xp[i], y=yp[i],
                    text=f"{'▲' if _evol1>=0 else '▼'}{abs(_evol1):.1f}%",
                    showarrow=False, yshift=28,
                    font=dict(size=9, color=_col1))
            fig1.update_layout(**base_layout(240))
            fig1.update_yaxes(tickformat='.0f', ticksuffix=' €')
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
            yrs=[str(_YR-4),str(_YR-3),str(_YR-2),str(_YR-1),str(_YR)]
            tv=[x for x in tots if x>0]; yl=yrs[:len(tv)]
            if tv:
                fig4=go.Figure(go.Bar(
                    x=yl, y=tv,
                    marker_color='#818CF8',
                    marker_line=dict(color=C['bg'], width=1),
                    text=[f"{y/1000:.0f}k€" for y in tv],
                    textposition='outside', textfont=dict(color=C['text'], size=10),
                    hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
                for i in range(1,len(tv)):
                    evol=(tv[i]/tv[i-1]-1)*100
                    fig4.add_annotation(x=yl[i],y=tv[i],
                        text=f"{'+' if evol>=0 else ''}{evol:.0f}%",
                        showarrow=False,yshift=18,
                        font=dict(size=9,color=C['green'] if evol>=0 else C['red']))
                fig4.update_layout(**base_layout(180))
                fig4.update_yaxes(tickformat='.0f',ticksuffix=' €')
                st.plotly_chart(fig4,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})
        with R:
            sec("Répartition","🍩","#818CF8","#0A0E1A")
            cats=["📈 Bourse","₿ Crypto","⚙️ Options","🏢 PEE","📋 PER","🛡️ AV","💵 Cash"]
            clrs=[C['blue'],C['gold'],C['purple'],C['teal'],"#A855F7","#6B7280","#06B6D4"]
            # Capital réel : depuis session_state (déjà syncé depuis GitHub à l'init)
            _ibkr_cap_reel = st.session_state.get('capital_reel', 0.0) or _ibkr_cr
            vals=[n(v(df_p,19+i,2)) for i in range(7)]
            # Toujours substituer Options (index 2) par la valeur app — ZERO lien Sheet
            if len(vals) > 2:
                vals[2] = _ibkr_cap_reel
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
    df_b=fetch("📊 Bourse")
    bi=n(v(df_b,5,1)); bs=n(v(df_b,5,3)); bpv=n(v(df_b,5,6)); bpp=n(v(df_b,5,8))
    bd=n(v(df_b,5,15)); bp=n(v(df_b,5,11))

    cols=st.columns(5)
    for col,(ti,va,su,co,ic,s2) in zip(cols,[
        ("TOTAL INVESTI", fmt(bi),       "",                   C['cyan'],  "💰", ""),
        ("SOLDE ACTUEL",  fmt(bs),       "",                   C['blue'],  "💶", ""),
        ("PV / MV",       fmt(bpv),      pct(bpp),             pcol(bpp),  "📈", ""),
        ("DIVIDENDES NET",f"{bd:.2f} €", f"{_YR} YTD net",       C['gold'],  "💰", ""),
        ("PARRAINAGE YTD",f"{bp:.2f} €", "",                   C['teal'],  "🤝", ""),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic,s2), unsafe_allow_html=True)

    L2,R2=st.columns(2)

    with L2:
        sec(f"DCA Mensuel {_YR} — CTO & PEA","💸","#7DD3FC","#0A1A1C")
        dca_cto=[n(v(df_b,11+i,2)) for i in range(12)]
        dca_pea=[n(v(df_b,11+i,3)) for i in range(12)]
        fig5=go.Figure()
        fig5.add_trace(go.Bar(name='CTO',x=mois_f,y=dca_cto,marker_color='#7DD3FC',
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_cto],
            textposition='inside',textfont=dict(color=C['bg'],size=9),
            hovertemplate='<b>%{x}</b><br>CTO: %{y:.2f} €<extra></extra>'))
        fig5.add_trace(go.Bar(name='PEA',x=mois_f,y=dca_pea,marker_color='#38BDF8',
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_pea],
            textposition='inside',textfont=dict(color=C['bg'],size=9),
            hovertemplate='<b>%{x}</b><br>PEA: %{y:.2f} €<extra></extra>'))
        # Moyenne mobile (total CTO+PEA par mois, sur les mois renseignés)
        _dca_tot5 = [a+b for a,b in zip(dca_cto,dca_pea)]
        _dca_actif5 = [x for x in _dca_tot5 if x>0]
        if _dca_actif5:
            _moy5 = sum(_dca_actif5)/len(_dca_actif5)
            # Ligne sur toute la largeur (tous les 12 mois)
            fig5.add_trace(go.Scatter(
                name=f'Moy. {_moy5:.0f}€/mois',
                x=mois_f, y=[_moy5]*12,
                mode='lines',
                line=dict(color='#F59E0B',width=2,dash='dot'),
                hovertemplate=f'Moyenne : {_moy5:.0f} €/mois<extra></extra>'
            ))
            # Annotation au-dessus de la ligne, côté droit
            fig5.add_annotation(
                x=mois_f[-1], y=_moy5,
                text=f'<b>{_moy5:.0f} €/mois</b>',
                showarrow=False, yshift=12,
                xanchor='right',
                font=dict(size=11, color='#F59E0B')
            )
        fig5.update_layout(**base_layout(280,True),barmode='stack')
        fig5.update_layout(legend=dict(orientation='h',y=-0.12,font=dict(size=11)))
        fig5.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig5,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # Tableau positions depuis watchlist portefeuille
        sec("Positions en portefeuille","📋","#7DD3FC","#0A1A1C")
        _wl_pf = st.session_state.get("wl_portefeuille", [])
        if _wl_pf:
            _pos_tbl = f"""<div style="overflow-x:auto;margin-bottom:12px">
<table style="width:100%;border-collapse:collapse;table-layout:fixed;font-size:11px">
<thead><tr style="background:#1C2333;color:{C['muted']};font-size:10px;text-transform:uppercase">
  <th style="padding:6px 10px;text-align:left;width:28%;border-bottom:1px solid {C['border']}">Action</th>
  <th style="padding:6px 10px;text-align:right;width:14%;border-bottom:1px solid {C['border']}">PRU</th>
  <th style="padding:6px 10px;text-align:right;width:16%;border-bottom:1px solid {C['border']}">Cours</th>
  <th style="padding:6px 10px;text-align:right;width:14%;border-bottom:1px solid {C['border']}">PV/MV %</th>
  <th style="padding:6px 10px;text-align:right;width:14%;border-bottom:1px solid {C['border']}">Cible BASE</th>
  <th style="padding:6px 10px;text-align:right;width:14%;border-bottom:1px solid {C['border']}">Upside</th>
</tr></thead><tbody>"""
            for _w in _wl_pf:
                _pru   = _w.get("pru", 0)
                _cours = _w.get("cours", 0)
                _cible = _w.get("cible", 0)
                _pvmv  = ((_cours - _pru) / _pru * 100) if _pru > 0 else 0
                _upside= ((_cible - _cours) / _cours * 100) if _cours > 0 else 0
                _pvclr = C['green'] if _pvmv >= 0 else C['red']
                _upclr = C['green'] if _upside >= 0 else C['red']
                _pos_tbl += f"""<tr style="border-bottom:1px solid {C['border']}22">
  <td style="padding:6px 10px;font-weight:600;color:{C['text']};overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{_w['name'][:20]}</td>
  <td style="padding:6px 10px;text-align:right;color:{C['muted']}">{f"{_pru:.2f}€" if _pru else "—"}</td>
  <td style="padding:6px 10px;text-align:right;color:{C['text']};font-weight:600">{f"{_cours:.2f}€" if _cours else "—"}</td>
  <td style="padding:6px 10px;text-align:right;color:{_pvclr};font-weight:700">{f"{_pvmv:+.1f}%" if _pru else "—"}</td>
  <td style="padding:6px 10px;text-align:right;color:{C['cyan']}">{f"{_cible:.0f}€" if _cible else "—"}</td>
  <td style="padding:6px 10px;text-align:right;color:{_upclr};font-weight:700">{f"{_upside:+.1f}%" if _cours else "—"}</td>
</tr>"""
            _pos_tbl += "</tbody></table></div>"
            st.markdown(_pos_tbl, unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-size:11px;color:{C['muted']};font-style:italic;padding:4px 0'>Ajoutez vos positions dans la Watchlist → 📈 Portefeuille</div>", unsafe_allow_html=True)

        # DCA cumul ligne
        dca_tot=[n(v(df_b,11+i,4)) for i in range(12)]
        xc=[mois_f[i] for i,x in enumerate(dca_tot) if x>0]
        yc=[x for x in dca_tot if x>0]
        if xc:
            sec(f"DCA Cumulé {_YR}","📈","#7DD3FC","#0A1A1C")
            figc=go.Figure(go.Bar(
                x=xc, y=yc,
                marker_color='#7DD3FC',
                marker_line=dict(color=C['bg'], width=1),
                text=[f"{y:.0f}€" for y in yc],
                textposition='outside', textfont=dict(color=C['text'], size=9),
                hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
            figc.update_layout(**base_layout(180))
            figc.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(figc,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # Solde mensuel — graphique waterfall (variation mois/mois)
        sec("Variation mensuelle du portefeuille","📋","#7DD3FC","#0A1A1C")
        _sol_wf = [n(v(df_b,11+i,9)) for i in range(12)]
        _xwf    = [mois_s[i] for i,x in enumerate(_sol_wf) if x>0]
        _ywf    = [x for x in _sol_wf if x>0]
        if len(_ywf) > 1:
            _measures = ["absolute"] + ["relative"]*(len(_ywf)-1)
            _deltas   = [_ywf[0]] + [_ywf[i]-_ywf[i-1] for i in range(1,len(_ywf))]
            fig_wf = go.Figure(go.Waterfall(
                x=_xwf, measure=_measures, y=_deltas,
                connector=dict(line=dict(color=C['border'],width=1)),
                increasing=dict(marker_color=C['green']),
                decreasing=dict(marker_color=C['red']),
                totals=dict(marker_color='#7DD3FC'),
                text=[f"{'+' if d>=0 else ''}{d/1000:.1f}k" if i>0 else f"{d/1000:.1f}k" for i,d in enumerate(_deltas)],
                textposition="outside",
                textfont=dict(size=9,color=C['text']),
                hovertemplate='<b>%{x}</b><br>%{y:+,.0f} €<extra></extra>'
            ))
            fig_wf.update_layout(**base_layout(200,False))
            fig_wf.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(fig_wf,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

    with R2:
        # Donut CTO / PEA
        sec("Répartition CTO / PEA","🍩","#7DD3FC","#0A1A1C")
        _cto_val = n(v(df_b,5,3)) * (1 - n(v(df_b,5,8))/100) if n(v(df_b,5,3)) else 0
        # Utilise directement les soldes du mois le plus récent
        _last_cto = next((n(v(df_b,11+i,7)) for i in range(11,-1,-1) if n(v(df_b,11+i,9))>0), 0)
        _last_pea = next((n(v(df_b,11+i,8)) for i in range(11,-1,-1) if n(v(df_b,11+i,9))>0), 0)
        _last_tot = _last_cto + _last_pea
        if _last_tot > 0:
            _fig_donut_b = go.Figure(go.Pie(
                labels=['CTO', 'PEA'], values=[_last_cto, _last_pea], hole=0.55,
                marker=dict(colors=[C['cyan'], C['green']], line=dict(color=C['bg'],width=2)),
                textinfo='percent', textfont=dict(size=11,color='white'),
                hovertemplate='<b>%{label}</b><br>%{value:,.0f} €<br>%{percent}<extra></extra>'
            ))
            _fig_donut_b.add_annotation(text=f"<b>{_last_tot/1000:.0f}k€</b>",x=0.5,y=0.5,
                font=dict(size=14,color=C['text'],family='Space Grotesk'),showarrow=False)
            _fig_donut_b.update_layout(**base_layout(160,False))
            _fig_donut_b.update_layout(showlegend=False,margin=dict(l=0,r=0,t=5,b=5))
            st.plotly_chart(_fig_donut_b,use_container_width=True,config={'displayModeBar':False})
            for _lbl, _clr, _val in [('CTO',C['cyan'],_last_cto),('PEA',C['green'],_last_pea)]:
                _p = _val/_last_tot*100
                st.markdown(f"""<div style="display:flex;align-items:center;justify-content:space-between;
padding:4px 8px;border-radius:6px;margin-bottom:3px;background:{C['card']}">
<div style="display:flex;align-items:center;gap:8px">
  <div style="width:10px;height:10px;border-radius:2px;background:{_clr}"></div>
  <span style="font-size:12px;color:{C['text']};font-weight:500">{_lbl}</span>
</div>
<span style="font-size:12px;color:{_clr};font-weight:700">{fmt(_val)} · {_p:.1f}%</span>
</div>""", unsafe_allow_html=True)

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
            fig6.add_trace(go.Bar(name='CTO', x=xsol, y=ycto,
                marker_color='#7DD3FC',
                hovertemplate='<b>%{x}</b><br>CTO: %{y:.0f} €<extra></extra>'))
            fig6.add_trace(go.Bar(name='PEA', x=xsol, y=ypea,
                marker_color='#38BDF8',
                hovertemplate='<b>%{x}</b><br>PEA: %{y:.0f} €<extra></extra>'))
            for i,(x_,y_) in enumerate(zip(xsol,ysol)):
                fig6.add_annotation(x=x_,y=y_,text=f"{y_/1000:.0f}k€",
                    showarrow=False,yshift=10,font=dict(size=9,color=C['text']))
            fig6.update_layout(**base_layout(280,True),barmode='stack')
            fig6.update_layout(legend=dict(orientation='h',y=-0.12,font=dict(size=11)))
            fig6.update_yaxes(tickformat='.0f',ticksuffix=' €')
            st.plotly_chart(fig6,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

        # Dividendes — graphique barres horizontales
        sec(f"Dividendes {_YR}","💰","#7DD3FC","#0A1A1C")
        div_rows=[]
        for i in range(15):
            r_=11+i
            act=str(v(df_b,r_,15,"")).strip()
            pays=str(v(df_b,r_,16,"")).strip()
            net=n(v(df_b,r_,17,0))
            if act and act not in ["Action",""] and net>0:
                div_rows.append({"Action":act,"Pays":pays,"_net":net})
        if div_rows:
            df_div=pd.DataFrame(div_rows).sort_values("_net",ascending=True).reset_index(drop=True)
            _total_div = df_div["_net"].sum()
            fig_div=go.Figure(go.Bar(
                x=df_div["_net"], y=df_div["Action"],
                orientation='h',
                marker_color='#7DD3FC',
                text=[f"{x:.2f} €" for x in df_div["_net"]],
                textposition='outside',
                textfont=dict(color=C['text'],size=10),
                hovertemplate='<b>%{y}</b><br>%{x:.2f} €<extra></extra>'
            ))
            fig_div.update_layout(**base_layout(max(180, len(div_rows)*32+40), False))
            fig_div.update_layout(margin=dict(l=0,r=60,t=10,b=10))
            fig_div.update_xaxes(ticksuffix=' €', showgrid=True)
            fig_div.update_yaxes(tickfont=dict(size=11))
            st.plotly_chart(fig_div, use_container_width=True, config={'displayModeBar':False})
            st.markdown(f"<div style='text-align:right;font-size:11px;color:{C['gold']};margin-top:-8px;font-weight:700'>Total : {_total_div:.2f} €</div>", unsafe_allow_html=True)

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
                "valeur_usd":n(v(df_ct,r_,5)),"valeur_eur":n(v(df_ct,r_,6)),
                "pvmv":n(v(df_ct,r_,11)),"perf":n(v(df_ct,r_,12))})

        _tbl_c = "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:13px'>"
        _tbl_c += ("<thead><tr style='background:#111827'>"
            f"<th style='padding:7px 10px;text-align:left;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Crypto</th>"
            f"<th style='padding:7px 10px;text-align:left;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Code</th>"
            f"<th style='padding:7px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Montant</th>"
            f"<th style='padding:7px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Valeur $</th>"
            f"<th style='padding:7px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Valeur €</th>"
            f"<th style='padding:7px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>PV/MV €</th>"
            f"<th style='padding:7px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Perf.</th>"
            "</tr></thead><tbody>")
        for row_c in cdata:
            _pvmv_col = C['green'] if row_c['pvmv']>=0 else C['red']
            _perf_col = C['green'] if row_c['perf']>=0 else C['red']
            _pvmv_str = f"{'+' if row_c['pvmv']>=0 else ''}{row_c['pvmv']:.2f} €"
            _perf_str = f"{'+' if row_c['perf']>=0 else ''}{row_c['perf']:.1f} %"
            _tbl_c += ("<tr style='border-bottom:1px solid #1F2937'>"
                f"<td style='padding:6px 10px'>{row_c['Crypto']}</td>"
                f"<td style='padding:6px 10px;color:{C['muted']}'>{row_c['Code']}</td>"
                f"<td style='padding:6px 10px;text-align:right'>{row_c['Montant']}</td>"
                f"<td style='padding:6px 10px;text-align:right'>{row_c['valeur_usd']:.2f} $</td>"
                f"<td style='padding:6px 10px;text-align:right'>{fmt2(row_c['valeur_eur'])}</td>"
                f"<td style='padding:6px 10px;text-align:right;color:{_pvmv_col};font-weight:600'>{_pvmv_str}</td>"
                f"<td style='padding:6px 10px;text-align:right;color:{_perf_col};font-weight:600'>{_perf_str}</td>"
                "</tr>")
        _tot_pvmv_col = C['green'] if cpv>=0 else C['red']
        _tot_perf_col = C['green'] if cp>=0 else C['red']
        _tot_pvmv_str = f"{'+' if cpv>=0 else ''}{cpv:.2f} €"
        _tot_perf_str = f"{'+' if cp>=0 else ''}{cp:.1f} %"
        _tbl_c += ("<tr style='background:#111827;font-weight:700'>"
            "<td style='padding:7px 10px' colspan='3'>TOTAL</td>"
            f"<td style='padding:7px 10px;text-align:right'>{cd:.2f} $</td>"
            f"<td style='padding:7px 10px;text-align:right'>{fmt2(cv)}</td>"
            f"<td style='padding:7px 10px;text-align:right;color:{_tot_pvmv_col}'>{_tot_pvmv_str}</td>"
            f"<td style='padding:7px 10px;text-align:right;color:{_tot_perf_col}'>{_tot_perf_str}</td>"
            "</tr>")
        _tbl_c += "</tbody></table></div>"
        st.markdown(_tbl_c, unsafe_allow_html=True)

        df_c26=fetch("₿ Crypto")
        sec(f"DCA Mensuel {_YR}","💸","#FCD34D","#1C100A")
        dca_c=[n(v(df_c26,20+i,2)) for i in range(12)]
        fig7=go.Figure(go.Bar(x=mois_s,y=dca_c,name='DCA mensuel',
            marker_color=['#FCD34D' if x>0 else C['border'] for x in dca_c],
            text=[f"{x:.0f}€" if x>0 else "" for x in dca_c],
            textposition='outside',textfont=dict(color=C['text'],size=10)))
        # Moyenne mobile crypto
        _dca_actif7 = [x for x in dca_c if x>0]
        if _dca_actif7:
            _moy7 = sum(_dca_actif7)/len(_dca_actif7)
            # Ligne sur toute la largeur (tous les 12 mois)
            fig7.add_trace(go.Scatter(
                name=f'Moy. {_moy7:.0f}€/mois',
                x=mois_s, y=[_moy7]*12,
                mode='lines',
                line=dict(color='#F59E0B',width=2,dash='dot'),
                hovertemplate=f'Moyenne : {_moy7:.0f} €/mois<extra></extra>'
            ))
            # Annotation au-dessus de la ligne, côté droit
            fig7.add_annotation(
                x=mois_s[-1], y=_moy7,
                text=f'<b>{_moy7:.0f} €/mois</b>',
                showarrow=False, yshift=12,
                xanchor='right',
                font=dict(size=11, color='#F59E0B')
            )
        fig7.update_layout(**base_layout(200))
        fig7.update_layout(showlegend=True,legend=dict(orientation='h',y=-0.30,font=dict(size=11)))
        fig7.update_layout(margin=dict(b=60))
        fig7.update_yaxes(ticksuffix=' €')
        st.plotly_chart(fig7,use_container_width=True,config={'displayModeBar':False})

        # Évolution mensuelle du portefeuille crypto (col Q = index 16, lignes 12→23)
        _sol_c = [n(v(df_c26, 11+i, 16)) for i in range(12)]  # lignes 12-23 = index 11-22
        _xc_ev = [mois_f[i] for i, x in enumerate(_sol_c) if x > 0]
        _yc_ev = [x for x in _sol_c if x > 0]
        if _xc_ev:
            sec(f"Évolution du portefeuille crypto {_YR}", "📈", "#FCD34D", "#1C100A")
            _fig_c_ev = go.Figure(go.Bar(
                x=_xc_ev, y=_yc_ev,
                marker_color='#FCD34D',
                marker_line=dict(color=C['bg'], width=1),
                text=[f"{y/1000:.1f}k€" for y in _yc_ev],
                textposition='outside', textfont=dict(color=C['text'], size=9),
                hovertemplate='<b>%{x}</b><br>%{y:,.0f} €<extra></extra>'
            ))
            if len(_yc_ev) > 1:
                _evol_c = (_yc_ev[-1] / _yc_ev[0] - 1) * 100
                _fig_c_ev.add_annotation(
                    x=_xc_ev[-1], y=_yc_ev[-1],
                    text=f"{'+' if _evol_c >= 0 else ''}{_evol_c:.1f}% YTD",
                    showarrow=False, yshift=22,
                    font=dict(size=10, color=C['green'] if _evol_c >= 0 else C['red'])
                )
            _fig_c_ev.update_layout(**base_layout(220))
            _fig_c_ev.update_yaxes(tickformat='.0f', ticksuffix=' €')
            st.plotly_chart(_fig_c_ev, use_container_width=True,
                config={'displayModeBar': True, 'scrollZoom': True,
                        'modeBarButtonsToRemove': ['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],
                        'displaylogo': False})

    with R3:
        sec("Répartition","🍩","#FCD34D","#1C100A")
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
# ══════════════════════════════════════════════════════
# TAB 4 — OPTIONS
# ══════════════════════════════════════════════════════
with tab4:
    # ── KPIs GLOBAUX (tous CSV, indépendants du filtre années) ──
    # Capital investi, capital réel, capital actuel → toujours sur ALL
    _fx_live = st.session_state.get('eurusd_live', None)
    _ibkr_kpis_all = compute_ibkr_kpis(st.session_state['ibkr_data'], fx_live=_fx_live)
    st.session_state['ibkr_kpis'] = _ibkr_kpis_all  # accessible depuis autres onglets
    _cap_inv  = _ibkr_kpis_all['capital_investi']
    _cap_act  = _ibkr_kpis_all['capital_actuel']

    # ── KPI Capital Réel : saisie manuelle persistante ──
    _cr_col1, _cr_col2, _cr_col3, _cr_col4 = st.columns(4)

    # Hauteur uniforme pour toutes les KPI cards (inclut input + aide)
    _KPI_H = "148px"  # hauteur uniforme toutes KPI cards

    with _cr_col1:
        _cr_val = st.session_state['capital_reel']
        # Card avec crayon — HTML visuel + popover Streamlit natif pour la saisie
        st.markdown(f"""<div style='position:relative;background:{C['card']};
border:1px solid {C['border']};border-top:2px solid {C['teal']};border-radius:10px;
padding:14px 18px;height:118px;box-sizing:border-box;display:flex;flex-direction:column'>
  <div style='font-size:10px;color:{C['muted']};text-transform:uppercase;
  letter-spacing:.08em;margin-bottom:4px'>🏦 CAPITAL RÉEL</div>
  <div style='font-size:22px;font-weight:700;color:{C['text']};line-height:1.2;flex:1'>
    {_cr_val:.2f} €</div>
  <div style='font-size:12px;color:{C['teal']}'>← modifiable</div>
</div>""", unsafe_allow_html=True)
        with st.popover("✏️", use_container_width=False):
            st.markdown("**Modifier le capital réel**")
            st.caption(f"Valeur actuelle : {_cr_val:.2f} €")
            _new_cr = st.number_input("Nouveau capital IBKR (€)", value=float(_cr_val),
                                      min_value=0.0, format="%.2f", key="cr_input")
            if st.button("✓ Enregistrer", key="cr_save", use_container_width=True):
                st.session_state['capital_reel'] = _new_cr
                save_capital_reel(_new_cr)
                st.rerun()

    with _cr_col2:
        _dep_info = _ibkr_kpis_all.get('dernier_depot')
        _dep_sub2 = (f"Dernier versement : +{_dep_info['montant']:.0f}€ ({_dep_info['mois']} {_dep_info['annee']})"
                     if _dep_info else "")
        st.markdown(card("CAPITAL INVESTI", f"{_cap_inv:.2f} €",
                         "depuis ouverture du compte", C['blue'], "💰", _dep_sub2), unsafe_allow_html=True)

    # cols 3 et 4 seront remplis APRÈS le filtre années (voir plus bas)
    _kpi_col4 = _cr_col3
    _kpi_col5 = _cr_col4
    # Fallback si pas de données IBKR chargées
    if not st.session_state.get('ibkr_data'):
        with _kpi_col4:
            st.markdown(card("ROI TOTAL", "—", "charger un relevé IBKR", C['purple'], "🏆"), unsafe_allow_html=True)
        with _kpi_col5:
            st.markdown(card("PRIMES BRUTES", "—", "charger un relevé IBKR", C['gold'], "💰"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════
    # SECTION IBKR
    # ══════════════════════════════════════════════════
    sec("Stratégie de la Roue — Trades IBKR", "⚙️", "#FDA4AF", "#1C0A12")

    # ── Zone import discrète ──
    with st.expander("📂 Importer / gérer les relevés IBKR", expanded=not bool(st.session_state['ibkr_data'])):
        _col_import, _col_del = st.columns([3, 1])
        with _col_import:
            uploaded_files = st.file_uploader(
                "Relevé(s) IBKR (.htm)",
                type=['htm','html'], accept_multiple_files=True,
                label_visibility="collapsed",
                key="ibkr_uploader"
            )
            if uploaded_files:
                for f in uploaded_files:
                    file_bytes = f.read()
                    parsed = parse_ibkr_html(file_bytes)
                    if parsed and parsed['year']:
                        dest = IBKR_DIR / f"ibkr_{parsed['year']}.htm"
                        dest.write_bytes(file_bytes)
                        st.session_state['ibkr_data'][parsed['year']] = parsed
                        st.session_state.pop('options_auto_refreshed', None)
                        # ── Sauvegarde GitHub ──
                        gh_path = f"ibkr_data/ibkr_{parsed['year']}.htm"
                        _, sha = gh_read(gh_path)
                        ok = gh_write(gh_path, file_bytes,
                                      f"upload IBKR {parsed['year']}", sha)
                        if ok:
                            st.toast(f"✅ IBKR {parsed['year']} sauvegardé sur GitHub", icon="💾")
                        else:
                            st.toast(f"⚠️ IBKR {parsed['year']} en local seulement (GitHub KO)", icon="⚠️")
        with _col_del:
            loaded_years = sorted(st.session_state['ibkr_data'].keys())
            if loaded_years:
                _yr_to_del = st.selectbox("🗑 Supprimer :", ["—"] + [str(y) for y in loaded_years],
                                          label_visibility="visible", key="ibkr_del_sel")
                if _yr_to_del != "—":
                    for _ext in ('.htm', '.html'):
                        _del_file = IBKR_DIR / f"ibkr_{_yr_to_del}{_ext}"
                        if _del_file.exists(): _del_file.unlink()
                    if int(_yr_to_del) in st.session_state['ibkr_data']:
                        del st.session_state['ibkr_data'][int(_yr_to_del)]
                    st.rerun()

    loaded_years = sorted(st.session_state['ibkr_data'].keys())

    # ── Sélecteur d'années — multiselect déroulant ──
    if loaded_years:
        _prev_sel_yrs = st.session_state.get('ibkr_active_years', loaded_years)
        _prev_sel_yrs = [y for y in _prev_sel_yrs if y in loaded_years] or loaded_years
        _col_yr_sel, _ = st.columns([2, 4])
        with _col_yr_sel:
            st.markdown("""<style>
[data-testid="stMultiSelect"][aria-label="ibkr_yr_multiselect"] span[data-baseweb="tag"] {
    background-color: #1C0A12 !important;
    color: #FDA4AF !important;
}
</style>""", unsafe_allow_html=True)
            _sel_yrs = st.multiselect(
                "Années affichées",
                options=loaded_years,
                default=_prev_sel_yrs,
                format_func=lambda y: str(y),
                placeholder="Sélectionner les années...",
                key="ibkr_yr_multiselect",
                label_visibility="collapsed"
            )
        if not _sel_yrs: _sel_yrs = loaded_years
        st.session_state['ibkr_active_years'] = _sel_yrs

    if not st.session_state['ibkr_data']:
        st.markdown(
            f"<div style='text-align:center;padding:40px;color:{C['muted']};font-size:13px'>"
            "📂 Importez vos relevés IBKR pour afficher vos trades<br>"
            "<span style='font-size:11px'>Téléchargez vos CSV depuis Interactive Brokers → Rapports → Relevé de compte</span>"
            "</div>", unsafe_allow_html=True
        )
    else:
        # ── Fusion de tous les trades ──
        all_trades_raw = []
        for yr_data in st.session_state['ibkr_data'].values():
            all_trades_raw.extend(yr_data['trades'])
        all_positions = []
        for yr_data in st.session_state['ibkr_data'].values():
            all_positions.extend(yr_data['positions'])

        # Grouper par symbole pour statut final
        syms_seen = {}
        trades_by_sym = {}
        for t in all_trades_raw:
            sym = t['symbole']
            if sym not in trades_by_sym: trades_by_sym[sym] = []
            trades_by_sym[sym].append(t)

        # Construire liste consolidée (1 ligne par symbole/option)
        # Construire l'ensemble des symboles autorisés (présents dans Synthèse)
        _syms_ok = set()
        for yr_data in st.session_state['ibkr_data'].values():
            _syms_ok |= yr_data.get('syms_in_synthese', set())

        # Symboles avec assignation (code A) — absents de synthèse mais valides
        _syms_assigned = set()
        for sym2, trs2 in trades_by_sym.items():
            if any('A' in t.get('code','') for t in trs2):
                _syms_assigned.add(sym2)

        options_consolidated = []
        for sym, sym_trades in trades_by_sym.items():
            # Inclure si présent dans Synthèse OU si assignation
            if sym not in _syms_ok and sym not in _syms_assigned:
                continue
            open_trade  = next((t for t in sym_trades if t['quantite'] < 0), None)
            close_trade = next((t for t in sym_trades if t['quantite'] > 0), None)
            # Si pas de trade d'ouverture dans les années chargées → clôture orpheline, ignorer
            if open_trade is None:
                continue
            # Statut : utiliser le trade de clôture s'il existe, sinon 'Ouverte'
            if close_trade:
                statut_final = close_trade['statut'] if close_trade['statut'] != 'Ouverte' else sym_trades[-1]['statut']
            else:
                statut_final = 'Ouverte'
            pl_net      = sum(t['pl_realise'] for t in sym_trades)
            # Prime encaissée = produit du trade d'OUVERTURE uniquement (vente initiale)
            # Ne pas inclure le rachat (négatif) pour les roulées/fermées
            # Prime brute = produit USD de la vente initiale (exact, cohérent avec Google Sheet)
            prime_nette  = sum(abs(t['produit']) for t in sym_trades if t['quantite'] < 0)
            # Frais = déjà injectés depuis Synthèse évaluée (même valeur sur tous les trades)
            frais_tot   = open_trade.get('frais', 0.0)
            type_tr = open_trade.get('type_trade', '')
            if not type_tr:
                cp = open_trade.get('call_put','')
                lbl = 'Put' if cp == 'P' else 'Call'
                type_tr = f"Vente {lbl}"
            nb_contrats = int(abs(open_trade.get('quantite', 1)))
            # annee_ref : année de clôture si clôturé, sinon année d'ouverture
            if statut_final != 'Ouverte' and close_trade:
                annee_ref = close_trade['annee']
            else:
                annee_ref = open_trade['annee']
            options_consolidated.append({
                'symbole': sym, 'ticker': open_trade['ticker'],
                'call_put': open_trade['call_put'], 'strike': open_trade['strike'],
                'expiration': open_trade['expiration'], 'date': open_trade['date'],
                'prime_nette': prime_nette, 'frais': frais_tot,
                'pl_net': pl_net, 'statut': statut_final,
                'type_trade': type_tr, 'nb_contrats': nb_contrats,
                'annee': annee_ref
            })

        # ── Filtre années multi-sélection ──
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        avail_years = sorted(set(o['annee'] for o in options_consolidated if o['annee']))

        # Init : toutes les années sélectionnées par défaut
        # Années actives = sélection multiselect du dessus
        active_years = [y for y in avail_years if y in st.session_state.get('ibkr_active_years', avail_years)]
        if not active_years: active_years = avail_years

        # Taux FX basé uniquement sur les années sélectionnées
        _fx_data = [st.session_state['ibkr_data'][y] for y in active_years if y in st.session_state['ibkr_data']]

        # Filtrer
        opts_filtered = [o for o in options_consolidated if o['annee'] in active_years]

        opts_open    = [o for o in opts_filtered if o['statut'] == 'Ouverte']
        opts_closed  = [o for o in opts_filtered if o['statut'] != 'Ouverte']

        # ── Cours des sous-jacents : UNIQUEMENT Yahoo Finance (live) ──
        _live_eur = st.session_state.get('options_cours_live', {})
        _live_usd = st.session_state.get('options_cours_live_usd', {})
        if _live_eur:
            _cours_actions     = _live_eur   # EUR → pour compatibilité
            _cours_actions_usd = _live_usd   # USD → pour Prix Live + calcul marge
        else:
            # Fallback HTML en attendant le refresh auto
            _cours_actions = {}
            for _yr_d in st.session_state['ibkr_data'].values():
                for _tk, _c in _yr_d.get('cours_sous_jacents', {}).items():
                    if _c > 0:
                        _cours_actions[_tk] = _c
            _cours_actions_usd = {}  # pas de USD disponible en fallback
        _last_opt_refresh = st.session_state.get('options_cours_last_refresh', None)

        # ── Taux EUR/USD : moyenne des taux valides sur années sélectionnées ──
        _fx_vals = [d.get('fx', 0) for d in _fx_data if 0.8 <= d.get('fx', 0) <= 1.8]
        _fx = sum(_fx_vals) / len(_fx_vals) if _fx_vals else 1.16


        # ── KPIs ROI + Primes filtrés par années sélectionnées ──
        _ibkr_kpis_filtered = compute_ibkr_kpis(
            {y: st.session_state['ibkr_data'][y] for y in active_years
             if y in st.session_state['ibkr_data']},
            fx_live=_fx_live
        )

        # KPI col3/col4 : toujours sur ALL (indépendant du filtre)
        _primes_all = _ibkr_kpis_all['primes_nettes_eur']
        _fx_all     = _ibkr_kpis_all.get('fx', 1.16)
        # ROI = primes nettes / capital réel (si saisi) sinon / capital investi
        _cap_ref    = st.session_state['capital_reel'] if st.session_state['capital_reel'] > 0 else _cap_inv
        _roi_all    = (_primes_all / _cap_ref * 100) if _cap_ref > 0 else 0.0

        _roi_base_lbl = "capital réel" if st.session_state['capital_reel'] > 0 else "capital investi"
        _cr = st.session_state['capital_reel']
        _perf_globale = ((_cr - _cap_inv) / _cap_inv * 100) if _cr > 0 and _cap_inv > 0 else None
        _perf_col = pcol(_perf_globale) if _perf_globale is not None else C['muted']
        _perf_str = f"{_perf_globale:+.2f} %" if _perf_globale is not None else "—"
        with _kpi_col4:
            st.markdown(card("ROI TOTAL", f"{_roi_all:+.2f} %",
                             f"primes nettes / {_roi_base_lbl}", pcol(_roi_all), "🏆"), unsafe_allow_html=True)
            with st.popover("ⓘ aide", use_container_width=True):
                st.markdown(f"""**ROI Total** = Primes nettes ÷ Capital Réel  
**Perf. globale** = {_perf_str} (réel−investi)/investi""")

        with _kpi_col5:
            st.markdown(
                f"""<div style='background:{C['card']};border-radius:10px;padding:14px 16px;
border:1px solid {C['gold']}44;border-top:2px solid {C['gold']}'>
<div style='font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px'>
💰 PRIMES BRUTES ENCAISSÉES</div>
<div style='font-size:22px;font-weight:700;color:{C['gold']};font-family:Space Grotesk'>
{_ibkr_kpis_all['primes_brutes_eur']:+.2f} €</div>
<div style='font-size:11px;color:{C['muted']};margin-top:2px'>≈ ${_ibkr_kpis_all.get('primes_brutes_usd', _ibkr_kpis_all['primes_brutes_eur']*1.075):.2f} · Profit C/T positifs (hors roulements)</div>
<div style='border-top:1px solid {C['border']};margin:6px 0 4px'></div>
<div style='font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.06em'>P&L NET réalisé (gains − pertes)</div>
<div style='font-size:16px;font-weight:700;color:{pcol(_primes_all)};font-family:Space Grotesk'>
{_primes_all:+.2f} €<span style='font-size:10px;font-weight:400;color:{C['muted']}'> ≈ ${_primes_all*_fx_all:.2f}</span></div>
</div>""", unsafe_allow_html=True)

        def _cell(eur, col, bold=False):
            """Cellule avec X.XX€ en grand et $X.XX en petit (CSV en EUR)."""
            fw = "font-weight:700;" if bold else ""
            abs_eur = abs(eur); abs_usd = abs(eur * _fx)
            sign = "+" if eur > 0 else ("-" if eur < 0 else "")
            return (f"<td style='padding:6px 10px;text-align:right'>"
                    f"<span style='color:{col};{fw}font-size:12px'>{sign}{abs_eur:.2f} €</span><br>"
                    f"<span style='color:{col};font-size:10px;opacity:.7'>{sign}${abs_usd:.2f}</span>"
                    f"</td>")

        def _cell_usd(usd, col, bold=False):
            """Cellule avec $X.XX en grand et X.XX€ en petit (prime brute en USD)."""
            fw = "font-weight:700;" if bold else ""
            abs_usd = abs(usd); abs_eur = abs(usd / _fx) if _fx > 0 else 0
            sign = "+" if usd > 0 else ("-" if usd < 0 else "")
            return (f"<td style='padding:6px 10px;text-align:right'>"
                    f"<span style='color:{col};{fw}font-size:12px'>{sign}${abs_usd:.2f}</span><br>"
                    f"<span style='color:{col};font-size:10px;opacity:.7'>{sign}{abs_eur:.2f} €</span>"
                    f"</td>")

        def _cell_frais(eur):
            abs_eur = abs(eur); abs_usd = abs(eur * _fx)
            return (f"<td style='padding:6px 10px;text-align:right'>"
                    f"<span style='color:{C['red']};font-size:12px'>-{abs_eur:.2f} €</span><br>"
                    f"<span style='color:{C['red']};font-size:10px;opacity:.7'>-${abs_usd:.2f}</span></td>")

        # ── KPIs trades ──
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        _total_pl      = sum(o['pl_net'] for o in opts_filtered if o['statut'] != 'Ouverte')
        _total_frais   = sum(o['frais'] for o in opts_filtered)  # tous statuts : frais payés dès l'ouverture
        _nb_total      = len([o for o in opts_filtered if o['statut'] != 'Ouverte'])
        _nb_exp        = len([o for o in opts_filtered if o['statut'] == 'Expirée'])
        _nb_ass        = len([o for o in opts_filtered if o['statut'] in ('Assignée','Fermée','Roulée')])
        _win_rate      = (_nb_exp / _nb_total * 100) if _nb_total > 0 else 0

        # ROI sur les années filtrées = primes filtrées / capital investi total
        # ROI période = primes filtrées / capital investi total (ALL)
        _roi_trades = (_total_pl / _cap_inv * 100) if _cap_inv > 0 else 0

        _k1,_k2,_k3,_k4,_k5,_k6 = st.columns(6)
        with _k1: st.markdown(card("TRADES CLÔTURÉS", str(_nb_total), f"{len(opts_open)} ouvert(s)", C['purple'],"⚙️"), unsafe_allow_html=True)
        with _k2: st.markdown(card("WIN RATE", f"{_win_rate:.0f}%", f"{_nb_exp} expirées / {_nb_ass} roulées/fermées", C['green'] if _win_rate >= 70 else C['gold'],"✅"), unsafe_allow_html=True)
        with _k3: st.markdown(card("PRIME OBTENUE", f"{_total_pl:+.2f} €", f"≈ ${_total_pl*_fx:+.2f}", pcol(_total_pl),"💰"), unsafe_allow_html=True)
        with _k4: st.markdown(card("FRAIS TOTAUX", f"-{_total_frais:.2f} €", f"≈ -${_total_frais*_fx:.2f}", C['red'],"📋"), unsafe_allow_html=True)
        with _k5: st.markdown(card("NET (P/L−frais)", f"{(_total_pl - _total_frais):+.2f} €", f"≈ ${(_total_pl - _total_frais)*_fx:+.2f}", pcol(_total_pl - _total_frais),"💹"), unsafe_allow_html=True)
        with _k6:
            st.markdown(card("ROI (période)", f"{_roi_trades:+.2f} %", "primes / capital investi", pcol(_roi_trades),"📈"), unsafe_allow_html=True)
            with st.popover("ⓘ aide", use_container_width=True):
                st.markdown("""**ROI Période** = Primes nettes de la période sélectionnée ÷ Capital Investi total (somme des dépôts)""")
        st.markdown("<br>", unsafe_allow_html=True)

        # Timestamp cours live affiché plus bas (sous positions ouvertes)

        # ── Helpers date et tri ──
        from datetime import datetime
        _MONTHS = {'JAN':1,'FEB':2,'MAR':3,'APR':4,'MAY':5,'JUN':6,
                   'JUL':7,'AUG':8,'SEP':9,'OCT':10,'NOV':11,'DEC':12}
        def _parse_exp(s):
            """Convertit '23JAN26' en datetime triable."""
            try:
                day = int(s[:2]); mon = _MONTHS.get(s[2:5].upper(),1); yr = 2000+int(s[5:])
                return datetime(yr, mon, day)
            except: return datetime(2099,1,1)
        def _parse_date(s):
            """Convertit '2026-01-23' en datetime triable."""
            try: return datetime.strptime(s, '%Y-%m-%d')
            except: return datetime(2099,1,1)
        def _fmt_date(s):
            """Formate '2026-01-23' → '23.01.2026'."""
            try: return datetime.strptime(s, '%Y-%m-%d').strftime('%d.%m.%Y')
            except: return s
        def _fmt_exp(s):
            """Formate '23JAN26' → '23.01.2026'."""
            try:
                d = _parse_exp(s)
                return d.strftime('%d.%m.%Y') if d.year != 2099 else s
            except: return s

        # ── Helpers cellules $+€ ──

        # ── Helpers en-têtes tableaux ──
        _TH  = lambda t,w: f"<th style='padding:7px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']};width:{w}'>{t}</th>"
        _THL = lambda t,w: f"<th style='padding:7px 10px;text-align:left;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']};width:{w}'>{t}</th>"
        _THC = lambda t,w: f"<th style='padding:7px 10px;text-align:center;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']};width:{w}'>{t}</th>"

        # ── Tableau positions ouvertes ──
        if opts_open:
            sec(f"Positions ouvertes ({len(opts_open)})", "🟢", C['green'], "#0A1A0D")

            # Tri par défaut : date ouverture décroissant (plus récent en premier)
            _open_sorted = sorted(opts_open, key=lambda o: _parse_date(o['date']), reverse=True)

            tbl_o = "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:14px'>"
            tbl_o += "<thead><tr style='background:#0A1A0D'>"
            tbl_o += _THL("Symbole","13%") + _THL("Ticker","5%") + _THL("Type","8%") + _THC("Qté","3%") + _THL("Strike","5%") + _THC("Prix Live","6%") + _THL("Ouverture","7%") + _THL("Expiration","7%") + _THC("J. rest.","5%") + _THC("Marge","7%") + _TH("Frais","6%") + _TH("Prime enc.","8%") + _TH("Rdt","5%") + _TH("Rdt ann.","5%")
            tbl_o += "</tr></thead><tbody>"
            _tot_o_frais = _tot_o_pl = 0.0
            for o in _open_sorted:
                _cp_col  = C['purple'] if o['call_put'] == 'C' else C['gold']
                _pl_col  = C['green'] if o['pl_net'] >= 0 else C['red']
                _pn_col  = C['green'] if o['prime_nette'] >= 0 else C['red']
                _tot_o_frais += o['frais']; _tot_o_pl += o['pl_net']
                tbl_o += f"<tr style='border-bottom:1px solid {C['border']}22'>"
                _tt = o.get('type_trade','')
                _tt_col = "#9945FF" if 'Put' in _tt else "#627EEA"
                tbl_o += f"<td style='padding:7px 10px;font-family:monospace;font-size:11px;color:{C['cyan']}'>{o['symbole']}</td>"
                tbl_o += f"<td style='padding:7px 10px;font-weight:600;color:{C['text']}'>{o['ticker']}</td>"
                _type_colors = {
                    'Vente Put':  ('#F59E0B','#2A1800'),
                    'Vente Call': ('#60A5FA','#0A1A2E'),
                    'Achat Put':  ('#A78BFA','#1A0A2E'),
                    'Achat Call': ('#34D399','#0A2A1A'),
                }
                _tt_c, _tt_bg = _type_colors.get(_tt, ('#8B949E','#1A1A1A'))
                tbl_o += f"<td style='padding:7px 10px'><span style='background:{_tt_bg};color:{_tt_c};border:1px solid {_tt_c}44;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:600;white-space:nowrap'>{_tt}</span></td>"
                tbl_o += f"<td style='padding:7px 10px;text-align:center;font-weight:700;color:{C['text']}'>{o.get('nb_contrats',1)}</td>"
                tbl_o += f"<td style='padding:7px 10px;color:{C['text']}'>${o['strike']}</td>"
                # ── Prix Live (USD) + Marge ITM/OTM ──
                _strike_str  = o.get('strike','').replace('$','')
                _ticker_o    = o.get('ticker','')
                _cp_o        = o.get('call_put','')
                # Prix live en USD (strike est en USD → même devise pour le calcul)
                _cours_o_usd = _cours_actions_usd.get(_ticker_o, 0)
                _cours_o_eur = _cours_actions.get(_ticker_o, 0)
                # Cellule Prix Live en USD
                if _cours_o_usd > 0:
                    _prix_live_cell = (f"<td style='padding:7px 10px;text-align:center;"
                                       f"font-weight:700;color:{C['cyan']}'>"
                                       f"${_cours_o_usd:.2f}</td>")
                elif _cours_o_eur > 0:
                    # Fallback EUR si USD pas disponible
                    _prix_live_cell = (f"<td style='padding:7px 10px;text-align:center;"
                                       f"font-weight:700;color:{C['gold']}'>"
                                       f"{_cours_o_eur:.2f}€</td>")
                else:
                    _prix_live_cell = f"<td style='padding:7px 10px;text-align:center;color:{C['muted']}'>—</td>"
                # Cellule Marge ITM/OTM — calcul en USD (strike USD vs prix USD)
                try:
                    _strike_f  = float(_strike_str)
                    _prix_calc = _cours_o_usd if _cours_o_usd > 0 else 0
                    if _prix_calc > 0 and _strike_f > 0:
                        if _cp_o == 'P':
                            _marge_pct = (_prix_calc - _strike_f) / _strike_f * 100
                        else:
                            _marge_pct = (_strike_f - _prix_calc) / _strike_f * 100
                        _m_col  = C['green'] if _marge_pct >= 0 else C['red']
                        _m_lbl  = f"{'OTM' if _marge_pct >= 0 else 'ITM'} {_marge_pct:+.1f}%"
                        _m_cell = f"<td style='padding:6px 8px;text-align:center'><span style='background:{_m_col}22;color:{_m_col};border-radius:6px;padding:2px 5px;font-size:10px;font-weight:700;white-space:nowrap'>{_m_lbl}</span></td>"
                    else:
                        _m_cell = f"<td style='padding:7px 10px;text-align:center;color:{C['muted']}'>—</td>"
                except:
                    _m_cell = f"<td style='padding:7px 10px;text-align:center;color:{C['muted']}'>—</td>"
                tbl_o += _prix_live_cell
                tbl_o += f"<td style='padding:7px 10px;color:{C['muted']}'>{_fmt_date(o['date'])}</td>"
                tbl_o += f"<td style='padding:7px 10px;color:{C['muted']}'>{_fmt_exp(o['expiration'])}</td>"
                # Nb jours restants avant expiration
                try:
                    _exp_dt = _parse_exp(o['expiration'])
                    _today_dt = datetime.now(_TZ_PARIS).replace(tzinfo=None)
                    _jours = (_exp_dt - _today_dt).days
                    if _jours < 0:
                        _j_txt = "Expiré"; _j_col = C['red']
                    elif _jours <= 7:
                        _j_txt = str(_jours); _j_col = C['red']
                    elif _jours <= 21:
                        _j_txt = str(_jours); _j_col = C['gold']
                    else:
                        _j_txt = str(_jours); _j_col = C['green']
                except:
                    _j_txt = "—"; _j_col = C['muted']
                tbl_o += f"<td style='padding:7px 10px;text-align:center;font-weight:700;color:{_j_col}'>{_j_txt}</td>"
                tbl_o += _m_cell
                tbl_o += _cell_frais(o['frais'])
                _pn_net = o['prime_nette'] / _fx - o['frais']  # prime en € nette de frais
                tbl_o += _cell(_pn_net, C['gold'])
                # Rendement = prime enc. / marge requise
                try:
                    _strike_rdt = float(o['strike'].replace('$','')) if isinstance(o['strike'], str) else float(o['strike'])
                    _marge_req  = _strike_rdt * 100 * o.get('nb_contrats', 1)
                    _rdt = (o['prime_nette'] / _marge_req * 100) if _marge_req > 0 else 0
                    # Rendement annualisé
                    try:
                        _exp_rdt = _parse_exp(o['expiration'])
                        _open_rdt = datetime.strptime(o['date'], '%Y-%m-%d')
                        _nb_j_rdt = max((_exp_rdt - _open_rdt).days, 1)
                    except:
                        _nb_j_rdt = 30
                    _rdt_ann = _rdt / _nb_j_rdt * 365
                    _rdt_col = C['green'] if _rdt >= 0 else C['red']
                    tbl_o += f"<td style='padding:6px 8px;text-align:right'><span style='color:{_rdt_col};font-weight:700;font-size:11px'>{_rdt:+.1f}%</span></td>"
                    tbl_o += f"<td style='padding:6px 8px;text-align:right'><span style='color:{_rdt_col};font-size:11px'>{_rdt_ann:+.0f}%</span></td>"
                except:
                    tbl_o += f"<td style='padding:6px 8px;text-align:center;color:{C['muted']}'>—</td>"
                    tbl_o += f"<td style='padding:6px 8px;text-align:center;color:{C['muted']}'>—</td>"
                tbl_o += "</tr>"
            # Ligne total
            _tpl_col = C['green'] if _tot_o_pl >= 0 else C['red']
            tbl_o += f"<tr style='background:{C['card']};border-top:2px solid {C['border']};font-weight:700'>"
            _tot_o_net = _tot_o_pl
            _tot_o_pn = sum(o['prime_nette'] for o in _open_sorted)
            tbl_o += f"<td colspan='10' style='padding:8px 10px;color:{C['muted']};font-size:11px;text-transform:uppercase;letter-spacing:.05em'>Total</td>"
            tbl_o += _cell_frais(_tot_o_frais)
            tbl_o += _cell(sum(o['prime_nette']/_fx - o['frais'] for o in _open_sorted), C['gold'])
            tbl_o += "<td colspan='2'></td>"
            tbl_o += "</tr>"
            tbl_o += "</tbody></table></div>"
            st.markdown(tbl_o, unsafe_allow_html=True)
            # Timestamp cours live discret
            if _last_opt_refresh:
                st.markdown(
                    f"<div style='font-size:10px;color:{C['muted']};padding:2px 0 4px'>"
                    f"📡 cours live MAJ à <b style='color:{C['green']}'>{_last_opt_refresh}</b></div>",
                    unsafe_allow_html=True)

        # ── Tableau historique ──
        if opts_closed:
            sec(f"Historique trades ({len(opts_closed)})", "📋", C['muted'], "#0A0E1A")

            # ── Filtres statut multi-sélection ──
            _stat_sel_key = 'opt_stat_selected'
            _all_statuts  = ['Expirée', 'Roulée', 'Fermée', 'Assignée']
            # Garder uniquement les statuts présents dans les données
            _present_statuts = sorted(set(o['statut'] for o in opts_closed))

            if _stat_sel_key not in st.session_state:
                st.session_state[_stat_sel_key] = {s: True for s in _all_statuts}
            # Ajouter automatiquement les nouveaux statuts (ex: 'Roulée' apparu après déploiement)
            for s in _all_statuts + _present_statuts:
                if s not in st.session_state[_stat_sel_key]:
                    st.session_state[_stat_sel_key][s] = True

            # Filtre statuts discret
            _prev_active_stat = [s for s in _present_statuts if st.session_state[_stat_sel_key].get(s, True)]
            if not _prev_active_stat: _prev_active_stat = _present_statuts
            st.markdown("""<style>
span[data-baseweb="tag"] { background-color: #111827 !important; color: #6B7280 !important; border: 1px solid #374151 !important; }
</style>""", unsafe_allow_html=True)
            _sel_statuts = st.multiselect(
                "Filtrer par statut",
                options=_present_statuts,
                default=_prev_active_stat,
                key="stat_multisel",
                label_visibility="collapsed",
                placeholder="Tous les statuts"
            )
            if not _sel_statuts: _sel_statuts = _present_statuts
            for s in _present_statuts:
                st.session_state[_stat_sel_key][s] = (s in _sel_statuts)

            _active_statuts = _sel_statuts if _sel_statuts else _present_statuts
            opts_display = [o for o in opts_closed if o['statut'] in _active_statuts]

            # Tri par défaut : date d'ouverture décroissant (plus récent en premier)
            opts_display = sorted(opts_display, key=lambda o: _parse_date(o['date']), reverse=True)


            def _scol(s):
                return {
                    'Expirée': ('#3FB950','#0D2A0D'),
                    'Roulée':  (C['gold'],'#2A1800'),
                    'Fermée':  (C['cyan'],'#0D1A2A'),
                    'Assignée':(C['red'],'#2A0D0D'),
                }.get(s,(C['muted'],C['card']))

            tbl_h = "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:14px'>"
            tbl_h += "<thead><tr style='background:#111827'>"
            tbl_h += (_THL("Symbole","14%") + _THL("Ticker","5%") + _THL("Type","9%") + _THC("Qté","3%") + _THL("Strike","5%") +
                      _THL("Ouverture","7%") + _THL("Expiration","7%") +
                      _TH("Frais","6%") +
                      _TH("Prime obtenue","9%") + _TH("Rdt","5%") + _TH("Rdt ann.","6%") + _TH("Statut","7%"))
            tbl_h += "</tr></thead><tbody>"
            _tot_prime = _tot_frais = _tot_pl = 0.0
            for o in opts_display:
                _cp_col  = C['purple'] if o['call_put'] == 'C' else C['gold']
                _pl_col  = C['green'] if o['pl_net'] >= 0 else C['red']
                _pn_col  = C['green'] if o['prime_nette'] >= 0 else C['red']
                _sc, _sbg = _scol(o['statut'])
                _tot_prime += o['prime_nette']; _tot_frais += o['frais']; _tot_pl += o['pl_net']
                tbl_h += f"<tr style='border-bottom:1px solid {C['border']}22'>"
                _tt = o.get('type_trade','')
                _type_colors_h = {
                    'Vente Put':  ('#F59E0B','#2A1800'),
                    'Vente Call': ('#60A5FA','#0A1A2E'),
                    'Achat Put':  ('#A78BFA','#1A0A2E'),
                    'Achat Call': ('#34D399','#0A2A1A'),
                }
                _tt_hc, _tt_hbg = _type_colors_h.get(_tt, ('#8B949E','#1A1A1A'))
                tbl_h += f"<td style='padding:7px 10px;font-family:monospace;font-size:11px;color:{C['cyan']}'>{o['symbole']}</td>"
                tbl_h += f"<td style='padding:7px 10px;font-weight:600;color:{C['text']}'>{o['ticker']}</td>"
                tbl_h += f"<td style='padding:7px 10px'><span style='background:{_tt_hbg};color:{_tt_hc};border:1px solid {_tt_hc}44;border-radius:6px;padding:2px 8px;font-size:11px;font-weight:600;white-space:nowrap'>{_tt}</span></td>"
                tbl_h += f"<td style='padding:7px 10px;text-align:center;font-weight:700;color:{C['text']}'>{o.get('nb_contrats',1)}</td>"
                tbl_h += f"<td style='padding:7px 10px;color:{C['text']}'>${o['strike']}</td>"
                tbl_h += f"<td style='padding:7px 10px;color:{C['muted']}'>{_fmt_date(o['date'])}</td>"
                tbl_h += f"<td style='padding:7px 10px;color:{C['muted']}'>{_fmt_exp(o['expiration'])}</td>"

                tbl_h += _cell_frais(o['frais'])
                tbl_h += _cell(o['pl_net'], _pl_col, bold=True)
                # Rendement historique
                try:
                    _strike_h = float(o['strike'].replace('$','')) if isinstance(o['strike'], str) else float(o['strike'])
                    _marge_h  = _strike_h * 100 * o.get('nb_contrats', 1)
                    _rdt_h    = (o['pl_net'] / (_marge_h / _fx) * 100) if _marge_h > 0 else 0
                    try:
                        _exp_h  = _parse_exp(o['expiration'])
                        _open_h = datetime.strptime(o['date'], '%Y-%m-%d')
                        _nb_j_h = max((_exp_h - _open_h).days, 1)
                    except:
                        _nb_j_h = 30
                    _rdt_ann_h = _rdt_h / _nb_j_h * 365
                    _rdt_col_h = C['green'] if _rdt_h >= 0 else C['red']
                    tbl_h += f"<td style='padding:6px 8px;text-align:right'><span style='color:{_rdt_col_h};font-weight:700;font-size:11px'>{_rdt_h:+.1f}%</span></td>"
                    tbl_h += f"<td style='padding:6px 8px;text-align:right'><span style='color:{_rdt_col_h};font-size:11px'>{_rdt_ann_h:+.0f}%</span></td>"
                except:
                    tbl_h += f"<td style='padding:6px 8px;text-align:center;color:{C['muted']}'>—</td>"
                    tbl_h += f"<td style='padding:6px 8px;text-align:center;color:{C['muted']}'>—</td>"
                tbl_h += f"<td style='padding:7px 10px;text-align:center'><span style='background:{_sbg};color:{_sc};border-radius:12px;padding:2px 8px;font-size:10px;font-weight:600'>{o['statut']}</span></td>"
                tbl_h += "</tr>"
            # Ligne total
            _tp_col  = C['green'] if _tot_prime >= 0 else C['red']
            _tpl_col = C['green'] if _tot_pl    >= 0 else C['red']
            tbl_h += f"<tr style='background:{C['card']};border-top:2px solid {C['border']};font-weight:700'>"
            tbl_h += f"<td colspan='7' style='padding:8px 10px;color:{C['muted']};font-size:11px;text-transform:uppercase;letter-spacing:.05em'>Total ({len(opts_display)} trades)</td>"
            tbl_h += _cell_frais(_tot_frais)
            tbl_h += _cell(_tot_pl, C['green'] if _tot_pl >= 0 else C['red'], bold=True)
            tbl_h += "<td colspan='3'></td></tr>"
            tbl_h += "</tbody></table></div>"
            st.markdown(tbl_h, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
with tab8:
    if not st.session_state.get('ibkr_data'):
        st.markdown(f"<div style='text-align:center;padding:60px;color:{C["muted"]};font-size:13px'>📂 Chargez vos relevés IBKR dans l'onglet Options pour accéder à l'analyse.</div>", unsafe_allow_html=True)
    else:
        _fx_an  = st.session_state.get('eurusd_live', 1.10) or 1.10
        _MOIS_FR_AN = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
        from datetime import datetime as _dt_an
        _now_an = _dt_an.now()

        # ── Toutes les trades disponibles ──────────────────────
        _all_trades_an = []
        for _yd in st.session_state['ibkr_data'].values():
            _all_trades_an.extend(_yd.get('trades', []))

        # TABLEAU ACTIONS IBKR (PRU classique / PRU ajusté)
        # ══════════════════════════════════════════════════════
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        sec("Actions détenues sur IBKR", "📦", "#F0883E", "#1C1000")

        # Fusionner actions_detenues de toutes les années (garder la plus récente)
        _all_actions = {}
        for _yr in sorted(st.session_state['ibkr_data'].keys()):
            _yr_data = st.session_state['ibkr_data'][_yr]
            for ticker, info in _yr_data.get('actions_detenues', {}).items():
                _all_actions[ticker] = info  # écrase par la plus récente

        # PRU classique réel = recalculé depuis les achats réels (toutes années)
        # = Σ(qty × prix_achat) / Σ(qty) — ignorer le PRU IBKR qui intègre les primes
        _achats_cumul = {}  # {ticker: {qty_total, cout_total}}
        for _yr_data in st.session_state['ibkr_data'].values():
            for ticker, ach in _yr_data.get('achats_actions', {}).items():
                if ticker not in _achats_cumul:
                    _achats_cumul[ticker] = {'qty_total': 0.0, 'cout_total': 0.0}
                _achats_cumul[ticker]['qty_total']  += ach['qty_total']
                _achats_cumul[ticker]['cout_total'] += ach['cout_total']

        # Calculer total des primes par ticker (toutes années confondues)
        def _ticker_from_sym(sym):
            return sym.split()[0] if sym else ''

        _primes_par_ticker = {}
        for _yr_data in st.session_state['ibkr_data'].values():
            for sym, total_real in _yr_data.get('synthese_realise', {}).items():
                tk = _ticker_from_sym(sym)
                _primes_par_ticker[tk] = _primes_par_ticker.get(tk, 0.0) + total_real

        if _all_actions:
            _fx_live_act = st.session_state.get('eurusd_live', 1.10)

            _tbl_act  = "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:12px'>"
            _tbl_act += "<thead><tr style='background:#1C1000'>"
            _tbl_act += (
                f"<th style='padding:7px 12px;text-align:left;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Ticker</th>"
                f"<th style='padding:7px 12px;text-align:center;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Qté</th>"
                f"<th style='padding:7px 12px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>PRU Classique</th>"
                f"<th style='padding:7px 12px;text-align:right;font-size:10px;color:{C['gold']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>PRU Ajusté ★</th>"
                f"<th style='padding:7px 12px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Cours Live</th>"
                f"<th style='padding:7px 12px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>PV/MV Classique</th>"
                f"<th style='padding:7px 12px;text-align:right;font-size:10px;color:{C['gold']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>PV/MV Ajusté</th>"
                f"<th style='padding:7px 12px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Primes totales</th>"
            )
            _tbl_act += "</tr></thead><tbody>"

            for ticker, info in sorted(_all_actions.items()):
                qty        = info['quantite']
                cours_usd  = _cours_actions_usd.get(ticker, info.get('cours', 0.0))
                primes_tot = _primes_par_ticker.get(ticker, 0.0)  # EUR

                # PRU classique = recalculé depuis les vrais achats (ignorer IBKR qui intègre les primes)
                _ach = _achats_cumul.get(ticker, {})
                if _ach.get('qty_total', 0) > 0:
                    pru_class = _ach['cout_total'] / _ach['qty_total']
                else:
                    pru_class = info['pru_classique']  # fallback IBKR si pas de transaction trouvée

                # PRU ajusté = PRU classique - (primes totales en USD / qty actuelle)
                primes_tot_usd = primes_tot * (_fx_live_act if _fx_live_act else 1.10)
                pru_ajuste = pru_class - (primes_tot_usd / qty) if qty != 0 else pru_class

                pvmv_class = (cours_usd - pru_class) * qty if cours_usd > 0 else None
                pvmv_ajust = (cours_usd - pru_ajuste) * qty if cours_usd > 0 else None
                pvmv_class_pct = (cours_usd / pru_class - 1) * 100 if pru_class > 0 and cours_usd > 0 else None
                pvmv_ajust_pct = (cours_usd / pru_ajuste - 1) * 100 if pru_ajuste > 0 and cours_usd > 0 else None

                def _pvmv_cell(val, pct):
                    if val is None or pct is None: return f"<td style='padding:7px 12px;text-align:right;color:{C['muted']}'>—</td>"
                    col = C['green'] if val >= 0 else C['red']
                    bg  = '#0D2A0D' if val >= 0 else '#2A0D0D'
                    return (f"<td style='padding:7px 12px;text-align:right;background:{bg};border-radius:4px'>"
                            f"<span style='color:{col};font-weight:700;font-size:14px'>{pct:+.1f}%</span><br>"
                            f"<span style='color:{col};font-size:11px;opacity:.8'>{val:+.2f} $</span></td>")

                _cours_cell = (f"<span style='color:{C['cyan']};font-weight:700'>${cours_usd:.2f}</span>" if cours_usd > 0
                               else f"<span style='color:{C['muted']}'>—</span>")
                _pru_aj_col = C['gold'] if pru_ajuste < pru_class else C['text']

                _tbl_act += f"<tr style='border-bottom:1px solid {C['border']}22'>"
                _tbl_act += f"<td style='padding:7px 12px;font-weight:700;color:{C['text']};font-size:13px'>{ticker}</td>"
                _tbl_act += f"<td style='padding:7px 12px;text-align:center;color:{C['text']};font-weight:600'>{int(qty)}</td>"
                _tbl_act += f"<td style='padding:7px 12px;text-align:right;color:{C['muted']}'>${pru_class:.2f}</td>"
                _tbl_act += f"<td style='padding:7px 12px;text-align:right;font-weight:700;color:{_pru_aj_col}'>${pru_ajuste:.2f}</td>"
                _tbl_act += f"<td style='padding:7px 12px;text-align:right'>{_cours_cell}</td>"
                _tbl_act += _pvmv_cell(pvmv_class, pvmv_class_pct)
                _tbl_act += _pvmv_cell(pvmv_ajust, pvmv_ajust_pct)
                _tbl_act += f"<td style='padding:7px 12px;text-align:right;color:{C['green']}'>{primes_tot:+.2f} €<br><span style='font-size:10px;opacity:.7'>{primes_tot_usd:+.2f} $</span></td>"
                _tbl_act += "</tr>"

            _tbl_act += "</tbody></table></div>"
            _tbl_act += f"""<div style='font-size:10px;color:{C['muted']};padding:4px 0 0 0;margin-top:-6px;font-style:italic'>
★ PRU Ajusté = PRU Classique − (toutes primes perçues sur ce ticker ÷ nombre d'actions).
En dessous du PRU Ajusté = seuil pour vendre des calls sans risque de perte en cas d'assignation.</div>"""
            st.markdown(_tbl_act, unsafe_allow_html=True)
        else:
            st.markdown(f"<div style='font-size:12px;color:{C['muted']};font-style:italic;padding:8px 0'>Aucune action détenue dans les relevés IBKR chargés.</div>", unsafe_allow_html=True)

        # ══════════════════════════════════════════════════════
        # TABLEAU MENSUEL DES PRIMES
        # ══════════════════════════════════════════════════════
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        sec("Rendement mensuel des primes", "📅", "#FDA4AF", "#1C0A12")

        # Construire le dict mois→total_real depuis la Synthèse par trade
        # On regroupe les trades clôturés par (année, mois) via leur date de clôture/expiration
        # Source : synthese_realise[sym] = total_real EUR pour chaque symbole
        # On mappe chaque symbole à son mois via le trade de clôture
        _MOIS_FR = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']

        # Construire tableau par année — expander par année (année courante dépliée)
        from datetime import datetime as _dt_yr
        _YR_exp = _dt_yr.now().year
        _years_disp = sorted(st.session_state['ibkr_data'].keys(), reverse=True)
        for _yr in _years_disp:
            _yr_data = st.session_state['ibkr_data'][_yr]
            _fx_yr   = _yr_data.get('fx', 1.10)
            _synth_r = _yr_data.get('synthese_realise', {})  # {sym: total_real EUR}
            _trades_yr = _yr_data.get('trades', [])

            # Mapper symbole → mois de clôture (date du trade de clôture qty>0, ou expiration)
            _sym_mois = {}
            for t in _trades_yr:
                sym = t['symbole']
                qty = t.get('quantite', 0)
                date_s = t.get('date', '')
                if qty > 0 or 'Ep' in t.get('code','') or 'A' in t.get('code',''):
                    # trade de clôture → récupérer le mois
                    try:
                        from datetime import datetime as _dt2
                        _m = _dt2.strptime(date_s, '%Y-%m-%d').month
                        _sym_mois[sym] = _m
                    except: pass

            # Agréger total_real par mois
            _primes_mois = {m: 0.0 for m in range(1, 13)}
            for sym, total_real in _synth_r.items():
                mois = _sym_mois.get(sym)
                if mois:
                    _primes_mois[mois] += total_real

            # Afficher le tableau — style intégré dark
            _tot_m = sum(_primes_mois.values())
            _tot_col = C['green'] if _tot_m > 0 else (C['red'] if _tot_m < 0 else C['muted'])
            _tot_bg  = '#0D2A0D' if _tot_m > 0 else ('#2A0D0D' if _tot_m < 0 else C['card'])

            _tbl_m = (
                f"<div style='background:{C['card']};border:1px solid {C['border']};"
                f"border-radius:12px;overflow:hidden;margin-bottom:16px'>"
                # En-tête année
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"padding:10px 16px;border-bottom:1px solid {C['border']};background:#1C0A12'>"
                f"<span style='font-size:13px;font-weight:700;color:#FDA4AF;letter-spacing:.04em'>📆 {_yr}</span>"
                f"<span style='font-size:12px;font-weight:700;color:{_tot_col}'>"
                f"Total : {_tot_m:+.2f} € <span style='font-size:10px;opacity:.7'>≈ {_tot_m*_fx_yr:+.2f} $</span></span>"
                f"</div>"
                # Grille 12 mois
                f"<div style='display:grid;grid-template-columns:repeat(12,1fr)'>"
            )
            # Headers mois
            for m in _MOIS_FR:
                _tbl_m += (f"<div style='padding:6px 4px;text-align:center;font-size:10px;"
                           f"color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;"
                           f"border-right:1px solid {C['border']}22;border-bottom:1px solid {C['border']}'>{m}</div>")
            # Cellules valeurs
            for mois in range(1, 13):
                v_eur = _primes_mois[mois]
                _col_v = C['green'] if v_eur > 0 else (C['red'] if v_eur < 0 else C['muted'])
                _bg_v  = '#0D2A0D' if v_eur > 0 else ('#2A0D0D' if v_eur < 0 else 'transparent')
                _border_top = f'2px solid {_col_v}' if v_eur != 0 else f'2px solid {C["border"]}'
                if v_eur != 0:
                    _cell = (f"<div style='font-size:14px;font-weight:700;color:{_col_v};margin-bottom:2px'>{v_eur:+.2f} €</div>"
                             f"<div style='font-size:10px;color:{_col_v};opacity:.65'>{v_eur*_fx_yr:+.2f} $</div>")
                else:
                    _cell = f"<div style='font-size:14px;color:{C['muted']}'>—</div>"
                _tbl_m += (f"<div style='padding:10px 6px;text-align:center;background:{_bg_v};"
                           f"border-top:{_border_top};border-right:1px solid {C['border']}22'>{_cell}</div>")
            _tbl_m += "</div></div>"
            with st.expander(f"{'▼' if _yr == _YR_exp else '▶'} {_yr}  —  Total : {_tot_m:+.2f} €  ≈  {_tot_m*_fx_yr:+.2f} $", expanded=(_yr == _YR_exp)):
                st.markdown(_tbl_m, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════
with tab5:
    import pandas as pd
    try:
        df_pf  = fetch("🏆 Perf. Totale")
        df_ea  = fetch("📈 Évol. Annuelle")
        df_pat = fetch("🏠 Patrimoine")
    except Exception:
        df_pf = df_ea = df_pat = pd.DataFrame()

    # ── KPIs Performance — calculés depuis les mêmes sources que le tableau ──
    _pi_b  = sv(df_pf,6,2); _pl_b  = sv(df_pf,6,3)
    _pi_c  = sv(df_pf,7,2); _pl_c  = sv(df_pf,7,3)
    _pi_o  = st.session_state['ibkr_kpis'].get('capital_investi', sv(df_pf,8,2)) if 'ibkr_kpis' in st.session_state else sv(df_pf,8,2)
    _pl_o  = st.session_state.get('capital_reel', 0.0) or sv(df_pf,8,3)
    inv_t  = _pi_b + _pi_c + _pi_o
    live_t = _pl_b + _pl_c + _pl_o
    pvmv_t = live_t - inv_t
    pp_t   = (live_t/inv_t-1)*100 if inv_t else 0
    _tri_g = st.session_state['tri_global']['tri_global']

    c1,c2,c3,c4 = st.columns(4)
    for col,(ti,va,su,co,ic) in zip([c1,c2,c3,c4],[
        ("TOTAL INVESTI",    fmt(inv_t),          "",                   C['blue'],  "💰"),
        ("VALEUR ACTUELLE",  fmt(live_t),          "",                   C['cyan'],  "📈"),
        ("PV / MV TOTAL",    fmt(pvmv_t),          pct(pp_t),            pcol(pp_t), "💹"),
        ("TRI ANNUALISÉ",     pct(_tri_g) if _tri_g is not None else "—", "global, XIRR",  C['purple'],"⚡"),
    ]):
        with col: st.markdown(card(ti,va,su,co,ic),unsafe_allow_html=True)
    with c4:
        with st.popover("ⓘ aide", use_container_width=True):
            st.markdown("""**TRI Annualisé (XIRR)** = taux de rendement annuel qui égalise tous tes
versements réels (DCA Bourse le 4 de chaque mois depuis 02/2022, DCA Crypto depuis 08/2022,
dépôts IBKR réels pour les Options) avec la valeur actuelle de ton patrimoine.

Contrairement à *(valeur actuelle / investi - 1)*, le TRI tient compte du **timing** de chaque
versement : un euro investi en 2022 n'a pas le même poids qu'un euro investi le mois dernier.

C'est la métrique la plus juste pour comparer ta performance réelle à un indice (voir "TRI vs
Benchmarks" ci-contre).""")

    st.markdown("<br>",unsafe_allow_html=True)
    Lp, Rp = st.columns([3,2])

    with Lp:
        sec("Performance par enveloppe","🏆","#6EE7B7","#0A1C0F")
        from datetime import datetime as _dt_perf
        _now_perf = _dt_perf.now(_TZ_PARIS).replace(tzinfo=None)

        def _dca_cashflows(pi_total, pl_now, start_date, today):
            """Génère les flux DCA (montant constant le 4 de chaque mois) + valeur finale."""
            cfs = []
            d = start_date
            months = []
            while d <= today:
                months.append(d)
                if d.month == 12:
                    d = _dt_perf(d.year+1, 1, 4)
                else:
                    d = _dt_perf(d.year, d.month+1, 4)
            if not months: return None
            montant_mensuel = pi_total / len(months)
            for m in months:
                cfs.append((m, -montant_mensuel))
            cfs.append((today, pl_now))
            return cfs

        poches=[
            ("📈 Bourse (CTO+PEA)", sv(df_pf,6,2), sv(df_pf,6,3), C['blue'],   _dt_perf(2022,2,4)),
            ("₿ Crypto (Binance)",  sv(df_pf,7,2), sv(df_pf,7,3), C['gold'],   _dt_perf(2022,8,4)),
            ("⚙️ Options (IBK)",
            st.session_state['ibkr_kpis'].get('capital_investi', sv(df_pf,8,2)) if 'ibkr_kpis' in st.session_state else sv(df_pf,8,2),
            st.session_state.get('capital_reel', 0.0) or sv(df_pf,8,3),
            C['purple'], _dt_perf(2023,12,1)),
        ]

        _tbl_perf = "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:13px'>"
        _tbl_perf += ("<thead><tr style='background:#111827'>"
            f"<th style='padding:6px 10px;text-align:left;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Enveloppe</th>"
            f"<th style='padding:6px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Investi</th>"
            f"<th style='padding:6px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Valeur actuelle</th>"
            f"<th style='padding:6px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>PV/MV €</th>"
            f"<th style='padding:6px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Perf. globale</th>"
            f"<th style='padding:6px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>TRI annualisé</th>"
            "</tr></thead><tbody>")

        for po,pi,pl,pc,pdate in poches:
            ppv=pl-pi; pp=(pl/pi-1)*100 if pi else 0

            if "Options" in po and 'ibkr_kpis' in st.session_state:
                _all_dep = []
                for _yd in st.session_state['ibkr_data'].values():
                    for _lbl,_amt in _yd.get('depots_detail', []):
                        for _f in ("%Y-%m-%d","%d/%m/%Y","%m/%d/%Y","%d-%m-%Y"):
                            try:
                                _all_dep.append((_dt_perf.strptime(_lbl[:10], _f), -_amt)); break
                            except ValueError: continue
                _all_dep.sort(key=lambda x: x[0])
                _cfs = _all_dep + [(_now_perf, pl)] if _all_dep else None
            else:
                _cfs = _dca_cashflows(pi, pl, pdate, _now_perf)

            _xirr = xirr(_cfs) if _cfs and pi>0 and pl>0 else None

            _ppv_col = C['green'] if ppv>=0 else C['red']
            _pp_col  = C['green'] if pp>=0 else C['red']
            _cagr_col = C['green'] if (_xirr is not None and _xirr>=0) else C['red']
            _ppv_str = f"{'+' if ppv>=0 else '-'}{int(round(abs(ppv))):,} €".replace(',', ' ')
            _pp_str  = f"{'+' if pp>=0 else ''}{pp:.1f}%"
            _cagr_str = f"{'+' if _xirr>=0 else ''}{_xirr:.1f}%" if _xirr is not None else "—"
            _tbl_perf += ("<tr style='border-bottom:1px solid #1F2937'>"
                f"<td style='padding:7px 10px;color:{pc};font-weight:600'>{po}</td>"
                f"<td style='padding:7px 10px;text-align:right;color:{C['muted']}'>{fmt(pi)}</td>"
                f"<td style='padding:7px 10px;text-align:right'>{fmt(pl)}</td>"
                f"<td style='padding:7px 10px;text-align:right;color:{_ppv_col};font-weight:600'>{_ppv_str}</td>"
                f"<td style='padding:7px 10px;text-align:right;color:{_pp_col};font-weight:700'>{_pp_str}</td>"
                f"<td style='padding:7px 10px;text-align:right;color:{_cagr_col};font-weight:700'>{_cagr_str}</td>"
                "</tr>")

        tl=sum(p[2] for p in poches); ti2=sum(p[1] for p in poches)
        tpv=tl-ti2; tp=(tl/ti2-1)*100 if ti2 else 0
        _t_clr = C['green'] if tpv >= 0 else C['red']
        _t_sgn = '+' if tpv >= 0 else '-'
        _tot_pvmv_str = f"{_t_sgn}{int(round(abs(tpv))):,} €".replace(',', ' ')
        _tot_pp_str = f"{'+' if tp>=0 else ''}{tp:.1f}%"
        _tbl_perf += ("<tr style='background:#111827;font-weight:700'>"
            f"<td style='padding:8px 10px'>💰 TOTAL</td>"
            f"<td style='padding:8px 10px;text-align:right;color:{C['muted']}'>{fmt(ti2)}</td>"
            f"<td style='padding:8px 10px;text-align:right'>{fmt(tl)}</td>"
            f"<td style='padding:8px 10px;text-align:right;color:{_t_clr}'>{_tot_pvmv_str}</td>"
            f"<td style='padding:8px 10px;text-align:right;color:{_t_clr}'>{_tot_pp_str}</td>"
            f"<td style='padding:8px 10px;text-align:right;color:{C['muted']};font-size:11px'>—</td>"
            "</tr>")
        _tbl_perf += "</tbody></table></div>"
        st.markdown(_tbl_perf, unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:10px;color:{C['muted']};padding:4px 0 0 0;font-style:italic'>"
            "TRI (XIRR) calculé sur les versements réels : Bourse/Crypto = DCA le 4 de chaque mois depuis "
            "févr. 2022 / août 2022, Options = dépôts IBKR réels depuis déc. 2023.</div>", unsafe_allow_html=True)

    with Rp:
        sec("TRI vs Benchmarks","⚡","#6EE7B7","#0A1C0F")
        _tg = st.session_state['tri_global']
        _mon_pf_tri = _tg['tri_global']
        _benchs_data = []
        for _idx_name in ["SP500","CAC 40","STOXX 600"]:
            _b = _tg['benchmarks'].get(_idx_name, {})
            _benchs_data.append((_b.get('display', _idx_name), _b.get('tri')))

        _tbl_bench = "<div style='overflow-x:auto'><table style='width:100%;border-collapse:collapse;font-size:13px'>"
        _tbl_bench += (f"<thead><tr style='background:#111827'>"
            f"<th style='padding:6px 10px;text-align:left;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Indice</th>"
            f"<th style='padding:6px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>TRI simulé</th>"
            f"<th style='padding:6px 10px;text-align:right;font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em;border-bottom:1px solid {C['border']}'>Alpha vs Mon PF</th>"
            "</tr></thead><tbody>")

        _pf_col = C['gold'] if (_mon_pf_tri or 0) >= 0 else C['red']
        _tbl_bench += (f"<tr style='border-bottom:1px solid #1F2937;background:#1a1f2e'>"
            f"<td style='padding:7px 10px;font-weight:700;color:{C['gold']}'>🏆 Mon PF (Global)</td>"
            f"<td style='padding:7px 10px;text-align:right;font-weight:700;color:{_pf_col}'>{f'+{_mon_pf_tri:.2f}%' if _mon_pf_tri is not None else '—'}</td>"
            f"<td style='padding:7px 10px;text-align:right;color:{C['muted']};font-size:11px'>référence</td>"
            "</tr>")

        for _bname, _btri in _benchs_data:
            if _btri is None:
                _tbl_bench += (f"<tr style='border-bottom:1px solid #1F2937'>"
                    f"<td style='padding:7px 10px;color:{C['muted']}'>{_bname}</td>"
                    f"<td style='padding:7px 10px;text-align:right;color:{C['muted']}'>—</td>"
                    f"<td style='padding:7px 10px;text-align:right;color:{C['muted']}'>—</td>"
                    "</tr>")
                continue
            _tri_col = C['cyan'] if _btri >= 0 else C['red']
            _alpha = (_mon_pf_tri - _btri) if _mon_pf_tri is not None else None
            _alpha_col = C['green'] if (_alpha or 0) >= 0 else C['red']
            _alpha_str = f"{'+' if _alpha>=0 else ''}{_alpha:.2f} pts %" if _alpha is not None else "—"
            _tbl_bench += (f"<tr style='border-bottom:1px solid #1F2937'>"
                f"<td style='padding:7px 10px;color:{C['muted']}'>{_bname}</td>"
                f"<td style='padding:7px 10px;text-align:right;font-weight:600;color:{_tri_col}'>{'+' if _btri>=0 else ''}{_btri:.2f}%</td>"
                f"<td style='padding:7px 10px;text-align:right;font-weight:700;color:{_alpha_col}'>{_alpha_str}</td>"
                "</tr>")

        _tbl_bench += "</tbody></table></div>"
        st.markdown(_tbl_bench, unsafe_allow_html=True)
        st.markdown(f"""<div style="margin-top:12px;padding:10px 14px;background:{C['card']};
border-radius:6px;border-left:2px solid {C['muted']}">
<span style="font-size:10px;color:{C['muted']};font-style:italic">
TRI (XIRR) : Bourse/Crypto = DCA le 4 de chaque mois depuis févr. 2022 / août 2022,
Options = dépôts IBKR réels. Benchmarks simulés avec les mêmes flux (SP500 TR, CAC40 GR, STOXX 600).
Alpha = TRI Mon PF − TRI Indice (pts %).</span></div>""", unsafe_allow_html=True)



    # ── Évolution annuelle (pleine largeur) ──
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    sec("Évolution annuelle du patrimoine","📈","#6EE7B7","#0A1C0F")
    tots=[sv(df_ea,11+i,9) for i in range(5)]
    yrs=[str(_YR-4),str(_YR-3),str(_YR-2),str(_YR-1),str(_YR)]
    tv=[x for x in tots if x>0]; yl=yrs[:len(tv)]
    if tv:
        fig_ea=go.Figure(go.Bar(
            x=yl, y=tv,
            marker_color='#6EE7B7',
            marker_line=dict(color=C['bg'], width=1),
            text=[f"{y/1000:.0f}k€" for y in tv],
            textposition='outside', textfont=dict(color=C['text'], size=10),
            hovertemplate='<b>%{x}</b><br>%{y:.0f} €<extra></extra>'))
        for i in range(1,len(tv)):
            evol=(tv[i]/tv[i-1]-1)*100
            fig_ea.add_annotation(x=yl[i],y=tv[i],
                text=f"{'+' if evol>=0 else ''}{evol:.0f}%",
                showarrow=False,yshift=18,
                font=dict(size=10,color=C['green'] if evol>=0 else C['red']))
        fig_ea.update_layout(**base_layout(300))
        fig_ea.update_yaxes(tickformat='.0f',ticksuffix=' €')
        st.plotly_chart(fig_ea,use_container_width=True,config={'displayModeBar':True,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d','hoverClosestCartesian','hoverCompareCartesian','toggleSpikelines'],'displaylogo':False})

    # ── Section 2 : graphiques Performance ─────────────
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)

    # ── PV/MV et TRI dans le temps (snapshots GitHub) ──
    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    sec("PV/MV & TRI dans le temps","📈","#6EE7B7","#0A1C0F")
    _snaps = load_snapshots().get("snapshots", [])
    if _snaps:
        _snap_pvmv  = [s.get("pvmv", 0) for s in _snaps]
        _snap_tri   = [s.get("tri") for s in _snaps]
        _mois_cur = datetime.now().strftime("%Y-%m")
        _MOIS_FR = ["Jan","Fév","Mar","Avr","Mai","Jun","Jul","Aoû","Sep","Oct","Nov","Déc"]
        def _fmt_snap_lbl(ym):
            try: y,m = ym[:7].split("-"); return f"{_MOIS_FR[int(m)-1]} {y}"
            except: return ym
        _snap_dates = [_fmt_snap_lbl(s["date"]) for s in _snaps]
        _mois_cur_lbl = _fmt_snap_lbl(_mois_cur)
        if not any(_fmt_snap_lbl(s["date"]) == _mois_cur_lbl for s in _snaps):
            _snap_dates.append(_mois_cur_lbl + " ●")
            _snap_pvmv.append(pvmv_t)
            _snap_tri.append(_tri_g)
        _sc1, _sc2 = st.columns(2)
        with _sc1:
            _pvmv_col3 = C['green'] if (_snap_pvmv[-1] or 0) >= 0 else C['red']
            _r3,_g3,_b3 = int(_pvmv_col3[1:3],16),int(_pvmv_col3[3:5],16),int(_pvmv_col3[5:7],16)
            _fig_pv = go.Figure(go.Scatter(x=_snap_dates, y=_snap_pvmv, mode='lines+markers',
                line=dict(color=_pvmv_col3, width=2), marker=dict(color=_pvmv_col3, size=7),
                fill='tozeroy', fillcolor=f"rgba({_r3},{_g3},{_b3},0.10)",
                hovertemplate='<b>%{x}</b><br>PV/MV : %{y:+,.0f} €<extra></extra>'))
            _fig_pv.add_hline(y=0, line_color=C['border'], line_width=1)
            _fig_pv.update_layout(**base_layout(200))
            _fig_pv.update_yaxes(tickformat='.0f', ticksuffix=' €')
            st.markdown(f"<div style='font-size:11px;color:{C['muted']};margin-bottom:4px'>PV/MV totale</div>", unsafe_allow_html=True)
            st.plotly_chart(_fig_pv, use_container_width=True, config={'displayModeBar':False})
        with _sc2:
            _tri_vals3  = [t for t in _snap_tri if t is not None]
            _tri_dates3 = [_snap_dates[i] for i,t in enumerate(_snap_tri) if t is not None]
            if _tri_vals3:
                _fig_tri = go.Figure(go.Scatter(x=_tri_dates3, y=_tri_vals3, mode='lines+markers',
                    line=dict(color=C['purple'], width=2), marker=dict(color=C['purple'], size=7),
                    hovertemplate='<b>%{x}</b><br>TRI : %{y:.2f}%<extra></extra>'))
                _fig_tri.update_layout(**base_layout(200))
                _fig_tri.update_yaxes(ticksuffix='%')
                st.markdown(f"<div style='font-size:11px;color:{C['muted']};margin-bottom:4px'>TRI annualisé (XIRR)</div>", unsafe_allow_html=True)
                st.plotly_chart(_fig_tri, use_container_width=True, config={'displayModeBar':False})
        st.markdown(f"<div style='font-size:10px;color:{C['muted']};font-style:italic'>{len(_snaps)} snapshot(s) sauvegardé(s) · cliquez 📸 Snapshot en haut pour enregistrer le mois en cours</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"""<div style='background:{C['card']};border:1px solid {C['border']};border-left:3px solid {C['purple']};
border-radius:8px;padding:14px 18px;font-size:12px;color:{C['muted']}'>
⏳ <b style='color:{C['text']}'>Aucun snapshot encore enregistré</b><br>
Cliquez <b>"📸 Snapshot"</b> en haut de page pour enregistrer le premier point
(PV/MV actuelle : <b style='color:{C["green"]}'>{fmt(pvmv_t)}</b>, TRI : <b style='color:{C["purple"]}'>{pct(_tri_g) if _tri_g else "—"}</b>).
La courbe se construira mois après mois.</div>""", unsafe_allow_html=True)

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
                            except Exception:
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
                st.selectbox("Ajouter dans :", ["📈 Actions en Portefeuille", "⚙️ Actions en Portefeuille Option", "👀 Actions à Surveiller"], key="valo_wl_target")
                add_wl = st.button("⭐ Ajouter à la Watchlist", use_container_width=True, key="valo_add")
            else:
                st.selectbox("Ajouter dans :", ["📈 Actions en Portefeuille", "⚙️ Actions en Portefeuille Option", "👀 Actions à Surveiller"], key="valo_wl_target_2")
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

        # ── Calculation engine ────────────────────────
        results = {}

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

        # Score qualité synthétique sur 10 (maintenant que hist_d est dispo)
        if hist_d and hist_d.get("cagr_rev") is not None:
            _sc_rev  = min(hist_d.get("cagr_rev",0) or 0, 30) / 30 * 2.5
            _sc_ni   = min(hist_d.get("cagr_ni",0) or 0, 30) / 30 * 2.5
            _sc_m    = min(hist_d.get("margin",[0])[0] or 0, 40) / 40 * 2.5
            _sc_fcf  = min(hist_d.get("cagr_fcf",0) or 0, 30) / 30 * 2.5
            _score   = max(0, min(10, _sc_rev + _sc_ni + _sc_m + _sc_fcf))
            _score_col = C['green'] if _score >= 7 else (C['gold'] if _score >= 5 else C['red'])
            _score_lbl = "Excellente" if _score >= 8 else ("Bonne" if _score >= 6 else ("Correcte" if _score >= 4 else "Faible"))
            _sq_cols = st.columns([6, 1])
            with _sq_cols[0]:
                st.markdown(f"""<div style="background:{C['card']};border:1px solid {_score_col}44;border-radius:10px;
padding:12px 16px;margin-bottom:4px;display:flex;align-items:center;justify-content:space-between">
<div>
  <div style="font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.06em">Score de qualité</div>
  <div style="font-size:9px;color:{C['muted']};margin-top:2px">
    CAGR CA {hist_d.get('cagr_rev',0):.0f}% · BN {hist_d.get('cagr_ni',0):.0f}% · 
    Marge {hist_d.get('margin',[0])[0]:.0f}% · FCF {hist_d.get('cagr_fcf',0) or 0:.0f}%
  </div>
</div>
<div style="display:flex;align-items:baseline;gap:6px">
  <span style="font-family:'Space Grotesk';font-size:28px;font-weight:700;color:{_score_col}">{_score:.1f}</span>
  <span style="font-size:13px;color:{C['muted']}">/10</span>
  <span style="font-size:12px;color:{_score_col};font-weight:600">{_score_lbl}</span>
</div>
</div>""", unsafe_allow_html=True)
            with _sq_cols[1]:
                st.markdown("<div style='margin-top:6px'></div>", unsafe_allow_html=True)
                with st.popover("?", use_container_width=True):
                    _sq_txt = (
                        f"**Score de qualité /10** — {hist_d.get('n',5)} ans (Yahoo Finance)  \n\n"
                        f"| Critère | Valeur | Note |  \n|---|---|---|  \n"
                        f"| CAGR CA | {hist_d.get('cagr_rev',0):.1f}% | {_sc_rev:.1f}/2.5 |  \n"
                        f"| CAGR BN | {hist_d.get('cagr_ni',0):.1f}% | {_sc_ni:.1f}/2.5 |  \n"
                        f"| Marge nette | {hist_d.get('margin',[0])[0]:.1f}% | {_sc_m:.1f}/2.5 |  \n"
                        f"| CAGR FCF | {hist_d.get('cagr_fcf',0) or 0:.1f}% | {_sc_fcf:.1f}/2.5 |  \n"
                        f"| **Total** | | **{_score:.1f}/10** |  \n\n"
                        "≥8 Excellente · ≥6 Bonne · ≥4 Correcte · <4 Faible  \n\n"
                        "⚠️ Mesure la qualité historique, pas la valorisation."
                    )
                    st.markdown(_sq_txt)
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

        # ── 4 KPI synthèse — lus directement depuis results ──
        r_base_kpi   = results.get("BASE") or {}
        pp_base_kpi  = r_base_kpi.get("price_pay", 0) or 0
        vi_base_kpi  = r_base_kpi.get("price", 0) or 0
        cours_kpi    = st.session_state.get("valo_cours", 0)
        hist_eps_kpi = st.session_state.get("valo_hist", 0)
        upside_kpi   = (pp_base_kpi - cours_kpi) / cours_kpi * 100 if cours_kpi > 0 and pp_base_kpi > 0 else None

        _n_yr  = r_base_kpi.get("n_years", 5) if r_base_kpi else 5
        _per_v = st.session_state.get("valo_per_BASE", 25)
        _g_v   = st.session_state.get("valo_g_BASE", 9)
        _ms_v  = st.session_state.get("valo_ms_BASE", 10)
        _perf_v= st.session_state.get("valo_perf_BASE", 10)

        kpi_r = st.columns(4)
        # Cartes HTML avec st.popover ? dans la même colonne
        _kpi_data_h = [
            ("💰 PRIX À PAYER BASE",
             f"{pp_base_kpi:,.0f} €" if pp_base_kpi else "—",
             "avec marge de sécurité",
             C["green"] if upside_kpi and upside_kpi > 0 else C["red"] if upside_kpi is not None else C_VAL,
             (f"**Formule :** VI / (1+{_perf_v:.0f}%)^{_n_yr} x (1-{_ms_v:.0f}%) = **{pp_base_kpi:,.0f} €**  \n\n"
              f"Prix maximum pour acheter et atteindre **{_perf_v:.0f}%/an** sur {_n_yr} ans "
              f"avec marge de sécurité {_ms_v:.0f}%.  \n\n"
              "✅ Cours < Prix à payer = opportunité  \n❌ Cours > Prix à payer = trop cher")),
            ("📈 UPSIDE BASE",
             f"{upside_kpi:+.1f}%" if upside_kpi is not None else "—",
             "vs cours actuel",
             C["green"] if upside_kpi and upside_kpi > 0 else C["red"] if upside_kpi is not None else C["muted"],
             (f"**Formule :** (Prix à payer - Cours) / Cours  \n"
              f"= ({pp_base_kpi:,.0f} - {cours_kpi:,.0f}) / {cours_kpi:,.0f}  \n\n"
              "➕ **Positif** = action sous-évaluée vs ton objectif  \n"
              "➖ **Négatif** = action trop chère pour ton rendement cible")),
            ("🔍 VALEUR INTRINSÈQUE",
             f"{vi_base_kpi:,.0f} €" if vi_base_kpi else "—",
             "scénario BASE", "#7DD3FC",
             (f"**Formule :** EPS {_YR+_n_yr} projeté x PER {_per_v}x  \n\n"
              f"Valeur estimée dans {_n_yr} ans (scénario BASE) :  \n"
              f"- Croissance CA : **{_g_v:.0f}%/an**  \n- PER cible : **{_per_v}x**  \n\n"
              "Ne tient pas compte du rendement exigé ni de la marge de sécurité.")),
            ("📊 EPS ACTUEL",
             f"{hist_eps_kpi:.2f}" if hist_eps_kpi else "—",
             "€/$ par action", C["gold"],
             ("**EPS** = Bénéfice net / Nombre d'actions  \n\n"
              "Bénéfice par action du dernier exercice (Yahoo Finance).  \n"
              "Point de départ de toutes les projections EPS.")),
        ]
        for col_k, (ti, va, su, co, hlp) in zip(kpi_r, _kpi_data_h):
            with col_k:
                st.markdown(card(ti, va, su, co), unsafe_allow_html=True)
                with st.popover("ⓘ aide", use_container_width=True):
                    st.markdown(hlp)
        st.markdown("<br>", unsafe_allow_html=True)

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
            if "Portefeuille Option" in target_label:
                target_key, target_icon = "wl_options", "⚙️"
            elif "Portefeuille" in target_label:
                target_key, target_icon = "wl_portefeuille", "📈"
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
            save_watchlist_gh()  # persistance GitHub
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
    # Watchlist chargée globalement au démarrage (_wl_loaded) — guards de sécurité uniquement
    if "wl_portefeuille" not in st.session_state:
        st.session_state.wl_portefeuille = []
    if "wl_options" not in st.session_state:
        st.session_state.wl_options = []
    if "wl_surveillance" not in st.session_state:
        st.session_state.wl_surveillance = []
    if "watchlist" not in st.session_state:
        st.session_state.watchlist = (st.session_state.wl_portefeuille +
                                      st.session_state.wl_options +
                                      st.session_state.wl_surveillance)
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
            ("wl_options",      "⚙️ Actions en Portefeuille Option",       "#F0883E"),
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
                st.markdown(f"<div style='font-size:11px;color:{C['muted']};padding:8px 12px;margin-bottom:16px;font-style:italic'>Aucune action dans cette liste</div>", unsafe_allow_html=True)
                continue

            sorted_e = sorted(entries, key=get_ecart, reverse=not asc)

            # ── En-tête du tableau ──
            _hdr_style = f"font-size:10px;color:{C['muted']};text-transform:uppercase;letter-spacing:.06em;padding:6px 4px;border-bottom:1px solid {C['border']};white-space:nowrap"
            hdr_cols = st.columns([3.2, 1.0, 1.4, 1.4, 1.8, 1.5, 1.8, 2.2])
            hdr_labels = ["Action", "Ticker", "PRU (€)", "Prix Actuel", "Prix Cible", "Écart ▼▲", "Verdict", "Analystes"]
            for hc, hl in zip(hdr_cols, hdr_labels):
                hc.markdown(f"<div style='{_hdr_style}'>{hl}</div>", unsafe_allow_html=True)

            # ── Ligne par action ──
            for idx, w in enumerate(sorted_e):
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

                _row_style = f"padding:4px;border-bottom:1px solid {C['border']}33"
                row_cols = st.columns([3.2, 1.0, 1.4, 1.4, 1.8, 1.5, 1.8, 2.2])

                _ct = C["text"]; _cm = C["muted"]; _ccyan = C["cyan"]
                with row_cols[0]:
                    st.markdown(f"<div style='padding:8px 4px;font-weight:600;font-size:12px;color:{_ct}'>{w['name']}</div>", unsafe_allow_html=True)
                with row_cols[1]:
                    st.markdown(f"<div style='padding:8px 4px;text-align:center;font-family:monospace;font-size:10px;color:{list_color}'>{ticker_w or '—'}</div>", unsafe_allow_html=True)
                with row_cols[2]:
                    # PRU éditable
                    new_pru = st.number_input(
                        label="pru",
                        value=float(pru_w) if pru_w else 0.0,
                        min_value=0.0,
                        format="%.2f",
                        label_visibility="collapsed",
                        key=f"pru_input_{list_key}_{idx}"
                    )
                    if new_pru != float(pru_w):
                        for entry in st.session_state[list_key]:
                            if entry["name"] == w["name"]:
                                entry["pru"] = new_pru
                                break
                        st.rerun()
                with row_cols[3]:
                    st.markdown(f"<div style='padding:8px 4px;text-align:right;font-weight:700;font-size:12px;color:{_ct};background:{cours_bg};border-radius:4px'>{cours_w:,.2f} €</div>", unsafe_allow_html=True)
                with row_cols[4]:
                    st.markdown(f"<div style='padding:8px 4px;text-align:right;font-size:12px;color:{_ccyan};font-weight:700'>{a_payer_w:,.0f} €</div>", unsafe_allow_html=True)
                with row_cols[5]:
                    st.markdown(f"<div style='padding:8px 4px;text-align:right;background:{ecart_bg};color:{ecart_col};font-weight:700;font-size:12px;border-radius:4px'>{ecart_w:+.2f}%</div>", unsafe_allow_html=True)
                with row_cols[6]:
                    st.markdown(f"<div style='padding:8px 4px;text-align:center;color:{verdict_col};font-weight:700;font-size:11px;white-space:nowrap'>{verdict_txt}</div>", unsafe_allow_html=True)
                with row_cols[7]:
                    _an = fetch_analyst_data(ticker_w) if ticker_w else None
                    if _an:
                        # Badge consensus
                        _rec_html = ""
                        if _an.get('rec_label'):
                            _rec_html = (
                                f"<span style='background:{_an['rec_col']}33;color:{_an['rec_col']};font-size:11px;"
                                f"font-weight:700;padding:2px 8px;border-radius:4px;border:1px solid {_an['rec_col']}55'>"
                                f"{_an['rec_label']}</span>"
                            )
                        # Prix cible
                        _tp_html = ""
                        if _an.get('target_price'):
                            _nb = f" · {_an['nb_analysts']} anal." if _an.get('nb_analysts') else ""
                            _tp_html = f"<div style='font-size:11px;color:#E2E8F0;margin-top:3px'>Cible <b>{_an['target_price']:.0f}$</b>{_nb}</div>"
                        # Dividende
                        _div_html = ""
                        _MOIS_AN = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
                        if _an.get('ex_div_date'):
                            _ed = _an['ex_div_date']
                            _ed_str = f"{_ed.day} {_MOIS_AN[_ed.month-1]} {_ed.year}"
                            _yld = f" · <b>{_an['div_yield']:.2f}%</b>/an" if _an.get('div_yield') else ""
                            _div_html = f"<div style='font-size:10px;color:#818CF8;margin-top:3px'>💰 Ex-div {_ed_str}{_yld}</div>"
                        st.markdown(
                            f"<div style='padding:4px 4px'>{_rec_html}{_tp_html}{_div_html}</div>",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(f"<div style='padding:8px 4px;text-align:center;font-size:10px;color:{C['muted']}'>—</div>", unsafe_allow_html=True)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

        # ── Gestion des actions ──────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:12px;font-weight:600;color:{C_WL};margin-bottom:8px'>⚙️ Gérer les actions</div>", unsafe_allow_html=True)

        # Construire liste avec indication de la liste source
        _all_entries = []
        _list_labels = {
            "wl_portefeuille": "📈 Portefeuille",
            "wl_options":      "⚙️ Portefeuille Option",
            "wl_surveillance": "👀 Surveiller",
        }
        for _k, _lbl in _list_labels.items():
            for _w in st.session_state.get(_k, []):
                _all_entries.append((_w["name"], _k, _lbl))

        if _all_entries:
            _names_display = [f"{n}  ({lbl})" for n, k, lbl in _all_entries]
            _names_only    = [n for n, k, lbl in _all_entries]

            _mgmt_cols = st.columns([3, 2, 1, 1])
            with _mgmt_cols[0]:
                st.markdown("<div style='font-size:10px;color:{};margin-bottom:2px'>Action</div>".format(C['muted']), unsafe_allow_html=True)
                _sel_idx = st.selectbox("", _names_display,
                    label_visibility="collapsed", key="wl_mgmt_sel")
                _sel_name = _names_only[_names_display.index(_sel_idx)] if _sel_idx in _names_display else None
                _sel_source = next((k for n,k,l in _all_entries if n == _sel_name), None)

            with _mgmt_cols[1]:
                st.markdown("<div style='font-size:10px;color:{};margin-bottom:2px'>Déplacer vers</div>".format(C['muted']), unsafe_allow_html=True)
                _dest_options = ["📈 Actions en Portefeuille", "⚙️ Actions en Portefeuille Option", "👀 Actions à Surveiller"]
                _dest_label = st.selectbox("", _dest_options,
                    label_visibility="collapsed", key="wl_mgmt_dest")

            with _mgmt_cols[2]:
                st.markdown("<div style='font-size:10px;color:{};margin-bottom:2px'>&nbsp;</div>".format(C['muted']), unsafe_allow_html=True)
                if st.button("↗️ Déplacer", key="wl_move_btn", use_container_width=True):
                    if _sel_name and _sel_source:
                        # Trouver l'entrée
                        _entry = next((w for w in st.session_state.get(_sel_source, []) if w["name"] == _sel_name), None)
                        if _entry:
                            # Retirer de la source
                            st.session_state[_sel_source] = [w for w in st.session_state[_sel_source] if w["name"] != _sel_name]
                            # Ajouter dans la destination
                            if "Portefeuille Option" in _dest_label:
                                _dest_key = "wl_options"
                            elif "Portefeuille" in _dest_label:
                                _dest_key = "wl_portefeuille"
                            else:
                                _dest_key = "wl_surveillance"
                            _entry["liste"] = _dest_key
                            st.session_state[_dest_key].append(_entry)
                            save_watchlist_gh()  # persistance GitHub
                            st.rerun()

            with _mgmt_cols[3]:
                st.markdown("<div style='font-size:10px;color:{};margin-bottom:2px'>&nbsp;</div>".format(C['muted']), unsafe_allow_html=True)
                if st.button("🗑️", key="valo_del_btn", use_container_width=True,
                    help="Supprimer cette action de la watchlist"):
                    if _sel_name:
                        for k in ["wl_portefeuille", "wl_options", "wl_surveillance"]:
                            st.session_state[k] = [w for w in st.session_state.get(k, []) if w["name"] != _sel_name]
                        save_watchlist_gh()  # persistance GitHub
                        st.rerun()

        if st.button("🗑️ Vider toutes les listes", key="valo_clear"):
            for k in ["wl_portefeuille", "wl_options", "wl_surveillance"]:
                st.session_state[k] = []
            st.session_state.watchlist = []
            save_watchlist_gh()  # persistance GitHub
            st.rerun()

# ══════════════════════════════════════════════════════
# TAB 9 — CHANTIER (roadmap & dette technique connue)
# ══════════════════════════════════════════════════════
with tab_marche:
    # ── Guard : s'assurer que la watchlist est chargée depuis GitHub ──
    if "wl_portefeuille" not in st.session_state:
        _wl_gh_m = load_watchlist_gh()
        st.session_state.wl_portefeuille  = _wl_gh_m.get("wl_portefeuille", [])
        st.session_state.wl_options       = _wl_gh_m.get("wl_options", [])
        st.session_state.wl_surveillance  = _wl_gh_m.get("wl_surveillance", [])
        st.session_state.watchlist = (st.session_state.wl_portefeuille +
                                       st.session_state.wl_options +
                                       st.session_state.wl_surveillance)

    st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
    sec("Tableau de bord marché", "📊", "#818CF8", "#0D0F1A")

    # ── Marchés (indices + BTC + VIX) — variation journalière ──
    if YF_AVAILABLE:
        st.markdown("""<style>
.mkt-card { height: 290px !important; box-sizing: border-box !important; display: flex !important; flex-direction: column !important; border-radius: 8px; overflow: hidden; }
.mkt-card-body { padding: 10px 14px 6px 14px; flex-shrink: 0; }
.mkt-card-chart { flex: 1 !important; display: flex !important; flex-direction: column !important; justify-content: flex-end; overflow: hidden; }
.mkt-card-chart svg { width: 100% !important; height: 100% !important; display: block; }
</style>""", unsafe_allow_html=True)
        with st.expander("📊 Indices · VIX · Fear & Greed — variation journalière", expanded=True):
            _mkt_cols = st.columns(len(MARKET_TICKERS) + 2)  # +1 VIX +1 F&G
            for _mcol, (_mname, _mtk, _micon) in zip(_mkt_cols, MARKET_TICKERS):
                _snap = fetch_market_history(_mtk, "1d", "5m")
                with _mcol:
                    if _snap is None:
                        st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:10px 14px">
            <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em">{_micon} {_mname}</div>
            <div style="font-size:13px;color:{C['muted']};margin-top:4px">—</div></div>""", unsafe_allow_html=True)
                        continue
                    _vcol = C['green'] if _snap['var_pct']>=0 else C['red']
                    _unit = " $" if _mname=="BTC" else ""
                    _prix_str = f"{_snap['prix']:,.0f}{_unit}".replace(",", " ")
                    # SVG inline sparkline (card + courbe intégrées)
                    _serie_raw = _snap['serie']
                    _ref = _snap.get('ref') or (_serie_raw[0] if _serie_raw[0] != 0 else 1)
                    _serie_pct = [(v / _ref - 1) * 100 for v in _serie_raw]
                    _SW, _SH = 300, 180
                    # Range incluant toujours 0
                    _smn = min(min(_serie_pct), 0)
                    _smx = max(max(_serie_pct), 0)
                    _srng = (_smx - _smn) if _smx != _smn else 1
                    _PAD = 8  # padding haut/bas
                    _DRAW = _SH - 2 * _PAD
                    _spts = ' '.join(
                        f"{i/max(len(_serie_pct)-1,1)*_SW:.1f},{_PAD + _DRAW*(1-(v-_smn)/_srng):.1f}"
                        for i,v in enumerate(_serie_pct)
                    )
                    _spoly = f"0,{_SH} {_spts} {_SW},{_SH}"
                    # Ligne zéro : même calcul que les points
                    _sy0 = _PAD + _DRAW * (1 - (0 - _smn) / _srng)
                    _ssvg = (
                        f'<svg viewBox="0 0 {_SW} {_SH}" xmlns="http://www.w3.org/2000/svg" '
                        f'style="width:100%;display:block;border-radius:0 0 6px 6px;margin-top:-1px">'
                        f'<polygon points="{_spoly}" fill="{_vcol}" opacity="0.12"/>'
                        f'<line x1="0" y1="{_sy0:.1f}" x2="{_SW}" y2="{_sy0:.1f}" '
                        f'stroke="#ffffff" stroke-width="0.8" stroke-dasharray="4,4" opacity="0.25"/>'
                        f'<polyline points="{_spts}" fill="none" stroke="{_vcol}" '
                        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>'
                    )
                    st.markdown(
                        f'<div class="mkt-card" style="background:{C["card"]};border:1px solid {C["border"]}">'
                        f'<div class="mkt-card-body">'
                        f'<div style="font-size:11px;color:{C["muted"]};text-transform:uppercase;letter-spacing:.05em">{_micon} {_mname}</div>'
                        f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:2px">'
                        f'<span style="font-family:Space Grotesk;font-size:18px;font-weight:700">{_prix_str}</span>'
                        f'<span style="font-size:12px;font-weight:700;color:{_vcol}">{("+" if _snap["var_pct"]>=0 else "")}{_snap["var_pct"]:.2f}%</span>'
                        f'</div></div>'
                        f'<div class="mkt-card-chart">'
                        + _ssvg +
                        f'</div></div>',
                        unsafe_allow_html=True
                    )

            # ── VIX — card séparée avec sparkline ──
            with _mkt_cols[-2]:
                _vix_snap = fetch_market_history("^VIX", "1d", "5m")
                if _vix_snap is None:
                    st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:10px 14px">
        <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em">😱 VIX</div>
        <div style="font-size:13px;color:{C['muted']};margin-top:4px">—</div></div>""", unsafe_allow_html=True)
                else:
                    _vix_val = _vix_snap['prix']
                    _vix_var = _vix_snap['var_pct']
                    if _vix_val < 15:
                        _vix_label, _vix_col = "Calme", C['green']
                    elif _vix_val < 20:
                        _vix_label, _vix_col = "Normal", "#A3E635"
                    elif _vix_val < 30:
                        _vix_label, _vix_col = "Prudence", C['gold']
                    elif _vix_val < 40:
                        _vix_label, _vix_col = "Stress", C['red']
                    else:
                        _vix_label, _vix_col = "Panique !", "#FF00FF"
                    _vix_var_col = C['red'] if _vix_var >= 0 else C['green']
                    # Sparkline VIX en SVG inline
                    _vix_serie = _vix_snap['serie']
                    _vref = _vix_snap.get('ref') or (_vix_serie[0] if _vix_serie[0] != 0 else 1)
                    _vix_pct = [(v / _vref - 1) * 100 for v in _vix_serie]
                    _VW, _VH = 300, 180
                    _vmn = min(min(_vix_pct), 0)
                    _vmx = max(max(_vix_pct), 0)
                    _vrng = (_vmx - _vmn) if _vmx != _vmn else 1
                    _VPAD = 8
                    _VDRAW = _VH - 2 * _VPAD
                    _vpts = ' '.join(
                        f"{i/max(len(_vix_pct)-1,1)*_VW:.1f},{_VPAD + _VDRAW*(1-(v-_vmn)/_vrng):.1f}"
                        for i,v in enumerate(_vix_pct)
                    )
                    _vpoly = f"0,{_VH} {_vpts} {_VW},{_VH}"
                    _vy0 = _VPAD + _VDRAW * (1 - (0 - _vmn) / _vrng)
                    _vsvg = (
                        f'<svg viewBox="0 0 {_VW} {_VH}" xmlns="http://www.w3.org/2000/svg" ' +
                        f'style="width:100%;display:block;border-radius:0 0 6px 6px">' +
                        f'<polygon points="{_vpoly}" fill="{_vix_col}" opacity="0.12"/>' +
                        f'<line x1="0" y1="{_vy0:.1f}" x2="{_VW}" y2="{_vy0:.1f}" stroke="#ffffff" stroke-width="0.8" stroke-dasharray="4,4" opacity="0.25"/>' +
                        f'<polyline points="{_vpts}" fill="none" stroke="{_vix_col}" ' +
                        f'stroke-width="1.5" stroke-linejoin="round"/></svg>'
                    )
                    st.markdown(
                        f'<div class="mkt-card" style="background:{C["card"]};border:1px solid {_vix_col}44">' +
                        f'<div class="mkt-card-body">' +
                        f'<div style="font-size:11px;color:{C["muted"]};text-transform:uppercase;letter-spacing:.05em">😱 VIX — Peur</div>' +
                        f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:2px">' +
                        f'<span style="font-family:Space Grotesk;font-size:18px;font-weight:700">{_vix_val:.2f}</span>' +
                        f'<span style="font-size:12px;font-weight:700;color:{_vix_var_col}">{("+" if _vix_var>=0 else "")}{_vix_var:.2f}%</span>' +
                        f'</div>' +
                        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px">' +
                        f'<div style="padding:2px 8px;border-radius:4px;background:{_vix_col}22;display:inline-block">' +
                        f'<span style="font-size:11px;font-weight:700;color:{_vix_col}">{_vix_label}</span></div>' +
                        f'<span style="font-size:8px;color:{C["muted"]}">&lt;15 Calme &middot; &lt;20 Normal &middot; &lt;30 Prudence &middot; &lt;40 Stress</span>' +
                        f'</div></div>' +
                        f'<div class="mkt-card-chart">' +
                        _vsvg +
                        f'</div></div>',
                        unsafe_allow_html=True
                    )

            # ── Fear & Greed Index CNN ──
            with _mkt_cols[-1]:
                _fg_data = fetch_fear_greed()
                _FG_LABELS = {
                    'extreme fear':  ('Peur Extrême',    '#EF4444'),
                    'fear':          ('Peur',            '#F97316'),
                    'neutral':       ('Neutre',          '#EAB308'),
                    'greed':         ('Avidité',         '#84CC16'),
                    'extreme greed': ('Avidité Extrême', '#22C55E'),
                }
                if _fg_data is None:
                    st.markdown(f"""<div style="background:{C['card']};border:1px solid {C['border']};border-radius:8px;padding:10px 14px">
            <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em">😨 Fear &amp; Greed</div>
            <div style="font-size:13px;color:{C['muted']};margin-top:4px">—</div></div>""", unsafe_allow_html=True)
                else:
                    import math as _math
                    _fg_score = int(_fg_data['score'])
                    _fg_prev  = int(_fg_data['prev_close'])
                    _fg_label, _fg_col = _FG_LABELS.get(_fg_data['rating'].lower(), ('—', C['muted']))
                    _fg_delta = _fg_score - _fg_prev
                    _fg_delta_col = C['red'] if _fg_delta < 0 else C['green']

                    # ── Gauge SVG demi-cercle ──
                    # Centre (115,105), r=88, viewBox 240×145 (élargi pour ticks 0 et 100)
                    # score=0 → 180° (gauche), score=100 → 0° (droite)
                    _CX, _CY, _R = 115, 105, 88
                    _RI = 70  # rayon intérieur (épaisseur arc = 18)
                    _ARC = _math.pi * _R  # longueur demi-cercle

                    def _pt(angle_deg, r):
                        a = _math.radians(angle_deg)
                        return _CX + r * _math.cos(a), _CY - r * _math.sin(a)

                    # Zones : score 0→25→45→55→75→100 = angles 180→135→63→45→-27→0 (NON)
                    # Mapping score→angle : angle = 180 - score*1.8
                    # Zones en arcs SVG : on dessine 5 chemins de bord à bord
                    def _arc_path(s_start, s_end, color):
                        a1 = 180 - s_start * 1.8
                        a2 = 180 - s_end * 1.8
                        x1o, y1o = _pt(a1, _R)
                        x2o, y2o = _pt(a2, _R)
                        x1i, y1i = _pt(a1, _RI)
                        x2i, y2i = _pt(a2, _RI)
                        # arc extérieur gauche→droite (sens horaire = 0,1), arc intérieur droite→gauche
                        return (f'<path d="M{x1o:.1f},{y1o:.1f} A{_R},{_R} 0 0,1 {x2o:.1f},{y2o:.1f} '
                                f'L{x2i:.1f},{y2i:.1f} A{_RI},{_RI} 0 0,0 {x1i:.1f},{y1i:.1f} Z" '
                                f'fill="{color}" opacity="0.85"/>')

                    _zones_svg = (
                        _arc_path(0,  25,  '#EF4444') +
                        _arc_path(25, 45,  '#F97316') +
                        _arc_path(45, 55,  '#EAB308') +
                        _arc_path(55, 75,  '#84CC16') +
                        _arc_path(75, 100, '#22C55E')
                    )

                    # Aiguille
                    _needle_angle = 180 - _fg_score * 1.8
                    _nrad = _math.radians(_needle_angle)
                    _nx = _CX + 82 * _math.cos(_nrad)
                    _ny = _CY - 82 * _math.sin(_nrad)

                    # Ticks + labels repères 0,25,50,75,100
                    _ticks_svg = ''
                    for _v, _lbl in [(0,'0'),(25,'25'),(50,'50'),(75,'75'),(100,'100')]:
                        _ta = 180 - _v * 1.8
                        _tx1, _ty1 = _pt(_ta, _R + 4)
                        _tx2, _ty2 = _pt(_ta, _R + 14)
                        _tlx, _tly = _pt(_ta, _R + 26)
                        _ticks_svg += f'<line x1="{_tx1:.1f}" y1="{_ty1:.1f}" x2="{_tx2:.1f}" y2="{_ty2:.1f}" stroke="#666" stroke-width="1.5"/>'
                        _ticks_svg += f'<text x="{_tlx:.1f}" y="{_tly:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="10" fill="#888">{_lbl}</text>'

                    # Labels zones
                    _zone_labels = [
                        (12,  ['Ext.', 'Fear'],  '#EF4444'),
                        (35,  ['Fear'],           '#F97316'),
                        (50,  ['Neutral'],        '#EAB308'),
                        (65,  ['Greed'],          '#84CC16'),
                        (87,  ['Ext.', 'Greed'],  '#22C55E'),
                    ]
                    _zlabels_svg = ''
                    for _zs, _zlines, _zc in _zone_labels:
                        _za = 180 - _zs * 1.8
                        _zlx, _zly = _pt(_za, (_R + _RI) / 2)
                        _zoff = -5 if len(_zlines) > 1 else 0
                        for _i, _line in enumerate(_zlines):
                            _zlabels_svg += f'<text x="{_zlx:.1f}" y="{_zly + _zoff + _i*11:.1f}" text-anchor="middle" dominant-baseline="middle" font-size="9" font-weight="700" fill="white" stroke="#1a1a2e" stroke-width="3" paint-order="stroke">{_line}</text>'

                    _gauge = f"""<svg viewBox="0 0 240 145" xmlns="http://www.w3.org/2000/svg" style="width:100%;display:block">
  {_zones_svg}
  {_ticks_svg}
  {_zlabels_svg}
  <line x1="{_CX}" y1="{_CY}" x2="{_nx:.1f}" y2="{_ny:.1f}" stroke="white" stroke-width="3" stroke-linecap="round"/>
  <circle cx="{_CX}" cy="{_CY}" r="6" fill="white"/>
  <circle cx="{_CX}" cy="{_CY}" r="3" fill="#333"/>
  <text x="{_CX}" y="{_CY + 22}" text-anchor="middle" font-size="18" font-weight="700" fill="white">{_fg_score}</text>
</svg>"""

                    st.markdown(f"""<div class="mkt-card" style="background:{C['card']};border:1px solid {_fg_col}44;justify-content:space-between">
  <div class="mkt-card-body" style="padding:10px 14px 4px 14px">
    <div style="font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.05em">😨 Fear &amp; Greed — CNN</div>
  </div>
  <div style="flex:1;display:flex;align-items:center;justify-content:center">
    {_gauge}
  </div>
  <div style="padding:0 14px 10px 14px;display:flex;justify-content:space-between;align-items:center">
    <div style="padding:3px 10px;border-radius:4px;background:{_fg_col}22">
      <span style="font-size:12px;font-weight:700;color:{_fg_col}">{_fg_label}</span>
    </div>
    <div style="font-size:10px;color:{C['muted']}">Veille : <b style="color:{_fg_delta_col}">{_fg_prev}</b> ({'+' if _fg_delta>=0 else ''}{_fg_delta})</div>
  </div>
</div>""", unsafe_allow_html=True)




    # ── Calendrier Earnings ──
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    sec("Calendrier Earnings", "📅", "#818CF8", "#0D0F1A")
    with st.expander("📅 Calendrier Earnings", expanded=True):

        # Collecter tous les tickers : options IBKR ouvertes + watchlist (pas actions_detenues IBKR — elles seront dans wl_portefeuille)
        _earn_tickers = set()
        _ibkr_d = st.session_state.get('ibkr_data', {})
        # Options IBKR ouvertes uniquement
        for _yr_d in _ibkr_d.values():
            for _t in _yr_d.get('trades', []):
                if _t.get('statut') == 'Ouverte':
                    _earn_tickers.add(_t.get('ticker', ''))
        # Watchlist (toutes catégories)
        for _wl_key in ['wl_portefeuille', 'wl_options', 'wl_surveillance']:
            for _w in st.session_state.get(_wl_key, []):
                if _w.get('ticker'):
                    _earn_tickers.add(_w['ticker'])
        _earn_tickers.discard('')

        if not _earn_tickers:
            st.info("Aucun ticker trouvé — charge des données IBKR ou ajoute des tickers à la watchlist.")
        else:
            _earn_list = fetch_earnings_calendar(tuple(sorted(_earn_tickers)))

            # Badge sources
            _src_html = ' '.join([
                f'<span style="background:#1C2333;border:1px solid #2D3748;border-radius:4px;padding:2px 8px;font-size:11px;color:#94A3B8">{t}</span>'
                for t in sorted(_earn_tickers)
            ])
            st.markdown(f"<div style='margin-bottom:12px;display:flex;flex-wrap:wrap;gap:6px'>{_src_html}</div>",
                        unsafe_allow_html=True)

            if not _earn_list:
                st.info("Aucune date d'earnings trouvée pour ces tickers (données yfinance parfois indisponibles).")
            else:
                from datetime import date as _date, timedelta as _td
                _today_e = _date.today()
                # Regrouper par semaine
                _weeks = {}
                for _e in _earn_list:
                    _d = _e['date']
                    _monday = _d - _td(days=_d.weekday())
                    _weeks.setdefault(_monday, []).append(_e)

                # Pré-calcul : listes source par ticker
                _ibkr_options_set = set(
                    _t.get('ticker','') for _yr in _ibkr_d.values()
                    for _t in _yr.get('trades',[]) if _t.get('statut')=='Ouverte'
                )
                _wl_pf_set   = set(w.get('ticker','') for w in st.session_state.get('wl_portefeuille', []))
                _wl_opt_set  = set(w.get('ticker','') for w in st.session_state.get('wl_options', []))
                _wl_surv_set = set(w.get('ticker','') for w in st.session_state.get('wl_surveillance', []))

                # Retourne (label, couleur_accent, fond_teinté)
                def _earn_src(tk):
                    if tk in _ibkr_options_set: return '⚙️ Options IBKR', '#818CF8', '#818CF818'
                    if tk in _wl_pf_set:        return '📈 Portefeuille', '#6EE7B7', '#6EE7B718'
                    if tk in _wl_opt_set:       return '⚙️ Options WL',   '#C4B5FD', '#C4B5FD18'
                    if tk in _wl_surv_set:      return '👀 Surveillance', '#FCD34D', '#FCD34D18'
                    return '⭐ Watchlist', '#94A3B8', '#94A3B818'

                _MOIS_FR = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
                _JOUR_FULL = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi']

                for _wk_monday in sorted(_weeks.keys()):
                    _wk_end = _wk_monday + _td(days=4)
                    _is_this_week = _wk_monday <= _today_e <= _wk_end

                    # En-tête semaine
                    _wk_label = (
                        f"<span style='font-size:13px;font-weight:700;color:#E2E8F0'>"
                        f"Semaine du {_wk_monday.day} {_MOIS_FR[_wk_monday.month-1]}"
                        f" → {_wk_end.day} {_MOIS_FR[_wk_end.month-1]} {_wk_end.year}</span>"
                    )
                    # Délai jusqu'à la semaine
                    _days_to_wk = (_wk_monday - _today_e).days
                    if _is_this_week:
                        _delay_html = "<span style='font-size:11px;color:#818CF8;font-weight:600;margin-left:10px'>— cette semaine</span>"
                    elif _days_to_wk > 0:
                        _delay_html = f"<span style='font-size:11px;color:#64748B;margin-left:10px'>— dans {_days_to_wk} jour{'s' if _days_to_wk > 1 else ''}</span>"
                    else:
                        _delay_html = "<span style='font-size:11px;color:#475569;margin-left:10px'>— passée</span>"
                    _this_wk_badge = (
                        "<span style='background:#7C3AED;color:white;font-size:10px;"
                        "padding:2px 9px;border-radius:10px;font-weight:700;margin-left:10px'>CETTE SEMAINE</span>"
                    ) if _is_this_week else ""

                    # Construire grille 5 colonnes (Lun→Ven)
                    # On indexe les earnings par jour de semaine (0=Lun, 4=Ven)
                    _by_day = {i: [] for i in range(5)}
                    for _e in _weeks[_wk_monday]:
                        _dow = _e['date'].weekday()
                        if 0 <= _dow <= 4:
                            _by_day[_dow].append(_e)

                    # Cellules colonnes
                    _cols_html = ''
                    for _dow in range(5):
                        _day_date = _wk_monday + _td(days=_dow)
                        _is_today = (_day_date == _today_e)
                        _day_events = _by_day[_dow]

                        # En-tête colonne
                        _hdr_bg  = '#1E293B' if _is_today else '#0D1117'
                        _hdr_col = '#818CF8' if _is_today else '#475569'
                        _hdr_day = f"{_JOUR_FULL[_dow][:3]} {_day_date.day} {_MOIS_FR[_day_date.month-1]}"
                        _today_dot = "<span style='color:#818CF8;margin-left:4px'>●</span>" if _is_today else ""

                        _events_html = ''
                        for _e in _day_events:
                            _tk  = _e['ticker']
                            _dl  = (_e['date'] - _today_e).days
                            _src_lbl, _src_c, _src_bg = _earn_src(_tk)

                            # EPS/Rev
                            _est_parts = []
                            if _e.get('eps_est') is not None:
                                _est_parts.append(f"EPS {_e['eps_est']:.2f}$")
                            if _e.get('rev_est') is not None:
                                _rv = _e['rev_est']
                                _est_parts.append(f"Rev {_rv/1e9:.1f}B$" if abs(_rv)>=1e9 else f"Rev {_rv/1e6:.0f}M$")
                            _est_str = ' · '.join(_est_parts)

                            # Bordure urgence (indépendante de la source)
                            if _dl < 0:
                                _card_border = '#374151'
                            elif _dl == 0:
                                _card_border = '#818CF8'
                            elif _dl <= 2:
                                _card_border = '#F97316'
                            else:
                                _card_border = '#334155'

                            _an_card = fetch_analyst_data(_tk)
                            _an_badge = (
                                f"<span style='font-size:9px;color:{_an_card['rec_col']};background:{_an_card['rec_col']}22;"
                                f"padding:1px 5px;border-radius:3px;font-weight:700;margin-left:4px'>{_an_card['rec_label']}</span>"
                            ) if _an_card else ""
                            _events_html += f"""<div style="background:{_src_bg};border:1px solid {_card_border};
    border-radius:6px;padding:8px 10px;margin-bottom:6px">
      <div style="font-size:14px;font-weight:800;color:#F1F5F9;letter-spacing:.03em">{_tk}</div>
      <div style="margin-top:3px">
        <span style="font-size:9px;color:{_src_c};font-weight:700">{_src_lbl}</span>{_an_badge}
      </div>
      {"<div style='font-size:11px;color:#E2E8F0;margin-top:5px;font-weight:500'>" + _est_str + "</div>" if _est_str else ""}
    </div>"""

                        _empty_cell = (
                            "<div style='height:40px;border:1px dashed #1E293B;border-radius:6px;"
                            "display:flex;align-items:center;justify-content:center'>"
                            "<span style='font-size:11px;color:#1E293B'>—</span></div>"
                        ) if not _events_html else ''

                        _cols_html += f"""<td style="width:20%;padding:6px;vertical-align:top">
      <div style="background:{_hdr_bg};border-radius:4px;padding:4px 8px;margin-bottom:6px;
      border-bottom:2px solid {_hdr_col}">
        <span style="font-size:11px;font-weight:700;color:{_hdr_col}">{_hdr_day}{_today_dot}</span>
      </div>
      {_events_html or _empty_cell}
    </td>"""

                    st.markdown(f"""<div style="margin-bottom:4px">{_wk_label}{_delay_html}{_this_wk_badge}</div>
    <div style="background:#0A0E17;border:1px solid {'#818CF8' if _is_this_week else '#1E293B'};
    border-radius:10px;padding:6px;margin-bottom:16px;overflow-x:auto">
    <table style="width:100%;border-collapse:collapse;table-layout:fixed"><tr>{_cols_html}</tr></table>
    </div>""", unsafe_allow_html=True)


        # ── Calendrier Dividendes ──
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    sec("Calendrier Dividendes", "💰", "#818CF8", "#0D0F1A")
    with st.expander("💰 Calendrier Dividendes", expanded=True):

        _div_tickers = set()
        for _wl_key in ['wl_portefeuille', 'wl_options', 'wl_surveillance']:
            for _w in st.session_state.get(_wl_key, []):
                if _w.get('ticker'):
                    _div_tickers.add(_w['ticker'])
        _div_tickers.discard('')

        if not _div_tickers:
            st.info("Aucun ticker dans la watchlist — ajoute des actions pour voir les dividendes.")
        else:
            _div_list = fetch_dividend_calendar(tuple(sorted(_div_tickers)))

            _div_src_html = ' '.join([
                f'<span style="background:#1C2333;border:1px solid #2D3748;border-radius:4px;padding:2px 8px;font-size:11px;color:#94A3B8">{t}</span>'
                for t in sorted(_div_tickers)
            ])
            st.markdown(f"<div style='margin-bottom:12px;display:flex;flex-wrap:wrap;gap:6px'>{_div_src_html}</div>",
                        unsafe_allow_html=True)

            if not _div_list:
                st.info("Aucune date ex-dividende à venir trouvée pour ces tickers (actions sans dividende ou données indisponibles).")
            else:
                from datetime import date as _date_div, timedelta as _td_div
                _today_div = _date_div.today()
                _MOIS_D = ['Jan','Fév','Mar','Avr','Mai','Jun','Jul','Aoû','Sep','Oct','Nov','Déc']
                _JOUR_D = ['Lundi','Mardi','Mercredi','Jeudi','Vendredi']

                _div_weeks = {}
                for _dv in _div_list:
                    _dd = _dv['ex_date']
                    _mon = _dd - _td_div(days=_dd.weekday())
                    _div_weeks.setdefault(_mon, []).append(_dv)

                for _wk_mon in sorted(_div_weeks.keys()):
                    _wk_end_d = _wk_mon + _td_div(days=4)
                    _is_tw_d  = _wk_mon <= _today_div <= _wk_end_d
                    _days_to  = (_wk_mon - _today_div).days
                    _wk_lbl   = (
                        f"<span style='font-size:13px;font-weight:700;color:#E2E8F0'>"
                        f"Semaine du {_wk_mon.day} {_MOIS_D[_wk_mon.month-1]}"
                        f" → {_wk_end_d.day} {_MOIS_D[_wk_end_d.month-1]} {_wk_end_d.year}</span>"
                    )
                    if _is_tw_d:
                        _delay_d = "<span style='font-size:11px;color:#818CF8;font-weight:600;margin-left:10px'>— cette semaine</span>"
                    elif _days_to > 0:
                        _s = 's' if _days_to > 1 else ''
                        _delay_d = f"<span style='font-size:11px;color:#64748B;margin-left:10px'>— dans {_days_to} jour{_s}</span>"
                    else:
                        _delay_d = "<span style='font-size:11px;color:#475569;margin-left:10px'>— passée</span>"
                    _tw_badge_d = (
                        "<span style='background:#7C3AED;color:white;font-size:10px;"
                        "padding:2px 9px;border-radius:10px;font-weight:700;margin-left:10px'>CETTE SEMAINE</span>"
                    ) if _is_tw_d else ""

                    _by_day_d = {i: [] for i in range(5)}
                    for _dv in _div_weeks[_wk_mon]:
                        _dow_d = _dv['ex_date'].weekday()
                        if 0 <= _dow_d <= 4:
                            _by_day_d[_dow_d].append(_dv)

                    _cols_div = ''
                    for _dow_d in range(5):
                        _day_d = _wk_mon + _td_div(days=_dow_d)
                        _is_today_d = (_day_d == _today_div)
                        _hdr_bg_d  = '#1E293B' if _is_today_d else '#0D1117'
                        _hdr_col_d = '#818CF8' if _is_today_d else '#475569'
                        _hdr_lbl_d = f"{_JOUR_D[_dow_d][:3]} {_day_d.day} {_MOIS_D[_day_d.month-1]}"
                        _today_dot_d = "<span style='color:#818CF8;margin-left:4px'>●</span>" if _is_today_d else ""

                        _evts_d = ''
                        for _dv in _by_day_d[_dow_d]:
                            _dl_d = (_dv['ex_date'] - _today_div).days
                            if _dl_d < 0:    _cb_d = '#374151'
                            elif _dl_d == 0: _cb_d = '#818CF8'
                            elif _dl_d <= 2: _cb_d = '#F97316'
                            else:            _cb_d = '#334155'
                            _yld_html = f"<div style='font-size:13px;color:#E2E8F0;margin-top:5px;font-weight:700'>{_dv['yield_pct']:.2f}%/an</div>" if _dv.get('yield_pct') else ""
                            _rate_html = f"<div style='font-size:11px;color:#94A3B8;margin-top:2px'>{_dv['rate']:.2f}$/an</div>" if _dv.get('rate') else ""
                            _evts_d += (
                                f'<div style="background:#818CF818;border:1px solid {_cb_d};'
                                f'border-radius:6px;padding:8px 10px;margin-bottom:6px">'
                                f'  <div style="font-size:14px;font-weight:800;color:#F1F5F9;letter-spacing:.03em">{_dv["ticker"]}</div>'
                                f'  <div style="font-size:9px;color:#818CF8;font-weight:700;margin-top:3px">💰 Ex-dividende</div>'
                                f'  {_yld_html}{_rate_html}'
                                f'</div>'
                            )

                        _empty_d = (
                            "<div style='height:40px;border:1px dashed #1E293B;border-radius:6px;"
                            "display:flex;align-items:center;justify-content:center'>"
                            "<span style='font-size:11px;color:#1E293B'>—</span></div>"
                        ) if not _evts_d else ''

                        _cols_div += (
                            f'<td style="width:20%;padding:6px;vertical-align:top">'
                            f'  <div style="background:{_hdr_bg_d};border-radius:4px;padding:4px 8px;margin-bottom:6px;border-bottom:2px solid {_hdr_col_d}">'
                            f'    <span style="font-size:11px;font-weight:700;color:{_hdr_col_d}">{_hdr_lbl_d}{_today_dot_d}</span>'
                            f'  </div>'
                            f'  {_evts_d or _empty_d}'
                            f'</td>'
                        )

                    st.markdown(
                        f'<div style="margin-bottom:4px">{_wk_lbl}{_delay_d}{_tw_badge_d}</div>'
                        f'<div style="background:#0A0E17;border:1px solid {("#818CF8" if _is_tw_d else "#1E293B")};'
                        f'border-radius:10px;padding:6px;margin-bottom:16px;overflow-x:auto">'
                        f'<table style="width:100%;border-collapse:collapse;table-layout:fixed"><tr>{_cols_div}</tr></table>'
                        f'</div>',
                        unsafe_allow_html=True
                    )


with tab9:
    sec("🚧 Chantier — Roadmap & dette technique", "🚧", "#F59E0B", "#1C1400")
    # ── DEBUG GitHub (temporaire) ──
    st.markdown(f"<div style='font-size:12px;color:{C['muted']};padding:4px 0 16px 0'>Mémo partagé entre sessions — état des chantiers en cours et à venir. Séquence validée le 28/06/2026.</div>", unsafe_allow_html=True)

    def _chantier_card(titre, icone, contenu, couleur, badge=None):
        _badge_html = f"<span style='background:{couleur};color:#0A0E14;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px;text-transform:uppercase;letter-spacing:.05em;margin-left:8px'>{badge}</span>" if badge else ""
        st.markdown(f"""<div style='background:{C['card']};border:1px solid {C['border']};border-left:3px solid {couleur};
border-radius:8px;padding:14px 18px;margin-bottom:12px'>
<div style='font-size:14px;font-weight:700;color:{couleur};margin-bottom:6px'>{icone} {titre}{_badge_html}</div>
<div style='font-size:12px;color:{C['text']};line-height:1.7'>{contenu}</div>
</div>""", unsafe_allow_html=True)

    # ── Chantiers terminés (expanders fermés) ──
    st.markdown(f"<div style='font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin:8px 0 10px 2px'>✅ Terminés</div>", unsafe_allow_html=True)

    with st.expander("✅ 1 — Export / Backup JSON", expanded=False):
        _chantier_card("Export / Backup JSON", "💾",
            """Bouton "💾 Backup" en haut à droite — génère <code>saminvest_backup_YYYYMMDD.json</code>
(capital_reel, watchlist, ibkr_kpis, années IBKR). Bouton "Restaurer" absent volontairement :
GitHub persiste déjà tout automatiquement. Sera ajouté en <b>chantier 7e</b> quand il aura une
vraie valeur (plus de fallback Sheet).""", "#6EE7B7")

    with st.expander("✅ 2 — Chantier Visuel — Vue d'ensemble", expanded=False):
        _chantier_card("Chantier Visuel — Vue d'ensemble", "🎨",
            """Bandeau indices journaliers (SP500/CAC40/STOXX600/BTC) avec sparklines + sélecteur timeframe
supprimé (variation journalière uniquement, via fast_info.previous_close aligné Yahoo Finance).<br>
Expander "Objectifs & progression de l'année" : 4 cards (Objectif PF, DCA mensuel mois en cours
Bourse+Crypto+Options, Année écoulée, Reste à atteindre) + popovers ✏️ persistés GitHub.<br>
Expander "Évolution mensuelle & Répartition". Objectifs persistés sur GitHub (objectifs.json).""",
            "#6EE7B7")

    with st.expander("✅ Persistance GitHub (hors séquence numérotée)", expanded=False):
        _chantier_card("Persistance GitHub — HTML IBKR + capital_reel + watchlist + objectifs", "💾",
            """Infrastructure GitHub API en place : gh_read / gh_write / gh_list.<br>
Persisté automatiquement : <code>ibkr_data/*.htm</code> (restauré au démarrage),
<code>capital_reel.json</code>, <code>watchlist.json</code>, <code>objectifs.json</code>.<br>
Token : <code>saminvest-persistence</code> (no expiry). Secrets Streamlit Cloud : GITHUB_TOKEN,
GITHUB_REPO, GITHUB_BRANCH.""", "#6EE7B7")

    # ── Séquence en cours / à venir ──
    st.markdown(f"<div style='font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin:18px 0 10px 2px'>📋 Séquence validée — à venir</div>", unsafe_allow_html=True)

    with st.expander("🔄 3 — Contexte Marché (en cours)", expanded=True):
        _chantier_card("Onglet Contexte Marché", "🌍",
            """Nouvel onglet dédié créé entre Watchlist et Chantier.<br>
<b>✅ Fait</b> : Indices journaliers (SP500/CAC40/STOXX600/BTC) avec sparklines SVG inline,
courbes normalisées par rapport à la clôture J-1, ligne de référence à 0, cards hauteur fixe.<br>
<b>✅ Fait</b> : VIX avec sparkline intégrée + badge de niveau (Calme/Normal/Prudence/Stress).<br>
<b>✅ Fait</b> : Fear &amp; Greed Index CNN avec gauge SVG demi-cercle + 5 zones colorées. Fix viewBox (tick "100" ne dépasse plus).<br>
<b>✅ Fait</b> : Calendrier Earnings — vrai calendrier visuel 5 colonnes Lun→Ven par semaine. Fond teinté par source, bordure d'urgence, compteur "dans X jours". Sources : options IBKR ouvertes + watchlist uniquement.<br>
<b>✅ Fait</b> : Consensus Analystes (yf recommendationMean) — badge coloré Strong Buy/Buy/Hold/Underperform/Sell + prix cible + nb analystes. Ajouté sur les cards du Calendrier Earnings et colonne dédiée dans la Watchlist (3 listes). Cache 1h.<br>
<b>✅ Fait</b> : Dividendes — ligne ex-dividende + rendement %/an sous le badge Analystes dans la Watchlist. Calendrier Dividendes visuel (même grille 5 colonnes que Earnings) dans Contexte Marché, alimenté par la watchlist. Cache 1h.<br>
<b>🔄 Reste</b> : Robustesse source données yfinance (fallback si calendar vide).""",
            "#EAB308")

    _chantier_card("4 — Alertes visuelles in-app", "🔔",
        """Bandeau/badge si position options proche ITM, DCA mensuel manqué, etc. Pas d'email
(cron externe hors scope). À faire après stabilisation visuelle de tous les onglets.""",
        C['cyan'])

    _chantier_card("6 — News sur positions détenues", "📰",
        """yf.Ticker.news (gratuit, pas de clé API). Section repliable par ticker dans l'onglet
Bourse <b>ou dans l'onglet Contexte Marché</b>. Qualité variable selon les tickers
(parfois vide pour petites caps type MARA/NIO).""",
        C['blue'])

    _chantier_card("7 — 🗺️ GRAND CHANTIER — Autonomie totale vs Google Sheet", "🗺️",
        """À démarrer après stabilisation des points 1-6.<br>
<b>7a</b> — Snapshot Sheet actuel en JSON "point zéro"<br>
<b>7b</b> — Formulaires de saisie : dividendes, PEE/AV, versements Bourse/Crypto, retraits<br>
<b>7c</b> — Migration KPI Performance/Vue d'ensemble vers JSON (couper sv(df_pf,...))<br>
<b>7d</b> — Suppression totale dépendance gspread/Sheet<br>
<b>7e</b> — Ajouter bouton "📂 Restaurer" + étendre backup JSON aux nouvelles données manuelles
(obligatoire avant coupure définitive du Sheet)<br><br>
Dépendances Sheet restantes : <code>sv(df_pf,6,2/3)</code> Bourse et <code>sv(df_pf,7,2/3)</code>
Crypto. Options déjà 100% IBKR/JSON.""",
        "#A78BFA", "Plusieurs sessions")

    _chantier_card("8 — Onglet Fiscalité dédié", "🧾",
        """Dépend de 7b — tracker ventes Bourse/Crypto (date, qté, prix, PRU, PV/MV).
Options ont déjà leur historique. Calcul PFU/flat tax.""",
        C['purple'], "Après point 7")

    _chantier_card("9 — Retraits dans le TRI", "↩️",
        """Dépend de 7b — saisis via formulaires, XIRR les gère nativement. Aucun retrait
effectué à ce jour → calcul actuel correct.""",
        C['purple'], "Après point 7")

    _chantier_card("10 — Snapshots mensuels (partie 2) — Tous graphiques historiques", "📸",
        """Partie 1 ✅ : bouton Snapshot PV/MV & TRI global opérationnel (persisté GitHub).<br>
<b>Partie 2 (après chantier 7)</b> : étendre la logique snapshot à tous les graphiques
annuels et mensuels alimentés par Google Sheet (Évolution annuelle du patrimoine,
Évolution mensuelle, etc.). Une fois les données en dur dans l'app (7b/7c), ces graphiques
seront reconstruits depuis le JSON — le Snapshot figera le point de fin de mois pour chaque courbe.""",
        "#A78BFA", "Après point 7")

    # ── Au fil de l'eau ──
    st.markdown(f"<div style='font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin:18px 0 10px 2px'>🔵 Au fil de l'eau</div>", unsafe_allow_html=True)

    _chantier_card("Mobile / responsive", "📱",
        """Usage mobile fréquent — tester tableaux HTML en conditions réelles, ajuster si besoin.""",
        C['muted'])

    _chantier_card("Rebalancing assistant", "⚖️",
        """À creuser ensemble, pas prioritaire.""", C['muted'])

    _chantier_card("Convertisseur EUR/USD live", "💱",
        """eurusd_live déjà en session_state → widget dans l'onglet Options. Basse priorité.""",
        C['muted'])

    # ── Limites connues ──
    st.markdown(f"<div style='font-size:11px;color:{C['muted']};text-transform:uppercase;letter-spacing:.08em;font-weight:700;margin:18px 0 10px 2px'>⚠️ Limites connues</div>", unsafe_allow_html=True)

    _chantier_card("Retraits non gérés dans le TRI Global", "⚠️",
        """Aucun retrait à ce jour → calcul correct. Si retrait futur : (1) cashflow positif dans
TRI global, (2) vente de parts simulée dans les indices. XIRR gère déjà les flux positifs
intermédiaires — seule la collecte de la donnée "retrait" manque (sera traitée en 7b).""",
        "#F59E0B")
