# -*- coding: utf-8 -*-
"""
app.py - Dashboard Streamlit SOL BOT (KHUSUS BACKTEST).

Cara menjalankan:
    pip install -r requirements.txt
    streamlit run app.py

PENTING: Dashboard ini hanya menjalankan BACKTEST dengan data historis asli
dari Binance. Tidak ada live trading, tidak ada API key, tidak ada order sungguhan.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from backtest import Pengaturan, ambil_data_binance, buat_kesimpulan, jalankan_backtest

# ---------------------------------------------------------------------------
# PENGATURAN HALAMAN
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="SOL BOT - Dashboard Backtest",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS KUSTOM supaya tampilan lebih cantik (tema gelap ala Solana)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    .stApp { background: linear-gradient(180deg, #0b0f1a 0%, #111827 100%); }
    .judul-utama {
        font-size: 2.3rem; font-weight: 800; margin-bottom: 0.1rem;
        background: linear-gradient(90deg, #9945FF, #14F195);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    }
    .subjudul { color: #9ca3af; margin-bottom: 1.2rem; }
    .kartu {
        background: #161e2e; border: 1px solid #263045; border-radius: 16px;
        padding: 18px 20px; box-shadow: 0 6px 18px rgba(0,0,0,0.35);
        height: 100%;
    }
    .kartu-label { color: #9ca3af; font-size: 0.9rem; text-transform: uppercase; letter-spacing: .05em; }
    .kartu-nilai { color: #f9fafb; font-size: 2rem; font-weight: 800; margin-top: 4px; }
    .kartu-kecil { font-size: 0.95rem; margin-top: 2px; }
    .hijau { color: #14F195 !important; }
    .merah { color: #ff5c7a !important; }
    .abu { color: #9ca3af !important; }
    .kotak-hijau {
        background: rgba(20,241,149,0.12); border: 2px solid #14F195; color: #14F195;
        border-radius: 14px; padding: 18px; font-size: 1.5rem; font-weight: 800; text-align: center;
    }
    .kotak-merah {
        background: rgba(255,92,122,0.12); border: 2px solid #ff5c7a; color: #ff5c7a;
        border-radius: 14px; padding: 18px; font-size: 1.5rem; font-weight: 800; text-align: center;
    }
    .saran {
        background: #161e2e; border-left: 4px solid #9945FF; border-radius: 10px;
        padding: 12px 16px; margin: 8px 0; color: #e5e7eb;
    }
    .disclaimer { color: #9ca3af; font-size: 0.85rem; margin-top: 1rem; }
    /* Tombol besar di sidebar */
    section[data-testid="stSidebar"] button[kind="primary"] {
        width: 100%; height: 3.4rem; font-size: 1.15rem; font-weight: 800;
        background: linear-gradient(90deg, #9945FF, #14F195); color: #0b0f1a; border: none;
        border-radius: 12px;
    }
    section[data-testid="stSidebar"] button[kind="primary"]:hover { filter: brightness(1.1); color: #000; }
    h3 { color: #e5e7eb !important; }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# AMBIL DATA (di-cache 10 menit supaya tidak bolak-balik download dari Binance)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=600, show_spinner=False)
def ambil_data_cache(hari: int):
    """Mengambil data asli Binance dan menyimpannya di cache Streamlit."""
    df, sumber = ambil_data_binance(hari)
    return df, sumber, df.attrs.get("mulai_periode_ms")


# ---------------------------------------------------------------------------
# SIDEBAR: SEMUA SETTING STRATEGI
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Setting Strategi")
    periode_label = st.selectbox("Pilih Periode", ["7 hari", "30 hari", "90 hari"], index=1)
    hari = int(periode_label.split()[0])
    modal_awal = st.slider("Modal Awal (USDT)", 10, 1000, 100, step=10)
    tp1 = st.slider("TP 1 (%) - jual 50%", 1.0, 5.0, 2.5, step=0.1)
    tp2 = st.slider("TP 2 (%) - jual sisa 50%", 3.0, 10.0, 5.0, step=0.1)
    sl = st.slider("Stop Loss (%) - jual semua", 0.5, 3.0, 1.5, step=0.1)
    rsi_buy = st.slider("RSI Buy (beli jika RSI di bawah)", 25, 40, 35, step=1)

    with st.expander("🔧 Pengaturan lanjutan"):
        jendela_rsi = st.slider(
            "Jendela RSI (candle)", 1, 24, 1, step=1,
            help="1 = RSI harus di bawah batas pada candle yang SAMA dengan cross EMA (aturan asli). "
                 "Angka lebih besar = cukup RSI rendah di salah satu dari N candle terakhir.",
        )
        st.caption("Tetap: trailing ke harga modal di +1.5%, jual semua jika RSI > 72, "
                   "10% saldo per trade, maks 3 posisi, fee 0.1% tiap beli & jual.")

    if tp2 <= tp1:
        st.warning("TP 2 lebih kecil/sama dengan TP 1. TP 2 otomatis disamakan dengan TP 1.")

    tombol = st.button("▶️ JALANKAN BACKTEST", type="primary", width="stretch")
    st.markdown("---")
    st.caption("Mode: **BACKTEST SAJA**. Tidak ada live trading, tidak ada API key, tidak ada order.")

# ---------------------------------------------------------------------------
# JUDUL
# ---------------------------------------------------------------------------
st.markdown('<div class="judul-utama">🚀 SOL BOT - Dashboard Backtest Tim</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subjudul">Backtest SOL/USDT candle 5 menit • data asli Binance via ccxt • '
    "tanpa live trading</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# JALANKAN BACKTEST SAAT TOMBOL DITEKAN
# ---------------------------------------------------------------------------
if tombol:
    with st.spinner("Sedang backtest, tunggu ya..."):
        try:
            df, sumber, mulai_ms = ambil_data_cache(hari)
            df = df.copy()
            df.attrs["mulai_periode_ms"] = mulai_ms
            pengaturan = Pengaturan(modal_awal=float(modal_awal), tp1=tp1, tp2=tp2, sl=sl,
                                    rsi_buy=float(rsi_buy), jendela_rsi=int(jendela_rsi))
            hasil = jalankan_backtest(df, pengaturan)
            hasil["sumber"] = sumber
            hasil["periode_label"] = periode_label
            st.session_state["hasil"] = hasil
        except Exception as e:  # noqa: BLE001
            st.error(f"Gagal mengambil data dari Binance. Coba lagi beberapa saat.\n\nDetail: {e}")
            st.stop()

if "hasil" not in st.session_state:
    st.info("👈 Atur strategi di sidebar kiri, lalu tekan **▶️ JALANKAN BACKTEST**.")
    st.stop()

hasil = st.session_state["hasil"]
s = hasil["statistik"]
trades = hasil["trades"]
equity = hasil["equity"]
p = hasil["pengaturan"]

st.caption(
    f"Sumber data: **{hasil['sumber']}** • Periode {hasil['periode_label']}: "
    f"{s['mulai']:%d %b %Y %H:%M} s/d {s['selesai']:%d %b %Y %H:%M} (JST) • "
    f"{s['jumlah_candle']:,} candle • {s['jumlah_sinyal']} sinyal BUY • Jendela RSI {p['jendela_rsi']} candle"
)


# ---------------------------------------------------------------------------
# BARIS 1: 4 KOTAK METRIK BESAR
# ---------------------------------------------------------------------------
def kartu(label: str, nilai: str, kecil: str = "", warna: str = "") -> str:
    """Membuat HTML satu kartu metrik."""
    return (f'<div class="kartu"><div class="kartu-label">{label}</div>'
            f'<div class="kartu-nilai {warna}">{nilai}</div>'
            f'<div class="kartu-kecil {warna or "abu"}">{kecil}</div></div>')


warna_profit = "hijau" if s["profit"] > 0 else ("merah" if s["profit"] < 0 else "")
k1, k2, k3, k4 = st.columns(4)
k1.markdown(kartu("💰 Saldo Akhir", f"{s['saldo_akhir']:,.2f} USDT",
                  f"Modal awal {s['modal_awal']:,.2f} USDT"), unsafe_allow_html=True)
k2.markdown(kartu("📈 Total Profit", f"{s['profit']:+,.2f} USDT",
                  f"{s['profit_persen']:+.2f}%", warna_profit), unsafe_allow_html=True)
k3.markdown(kartu("🎯 Win Rate", f"{s['win_rate']:.1f}%",
                  f"{s['menang']} menang / {s['kalah']} kalah dari {s['jumlah_trade']} trade",
                  "hijau" if s["win_rate"] > 55 else ""), unsafe_allow_html=True)
k4.markdown(kartu("📉 Max Drawdown", f"{s['max_drawdown']:.2f}%",
                  "Penurunan terbesar dari puncak equity", "merah" if s["max_drawdown"] < 0 else ""),
            unsafe_allow_html=True)

st.write("")

if s["jumlah_trade"] == 0:
    st.warning(
        f"Tidak ada trade di periode ini. Dari {s['jumlah_candle']:,} candle: RSI < {p['rsi_buy']:.0f} terjadi di "
        f"{s['candle_syarat_rsi']} candle, EMA9 cross ke atas EMA21 di {s['candle_syarat_cross']} candle, "
        f"volume naik 20% di {s['candle_syarat_volume']} candle, tapi ketiganya tidak pernah terjadi di candle yang sama. "
        "Coba naikkan 'Jendela RSI' di Pengaturan lanjutan atau naikkan RSI Buy."
    )

# ---------------------------------------------------------------------------
# BARIS 2: DUA GRAFIK PLOTLY
# ---------------------------------------------------------------------------
tema_grafik = dict(
    template="plotly_dark", paper_bgcolor="#161e2e", plot_bgcolor="#161e2e",
    margin=dict(l=10, r=10, t=70, b=10), height=440, font=dict(color="#e5e7eb"),
    legend=dict(orientation="h", y=1.0, x=1, xanchor="right", yanchor="bottom"),
)

g1, g2 = st.columns(2)
with g1:
    fig_eq = go.Figure()
    fig_eq.add_trace(go.Scatter(x=equity["waktu"], y=equity["equity"], mode="lines", name="Equity",
                                line=dict(color="#14F195", width=2), fill="tozeroy",
                                fillcolor="rgba(20,241,149,0.08)"))
    fig_eq.add_hline(y=s["modal_awal"], line_dash="dot", line_color="#9ca3af",
                     annotation_text="Modal awal", annotation_position="bottom right")
    rentang = max(equity["equity"].max() - equity["equity"].min(), s["modal_awal"] * 0.01)
    fig_eq.update_yaxes(range=[equity["equity"].min() - rentang * 0.3, equity["equity"].max() + rentang * 0.3],
                        title="USDT")
    fig_eq.update_layout(title="📊 Equity Curve (modal naik turun)", **tema_grafik)
    st.plotly_chart(fig_eq, width="stretch", theme=None)

with g2:
    harga = hasil["harga"]
    fig_h = go.Figure()
    fig_h.add_trace(go.Scattergl(x=harga["waktu"], y=harga["close"], mode="lines", name="Harga SOL",
                                 line=dict(color="#9945FF", width=1.4)))
    if not hasil["beli"].empty:
        fig_h.add_trace(go.Scatter(x=hasil["beli"]["waktu"], y=hasil["beli"]["harga"], mode="markers",
                                   name="BUY", marker=dict(color="#14F195", size=11, symbol="triangle-up",
                                                           line=dict(color="#0b0f1a", width=1))))
    if not hasil["jual"].empty:
        fig_h.add_trace(go.Scatter(x=hasil["jual"]["waktu"], y=hasil["jual"]["harga"], mode="markers",
                                   name="SELL", text=hasil["jual"]["alasan"],
                                   hovertemplate="SELL %{text}<br>%{y:.3f} USDT<extra></extra>",
                                   marker=dict(color="#ff5c7a", size=11, symbol="triangle-down",
                                               line=dict(color="#0b0f1a", width=1))))
    fig_h.update_yaxes(title="USDT")
    fig_h.update_layout(title="💹 Harga SOL/USDT + titik BUY / SELL", **tema_grafik)
    st.plotly_chart(fig_h, width="stretch", theme=None)

# ---------------------------------------------------------------------------
# BARIS 4: TABEL TRADE + DOWNLOAD CSV
# ---------------------------------------------------------------------------
st.markdown("### 📋 Daftar Semua Trade")
if trades.empty:
    st.info("Belum ada trade untuk ditampilkan.")
else:
    tabel = trades[["Tanggal", "Beli", "Jual", "Profit", "Profit %", "Alasan"]].copy()
    tabel["Tanggal"] = tabel["Tanggal"].dt.strftime("%Y-%m-%d %H:%M")

    def warnai_baris(baris):
        """Hijau jika profit, merah jika rugi."""
        warna = "rgba(20,241,149,0.18)" if baris["Profit"] > 0 else "rgba(255,92,122,0.18)"
        return [f"background-color: {warna}"] * len(baris)

    gaya = (tabel.style.apply(warnai_baris, axis=1)
            .format({"Beli": "{:.3f}", "Jual": "{:.3f}", "Profit": "{:+.4f} USDT", "Profit %": "{:+.2f}%"}))
    st.dataframe(gaya, width="stretch", hide_index=True, height=min(420, 38 + 35 * len(tabel)))
    st.caption("Alasan: TP1 = jual 50% di TP 1 • TP2 = jual sisa di TP 2 • SL = stop loss • "
               "BE = keluar di harga modal (trailing) • RSI = RSI > 72 • AKHIR = ditutup di akhir data. "
               "Profit sudah termasuk fee beli & jual.")

    csv = trades.copy()
    csv["Tanggal"] = csv["Tanggal"].dt.strftime("%Y-%m-%d %H:%M")
    csv["Waktu Jual Terakhir"] = csv["Waktu Jual Terakhir"].dt.strftime("%Y-%m-%d %H:%M")
    st.download_button("⬇️ Download CSV", data=csv.to_csv(index=False).encode("utf-8"),
                       file_name=f"sol_backtest_{hari}hari.csv", mime="text/csv")

# ---------------------------------------------------------------------------
# BARIS 5: KESIMPULAN OTOMATIS + 3 SARAN
# ---------------------------------------------------------------------------
st.markdown("### 🧠 Kesimpulan Otomatis")
kesimpulan = buat_kesimpulan(hasil)
if kesimpulan["layak"]:
    st.markdown('<div class="kotak-hijau">✅ LAYAK COBA LIVE MODAL KECIL</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="kotak-merah">❌ JANGAN LIVE DULU</div>', unsafe_allow_html=True)
st.caption(f"Syarat layak: Win Rate > 55% DAN Profit > 0. Hasil: Win Rate {s['win_rate']:.1f}%, "
           f"Profit {s['profit']:+.2f} USDT, dari {s['jumlah_trade']} trade.")

st.markdown("#### 💡 3 Saran Perbaikan TP/SL (dihitung dari hasil di atas)")
for nomor, isi in enumerate(kesimpulan["saran"], 1):
    st.markdown(f'<div class="saran"><b>{nomor}.</b> {isi}</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="disclaimer">⚠️ Disclaimer: hasil backtest BUKAN jaminan hasil di masa depan. '
    "Backtest memakai data masa lalu, tidak memperhitungkan slippage, dan memakai asumsi "
    "(mis. SL dianggap kena lebih dulu jika SL & TP terjadi di candle yang sama). "
    "Ini bukan saran keuangan.</div>",
    unsafe_allow_html=True,
)
