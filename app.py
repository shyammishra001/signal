import os
import re
import time
from datetime import datetime
from io import StringIO
try:
    # Python 3.9+ standard library
    from zoneinfo import ZoneInfo
except ImportError:
    # Python 3.8 compatibility package
    from backports.zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st
from streamlit_autorefresh import st_autorefresh

BASE = "https://api.indstocks.com"
IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="SHYAM AI | F&O Explosion Scanner V2.5", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")
st.markdown("""
<style>
.block-container{padding-top:1rem;padding-bottom:2rem;max-width:1600px}
[data-testid="stMetric"]{background:rgba(120,120,140,.10);padding:12px;border-radius:10px}
.small-note{font-size:.86rem;opacity:.82}
section[data-testid="stSidebar"]{min-width:285px}
</style>
""", unsafe_allow_html=True)

# Optional deployment password. Environment variable only: the local Ubuntu
# build must not require a .streamlit/secrets.toml file to start.
def get_app_password():
    return os.getenv("APP_PASSWORD", "").strip()

app_password = get_app_password()
if app_password:
    if not st.session_state.get("app_authenticated"):
        st.title("🔐 SHYAM AI — Secure Access")
        entered = st.text_input("Dashboard password", type="password")
        if st.button("Unlock", type="primary"):
            if entered == app_password:
                st.session_state["app_authenticated"] = True
                st.rerun()
            else:
                st.error("Password गलत है।")
        st.stop()

st.title("🚀 SHYAM AI — F&O EXPLOSION SCANNER V2.5")
st.caption("INDstocks API • NSE F&O universe • Clean professional CE/PE option chain • READ-ONLY / No order placement")
st.info("यह build केवल market data पढ़ता है। कोई order place नहीं करता। API token को किसी screenshot, chat या public repository में साझा न करें।")
show_api_settings = st.toggle("⚙️ API Settings दिखाएँ", value=False, key="show_api_settings")

with st.sidebar:
    st.header("🔐 INDstocks API")
    token = st.text_input("Access Token", type="password", key="api_token", help="INDstocks से मिला current access token. इसे सार्वजनिक रूप से साझा न करें।")
    if st.button("🧹 Clear Token / Lock Dashboard", use_container_width=True):
        st.session_state["api_token"] = ""
        st.session_state.pop("ranked", None)
        st.session_state.pop("last_chain", None)
        st.rerun()
    st.divider()
    auto_refresh = st.toggle("Scanner auto refresh", value=True)
    refresh_seconds = st.selectbox("Refresh interval", [10, 15, 20, 30], index=1)
    universe_mode = st.radio("F&O Universe", ["All NSE stock F&O", "Top 100 by volume"], index=0)
    st.divider()
    st.caption("पहली बार 1m/3m/5m history collect होगी। 5 मिनट बाद पूरे momentum windows उपलब्ध होंगे।")

# Token भरने के बाद dashboard को full-width करें; settings toggle से sidebar वापस दिखेगा।
if token.strip() and not show_api_settings:
    st.markdown("<style>section[data-testid='stSidebar']{display:none!important;}div[data-testid='stSidebarNav']{display:none!important;}section.main>div{max-width:100%!important;}</style>", unsafe_allow_html=True)
if token.strip() and not show_api_settings:
    st.caption("🔒 API token session में सुरक्षित है। Settings बदलने के लिए ऊपर ‘API Settings दिखाएँ’ चालू करें।")

headers = {"Authorization": token.strip()} if token.strip() else {}


def api_get(path, params=None, timeout=40):
    response = requests.get(BASE + path, headers=headers, params=params, timeout=timeout)
    try:
        payload = response.json()
    except Exception:
        payload = {"raw": response.text[:2000]}
    if not response.ok:
        raise RuntimeError(f"HTTP {response.status_code}: {payload}")
    return payload


@st.cache_data(ttl=1800, show_spinner=False)
def download_master(source, auth_token):
    response = requests.get(
        f"{BASE}/market/instruments",
        headers={"Authorization": auth_token},
        params={"source": source},
        timeout=75,
    )
    response.raise_for_status()
    return pd.read_csv(StringIO(response.text), low_memory=False)


def normalize_cols(frame):
    frame = frame.copy()
    frame.columns = [str(col).strip().upper() for col in frame.columns]
    return frame


def clean_symbol(value):
    if value is None:
        return ""
    symbol = str(value).strip().upper()
    if symbol in {"", "NAN", "NONE", "NULL", "<NA>"}:
        return ""
    symbol = re.sub(r"\s+", "", symbol)
    return symbol.replace("_", "-")


def safe_float(value):
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").replace("%", "").strip()
            if value.lower() in {"", "none", "nan", "null", "-"}:
                return None
        result = float(value)
        return result if pd.notna(result) else None
    except Exception:
        return None


def make_universe(equity_master, fno_master):
    equity = normalize_cols(equity_master)
    fno = normalize_cols(fno_master)
    required = {"EXCH", "SECURITY_ID", "INSTRUMENT_NAME", "TRADING_SYMBOL"}
    missing_eq = required - set(equity.columns)
    missing_fno = required - set(fno.columns)
    if missing_eq or missing_fno:
        raise ValueError(f"Master columns missing. Equity={sorted(missing_eq)}; F&O={sorted(missing_fno)}")

    eq_mask = equity["EXCH"].astype(str).str.upper().str.strip().eq("NSE")
    eq_mask &= equity["INSTRUMENT_NAME"].astype(str).str.upper().str.strip().eq("EQUITY")
    if "SEGMENT" in equity.columns:
        seg = equity["SEGMENT"].astype(str).str.upper().str.strip()
        eq_mask &= seg.isin(["E", "EQUITY", "CASH"])
    eq = equity.loc[eq_mask].copy()
    eq["SECURITY_ID"] = eq["SECURITY_ID"].astype(str).str.replace(r"\.0$", "", regex=True)
    # The exchange trading symbol is the canonical NSE ticker for API underlying lookups.
    eq["SYMBOL_KEY"] = eq["TRADING_SYMBOL"].map(clean_symbol)
    missing = eq["SYMBOL_KEY"].eq("")
    if "SYMBOL_NAME" in eq.columns:
        eq.loc[missing, "SYMBOL_KEY"] = eq.loc[missing, "SYMBOL_NAME"].map(clean_symbol)

    der_mask = fno["EXCH"].astype(str).str.upper().str.strip().eq("NSE")
    der_mask &= fno["INSTRUMENT_NAME"].astype(str).str.upper().str.strip().isin(["OPTSTK", "FUTSTK"])
    der = fno.loc[der_mask].copy()
    # INDstocks master: SYMBOL_NAME is the canonical base ticker (e.g. HDFCBANK).
    # UNDERLYING_SCRIP_NAME is often the long company name, not the NSE ticker.
    der["SYMBOL_KEY"] = der.get("SYMBOL_NAME", pd.Series("", index=der.index)).map(clean_symbol)
    missing = der["SYMBOL_KEY"].eq("")
    if "TRADING_SYMBOL" in der.columns:
        derived = der["TRADING_SYMBOL"].map(lambda x: clean_symbol(re.split(r"[-_]", str(x), maxsplit=1)[0]))
        der.loc[missing, "SYMBOL_KEY"] = derived.loc[missing]
    # Last-resort field only; full company names will not match cash tickers and are discarded.
    missing = der["SYMBOL_KEY"].eq("")
    if "UNDERLYING_SCRIP_NAME" in der.columns:
        fallback = der["UNDERLYING_SCRIP_NAME"].map(clean_symbol)
        der.loc[missing, "SYMBOL_KEY"] = fallback.loc[missing]

    # Only use real ticker-to-ticker matching. Descriptive company-name fields are excluded.
    cash_keys = set(eq["SYMBOL_KEY"]) - {""}
    fno_keys = set(der["SYMBOL_KEY"]) - {""}
    matched = cash_keys & fno_keys
    matched_eq = eq[eq["SYMBOL_KEY"].isin(matched)].drop_duplicates("SYMBOL_KEY")
    universe = matched_eq[["SYMBOL_KEY", "SECURITY_ID", "TRADING_SYMBOL"]].copy()
    universe.columns = ["SYMBOL", "SECURITY_ID", "CASH_TRADING_SYMBOL"]
    universe["SCRIP_CODE"] = "NSE_" + universe["SECURITY_ID"].astype(str)
    universe = universe.sort_values("SYMBOL").reset_index(drop=True)

    diagnostics = {
        "equity_master_rows": len(equity),
        "NSE_cash_equity_rows": len(eq),
        "F&O_master_rows": len(fno),
        "NSE_stock_F&O_contract_rows": len(der),
        "unique_cash_symbols": len(cash_keys),
        "unique_F&O_symbols": len(fno_keys),
        "matched_F&O_stocks": len(universe),
        "unmatched_F&O_sample": sorted(fno_keys - cash_keys)[:40],
        "unmatched_cash_sample": sorted(cash_keys - fno_keys)[:40],
        "matched_symbols_sample": sorted(matched)[:50],
        "equity_columns": list(equity.columns),
        "fno_columns": list(fno.columns),
    }
    return universe, der, diagnostics


def load_static_fno_symbols(live_universe):
    """Load a committed symbol master for fast autocomplete; live API remains source of truth."""
    static_symbols = []
    path = os.path.join(os.path.dirname(__file__), "nse_fno_stock_master.csv")
    try:
        if os.path.exists(path):
            master = pd.read_csv(path)
            col = next((c for c in ("SYMBOL", "TRADING_SYMBOL", "CASH_TRADING_SYMBOL") if c in master.columns), None)
            if col:
                static_symbols = [clean_symbol(x) for x in master[col].dropna().tolist()]
    except Exception:
        static_symbols = []
    live_symbols = live_universe["SYMBOL"].dropna().astype(str).map(clean_symbol).tolist()
    return sorted(set(x for x in static_symbols + live_symbols if x)), bool(static_symbols)


def _first_value(obj, *keys):
    for key in keys:
        if isinstance(obj, dict) and key in obj and obj.get(key) is not None:
            return obj.get(key)
    return None


