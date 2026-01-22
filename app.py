import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(page_title="Daily Trading Dashboard", layout="wide")

st.title("📈 Daily Prices Dashboard (Clean + Trader Style)")
st.caption("Upload daily OHLC CSVs → stacked charts → highlight daily moves + volatility + regime shifts ⚡")

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.header("⚙️ Controls")

uploaded_files = st.sidebar.file_uploader(
    "Upload one or more DAILY CSV files",
    type=["csv"],
    accept_multiple_files=True
)

chart_mode = st.sidebar.selectbox(
    "Chart Mode",
    ["Close Line (Clean)", "Candlestick + Close", "Candlestick Only"]
)

resample_tf = st.sidebar.selectbox(
    "Resample Timeframe",
    ["Daily", "Weekly", "Monthly"]
)

rolling_window = st.sidebar.slider("Smooth Close (Rolling)", 1, 50, 7)
vol_window = st.sidebar.slider("Volatility Window (days)", 5, 60, 20)

big_move_threshold = st.sidebar.slider("Big Move Threshold (% change)", 0.1, 10.0, 2.0, 0.1)

show_change_bars = st.sidebar.checkbox("Show Daily Change Bars (Δ Close)", True)
overlay_compare = st.sidebar.checkbox("Overlay Compare All Closes", False)

# ----------------------------
# Helpers
# ----------------------------
def resample_ohlc(df, tf):
    """Resample OHLC to Weekly/Monthly while keeping OHLC logic correct."""
    if tf == "Daily":
        return df

    rule = "W" if tf == "Weekly" else "M"

    df = df.set_index("date")
    out = pd.DataFrame()
    out["open"] = df["open"].resample(rule).first()
    out["high"] = df["high"].resample(rule).max()
    out["low"] = df["low"].resample(rule).min()
    out["close"] = df["close"].resample(rule).last()

    out = out.dropna().reset_index()
    return out


def load_and_clean_csv(file):
    df = pd.read_csv(file)

    required = {"date", "open", "high", "low", "close"}
    if not required.issubset(df.columns):
        st.error(f"❌ {file.name} missing required columns. Needs: {required}")
        return None

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df = df.dropna(subset=["open", "high", "low", "close"])

    # Resample if needed
    df = resample_ohlc(df, resample_tf)

    # Features
    df["delta_close"] = df["close"].diff()
    df["return_pct"] = df["close"].pct_change() * 100
    df["close_smooth"] = df["close"].rolling(rolling_window).mean()
    df["volatility"] = df["return_pct"].rolling(vol_window).std()

    return df


