import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

st.set_page_config(page_title="Crazy Multi-CSV Trading Dashboard", layout="wide")

st.title("📈 Crazy Interactive Multi-CSV Trading Dashboard")
st.caption("Upload multiple OHLC CSVs → stacked charts → detect spikes → highlight price changes like a terminal ⚡")

# -------------------------
# Sidebar Controls
# -------------------------
st.sidebar.header("⚙️ Controls")

uploaded_files = st.sidebar.file_uploader(
    "Upload one or more CSV files",
    type=["csv"],
    accept_multiple_files=True
)

chart_mode = st.sidebar.selectbox(
    "Chart Type",
    ["Candlestick + Close", "Close Line Only", "Candlestick Only"]
)

rolling_window = st.sidebar.slider("Rolling Smooth (Close)", 1, 50, 1)
show_volume_like = st.sidebar.checkbox("Show 'Volatility Heat' (fake volume style)", True)

spike_threshold = st.sidebar.slider("Spike Detection Threshold (Z-score)", 1.0, 6.0, 2.5, 0.1)
pct_jump_threshold = st.sidebar.slider("Big % Jump Threshold", 0.1, 10.0, 1.5, 0.1)

sync_xaxis = st.sidebar.checkbox("Sync X-axis across all charts", True)

st.sidebar.markdown("---")
st.sidebar.caption("Made to feel like a trading dashboard 🚀")

# -------------------------
# Helpers
# -------------------------
def load_and_clean_csv(file):
    df = pd.read_csv(file)

    # Required columns check
    required = {"date", "open", "high", "low", "close"}
    if not required.issubset(set(df.columns)):
        st.error(f"❌ {file.name} missing required columns: {required}")
        return None

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date")

    # Convert numeric columns
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"])

    # Features
    df["return"] = df["close"].pct_change() * 100
    df["delta"] = df["close"].diff()
    df["abs_delta"] = df["delta"].abs()

    # Z-score spike detection
    if df["delta"].std() != 0:
        df["z"] = (df["delta"] - df["delta"].mean()) / df["delta"].std()
    else:
        df["z"] = 0

    # Rolling smooth
    df["close_smooth"] = df["close"].rolling(rolling_window).mean()

    # "volatility heat"
    df["vol_heat"] = df["return"].rolling(20).std()

    return df


def make_chart(df, title):
    # --- Create 2 rows: Price + Volatility
    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.75, 0.25]
    )

    # ---------------- PRICE CHART ----------------
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["close"],
        mode="lines",
        name="Close",
        line=dict(width=2),
        hovertemplate="Date=%{x}<br>Close=%{y}<extra></extra>"
    ), row=1, col=1)

    # Optional smoothing
    if rolling_window > 1:
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["close_smooth"],
            mode="lines",
            name=f"Smooth({rolling_window})",
            line=dict(width=1, dash="dot"),
            opacity=0.8
        ), row=1, col=1)

    # --- Spike detection markers (only a few points)
    spikes = df[np.abs(df["z"]) >= spike_threshold]
    if len(spikes) > 0:
        fig.add_trace(go.Scatter(
            x=spikes["date"],
            y=spikes["close"],
            mode="markers",
            name=f"Spikes (Z≥{spike_threshold})",
            marker=dict(size=6, symbol="circle"),
            hovertemplate="SPIKE<br>Date=%{x}<br>Close=%{y}<extra></extra>"
        ), row=1, col=1)

    # --- Big % jump shading (clean highlight)
    jumps = df[np.abs(df["return"]) >= pct_jump_threshold]
    for _, r in jumps.iterrows():
        fig.add_vrect(
            x0=r["date"],
            x1=r["date"],
            opacity=0.15,
            line_width=0
        )

    # ---------------- VOL HEAT PANEL ----------------
    fig.add_trace(go.Scatter(
        x=df["date"],
        y=df["vol_heat"].fillna(0),
        mode="lines",
        name="Vol Heat",
        line=dict(width=1),
        opacity=0.9,
        hovertemplate="Vol Heat=%{y}<extra></extra>"
    ), row=2, col=1)

    # ---------------- Layout polish ----------------
    fig.update_layout(
        title=title,
        height=520,
        margin=dict(l=10, r=10, t=50, b=10),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        xaxis=dict(rangeslider=dict(visible=False)),
    )

    fig.update_yaxes(title_text="Price", row=1, col=1)
    fig.update_yaxes(title_text="Vol", row=2, col=1)

    return fig



# -------------------------
# Main
# -------------------------
if not uploaded_files:
    st.info("⬅️ Upload CSVs from the sidebar. (Must contain: date, open, high, low, close)")
    st.stop()

dfs = []
names = []

for f in uploaded_files:
    df = load_and_clean_csv(f)
    if df is not None and len(df) > 10:
        dfs.append(df)
        names.append(f.name)

if not dfs:
    st.warning("No valid datasets found.")
    st.stop()

# Summary table
st.subheader("📌 Quick Summary")
summary_rows = []
for name, df in zip(names, dfs):
    summary_rows.append({
        "File": name,
        "Rows": len(df),
        "Start": df["date"].min(),
        "End": df["date"].max(),
        "Last Close": df["close"].iloc[-1],
        "Last %Change": df["return"].iloc[-1],
        "Max Abs Δ": df["abs_delta"].max(),
        "Max |%Change|": df["return"].abs().max()
    })

summary_df = pd.DataFrame(summary_rows)
st.dataframe(summary_df, use_container_width=True)

st.markdown("---")

# Stacked charts
st.subheader("📊 Stacked Interactive Charts (Top → Bottom)")

for name, df in zip(names, dfs):
    col1, col2 = st.columns([4, 1])

    with col1:
        fig = make_chart(df, title=f"📈 {name}")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("### ⚡ Signals")
        last_close = df["close"].iloc[-1]
        last_ret = df["return"].iloc[-1]
        max_spike = df["z"].abs().max()

        st.metric("Last Close", f"{last_close:.4f}")
        st.metric("Last %Change", f"{last_ret:.2f}%")
        st.metric("Max Spike (Z)", f"{max_spike:.2f}")

        # Highlight direction bias
        up_moves = (df["delta"] > 0).sum()
        down_moves = (df["delta"] < 0).sum()

        st.markdown("#### 📌 Bias")
        if up_moves > down_moves:
            st.success("More Up Moves 📈")
        elif down_moves > up_moves:
            st.error("More Down Moves 📉")
        else:
            st.info("Neutral ⚖️")

        # Extreme move preview
        biggest_move = df.loc[df["abs_delta"].idxmax()]
        st.markdown("#### 💥 Biggest Move")
        st.write(f"🕒 {biggest_move['date']}")
        st.write(f"Δ Close: {biggest_move['delta']:.4f}")
        st.write(f"Close: {biggest_move['close']:.4f}")

st.markdown("---")

# Crazy Comparison Mode
st.subheader("🧠 Crazy Mode: Compare All Closes Together (Overlay)")
compare = st.checkbox("Enable Overlay Comparison")

if compare:
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
        height=500,
        hovermode="x unified",
        xaxis=dict(rangeslider=dict(visible=True))
    )
    st.plotly_chart(fig2, use_container_width=True)

st.success("✅ Dashboard ready. Upload new CSVs anytime and it auto-updates like a live terminal.")
