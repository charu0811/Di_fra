import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ----------------------------
# Page Config
# ----------------------------
st.set_page_config(page_title="Trading Dashboard", layout="wide")

st.title("📈 Multi-CSV Trading Dashboard (Clean + Interactive)")
st.caption("Upload multiple OHLC CSVs → stacked charts → spikes + volatility → overlay comparison ⚡")

# ----------------------------
# Sidebar
# ----------------------------
st.sidebar.header("⚙️ Dashboard Controls")

uploaded_files = st.sidebar.file_uploader(
    "Upload one or more CSV files",
    type=["csv"],
    accept_multiple_files=True
)

chart_mode = st.sidebar.selectbox(
    "Chart Mode",
    ["Close Line (Clean)", "Candlestick + Close", "Candlestick Only"]
)

rolling_window = st.sidebar.slider("Smooth Close (Rolling Window)", 1, 50, 5)
spike_threshold = st.sidebar.slider("Spike Detection (Z-score)", 1.0, 8.0, 3.5, 0.1)
vol_window = st.sidebar.slider("Volatility Window", 5, 60, 20)

st.sidebar.markdown("---")
compare_overlay = st.sidebar.checkbox("Overlay Compare All Closes", False)

# ----------------------------
# Helper: Load & Clean CSV
# ----------------------------
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

    # Features
    df["delta"] = df["close"].diff()
    df["return_pct"] = df["close"].pct_change() * 100

    # Smooth close
    df["close_smooth"] = df["close"].rolling(rolling_window).mean()

    # Volatility
    df["vol_heat"] = df["return_pct"].rolling(vol_window).std()

    # Z-score spikes
    std = df["delta"].std()
    if std and std != 0:
        df["z"] = (df["delta"] - df["delta"].mean()) / std
    else:
        df["z"] = 0

    return df

# ----------------------------
# Helper: Chart Builder
# ----------------------------
def make_chart(df, title):
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.75, 0.25]
    )

    # ---- PRICE CHART (Row 1) ----
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

    # Smooth line
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

    # Spike markers (only important points)
    spikes = df[np.abs(df["z"]) >= spike_threshold]
    if len(spikes) > 0:
        fig.add_trace(
            go.Scatter(
                x=spikes["date"],
                y=spikes["close"],
                mode="markers",
                name=f"Spikes (Z≥{spike_threshold})",
                marker=dict(size=7, symbol="circle"),
                hovertemplate="SPIKE<br>Date=%{x}<br>Close=%{y}<extra></extra>"
            ),
            row=1, col=1
        )

    # ---- VOLATILITY PANEL (Row 2) ----
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["vol_heat"].fillna(0),
            mode="lines",
            name=f"Volatility({vol_window})",
            line=dict(width=1),
            hovertemplate="Vol=%{y}<extra></extra>"
        ),
        row=2, col=1
    )

    # Layout
    fig.update_layout(
        title=title,
        height=560,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0)
    )

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Vol", row=2, col=1)

    return fig

# ----------------------------
# Main App
# ----------------------------
if not uploaded_files:
    st.info("⬅️ Upload CSV files from the sidebar (must have: date, open, high, low, close)")
    st.stop()

dfs = []
names = []

for f in uploaded_files:
    df = load_and_clean_csv(f)
    if df is not None and len(df) > 5:
        dfs.append(df)
        names.append(f.name)

if not dfs:
    st.warning("No valid datasets loaded.")
    st.stop()

# ----------------------------
# Summary Table
# ----------------------------
st.subheader("📌 Quick Summary")

summary_rows = []
for name, df in zip(names, dfs):
    last_close = df["close"].iloc[-1]
    last_ret = df["return_pct"].iloc[-1] if not np.isnan(df["return_pct"].iloc[-1]) else 0
    max_spike = df["z"].abs().max()

    summary_rows.append({
        "File": name,
        "Rows": len(df),
        "Start": df["date"].min(),
        "End": df["date"].max(),
        "Last Close": float(last_close),
        "Last %Change": float(last_ret),
        "Max Spike (Z)": float(max_spike),
    })

summary_df = pd.DataFrame(summary_rows)
st.dataframe(summary_df, use_container_width=True)

st.markdown("---")

# ----------------------------
# Stacked Charts
# ----------------------------
st.subheader("📊 Stacked Charts (Top → Bottom)")

for name, df in zip(names, dfs):
    left, right = st.columns([4.5, 1.5])

    with left:
        fig = make_chart(df, f"📈 {name}")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("### ⚡ Live Stats")

        last_close = df["close"].iloc[-1]
        last_ret = df["return_pct"].iloc[-1] if not np.isnan(df["return_pct"].iloc[-1]) else 0
        max_spike = df["z"].abs().max()

        st.metric("Last Close", f"{last_close:.6f}")
        st.metric("Last %Change", f"{last_ret:.2f}%")
        st.metric("Max Spike (Z)", f"{max_spike:.2f}")

        # Biggest move row
        biggest = df.loc[df["delta"].abs().idxmax()]
        st.markdown("#### 💥 Biggest Move")
        st.write(f"📅 {biggest['date']}")
        st.write(f"Δ Close: {biggest['delta']:.6f}")
        st.write(f"Close: {biggest['close']:.6f}")

st.markdown("---")

# ----------------------------
# Overlay Compare Mode
# ----------------------------
if compare_overlay:
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
        title="Overlay Close Comparison",
        height=550,
        hovermode="x unified",
        xaxis=dict(rangeslider=dict(visible=True))
    )

    st.plotly_chart(fig2, use_container_width=True)

st.success("✅ Dashboard loaded successfully. Upload more CSVs anytime.")