def make_daily_chart(df, title):
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.60, 0.20, 0.20]
    )

    # ---------------- Row 1: Price ----------------
    if chart_mode in ["Candlestick + Close", "Candlestick Only"]:
        fig.add_trace(
            go.Candlestick(
                x=df["date"],
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="OHLC"
            ),
            row=1, col=1
        )

    if chart_mode in ["Close Line (Clean)", "Candlestick + Close"]:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["close"],
                mode="lines",
                name="Close",
                line=dict(width=2),
                hovertemplate="Date=%{x}<br>Close=%{y}<extra></extra>"
            ),
            row=1, col=1
        )

    if rolling_window > 1:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["close_smooth"],
                mode="lines",
                name=f"Smooth({rolling_window})",
                line=dict(width=1, dash="dot"),
                opacity=0.9
            ),
            row=1, col=1
        )

    # Big move markers
    big_moves = df[df["return_pct"].abs() >= big_move_threshold]
    if len(big_moves) > 0:
        fig.add_trace(
            go.Scatter(
                x=big_moves["date"],
                y=big_moves["close"],
                mode="markers",
                name=f"Big Moves (≥{big_move_threshold}%)",
                marker=dict(size=7, symbol="diamond"),
                hovertemplate="BIG MOVE<br>Date=%{x}<br>Close=%{y}<extra></extra>"
            ),
            row=1, col=1
        )

    # ---------------- Row 2: Δ Close bars ----------------
    if show_change_bars:
        colors = np.where(df["delta_close"] >= 0, 1, -1)
        fig.add_trace(
            go.Bar(
                x=df["date"],
                y=df["delta_close"].fillna(0),
                name="Δ Close",
                opacity=0.45,
                hovertemplate="Date=%{x}<br>Δ Close=%{y}<extra></extra>"
            ),
            row=2, col=1
        )

    # ---------------- Row 3: Volatility ----------------
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["volatility"].fillna(0),
            mode="lines",
            name=f"Vol({vol_window})",
            line=dict(width=1),
            hovertemplate="Vol=%{y}<extra></extra>"
        ),
        row=3, col=1
    )

    fig.update_layout(
        title=title,
        height=680,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Δ Close", row=2, col=1)
    fig.update_yaxes(title_text="Vol", row=3, col=1)

    return fig


# ----------------------------
# Main
# ----------------------------
if not uploaded_files:
    st.info("⬅️ Upload daily OHLC CSVs (date, open, high, low, close)")
    st.stop()

dfs, names = [], []

for f in uploaded_files:
    df = load_and_clean_csv(f)
    if df is not None and len(df) > 10:
        dfs.append(df)
        names.append(f.name)

if not dfs:
    st.warning("No valid daily datasets loaded.")
    st.stop()

# ----------------------------
# Summary
# ----------------------------
st.subheader("📌 Quick Summary (Daily)")

summary_rows = []
for name, df in zip(names, dfs):
    last_close = df["close"].iloc[-1]
    last_ret = df["return_pct"].iloc[-1] if not np.isnan(df["return_pct"].iloc[-1]) else 0
    max_abs_ret = df["return_pct"].abs().max()

    summary_rows.append({
        "File": name,
        "Rows": len(df),
        "Start": df["date"].min(),
        "End": df["date"].max(),
        "Last Close": float(last_close),
        "Last %Change": float(last_ret),
        "Max |%Change|": float(max_abs_ret),
    })

summary_df = pd.DataFrame(summary_rows)
st.dataframe(summary_df, use_container_width=True)

st.markdown("---")

# ----------------------------
# Stacked charts
# ----------------------------
st.subheader("📊 Stacked Daily Charts (Top → Bottom)")

for name, df in zip(names, dfs):
    left, right = st.columns([4.5, 1.5])

    with left:
        fig = make_daily_chart(df, f"📈 {name} ({resample_tf})")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("### ⚡ Stats")

        last_close = df["close"].iloc[-1]
        last_ret = df["return_pct"].iloc[-1] if not np.isnan(df["return_pct"].iloc[-1]) else 0

        st.metric("Last Close", f"{last_close:.6f}")
        st.metric("Last %Change", f"{last_ret:.2f}%")

        biggest = df.loc[df["return_pct"].abs().idxmax()]
        st.markdown("#### 💥 Biggest Day")
        st.write(f"📅 {biggest['date']}")
        st.write(f"% Change: {biggest['return_pct']:.2f}%")
        st.write(f"Close: {biggest['close']:.6f}")

st.markdown("---")

# ----------------------------
# Overlay compare
# ----------------------------
if overlay_compare:
    st.subheader("🧠 Overlay Compare (All Closes)")

    fig2 = go.Figure()
    for name, df in zip(names, dfs):
        fig2.add_trace(go.Scatter(
            x=df["date"],
            y=df["close"],
            mode="lines",
            name=name
        ))

    fig2.update_layout(
        title=f"Overlay Close Comparison ({resample_tf})",
        height=550,
        hovermode="x unified",
        xaxis=dict(rangeslider=dict(visible=True))
    )

    st.plotly_chart(fig2, use_container_width=True)

st.success("✅ Daily dashboard loaded. Upload more files anytime.")