def fetch_quotes(universe):
    codes = universe["SCRIP_CODE"].astype(str).tolist()
    if not codes:
        raise ValueError("NSE F&O stock universe खाली है।")
    all_rows = []
    for start in range(0, len(codes), 200):
        batch = codes[start:start + 200]
        payload = api_get("/market/quotes/full", {"scrip-codes": ",".join(batch)})
        if not isinstance(payload, dict) or payload.get("status") != "success":
            raise RuntimeError(f"Quote API success नहीं लौटा: {str(payload)[:1200]}")
        data = payload.get("data", {}) or {}
        for code in batch:
            quote = data.get(code) if isinstance(data, dict) else None
            if not isinstance(quote, dict):
                continue
            security_id = code.replace("NSE_", "", 1)
            match = universe[universe["SECURITY_ID"].astype(str).eq(security_id)]
            if match.empty:
                continue
            item = match.iloc[0]
            depth = quote.get("market_depth") or {}
            aggregate = depth.get("aggregate") or {}
            ltp = safe_float(_first_value(quote, "live_price", "ltp", "last_price"))
            prev_close = safe_float(_first_value(quote, "prev_close", "previous_close", "previous_close_price"))
            day_change = safe_float(_first_value(quote, "day_change", "change"))
            day_pct = safe_float(_first_value(quote, "day_change_percentage", "change_percentage", "day_change_percent"))
            # INDstocks documented field is day_change_percentage; calculate only if omitted.
            if day_pct is None and day_change is not None and prev_close not in (None, 0):
                day_pct = day_change / prev_close * 100
            all_rows.append({
                "SYMBOL": item["SYMBOL"], "SECURITY_ID": security_id, "SCRIP_CODE": code,
                "LTP": ltp, "DAY_%": day_pct, "DAY_CHANGE": day_change,
                "VOLUME": safe_float(_first_value(quote, "volume", "traded_volume")),
                "OPEN": safe_float(_first_value(quote, "day_open", "open")),
                "HIGH": safe_float(_first_value(quote, "day_high", "high")),
                "LOW": safe_float(_first_value(quote, "day_low", "low")),
                "PREV_CLOSE": prev_close,
                "BUY_QTY": safe_float(aggregate.get("total_buy")),
                "SELL_QTY": safe_float(aggregate.get("total_sell")),
            })
    frame = pd.DataFrame(all_rows)
    if not frame.empty:
        frame = frame.drop_duplicates("SYMBOL", keep="last")
        # A 200 response with blank values is not counted as a usable quote.
        frame = frame[frame["LTP"].notna()].copy()
    return frame.reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def fetch_daily_history(scrip_code, auth_token):
    """Fetch up to ~45 calendar days of daily OHLCV for one NSE cash scrip."""
    end_ms = int(time.time() * 1000)
    start_ms = end_ms - 45 * 24 * 60 * 60 * 1000
    response = requests.get(
        f"{BASE}/market/historical/1day",
        headers={"Authorization": auth_token},
        params={"scrip-codes": str(scrip_code), "start_time": start_ms, "end_time": end_ms},
        timeout=35,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise RuntimeError(f"Historical API success नहीं लौटा: {str(payload)[:500]}")
    item = (payload.get("data") or {}).get(str(scrip_code), {}) or {}
    candles = item.get("candles") or []
    rows = []
    for candle in candles:
        if not isinstance(candle, dict):
            continue
        rows.append({
            "TS": safe_float(candle.get("ts")), "OPEN": safe_float(candle.get("o")),
            "HIGH": safe_float(candle.get("h")), "LOW": safe_float(candle.get("l")),
            "CLOSE": safe_float(candle.get("c")), "VOLUME": safe_float(candle.get("v")),
        })
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.dropna(subset=["TS", "CLOSE"]).sort_values("TS").drop_duplicates("TS")
    frame["DATE"] = pd.to_datetime(frame["TS"], unit="s", utc=True).dt.tz_convert(IST)
    frame["RETURN_%"] = pd.to_numeric(frame["CLOSE"], errors="coerce").pct_change() * 100
    return frame.reset_index(drop=True)


def historical_risk_context(row):
    """Summarise recent daily behaviour; never infer the cause of a price shock."""
    code = str(row.get("SCRIP_CODE", "")).strip()
    if not code:
        return {"available": False, "note": "Historical candles के लिए NSE scrip code उपलब्ध नहीं।"}
    hist = fetch_daily_history(code, token.strip())
    if hist is None or hist.empty or len(hist) < 8:
        return {"available": False, "note": "पर्याप्त daily history नहीं मिली; historical risk score लागू नहीं हुआ।"}
    recent = hist.tail(20).copy()
    returns = pd.to_numeric(recent["RETURN_%"], errors="coerce").dropna()
    median_abs = float(returns.abs().median()) if not returns.empty else 0.0
    volatility = float(returns.std()) if len(returns) > 1 else 0.0
    worst_day = float(returns.min()) if not returns.empty else 0.0
    close = pd.to_numeric(recent["CLOSE"], errors="coerce").dropna()
    peak_drawdown = float(((close / close.cummax()) - 1).min() * 100) if not close.empty else 0.0
    day_move = safe_float(row.get("DAY_%")) or 0.0
    typical = max(median_abs, 0.25)
    shock_multiple = abs(day_move) / typical
    breadth_down = float((pd.to_numeric(ranked.get("DAY_%"), errors="coerce") < 0).mean() * 100) if "DAY_%" in ranked.columns and len(ranked) else None
    if shock_multiple >= 4 or abs(day_move) >= 10:
        severity = "EXTREME"
    elif shock_multiple >= 2.5 or abs(day_move) >= 6:
        severity = "HIGH"
    elif shock_multiple >= 1.5:
        severity = "ELEVATED"
    else:
        severity = "NORMAL"
    if breadth_down is not None and breadth_down >= 70:
        breadth_note = f"F&O universe का लगभग {breadth_down:.0f}% हिस्सा गिरावट में: broad-market pressure संभव।"
    elif breadth_down is not None and breadth_down <= 35:
        breadth_note = f"सिर्फ लगभग {breadth_down:.0f}% F&O universe गिरा: यह move stock-specific हो सकता है।"
    else:
        breadth_note = f"F&O universe में गिरावट वाले stocks लगभग {breadth_down:.0f}% हैं।" if breadth_down is not None else "Market breadth उपलब्ध नहीं।"
    return {
        "available": True, "days": int(len(hist)), "median_abs_day": median_abs,
        "volatility": volatility, "worst_day": worst_day, "peak_drawdown": peak_drawdown,
        "shock_multiple": shock_multiple, "severity": severity, "breadth_down": breadth_down,
        "breadth_note": breadth_note,
        "note": f"आज का {day_move:+.2f}% move हाल के सामान्य दैनिक move ({median_abs:.2f}% median) का लगभग {shock_multiple:.1f}x है। हाल के 20 sessions का सबसे खराब daily return {worst_day:.2f}% और peak-to-trough drawdown {peak_drawdown:.2f}% रहा। {breadth_note}",
    }


def collect_momentum(quotes):
    now = time.time()
    snapshots = st.session_state.setdefault("snapshots", [])
    usable = quotes[["SYMBOL", "LTP", "VOLUME"]].copy()
    usable = usable[usable["LTP"].notna()]
    snapshots.append({"t": now, "data": usable})
    snapshots = [snap for snap in snapshots if now - snap["t"] <= 900]
    st.session_state["snapshots"] = snapshots
    out = quotes.copy()
    for minutes in (1, 3, 5):
        target = now - minutes * 60
        candidates = [snap for snap in snapshots[:-1] if snap["t"] <= target]
        if candidates:
            old = candidates[-1]["data"].drop_duplicates("SYMBOL").set_index("SYMBOL")
            old_ltp = out["SYMBOL"].map(old["LTP"])
            out[f"MOM_{minutes}M_%"] = (out["LTP"] / old_ltp.replace(0, pd.NA) - 1) * 100
        else:
            out[f"MOM_{minutes}M_%"] = pd.NA
    if len(snapshots) >= 2:
        previous = snapshots[-2]["data"].drop_duplicates("SYMBOL").set_index("SYMBOL")
        old_volume = out["SYMBOL"].map(previous["VOLUME"])
        out["VOL_DELTA"] = (out["VOLUME"] - old_volume).clip(lower=0)
    else:
        out["VOL_DELTA"] = 0

    def pos(x):
        return x.fillna(0).clip(lower=0)
    def neg(x):
        return (-x.fillna(0)).clip(lower=0)

    # Direction must not be overwritten by a flat 1m snapshot: otherwise, after
    # the market pauses/closes, both tables incorrectly become empty.
    out["DIRECTION"] = "SIDEWAYS"
    day_direction = out["DAY_%"].fillna(0)
    out.loc[day_direction > 0.001, "DIRECTION"] = "UP"
    out.loc[day_direction < -0.001, "DIRECTION"] = "DOWN"
    valid_m1 = out["MOM_1M_%"].notna()
    out.loc[valid_m1 & (out["MOM_1M_%"] > 0.01), "DIRECTION"] = "UP"
    out.loc[valid_m1 & (out["MOM_1M_%"] < -0.01), "DIRECTION"] = "DOWN"

    vol_rank = out["VOL_DELTA"].rank(pct=True).fillna(0)
    day_up, day_down = pos(out["DAY_%"]), neg(out["DAY_%"])
    m1_up, m1_dn = pos(out["MOM_1M_%"]), neg(out["MOM_1M_%"])
    m3_up, m3_dn = pos(out["MOM_3M_%"]), neg(out["MOM_3M_%"])
    m5_up, m5_dn = pos(out["MOM_5M_%"]), neg(out["MOM_5M_%"])
    up_consistent = ((out["DAY_%"].fillna(0) > 0) & (out["MOM_1M_%"].fillna(0) >= 0) &
                     (out["MOM_3M_%"].fillna(0) >= 0)).astype(float)
    dn_consistent = ((out["DAY_%"].fillna(0) < 0) & (out["MOM_1M_%"].fillna(0) <= 0) &
                     (out["MOM_3M_%"].fillna(0) <= 0)).astype(float)
    out["UP_SCORE"] = ((day_up.clip(0, 5) / 5 * 30) + (m1_up.clip(0, .5) / .5 * 25) +
                       (m3_up.clip(0, 1) / 1 * 15) + (m5_up.clip(0, 1.5) / 1.5 * 10) +
                       vol_rank * 10 + up_consistent * 10).clip(0, 100).round(1)
    out["DOWN_SCORE"] = ((day_down.clip(0, 5) / 5 * 30) + (m1_dn.clip(0, .5) / .5 * 25) +
                         (m3_dn.clip(0, 1) / 1 * 15) + (m5_dn.clip(0, 1.5) / 1.5 * 10) +
                         vol_rank * 10 + dn_consistent * 10).clip(0, 100).round(1)
    out["SIGNAL"] = "WAIT / COLLECTING DATA"
    enough = out["MOM_1M_%"].notna() & out["MOM_3M_%"].notna()
    out.loc[enough & (out["MOM_1M_%"] > .15) & (out["MOM_3M_%"] > .25), "SIGNAL"] = "UP MOMENTUM WATCH"
    out.loc[enough & (out["MOM_1M_%"] < -.15) & (out["MOM_3M_%"] < -.25), "SIGNAL"] = "DOWN MOMENTUM WATCH"
    flat_now = enough & (out["MOM_1M_%"].abs() < .01) & (out["MOM_3M_%"].abs() < .02)
    out.loc[flat_now, "SIGNAL"] = "SIDEWAYS / NO FRESH MOMENTUM"
    return out


def fetch_futures_oi(fno_master, universe):
    """Fetch nearest-month NSE stock-futures quotes and classify price/OI combinations."""
    master = normalize_cols(fno_master)
    required = {"EXCH", "INSTRUMENT_NAME", "SECURITY_ID"}
    if not required.issubset(master.columns):
        raise RuntimeError(f"F&O master में FUTSTK columns नहीं मिले: {sorted(required - set(master.columns))}")
    if "SYMBOL_NAME" not in master.columns:
        raise RuntimeError("F&O master में SYMBOL_NAME नहीं है; futures को cash ticker से match नहीं कर सकते।")
    fut = master[
        master["EXCH"].astype(str).str.upper().eq("NSE") &
        master["INSTRUMENT_NAME"].astype(str).str.upper().eq("FUTSTK")
    ].copy()
    fut["SYMBOL"] = fut["SYMBOL_NAME"].map(clean_symbol)
    fut["SECURITY_ID"] = fut["SECURITY_ID"].astype(str).str.replace(r"\.0$", "", regex=True)
    if "EXPIRY_DATE" in fut.columns:
        fut["_EXPIRY"] = pd.to_datetime(fut["EXPIRY_DATE"], errors="coerce", format="mixed", dayfirst=True)
        today = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()
        fut = fut[fut["_EXPIRY"].notna() & (fut["_EXPIRY"] >= today)]
        fut = fut.sort_values("_EXPIRY").drop_duplicates("SYMBOL", keep="first")
    else:
        fut = fut.drop_duplicates("SYMBOL")
    allowed = set(universe["SYMBOL"].map(clean_symbol))
    fut = fut[fut["SYMBOL"].isin(allowed)].copy()
    if fut.empty:
        return pd.DataFrame(), "F&O master में matching FUTSTK contracts नहीं मिले।"
    codes = ["NFO_" + sid for sid in fut["SECURITY_ID"].tolist()]
    quote_map = {}
    for start in range(0, len(codes), 200):
        batch = codes[start:start + 200]
        payload = api_get("/market/quotes/full", {"scrip-codes": ",".join(batch)})
        if payload.get("status") != "success":
            raise RuntimeError(f"Futures quote API response: {str(payload)[:1000]}")
        quote_map.update(payload.get("data", {}) or {})
    rows = []
    for _, contract in fut.iterrows():
        code = "NFO_" + str(contract["SECURITY_ID"])
        q = quote_map.get(code, {})
        if not isinstance(q, dict) or not q:
            continue
        ltp = safe_float(q.get("live_price"))
        day_pct = safe_float(q.get("day_change_percentage"))
        oi = safe_float(q.get("open_interest", q.get("oi")))
        oi_change = safe_float(q.get("open_interest_change", q.get("oi_change")))
        previous_oi = safe_float(q.get("previous_oi"))
        if oi_change is None and oi is not None and previous_oi is not None:
            oi_change = oi - previous_oi
        oi_change_pct = (oi_change / (oi - oi_change) * 100) if oi_change is not None and oi is not None and (oi - oi_change) > 0 else None
        rows.append({"Stock": contract["SYMBOL"], "Futures LTP": ltp, "Price Change %": day_pct,
                     "Current OI": oi, "OI Change": oi_change, "OI Change %": oi_change_pct,
                     "Expiry": str(contract.get("EXPIRY_DATE", "")), "Quote Code": code})
    result = pd.DataFrame(rows)
    if result.empty:
        return result, "Futures quote response खाली है।"
    if result["Current OI"].notna().sum() == 0 or result["OI Change"].notna().sum() == 0:
        return result, "API ने FUTSTK quotes दिए, लेकिन OI / OI change fields नहीं लौटाए। नीचे की OI lists को खाली रखना सही है; अनुमानित OI नहीं दिखाया जाएगा।"
    result["OI Setup"] = "UNCLASSIFIED"
    price_up = result["Price Change %"].fillna(0) > 0
    price_down = result["Price Change %"].fillna(0) < 0
    oi_up = result["OI Change"].fillna(0) > 0
    oi_down = result["OI Change"].fillna(0) < 0
    result.loc[price_up & oi_up, "OI Setup"] = "LONG BUILDUP"
    result.loc[price_down & oi_up, "OI Setup"] = "SHORT BUILDUP"
    result.loc[price_up & oi_down, "OI Setup"] = "SHORT COVERING"
    result.loc[price_down & oi_down, "OI Setup"] = "LONG UNWINDING"
    result["OI Activity Score"] = (result["OI Change %"].abs().fillna(0).rank(pct=True) * 100).round(1)
    return result, None


def expiry_dates(symbol, fno_rows):
    """Resolve upcoming OPTSTK expiries; return actionable diagnostics if unavailable."""
    errors = []
    symbol = clean_symbol(symbol)
    today = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()
    try:
        payload = api_get("/market/instruments/expiries", {"underlying": symbol, "segment": "DERIVATIVE"})
        values = payload.get("data", []) if isinstance(payload, dict) else []
        if isinstance(values, dict):
            values = values.get("expiries", values.get("data", []))
        dates = []
        if isinstance(values, list):
            for value in values:
                raw = (value.get("expiry") or value.get("expiry_date")) if isinstance(value, dict) else value
                parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
                if pd.notna(parsed) and parsed.normalize() >= today:
                    dates.append(parsed.strftime("%Y-%m-%d"))
        dates = sorted(set(dates))
        if dates:
            # Confirm at least one actual stock-option contract exists for this underlying.
            return dates, "INDstocks upcoming expiries API (OPTSTK availability confirmed by contract search on fetch)", None
        errors.append(f"Expiry API returned no future dates: {str(payload)[:500]}")
    except Exception as exc:
        errors.append(f"Expiry API: {exc}")

    try:
        page = 1
        dates = set()
        while page <= 10:
            payload = api_get("/market/instruments/search", {
                "underlying": symbol, "segment": "DERIVATIVE", "instrument_type": "OPTSTK",
                "page": str(page), "page_size": "100"
            })
            data = payload.get("data", {}) if isinstance(payload, dict) else {}
            instruments = data.get("instruments", []) if isinstance(data, dict) else []
            if not instruments:
                break
            for item in instruments:
                raw = item.get("expiry") if isinstance(item, dict) else None
                parsed = pd.to_datetime(raw, errors="coerce", format="mixed")
                if pd.notna(parsed) and parsed.normalize() >= today:
                    dates.add(parsed.strftime("%Y-%m-%d"))
            count = safe_float(data.get("count")) if isinstance(data, dict) else None
            if count is None or page * 100 >= count or len(instruments) < 100:
                break
            page += 1
        if dates:
            return sorted(dates), "INDstocks OPTSTK contract search", " | ".join(errors) or None
        errors.append(f"OPTSTK contract search returned no upcoming contracts: {str(payload)[:500]}")
    except Exception as exc:
        errors.append(f"OPTSTK contract search: {exc}")

    # Master fallback: SYMBOL_NAME is the documented base ticker. Also inspect
    # UNDERLYING_SCRIP_NAME only as a normalized exact/partial fallback, never as preferred.
    data = normalize_cols(fno_rows)
    if "EXPIRY_DATE" in data.columns and "INSTRUMENT_NAME" in data.columns:
        data = data[data["INSTRUMENT_NAME"].astype(str).str.upper().eq("OPTSTK")].copy()
        masks = []
        for col in ("SYMBOL_NAME", "UNDERLYING_SYMBOL", "UNDERLYING"):
            if col in data.columns:
                masks.append(data[col].map(clean_symbol).eq(symbol))
        if masks:
            mask = masks[0]
            for extra in masks[1:]:
                mask = mask | extra
            data = data[mask].copy()
        parsed = pd.to_datetime(data["EXPIRY_DATE"], errors="coerce", format="mixed", dayfirst=True)
        dates = sorted({x.strftime("%Y-%m-%d") for x in parsed.dropna() if x.normalize() >= today})
        if dates:
            return dates, "F&O master OPTSTK fallback", " | ".join(errors) or None
    return [], "No valid OPTSTK expiry source", " | ".join(errors + [f"{symbol}: live OPTSTK contracts/expiry not found. Check exact NSE ticker and API entitlement."])


def search_option_contracts(symbol, expiry):
    """Confirm that selected underlying+expiry actually has live OPTSTK contracts."""
    payload = api_get("/market/instruments/search", {
        "underlying": clean_symbol(symbol), "segment": "DERIVATIVE", "instrument_type": "OPTSTK",
        "expiry": expiry, "page": "1", "page_size": "100"
    })
    data = payload.get("data", {}) if isinstance(payload, dict) else {}
    instruments = data.get("instruments", []) if isinstance(data, dict) else []
    if not instruments:
        raise RuntimeError(f"{symbol} {expiry}: API contract search में OPTSTK contracts नहीं मिले। Response: {str(payload)[:1000]}")
    return instruments


def get_option_chain(underlying_id, expiry, strike_count):
    parsed = pd.to_datetime(expiry, errors="coerce", format="mixed")
    if pd.isna(parsed):
        raise ValueError(f"Expiry YYYY-MM-DD में नहीं है: {expiry}")
    params = {
        "exchange": "NSE", "segment": "EQUITY",
        "underlying-scrip": str(underlying_id).replace(".0", ""),
        "expiry": parsed.strftime("%Y-%m-%d"),
        "strike_count": str(int(strike_count)),
    }
    return api_get("/market/option-chain", params)


def option_leg_value(leg, key, greek=None):
    value = leg.get(key)
    if value is None and greek:
        value = (leg.get("greeks") or {}).get(greek)
    return safe_float(value)


def build_chain_frame(chain):
    data = chain.get("data", {}) if isinstance(chain, dict) else {}
    if not isinstance(data, dict):
        raise RuntimeError(f"Option-chain response format समझ नहीं आया: {str(chain)[:1200]}")
    strikes = data.get("strikes") or {}
    if not strikes:
        raise RuntimeError("API ने success दिया, लेकिन strikes खाली हैं। Expiry, underlying SECURITY_ID और API response जाँचना होगा।")
    rows = []
    for strike, pair in strikes.items():
        pair = pair if isinstance(pair, dict) else {}
        row = {}
        for side in ("ce", "pe"):
            leg = pair.get(side)
            leg = leg if isinstance(leg, dict) else {}
            prefix = side.upper()
            oi = option_leg_value(leg, "oi")
            previous_oi = option_leg_value(leg, "previous_oi")
            oi_change = option_leg_value(leg, "change_in_oi")
            if oi_change is None and oi is not None and previous_oi is not None:
                oi_change = oi - previous_oi
            row[f"{prefix} OI"] = oi
            row[f"{prefix} OI Change"] = oi_change
            row[f"{prefix} Volume"] = option_leg_value(leg, "volume")
            row[f"{prefix} LTP"] = option_leg_value(leg, "last_price")
            row[f"{prefix} IV"] = option_leg_value(leg, "iv")
            for greek in ("delta", "theta", "vega", "gamma"):
                row[f"{prefix} {greek.title()}"] = option_leg_value(leg, greek, greek)
            bid = option_leg_value(leg, "top_bid_price")
            ask = option_leg_value(leg, "top_ask_price")
            row[f"{prefix} Bid"] = bid
            row[f"{prefix} Ask"] = ask
            row[f"{prefix} Spread %"] = ((ask - bid) / ((ask + bid) / 2) * 100) if bid is not None and ask is not None and (ask + bid) > 0 else None
            row[f"{prefix} Trading Symbol"] = leg.get("trading_symbol")
        row["STRIKE"] = safe_float(strike) if safe_float(strike) is not None else strike
        rows.append(row)
    frame = pd.DataFrame(rows)
    if frame.empty:
        raise RuntimeError("Option chain में कोई strike row नहीं मिला।")
    frame = frame.sort_values("STRIKE").reset_index(drop=True)
    return frame, safe_float(data.get("underlying_ltp")), data.get("expiry")


def recommend_option_contract(chain, symbol, expiry, direction, fno_rows, contracts, budget=10000.0):
    """Return one liquid, one-lot option candidate that fits the user's premium budget."""
    frame, spot, _ = build_chain_frame(chain)
    if spot is None or frame.empty:
        return None, "Underlying LTP/strike data unavailable."
    master = normalize_cols(fno_rows) if fno_rows is not None else pd.DataFrame()
    lot_col = next((c for c in ("LOT_UNITS", "LOT_SIZE", "LOT_QTY", "LOT") if c in master.columns), None)
    ts_col = "TRADING_SYMBOL" if "TRADING_SYMBOL" in master.columns else None
    lot_map = {}
    if lot_col and ts_col:
        valid = master.dropna(subset=[ts_col]).copy()
        lot_map.update({str(r[ts_col]).strip().upper(): safe_float(r[lot_col]) for _, r in valid.iterrows()})
    # Contract-search response can carry lot size even if master naming differs.
    for item in contracts or []:
        if not isinstance(item, dict):
            continue
        ts = _first_value(item, "trading_symbol", "TRADING_SYMBOL", "symbol", "tradingsymbol")
        lot = _first_value(item, "lot_units", "LOT_UNITS", "lot_size", "LOT_SIZE", "lot_qty", "LOT_QTY")
        if ts and safe_float(lot):
            lot_map[str(ts).strip().upper()] = safe_float(lot)

    side = "CE" if str(direction).upper() == "UP" else "PE"
    delta_target = 0.52 if side == "CE" else -0.52
    choices = []
    for _, row in frame.iterrows():
        strike = safe_float(row.get("STRIKE"))
        ltp = safe_float(row.get(f"{side} LTP"))
        trading_symbol = str(row.get(f"{side} Trading Symbol") or "").strip().upper()
        lot = safe_float(lot_map.get(trading_symbol))
        if not trading_symbol or not ltp or ltp <= 0 or not lot or lot <= 0:
            continue
        premium = ltp * lot
        # Keep a 10% reserve for brokerage, taxes, spread and slippage.
        if premium > budget * 0.90:
            continue
        bid, ask = safe_float(row.get(f"{side} Bid")), safe_float(row.get(f"{side} Ask"))
        spread = safe_float(row.get(f"{side} Spread %"))
        volume = safe_float(row.get(f"{side} Volume")) or 0
        oi = safe_float(row.get(f"{side} OI")) or 0
        delta = safe_float(row.get(f"{side} Delta"))
        theta = safe_float(row.get(f"{side} Theta"))
        if bid is not None and ask is not None and (bid <= 0 or ask < bid):
            continue
        if spread is not None and spread > 10:
            continue
        if volume <= 0 and oi <= 0:
            continue
        # Score rewards a useful delta, liquidity and tight spread; penalizes theta burden.
        if delta is None:
            delta_score = 10.0
        else:
            delta_score = max(0.0, 30.0 - abs(abs(delta) - 0.52) * 75.0)
        liquidity_score = min(25.0, (volume / 1000.0) ** 0.5 * 5.0 + (oi / 10000.0) ** 0.5 * 5.0)
        spread_score = 20.0 if spread is None else max(0.0, 25.0 - spread * 2.5)
        theta_pct = abs(theta or 0) / ltp * 100
        theta_score = max(0.0, 20.0 - theta_pct * 2.0)
        score = delta_score + liquidity_score + spread_score + theta_score
        choices.append({
            "Stock": symbol, "Contract": trading_symbol, "Side": side, "Strike": strike,
            "Expiry": expiry, "Option LTP ₹": ltp, "Lot size": int(lot),
            "One-lot premium ₹": premium, "Budget left ₹": budget - premium,
            "Delta": delta, "Theta/day": theta, "Volume": volume, "OI": oi,
            "Spread %": spread, "Contract score /100": round(score, 1),
        })
    if not choices:
        return None, "₹10,000 budget (90% premium cap) में lot-size verified और liquid contract नहीं मिला। Lot size, LTP, bid/ask और volume/OI जाँचें।"
    choices.sort(key=lambda x: (x["Contract score /100"], x["Volume"], x["OI"]), reverse=True)
    return choices[0], None


def render_chain(chain, symbol, expiry, fno_rows=None, contracts=None):
    frame, spot, response_expiry = build_chain_frame(chain)
    # Resolve verified lot sizes from the F&O master and contract-search response.
    master = normalize_cols(fno_rows) if fno_rows is not None else pd.DataFrame()
    lot_col = next((c for c in ("LOT_UNITS", "LOT_SIZE", "LOT_QTY", "LOT") if c in master.columns), None)
    ts_col = "TRADING_SYMBOL" if "TRADING_SYMBOL" in master.columns else None
    lot_map = {}
    if lot_col and ts_col:
        valid_master = master.dropna(subset=[ts_col]).copy()
        for _, item in valid_master.iterrows():
            lot_value = safe_float(item.get(lot_col))
            if lot_value:
                lot_map[str(item.get(ts_col)).strip().upper()] = lot_value
    for item in contracts or []:
        if not isinstance(item, dict):
            continue
        ts = _first_value(item, "trading_symbol", "TRADING_SYMBOL", "symbol", "tradingsymbol")
        lot = _first_value(item, "lot_units", "LOT_UNITS", "lot_size", "LOT_SIZE", "lot_qty", "LOT_QTY")
        if ts and safe_float(lot):
            lot_map[str(ts).strip().upper()] = safe_float(lot)

    for side in ("CE", "PE"):
        symbol_col = f"{side} Trading Symbol"
        if symbol_col not in frame.columns:
            frame[symbol_col] = None
        frame[f"{side} Lot Size"] = frame[symbol_col].map(
            lambda x: safe_float(lot_map.get(str(x).strip().upper())) if x else None
        )
        frame[f"{side} One-Lot Buy ₹"] = frame[f"{side} LTP"] * frame[f"{side} Lot Size"]

    numeric_strikes = pd.to_numeric(frame["STRIKE"], errors="coerce")
    atm_strike = None
    atm_index = None
    if spot is not None and numeric_strikes.notna().any():
        atm_index = (numeric_strikes - spot).abs().idxmin()
        atm_strike = frame.loc[atm_index, "STRIKE"]
    ce_total = frame["CE OI"].fillna(0).sum()
    pe_total = frame["PE OI"].fillna(0).sum()
    pcr = pe_total / ce_total if ce_total else None
    max_ce = frame.loc[frame["CE OI"].fillna(0).idxmax(), "STRIKE"] if frame["CE OI"].notna().any() else None
    max_pe = frame.loc[frame["PE OI"].fillna(0).idxmax(), "STRIKE"] if frame["PE OI"].notna().any() else None

    a, b, c, d, e = st.columns(5)
    a.metric("Underlying LTP", f"₹{spot:,.2f}" if spot is not None else "—")
    b.metric("ATM Strike", str(atm_strike) if atm_strike is not None else "—")
    c.metric("PCR", f"{pcr:.2f}" if pcr is not None else "—")
    d.metric("Max CE OI", str(max_ce) if max_ce is not None else "—")
    e.metric("Max PE OI", str(max_pe) if max_pe is not None else "—")
    st.caption(f"{symbol} • Expiry: {response_expiry or expiry} • CE = GREEN (Call) • PE = RED (Put) • ATM strike highlighted in yellow")

    # Colour only the in-the-money side (plus ATM):
    # CE is ITM when strike < spot; PE is ITM when strike > spot.
    # OTM cells remain transparent/default so the table is not fully painted.
    primary_cols = [
        "CE OI", "CE OI Change", "CE Volume", "CE LTP", "CE Lot Size", "CE One-Lot Buy ₹", "STRIKE",
        "PE One-Lot Buy ₹", "PE Lot Size", "PE LTP", "PE Volume", "PE OI Change", "PE OI",
    ]
    primary_cols = [col for col in primary_cols if col in frame.columns]
    view = frame[primary_cols].copy()
    ce_cols = [c for c in view.columns if str(c).startswith("CE ")]
    pe_cols = [c for c in view.columns if str(c).startswith("PE ")]

    def side_color_style(row):
        styles = [""] * len(row)
        strike = safe_float(row.get("STRIKE"))
        is_atm = (atm_strike is not None and strike is not None
                  and abs(strike - safe_float(atm_strike)) < 1e-9)
        is_ce_itm = (spot is not None and strike is not None and strike < float(spot))
        is_pe_itm = (spot is not None and strike is not None and strike > float(spot))
        for idx, col in enumerate(view.columns):
            if col in ce_cols and (is_ce_itm or is_atm):
                styles[idx] = "background-color:#145c3b;color:#e3ffed;font-weight:600;"
            elif col in pe_cols and (is_pe_itm or is_atm):
                styles[idx] = "background-color:#7a202b;color:#ffe8ea;font-weight:600;"
            elif col == "STRIKE":
                styles[idx] = "background-color:#242424;color:#ffffff;font-weight:800;border-left:2px solid #e0b341;border-right:2px solid #e0b341;"
        if is_atm:
            for idx in range(len(styles)):
                styles[idx] += "border-top:2px solid #f4c542;border-bottom:2px solid #f4c542;"
            if "STRIKE" in view.columns:
                styles[list(view.columns).index("STRIKE")] += "background-color:#f4c542;color:#171717;"
        return styles

    styled = view.style.apply(side_color_style, axis=1).format(precision=2, na_rep="—")
    st.dataframe(styled, use_container_width=True, hide_index=True, height=570)
    st.caption("🟢 केवल ITM CE और ATM CE कॉलम हरे • 🔴 केवल ITM PE और ATM PE कॉलम लाल • OTM कॉलम सामान्य/transparent • Lot Size = एक lot में units • One-Lot Buy ₹ = LTP × Lot Size • पीली लाइन = ATM.")
    with st.expander("⚙️ Advanced Option Greeks, Theta & Bid/Ask (optional)", expanded=False):
        if atm_index is not None:
            atm_row_data = frame.loc[atm_index]
            ce_theta_lot = safe_float(atm_row_data.get("CE Theta / Lot / Day"))
            pe_theta_lot = safe_float(atm_row_data.get("PE Theta / Lot / Day"))
            t1, t2 = st.columns(2)
            t1.metric("ATM CE Theta / lot / day", f"₹{ce_theta_lot:,.2f}" if ce_theta_lot is not None else "Lot size unavailable")
            t2.metric("ATM PE Theta / lot / day", f"₹{pe_theta_lot:,.2f}" if pe_theta_lot is not None else "Lot size unavailable")
        advanced_cols = [c for c in frame.columns if c not in primary_cols and c not in {"STRIKE", "CE Trading Symbol", "PE Trading Symbol"}]
        if advanced_cols:
            advanced_view = frame[["STRIKE"] + advanced_cols].copy()
            st.dataframe(advanced_view.style.format(precision=2, na_rep="—"), use_container_width=True, hide_index=True, height=420)
        st.caption("ATM Theta/Lot/Day = Theta × lot size. Theta अनुमानित समय-मूल्य क्षय है; spot और IV स्थिर मानने पर। Bid/Ask spread execution cost बढ़ा सकता है।")
    st.download_button(
        "⬇️ Download Option Chain CSV",
        data=frame.to_csv(index=False).encode("utf-8"),
        file_name=f"{symbol}_{expiry}_option_chain.csv",
        mime="text/csv",
    )
    st.caption("OI change उपलब्ध API field से लिया जाता है; field न मिलने पर current OI − previous OI से निकाला जाता है। OI walls केवल indicative हैं, guaranteed support/resistance नहीं।")


if not token.strip():
    st.title("🔒 SHYAM AI — Dashboard Locked")
    st.info("बाईं ओर Sidebar में INDstocks Access Token डालें। Token हटाने पर Dashboard साफ़ Lock Screen दिखाएगा।")
    st.caption("यह ऐप केवल READ-ONLY market data पढ़ता है। कोई order place नहीं करता।")
    st.stop()

try:
    profile = api_get("/user/profile")
    if profile.get("status") != "success":
        st.warning(f"Profile response success नहीं है: {str(profile)[:1000]}")
        st.stop()
except Exception as exc:
    st.error(f"INDstocks API connection failed: {exc}")
    st.stop()

st.success("🟢 INDstocks API Connected • Read-only data access • कोई order place नहीं होगा।")

with st.spinner("NSE Equity और F&O Instrument Master पढ़ रहे हैं..."):
    try:
        equity_master = download_master("equity", token.strip())
        fno_master = download_master("fno", token.strip())
        universe, fno_rows, diagnostics = make_universe(equity_master, fno_master)
    except Exception as exc:
        st.error(f"Instrument Master Error: {exc}")
        st.stop()

if universe.empty:
    st.error("Cash और stock-F&O master का ticker match शून्य है। नीचे diagnostics देखें।")
    with st.expander("Instrument Master Diagnostics", expanded=True):
        st.json(diagnostics)
    st.stop()

if universe_mode == "Top 100 by volume" and "ranked" in st.session_state:
    volume_order = st.session_state["ranked"].sort_values("VOLUME", ascending=False)["SYMBOL"].head(100).tolist()
    scan_universe = universe[universe["SYMBOL"].isin(volume_order)].copy()
else:
    scan_universe = universe.copy()

k1, k2, k3, k4 = st.columns(4)
k1.metric("Matched NSE F&O Stocks", f"{len(universe)}")
k2.metric("Quote Universe", f"{len(scan_universe)}")
k3.metric("Refresh", f"{refresh_seconds}s" if auto_refresh else "Manual")
k4.metric("Mode", "READ ONLY")

if auto_refresh:
    st_autorefresh(interval=refresh_seconds * 1000, key="v2_refresh")

scan_col, status_col = st.columns([1, 3])
with scan_col:
    manual_scan = st.button("🔄 Scan Now", type="primary", use_container_width=True)
with status_col:
    st.caption("Top 10 Gainers और Top 10 Losers अलग-अलग rank होंगे। पहली स्कैन में Day % provisional ranking है; 1m/3m/5m windows समय के साथ भरेंगे।")

should_scan = manual_scan or auto_refresh or "ranked" not in st.session_state
if should_scan:
    try:
        with st.spinner(f"{len(scan_universe)} F&O stocks के live quotes ला रहे हैं..."):
            quotes = fetch_quotes(scan_universe)
            if quotes.empty:
                st.warning("API ने response दिया, लेकिन usable LTP quotes नहीं मिले। पिछला valid scanner snapshot सुरक्षित रखा गया है।")
            else:
                ranked_new = collect_momentum(quotes)
                has_directional = ranked_new["DIRECTION"].isin(["UP", "DOWN"]).any()
                if has_directional:
                    st.session_state["ranked"] = ranked_new
                    st.session_state["last_scan"] = datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S")
                    st.session_state["quote_count"] = len(quotes)
                    st.session_state["scan_snapshot_status"] = "LIVE / UPDATED"
                else:
                    # Keep last non-empty direction tables instead of replacing them with empty rows.
                    st.session_state["latest_quote_count"] = len(quotes)
                    st.session_state["scan_snapshot_status"] = "NO DIRECTIONAL CHANGE — LAST VALID SNAPSHOT RETAINED"
                    if "ranked" not in st.session_state:
                        st.session_state["ranked"] = ranked_new
                        st.session_state["last_scan"] = datetime.now(IST).strftime("%d-%b-%Y %H:%M:%S")
                        st.session_state["quote_count"] = len(quotes)
    except Exception as exc:
        st.error(f"Scanner refresh failed; previous valid rows are retained. Details: {exc}")

ranked = st.session_state.get("ranked")
if ranked is None:
    st.info("Scan Now दबाएँ; usable market quote मिलने पर Top 10 तैयार होंगे।")
    st.stop()

up_pool = ranked[ranked["DIRECTION"].eq("UP")].copy()
down_pool = ranked[ranked["DIRECTION"].eq("DOWN")].copy()
up = up_pool.sort_values(["UP_SCORE", "DAY_%"], ascending=False).head(10).copy()
down = down_pool.sort_values(["DOWN_SCORE", "DAY_%"], ascending=[False, True]).head(10).copy()

if up.empty or down.empty:
    st.info("एक या दोनों तरफ अभी directional stocks उपलब्ध नहीं हैं। Market बंद/flat हो, या quote में change न हो, तो खाली सूची को गलत signal से भरने के बजाय last valid snapshot रखा जाएगा।")
status_text = st.session_state.get("scan_snapshot_status", "LIVE / UPDATED")
if status_text != "LIVE / UPDATED":
    st.warning(status_text + " • नया quote snapshot directional नहीं था; नीचे पिछली valid सूची दिखाई जा रही है।")

def score_heat_style(value, high_color):
    """Transparent at zero; progressively stronger green/red as score approaches 100."""
    score = safe_float(value)
    if score is None:
        return ""
    strength = max(0.0, min(100.0, score)) / 100.0
    rgb = (25, 145, 75) if high_color == "green" else (190, 45, 55)
    alpha = 0.82 * strength
    return f"background-color: rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {alpha:.3f});"


left, right = st.columns(2)
compact_cols = ["SYMBOL", "LTP", "DAY_%", "MOM_1M_%", "MOM_3M_%", "MOM_5M_%", "UP_SCORE"]
with left:
    st.subheader("🟢 Fastest Rising F&O Stocks — Top 10")
    view = up[[c for c in compact_cols if c in up.columns]].rename(columns={"SYMBOL":"Stock", "DAY_%":"Day %", "MOM_1M_%":"1m %", "MOM_3M_%":"3m %", "MOM_5M_%":"5m %", "UP_SCORE":"Score /100"})
    if view.empty:
        st.dataframe(pd.DataFrame({"Status":["No rising stock in current valid snapshot"]}), use_container_width=True, hide_index=True)
    else:
        styled_up = view.style.apply(lambda row: [score_heat_style(row.get("Score /100"), "green")] * len(row), axis=1).format(precision=2, na_rep="—")
        st.dataframe(styled_up, use_container_width=True, hide_index=True, height=390)
with right:
    st.subheader("🔴 Fastest Falling F&O Stocks — Top 10")
    view = down[["SYMBOL", "LTP", "DAY_%", "MOM_1M_%", "MOM_3M_%", "MOM_5M_%", "DOWN_SCORE"]].rename(columns={"SYMBOL":"Stock", "DAY_%":"Day %", "MOM_1M_%":"1m %", "MOM_3M_%":"3m %", "MOM_5M_%":"5m %", "DOWN_SCORE":"Score /100"})
    if view.empty:
        st.dataframe(pd.DataFrame({"Status":["No falling stock in current valid snapshot"]}), use_container_width=True, hide_index=True, height=390)
    else:
        styled_down = view.style.apply(lambda row: [score_heat_style(row.get("Score /100"), "red")] * len(row), axis=1).format(precision=2, na_rep="—")
        st.dataframe(styled_down, use_container_width=True, hide_index=True, height=390)

st.caption("पूरी row heatmap: Rising में score 0 पर transparent और 100 के करीब गहरा हरा; Falling में 0 पर transparent और 100 के करीब गहरा लाल.")
st.caption(f"Last valid scan: {st.session_state.get('last_scan', '—')} • Usable quotes: {st.session_state.get('quote_count', 0)} / {len(scan_universe)} • Latest API quotes: {st.session_state.get('latest_quote_count', st.session_state.get('quote_count', 0))} • Ranking is relative, not a win probability.")



st.divider()
st.header("📈 NSE Futures OI Intelligence — Top 10")
st.caption("Nearest available FUTSTK contract के live price + OI change से classification: Price↑ OI↑ = Long Buildup; Price↓ OI↑ = Short Buildup; Price↑ OI↓ = Short Covering; Price↓ OI↓ = Long Unwinding.")
refresh_oi = st.button("🔄 Refresh Futures OI", key="refresh_futures_oi")
last_oi_time = st.session_state.get("futures_oi_time", 0)
if refresh_oi or ("futures_oi" not in st.session_state) or (time.time() - last_oi_time > 60):
    try:
        with st.spinner("NSE stock futures के OI quotes प्राप्त हो रहे हैं..."):
            oi_frame, oi_note = fetch_futures_oi(fno_master, universe)
            st.session_state["futures_oi"] = oi_frame
            st.session_state["futures_oi_note"] = oi_note
            st.session_state["futures_oi_time"] = time.time()
    except Exception as exc:
        st.session_state["futures_oi"] = pd.DataFrame()
        st.session_state["futures_oi_note"] = f"Futures OI API error: {exc}"
oi_frame = st.session_state.get("futures_oi", pd.DataFrame())
oi_note = st.session_state.get("futures_oi_note")
if oi_note:
    st.warning(oi_note)
if not oi_frame.empty and "OI Setup" in oi_frame.columns:
    oi_groups = [
        ("🟢 Long Buildup — Top 10", "LONG BUILDUP", True),
        ("🔴 Short Buildup — Top 10", "SHORT BUILDUP", True),
        ("🟦 Short Covering — Top 10", "SHORT COVERING", True),
        ("🟠 Long Unwinding — Top 10", "LONG UNWINDING", True),
    ]
    oi_cols = ["Stock", "Price Change %", "Current OI", "OI Change", "OI Change %", "OI Activity Score", "Expiry"]
    oi_left, oi_right = st.columns(2)
    for idx, (title, setup, _) in enumerate(oi_groups):
        subset = oi_frame[oi_frame["OI Setup"].eq(setup)].copy()
        if not subset.empty:
            subset = subset.sort_values(["OI Activity Score", "OI Change"], ascending=[False, False], na_position="last").head(10)
        with (oi_left if idx % 2 == 0 else oi_right):
            st.subheader(title)
            if subset.empty:
                st.info("इस समय इस category में कोई confirmed futures OI setup नहीं मिला।")
            else:
                st.dataframe(subset[oi_cols].style.format(precision=2, na_rep="—"), use_container_width=True, hide_index=True)
    with st.expander("All futures OI records / API fields"):
        st.dataframe(oi_frame, use_container_width=True, hide_index=True)
        st.download_button("⬇ Download Futures OI CSV", oi_frame.to_csv(index=False).encode("utf-8"), "SHYAM_AI_Futures_OI.csv", "text/csv")
# Pick one representative from each side, then select only ONE overall idea.
def _candidate_row(pool, score_col, direction):
    if pool.empty:
        return None
    row = pool.sort_values([score_col, "DAY_%"], ascending=[False, direction != "UP"]).iloc[0]
    return row

rise_one = _candidate_row(up_pool, "UP_SCORE", "UP")
fall_one = _candidate_row(down_pool, "DOWN_SCORE", "DOWN")

def _candidate_adjustment(row, direction):
    if row is None:
        return None
    score = safe_float(row.get("UP_SCORE" if direction == "UP" else "DOWN_SCORE")) or 0.0
    m1, m3, m5 = (safe_float(row.get("MOM_1M_%")),
                  safe_float(row.get("MOM_3M_%")),
                  safe_float(row.get("MOM_5M_%")))
    expected = 1 if direction == "UP" else -1
    windows = [v for v in (m1, m3, m5) if v is not None]
    confirmations = sum(1 for v in windows if v * expected > 0)
    # 1m/3m/5m are all considered; two aligned windows are enough for confirmation.
    aligned = len(windows) >= 2 and confirmations >= 2
    if aligned and confirmations == len(windows):
        score += 10
    elif aligned:
        score += 4
    elif len(windows) >= 2:
        score -= 12
    oi_setup = None
    if not oi_frame.empty and "OI Setup" in oi_frame.columns:
        matches = oi_frame[oi_frame["Stock"].astype(str).str.upper().eq(str(row["SYMBOL"]).upper())]
        if not matches.empty:
            oi_setup = str(matches.iloc[0]["OI Setup"])
    supportive = {"UP": {"LONG BUILDUP", "SHORT COVERING"}, "DOWN": {"SHORT BUILDUP", "LONG UNWINDING"}}
    opposing = {"UP": {"SHORT BUILDUP", "LONG UNWINDING"}, "DOWN": {"LONG BUILDUP", "SHORT COVERING"}}
    if oi_setup in supportive[direction]:
        score += 8
    elif oi_setup in opposing[direction]:
        score -= 8

    # Historical shock guard: a very large one-day move is NOT automatically
    # treated as a continuation signal. Compare it with the stock's own recent
    # daily behaviour and require fresh short-window confirmation before chasing.
    history = {"available": False, "note": "Historical context अभी उपलब्ध नहीं।"}
    history_error = None
    try:
        history = historical_risk_context(row)
    except Exception as exc:
        history_error = str(exc)[:240]
        history = {"available": False, "note": f"Historical API उपलब्ध नहीं: {history_error}"}
    if history.get("available") and history.get("severity") in {"HIGH", "EXTREME"}:
        continuing = aligned and confirmations >= 2 and ((direction == "DOWN" and m5 is not None and m5 < 0) or (direction == "UP" and m5 is not None and m5 > 0))
        if not continuing:
            score -= 18 if history.get("severity") == "EXTREME" else 12
            history["chase_guard"] = "बड़ा abnormal move है; fresh 1m/3m/5m confirmation के बिना chase नहीं। WAIT बेहतर।"
        else:
            score -= 5
            history["chase_guard"] = "बड़ा abnormal move है, पर short-window momentum जारी है; event-risk के कारण position caution जरूरी।"
    elif history.get("available"):
        history["chase_guard"] = "हाल का daily move historical range के भीतर/करीब है।"

    return {"symbol": str(row["SYMBOL"]), "direction": direction, "base_score": float(row.get("UP_SCORE" if direction == "UP" else "DOWN_SCORE", 0) or 0),
            "score": max(0.0, min(100.0, score)), "m1": m1, "m3": m3, "m5": m5,
            "confirmations": confirmations, "windows": len(windows), "aligned": aligned, "oi": oi_setup,
            "history": history, "history_error": history_error,
            "ltp": safe_float(row.get("LTP")), "day": safe_float(row.get("DAY_%"))}

rise_candidate = _candidate_adjustment(rise_one, "UP")
fall_candidate = _candidate_adjustment(fall_one, "DOWN")

st.divider()
st.header("🧠 Intelligent Adaptive Pick — सिर्फ एक Final Selection")
st.caption("Rising और Falling के leaders की तुलना 1m/3m/5m momentum, Futures OI और recent daily history से होती है। असामान्य 6–20% move पर historical shock guard chase-risk घटाता है; यह अपने-आप reversal या continuation नहीं मानता।")
side_candidates = [c for c in (rise_candidate, fall_candidate) if c is not None]
if side_candidates:
    cand_cols = st.columns(2)
    for col, label, candidate in zip(cand_cols, ["Rising leader", "🔻 Falling leader"], [rise_candidate, fall_candidate]):
        with col:
            if label == "Rising leader":
                st.markdown("<div style='font-size:1.35rem;font-weight:750;color:#198754;margin:0 0 .45rem 0;'>▲ Rising leader</div>", unsafe_allow_html=True)
            else:
                st.subheader(label)
            if candidate:
                day_value = candidate.get("day")
                day_value = 0.0 if day_value is None else day_value
                # Do not use st.metric(delta=...) here: Streamlit's built-in
                # delta arrow/color can visually conflict with the leader direction.
                # Render an explicit direction-colored line instead.
                is_down = candidate["direction"] == "DOWN"
                arrow = "▼" if is_down else "▲"
                tone = "#dc3545" if is_down else "#198754"
                st.metric(candidate["symbol"], f"{candidate['score']:.1f} / 100")
                st.markdown(
                    f"<div style='color:{tone};font-weight:700;font-size:0.95rem;'>"
                    f"{arrow} {candidate['direction']} • Day {day_value:+.2f}%</div>",
                    unsafe_allow_html=True
                )
                st.caption(f"1m: {candidate['m1'] if candidate['m1'] is not None else 'collecting'}% • 3m: {candidate['m3'] if candidate['m3'] is not None else 'collecting'}% • 5m: {candidate['m5'] if candidate['m5'] is not None else 'collecting'}% • OI: {candidate['oi'] or 'not confirmed'}")
                hctx = candidate.get("history") or {}
                if hctx.get("available"):
                    st.write(f"**Historical risk:** {hctx.get('severity')} • median daily move {hctx.get('median_abs_day', 0):.2f}% • 20-session worst day {hctx.get('worst_day', 0):.2f}% • 20-session drawdown {hctx.get('peak_drawdown', 0):.2f}% • shock {hctx.get('shock_multiple', 0):.1f}x")
                    st.caption(hctx.get("note", ""))
                    st.warning(hctx.get("chase_guard", ""))
                else:
                    st.caption(hctx.get("note", "Daily history not available; score में historical guard शामिल नहीं हुआ।"))
            else:
                st.info("इस दिशा में अभी कोई valid leader नहीं।")
    side_candidates.sort(key=lambda x: x["score"], reverse=True)
    final_pick = side_candidates[0]
    # Require real short-window confirmation and minimum score before calling it trade-ready.
    hist_ctx = final_pick.get("history") or {}
    shock_block = bool(hist_ctx.get("available") and hist_ctx.get("severity") == "EXTREME" and not final_pick.get("aligned"))
    trade_ready = bool(final_pick["aligned"] and final_pick["score"] >= 45 and not shock_block)
    st.session_state["intelligent_pick"] = {**final_pick, "trade_ready": trade_ready}
    if trade_ready:
        final_arrow = "🟢 ▲" if final_pick["direction"] == "UP" else "🔻"
        st.success(f"🏆 आज का एक Final Candidate: {final_arrow} {final_pick['symbol']} — {'BUY CE setup' if final_pick['direction']=='UP' else 'BUY PE setup'} • Adaptive score {final_pick['score']:.1f}/100")
        st.write("कारण: उपलब्ध 1m/3m/5m windows में कम-से-कम दो एक दिशा में confirm हैं; Futures OI confirmation score में शामिल है। Option contract ₹10,000 budget, lot size, liquidity, spread और Greeks जाँचने के बाद ही shortlist होगा।")
    else:
        st.warning(f"एक provisional leader: {final_pick['symbol']} ({'CE side' if final_pick['direction']=='UP' else 'PE side'}) — अभी WAIT / NO TRADE. 1m/3m/5m में कम-से-कम दो-window confirmation या minimum score पूरा नहीं है।")
else:
    final_pick = None
    trade_ready = False
    st.warning("अभी कोई directional candidate नहीं। Market data/1m-3m snapshots आने तक WAIT.")
    st.session_state.pop("intelligent_pick", None)



st.divider()
st.header("🔎 Stock / Option Score Search — आपका 0–100 Logic")
st.caption("किसी NSE F&O stock का नाम या पूरा option trading symbol लिखें। Stock का scanner score और option का अलग contract-quality score दिखेगा। Option score, stock score की जगह नहीं लेता।")
# One native searchable dropdown: type a few letters (REL, HDF, etc.) and select
# the matching stock or OPTSTK contract. No second "Matching stock" box.
search_symbols, has_static_master = load_static_fno_symbols(universe)
contract_master = normalize_cols(fno_master)
contract_symbols = []
if {"EXCH", "INSTRUMENT_NAME", "TRADING_SYMBOL"}.issubset(contract_master.columns):
    opt_rows = contract_master[
        contract_master["EXCH"].astype(str).str.upper().eq("NSE") &
        contract_master["INSTRUMENT_NAME"].astype(str).str.upper().eq("OPTSTK")
    ]
    contract_symbols = opt_rows["TRADING_SYMBOL"].dropna().astype(str).str.upper().unique().tolist()
search_choices = sorted(set(search_symbols + contract_symbols))
st.caption("GitHub में सेव static F&O master से नाम तुरंत मिलेंगे; चुने गए symbol का live score/contract data API से आएगा." if has_static_master else "F&O master से stock और option symbols खोजें; live data API से आएगा.")
search_query = st.selectbox(
    "Stock / Option Symbol खोजें — कुछ अक्षर टाइप करें",
    options=[""] + search_choices,
    index=0,
    placeholder="REL लिखें और RELIANCE चुनें…",
    key="score_lookup_single_search"
).strip().upper()
if st.button("🔍 Analyse Search", key="run_score_lookup", type="primary"):
    st.session_state.pop("score_lookup_result", None)
    if not search_query:
        st.warning("पहले stock या option symbol लिखें।")
    else:
        # First resolve as a stock ticker in the current NSE F&O universe.
        stock_match = ranked[ranked["SYMBOL"].astype(str).str.upper().eq(search_query)]
        if stock_match.empty:
            stock_match = ranked[ranked["SYMBOL"].astype(str).str.upper().str.contains(re.escape(search_query), na=False)]
        if not stock_match.empty:
            r = stock_match.iloc[0]
            direction = "UP" if str(r.get("DIRECTION")) == "UP" else ("DOWN" if str(r.get("DIRECTION")) == "DOWN" else "SIDEWAYS")
            up_base = safe_float(r.get("UP_SCORE")) or 0.0
            down_base = safe_float(r.get("DOWN_SCORE")) or 0.0
            if direction == "SIDEWAYS":
                direction = "UP" if up_base >= down_base else "DOWN"
                base_score = max(up_base, down_base)
            else:
                base_score = up_base if direction == "UP" else down_base
            m1, m3, m5 = (safe_float(r.get("MOM_1M_%")), safe_float(r.get("MOM_3M_%")), safe_float(r.get("MOM_5M_%")))
            expected = 1 if direction == "UP" else -1
            vals = [v for v in (m1, m3, m5) if v is not None]
            confirms = sum(1 for v in vals if direction != "SIDEWAYS" and v * expected > 0)
            adj = (10 if vals and confirms == len(vals) else 4 if confirms >= 2 else -12 if len(vals) >= 2 else 0)
            search_oi = None
            if not oi_frame.empty and "OI Setup" in oi_frame.columns:
                oi_hit = oi_frame[oi_frame["Stock"].astype(str).str.upper().eq(str(r["SYMBOL"]).upper())]
                if not oi_hit.empty:
                    search_oi = str(oi_hit.iloc[0]["OI Setup"])
            supportive_oi = {"UP": {"LONG BUILDUP", "SHORT COVERING"}, "DOWN": {"SHORT BUILDUP", "LONG UNWINDING"}}
            opposing_oi = {"UP": {"SHORT BUILDUP", "LONG UNWINDING"}, "DOWN": {"LONG BUILDUP", "SHORT COVERING"}}
            if direction in supportive_oi and search_oi in supportive_oi[direction]:
                adj += 8
            elif direction in opposing_oi and search_oi in opposing_oi[direction]:
                adj -= 8
            stock_score = max(0.0, min(100.0, (base_score or 0) + adj))
            st.session_state["score_lookup_result"] = {"kind":"stock", "symbol":str(r["SYMBOL"]), "direction":direction,
                "score":stock_score, "base":base_score or 0, "day":safe_float(r.get("DAY_%")), "oi":search_oi,
                "m1":m1,"m3":m3,"m5":m5,"confirms":confirms,"available":len(vals),"ltp":safe_float(r.get("LTP"))}
        else:
            # Resolve a derivative trading symbol from the already downloaded F&O master.
            fm = normalize_cols(fno_rows)
            opt_master = fm[fm.get("INSTRUMENT_NAME", pd.Series(index=fm.index, dtype=str)).astype(str).str.upper().eq("OPTSTK")].copy()
            ts_col = "TRADING_SYMBOL" if "TRADING_SYMBOL" in opt_master.columns else None
            if ts_col:
                opt_master["_TS"] = opt_master[ts_col].astype(str).str.upper().str.strip()
                hits = opt_master[opt_master["_TS"].eq(search_query)]
                if hits.empty:
                    hits = opt_master[opt_master["_TS"].str.contains(re.escape(search_query), na=False)].head(5)
            else:
                hits = opt_master.iloc[0:0]
            if hits.empty:
                st.session_state["score_lookup_result"] = {"kind":"error", "message":f"'{search_query}' current NSE F&O stock universe या OPTSTK trading-symbol master में नहीं मिला। Stock ticker या पूरा option symbol जाँचें।"}
            else:
                contract = hits.iloc[0]
                under = clean_symbol(contract.get("SYMBOL_NAME"))
                exp_raw = contract.get("EXPIRY_DATE")
                exp_parsed = pd.to_datetime(exp_raw, errors="coerce", format="mixed", dayfirst=True)
                exp_text = exp_parsed.strftime("%Y-%m-%d") if pd.notna(exp_parsed) else ""
                try:
                    under_row = universe[universe["SYMBOL"].eq(under)]
                    if under_row.empty:
                        raise RuntimeError(f"Underlying {under} current NSE F&O cash universe में match नहीं हुआ।")
                    if not exp_text:
                        raise RuntimeError("इस option contract की expiry master से parse नहीं हुई।")
                    opt_chain = get_option_chain(under_row.iloc[0]["SECURITY_ID"], exp_text, 25)
                    chain_frame, spot_ltp, _ = build_chain_frame(opt_chain)
                    trading_symbol = str(contract.get("TRADING_SYMBOL", "")).strip().upper()
                    option_type = str(contract.get("OPTION_TYPE", "")).upper()
                    if option_type not in {"CE", "PE"}:
                        option_type = "CE" if trading_symbol.endswith("CE") else "PE"
                    leg_side = option_type
                    found = None
                    for _, cr in chain_frame.iterrows():
                        if str(cr.get(f"{leg_side} Trading Symbol") or "").strip().upper() == trading_symbol:
                            found = cr
                            break
                    if found is None:
                        raise RuntimeError("Option chain में यह exact contract नहीं मिला। Expiry/contract availability जाँचें।")
                    ltp = safe_float(found.get(f"{leg_side} LTP")) or 0
                    delta = safe_float(found.get(f"{leg_side} Delta"))
                    theta = safe_float(found.get(f"{leg_side} Theta"))
                    volume = safe_float(found.get(f"{leg_side} Volume")) or 0
                    oi = safe_float(found.get(f"{leg_side} OI")) or 0
                    spread = safe_float(found.get(f"{leg_side} Spread %"))
                    if delta is None:
                        delta_score = 10.0
                    else:
                        delta_score = max(0.0, 30.0 - abs(abs(delta) - 0.52) * 75.0)
                    liquidity_score = min(25.0, (volume / 1000.0) ** 0.5 * 5.0 + (oi / 10000.0) ** 0.5 * 5.0)
                    spread_score = 20.0 if spread is None else max(0.0, 25.0 - spread * 2.5)
                    theta_pct = abs(theta or 0) / ltp * 100 if ltp > 0 else 100
                    theta_score = max(0.0, 20.0 - theta_pct * 2.0)
                    option_score = round(delta_score + liquidity_score + spread_score + theta_score, 1)
                    lot = safe_float(contract.get("LOT_UNITS", contract.get("LOT_SIZE")))
                    premium_cost = ltp * lot if lot else None
                    st.session_state["score_lookup_result"] = {"kind":"option", "symbol":under,"contract":trading_symbol,"side":leg_side,
                        "expiry":exp_text,"score":option_score,"ltp":ltp,"delta":delta,"theta":theta,"volume":volume,
                        "oi":oi,"spread":spread,"lot":lot,"premium":premium_cost,"budget_fit":premium_cost is not None and premium_cost <= 9000}
                except Exception as exc:
                    st.session_state["score_lookup_result"] = {"kind":"error", "message":f"Option analysis नहीं हो पाया: {exc}"}
result = st.session_state.get("score_lookup_result")
if result:
    if result["kind"] == "error":
        st.error(result["message"])
    elif result["kind"] == "stock":
        a,b,c = st.columns(3)
        a.metric(f"{result['symbol']} — Stock Score", f"{result['score']:.1f} / 100", delta=result["direction"])
        b.metric("Day Change", f"{result['day'] if result['day'] is not None else 0:.2f}%")
        c.metric("Current LTP", f"₹{result['ltp']:.2f}" if result["ltp"] is not None else "—")
        st.write(f"**आपके scanner logic का base score:** {result['base']:.1f}/100 • **Momentum confirmation:** {result['confirms']}/{result['available']} available windows • **Futures OI:** {result['oi'] or 'not confirmed'}")
        st.caption(f"1m: {result['m1'] if result['m1'] is not None else 'collecting'}% · 3m: {result['m3'] if result['m3'] is not None else 'collecting'}% · 5m: {result['m5'] if result['m5'] is not None else 'collecting'}%")
    elif result["kind"] == "option":
        a,b,c = st.columns(3)
        a.metric(f"{result['contract']} — Option Score", f"{result['score']:.1f} / 100", delta=result["side"])
        b.metric("Option LTP", f"₹{result['ltp']:.2f}")
        c.metric("One Lot Premium", f"₹{result['premium']:,.0f}" if result["premium"] is not None else "Lot size unavailable")
        st.write(f"Underlying: **{result['symbol']}** • Expiry: **{result['expiry']}** • Delta: {result['delta']} • Theta/day: {result['theta']} • Volume: {result['volume']:,.0f} • OI: {result['oi']:,.0f} • Spread: {result['spread'] if result['spread'] is not None else 'not available'}%")
        if result["budget_fit"]:
            st.success("यह एक lot ₹9,000 premium cap के अंदर है; कुल ₹10,000 budget में charges/slippage buffer बचता है।")
        else:
            st.warning("यह contract ₹9,000 premium cap में fit नहीं है या lot size उपलब्ध नहीं। ₹10,000 budget के लिए इसे eligible न मानें।")
        st.caption("Option score contract-quality score है: delta suitability, volume/OI liquidity, bid-ask spread और theta burden। यह stock scanner score से अलग है और buy recommendation/guaranteed probability नहीं है।")

st.download_button("⬇️ Download matched F&O stock list (CSV)", data=universe.drop(columns=["SECURITY_ID", "SCRIP_CODE"], errors="ignore").to_csv(index=False).encode("utf-8"), file_name="SHYAM_AI_NSE_FO_universe.csv", mime="text/csv")
with st.expander("📋 Matched NSE F&O Stocks — Clean View", expanded=False):
    st.write(f"Matched stocks: {len(universe)}")
    # User-facing table deliberately hides broker plumbing (SECURITY_ID / SCRIP_CODE).
    # Keep those identifiers only in the in-memory API universe and downloadable raw CSV.
    clean_ranked = ranked.copy()
    if "DIRECTION" in clean_ranked.columns:
        clean_ranked["Direction"] = clean_ranked["DIRECTION"].map({"UP":"🟢 UP", "DOWN":"🔻 DOWN"}).fillna("⚪ FLAT")
    elif "DAY_%" in clean_ranked.columns:
        day = pd.to_numeric(clean_ranked["DAY_%"], errors="coerce").fillna(0)
        clean_ranked["Direction"] = day.map(lambda x: "🟢 UP" if x > 0.001 else ("🔻 DOWN" if x < -0.001 else "⚪ FLAT"))
    preferred_cols = ["SYMBOL", "LTP", "DAY_%", "Direction", "VOLUME", "OPEN", "HIGH", "LOW", "PREV_CLOSE", "MOM_1M_%", "MOM_3M_%", "MOM_5M_%", "SIGNAL"]
    display_cols = [c for c in preferred_cols if c in clean_ranked.columns]
    clean_ranked = clean_ranked[display_cols].rename(columns={"SYMBOL":"Stock", "DAY_%":"Day %", "VOLUME":"Volume", "OPEN":"Open", "HIGH":"High", "LOW":"Low", "PREV_CLOSE":"Prev Close", "MOM_1M_%":"1m %", "MOM_3M_%":"3m %", "MOM_5M_%":"5m %"})
    st.dataframe(clean_ranked, use_container_width=True, hide_index=True, height=420)
with st.expander("🧰 Advanced diagnostics (technical details)", expanded=False):
    st.json(diagnostics)

st.divider()
st.header("📊 Professional Option Chain — CE / Strike / PE")
st.caption("Groww-inspired layout: CE कॉलम हरे, Strike बीच में, PE कॉलम लाल। ATM, PCR और अधिकतम OI स्तर ऊपर दिखेंगे।")
all_symbols = universe["SYMBOL"].tolist()
# Do not hide the selector merely because an instrument-master column did not match.
# The official live OPTSTK contract-search endpoint is the source of truth per selection.
option_symbols = sorted(all_symbols)
option_search = st.text_input("⚡ जल्दी स्टॉक खोजें (जैसे REL)", placeholder="REL लिखें → RELIANCE सुझाव आएगा",
                              key="option_underlying_quick_search").strip().upper()
option_suggestions = [x for x in option_symbols if option_search in x][:15] if option_search else option_symbols
if option_search and option_suggestions:
    st.caption("Matching F&O tickers: " + " • ".join(option_suggestions[:10]))
elif option_search:
    st.warning("इस नाम से कोई NSE stock-F&O ticker नहीं मिला।")
pick_state = st.session_state.get("intelligent_pick")
preferred = (pick_state["symbol"] if pick_state and pick_state["symbol"] in option_symbols else
             (up.iloc[0]["SYMBOL"] if not up.empty and up.iloc[0]["SYMBOL"] in option_symbols else option_symbols[0]))
select_options = option_suggestions if option_search and option_suggestions else option_symbols
select_default = preferred if preferred in select_options else (select_options[0] if select_options else option_symbols[0])
selected = st.selectbox("Underlying Stock (NSE F&O)", select_options,
                        index=select_options.index(select_default), key="v24_option_underlying")
underlying_row = universe[universe["SYMBOL"].eq(selected)].iloc[0]
st.success(f"Selected stock: **{selected}** • Contract type: **OPTSTK**")
exp_key = f"v24_expiries_{selected}"
if st.button("🔄 Refresh Expiry / OPTSTK Availability", key="v24_refresh_expiry"):
    st.session_state.pop(exp_key, None)
    st.session_state.pop("last_chain", None)
if exp_key not in st.session_state:
    with st.spinner(f"{selected} के OPTSTK expiry dates जाँच रहे हैं..."):
        dates, source, err = expiry_dates(selected, fno_rows)
        st.session_state[exp_key] = (dates, source, err)
dates, source, expiry_error = st.session_state[exp_key]
if not dates:
    st.error(f"❌ {selected}: इस समय valid upcoming OPTSTK expiry नहीं मिली। Option Chain fetch नहीं किया गया।")
    st.caption(f"Lookup source: {source}")
    if expiry_error:
        st.code(expiry_error)
else:
    st.success(f"✅ {selected}: {len(dates)} upcoming expiry date(s) found • Source: {source}")
    expiry = st.selectbox("Expiry Date", dates, index=0, key=f"v24_expiry_{selected}")
    strike_count = st.slider("ATM के दोनों तरफ strikes", min_value=5, max_value=25, value=12, key=f"v24_strikes_{selected}")
    st.caption(f"Selected contract: **{selected} | {expiry} | NSE OPTSTK**")
    if st.button("📈 Fetch Option Chain", type="primary", key="v24_fetch_chain"):
        try:
            with st.spinner(f"{selected} {expiry}: OPTSTK contracts verify करके Option Chain ला रहे हैं..."):
                contracts = search_option_contracts(selected, expiry)
                chain = get_option_chain(underlying_row["SECURITY_ID"], expiry, strike_count)
            if not isinstance(chain, dict) or chain.get("status") != "success":
                raise RuntimeError(f"Option Chain API success नहीं लौटा: {str(chain)[:1500]}")
            chain_data = chain.get("data", {})
            strikes = chain_data.get("strikes", {}) if isinstance(chain_data, dict) else {}
            if not isinstance(strikes, dict) or not strikes:
                raise RuntimeError(f"{selected} {expiry}: API response में strikes खाली हैं। Contract search मिला: {len(contracts)}; chain payload: {str(chain)[:1200]}")
            st.session_state["last_chain"] = {"symbol": selected, "expiry": expiry, "payload": chain,
                                               "contract_count": len(contracts), "contracts": contracts,
                                               "security_id": str(underlying_row["SECURITY_ID"])}
            st.success(f"✅ Option Chain loaded: {selected} • {expiry} • {len(strikes)} strikes • {len(contracts)} OPTSTK contracts found")
        except Exception as exc:
            st.session_state.pop("last_chain", None)
            st.error(f"❌ Option Chain नहीं आया: {exc}")

last_chain = st.session_state.get("last_chain")
if last_chain:
    if last_chain["symbol"] != selected or last_chain["expiry"] != (st.session_state.get(f"v24_expiry_{selected}") or last_chain["expiry"]):
        st.info("ऊपर selected underlying/expiry बदल गया है। नया chain देखने के लिए Fetch Option Chain दबाएँ।")
    else:
        st.caption(f"Loaded: {last_chain['symbol']} • Expiry: {last_chain['expiry']} • {last_chain['contract_count']} matching OPTSTK contracts")
        pick = st.session_state.get("intelligent_pick")
        if pick and pick.get("symbol") == last_chain["symbol"]:
            st.subheader("💰 ₹10,000 Budget — One-Lot Option Shortlist")
            if not pick.get("trade_ready"):
                st.warning("Scanner confirmation अभी WAIT है। नीचे chain देखकर contract shortlist कर सकते हैं, लेकिन इसे live buy signal न मानें।")
            recommendation, rec_error = recommend_option_contract(
                last_chain["payload"], last_chain["symbol"], last_chain["expiry"],
                pick["direction"], fno_rows, last_chain.get("contracts", []), 10000.0)
            if recommendation:
                st.success(f"Best-fit contract: {recommendation['Contract']} • {recommendation['Side']} • One-lot premium लगभग ₹{recommendation['One-lot premium ₹']:,.0f} / ₹10,000")
                st.dataframe(pd.DataFrame([recommendation]).style.format(precision=2, na_rep="—"), use_container_width=True, hide_index=True)
                st.caption("एक lot ही माना गया है; premium cost में brokerage, taxes और slippage शामिल नहीं हैं। Spread/volume/Greeks live quote के साथ बदल सकते हैं।")
            else:
                st.warning(rec_error)
        else:
            st.info("Intelligent pick उपलब्ध होने पर उसी stock का option contract budget के अनुसार shortlist होगा।")
        try:
            render_chain(last_chain["payload"], last_chain["symbol"], last_chain["expiry"], fno_rows, last_chain.get("contracts", []))
        except Exception as exc:
            st.error(f"Option Chain display error: {exc}")

with st.expander("🛡️ Safety, scoring and deployment notes"):
    st.markdown("""
- **No strategy execution / no order placement:** यह केवल scanner और market-data dashboard है।
- **Momentum:** 1m/3m/5m बदलाव quote snapshots से calculate होते हैं; Intelligent Pick में उपलब्ध तीनों windows से कम-से-कम दो का alignment जाँचा जाता है। पहले पर्याप्त समय तक ऐप चलना जरूरी है।
- **Historical shock guard:** चुने गए Rising/Falling leaders के लिए INDstocks `1day` candles से recent daily median move, worst daily fall और peak-to-trough drawdown देखे जाते हैं। 6–20% जैसे abnormal move पर बिना short-window confirmation chase score घटता है।
- **कारण की पुष्टि:** OHLCV history price move का आकार बताती है, कारण नहीं। Company announcement/news को अलग से verify किए बिना app किसी 20% fall को “market-wide” या “company-specific event” घोषित नहीं करेगा।
- **Top 10 Rising / Falling:** दोनों Top 10 rank lists बनी रहती हैं; Intelligent Adaptive Pick प्रत्येक दिशा से एक leader लेकर केवल एक overall candidate चुनता है।
- **Score Search:** Stock का score scanner के 0–100 logic से; option का अलग contract-quality score delta/liquidity/spread/theta से निकलेगा।
- **Option shortlist:** ₹10,000 budget में verified lot size के साथ एक lot का premium अधिकतम ₹9,000 रखा जाता है ताकि charges/spread के लिए buffer रहे। Lot size या liquidity verify न हो तो कोई contract recommend नहीं होता।
- **Option Chain:** केवल ITM Calls green और ITM Puts red; OTM cells dark रहते हैं। ATM strike पर divider है।
- **Futures OI:** NSE FUTSTK quote fields से चार OI setups बनते हैं; API OI field न दे तो अनुमान नहीं लगाया जाता।
- **API rate limits:** refresh interval बहुत कम न रखें। बड़े universe के quotes batch में माँगे जाते हैं।
- **Cloud deployment:** public hosting से पहले APP_PASSWORD लगाएँ। अगर broker account में IP allowlisting लागू है, तो fixed outbound IP वाली VM/network setup चाहिए; Cloud Run का सामान्य outbound IP स्थायी नहीं होता।
- **Trading:** signals को पहले paper-trading में validate करें; spread, slippage, liquidity और expiry theta का जोखिम रहता है।
""")
st.markdown("Official references: [INDstocks API docs](https://api-docs.indstocks.com/) · [Quotes](https://api-docs.indstocks.com/MarketQuote/) · [Instruments](https://api-docs.indstocks.com/instruments/) · [Option Chain](https://api-docs.indstocks.com/utility/)")
