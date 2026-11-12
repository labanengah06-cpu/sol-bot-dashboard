# -*- coding: utf-8 -*-
"""
backtest.py - Mesin backtest SOL BOT DASHBOARD.

PENTING:
- File ini HANYA untuk BACKTEST (simulasi dengan data historis).
- TIDAK ADA live trading, TIDAK ADA API key, TIDAK ADA kode kirim order.
- Data yang dipakai adalah data ASLI candle SOL/USDT 5 menit dari Binance
  (lewat library ccxt). Tidak ada data palsu / data contoh.

Isi file:
1. Ambil data candle dari Binance (dengan pagination + fallback endpoint resmi).
2. Hitung indikator: RSI(14), EMA 9, EMA 21, rata-rata volume 20 candle.
3. Jalankan simulasi strategi (TP1, TP2, SL, trailing ke harga modal, exit RSI).
4. Hitung statistik: saldo akhir, profit, win rate, max drawdown.
5. Buat saran perbaikan TP/SL berdasarkan hasil backtest yang sebenarnya.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict

import ccxt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# KONSTANTA UMUM
# ---------------------------------------------------------------------------

SIMBOL = "SOL/USDT"          # Pasangan yang di-backtest
TIMEFRAME = "5m"             # Candle 5 menit
MENIT_PER_CANDLE = 5         # 5 menit per candle
MS_PER_CANDLE = MENIT_PER_CANDLE * 60 * 1000
CANDLE_PEMANASAN = 300       # Candle tambahan sebelum periode, supaya RSI/EMA sudah "stabil"
ZONA_WAKTU = "Asia/Tokyo"    # Zona waktu untuk tampilan tanggal (bisa diganti, mis. "Asia/Jakarta")

# Endpoint data pasar publik RESMI milik Binance (hanya data pasar, tanpa login).
# Dipakai sebagai cadangan jika api.binance.com menolak akses (mis. HTTP 451 / blokir wilayah).
# Isinya tetap data asli Binance yang sama persis, bukan data buatan.
URL_CADANGAN_BINANCE = "https://data-api.binance.vision/api/v3"


# ---------------------------------------------------------------------------
# 1. AMBIL DATA DARI BINANCE
# ---------------------------------------------------------------------------

def _buat_exchange(pakai_cadangan: bool = False) -> ccxt.binance:
    """Membuat objek ccxt Binance khusus data publik (tanpa API key)."""
    exchange = ccxt.binance({
        "enableRateLimit": True,          # Patuhi batas request Binance
        "timeout": 20000,                 # Batas waktu 20 detik per request
        "options": {
            "defaultType": "spot",        # Pasar spot saja
            "fetchMarkets": ["spot"],     # Hanya muat daftar pasar spot (lebih cepat)
        },
    })
    if pakai_cadangan:
        # Arahkan semua request publik ke endpoint data resmi Binance.
        exchange.urls["api"]["public"] = URL_CADANGAN_BINANCE
    return exchange


def _ambil_dengan_pagination(exchange: ccxt.binance, sejak_ms: int, sampai_ms: int) -> list:
    """
    Mengambil candle sedikit demi sedikit (maks 1000 candle per request)
    dari waktu `sejak_ms` sampai `sampai_ms`.
    """
    semua = []
    kursor = sejak_ms
    while kursor < sampai_ms:
        potongan = exchange.fetch_ohlcv(SIMBOL, TIMEFRAME, since=kursor, limit=1000)
        if not potongan:
            break
        semua.extend(potongan)
        terakhir = potongan[-1][0]
        if terakhir < kursor:      # Pengaman agar tidak berputar selamanya
            break
        kursor = terakhir + MS_PER_CANDLE
        if len(potongan) < 1000:   # Sudah sampai data terbaru
            break
    return semua


def ambil_data_binance(hari: int) -> tuple[pd.DataFrame, str]:
    """
    Mengambil candle SOL/USDT 5 menit untuk `hari` terakhir (+ candle pemanasan).

    Mengembalikan:
        (DataFrame candle, keterangan sumber data)

    Urutan sumber:
        1) api.binance.com (endpoint utama Binance lewat ccxt)
        2) data-api.binance.vision (endpoint data publik resmi Binance) jika no.1 gagal
    Jika keduanya gagal, akan muncul error. Kode ini TIDAK PERNAH membuat data palsu.
    """
    sekarang_ms = int(time.time() * 1000)
    sejak_ms = sekarang_ms - hari * 24 * 60 * 60 * 1000 - CANDLE_PEMANASAN * MS_PER_CANDLE

    pesan_error = []
    for pakai_cadangan, nama in [
        (False, "Binance (api.binance.com via ccxt)"),
        (True, "Binance data publik resmi (data-api.binance.vision via ccxt)"),
    ]:
        try:
            exchange = _buat_exchange(pakai_cadangan)
            mentah = _ambil_dengan_pagination(exchange, sejak_ms, sekarang_ms)
            if not mentah:
                raise RuntimeError("Binance tidak mengirim data candle.")
            df = pd.DataFrame(mentah, columns=["timestamp", "open", "high", "low", "close", "volume"])
            df = df.drop_duplicates("timestamp").sort_values("timestamp").reset_index(drop=True)
            # Buang candle yang BELUM selesai (candle yang sedang berjalan sekarang).
            df = df[df["timestamp"] + MS_PER_CANDLE <= sekarang_ms].reset_index(drop=True)
            df["waktu"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_convert(ZONA_WAKTU)
            df.attrs["mulai_periode_ms"] = sekarang_ms - hari * 24 * 60 * 60 * 1000
            return df, nama
        except Exception as e:  # noqa: BLE001 - simpan error lalu coba sumber berikutnya
            pesan_error.append(f"{nama}: {type(e).__name__}: {e}")

    raise RuntimeError("Gagal mengambil data asli dari Binance.\n" + "\n".join(pesan_error))


# ---------------------------------------------------------------------------
# 2. INDIKATOR
# ---------------------------------------------------------------------------

def hitung_rsi(close: pd.Series, periode: int = 14) -> pd.Series:
    """RSI metode Wilder (sama seperti di TradingView/Binance)."""
    selisih = close.diff()
    naik = selisih.clip(lower=0)
    turun = -selisih.clip(upper=0)
    rata_naik = naik.ewm(alpha=1 / periode, adjust=False, min_periods=periode).mean()
    rata_turun = turun.ewm(alpha=1 / periode, adjust=False, min_periods=periode).mean()
    rs = rata_naik / rata_turun
    rsi = 100 - (100 / (1 + rs))
    # Jika tidak ada penurunan sama sekali, RSI = 100
    rsi = rsi.where(rata_turun != 0, 100.0)
    return rsi


def tambah_indikator(df: pd.DataFrame, rsi_buy: float, jendela_rsi: int = 1,
                     pengali_volume: float = 1.2) -> pd.DataFrame:
    """
    Menambahkan kolom indikator dan sinyal BUY ke DataFrame.

    Definisi sinyal BUY (dicek saat candle SELESAI / close):
      a) RSI(14) < rsi_buy.
         `jendela_rsi` = 1 artinya RSI harus < rsi_buy di candle yang SAMA (sesuai aturan asli).
         Jika diisi N > 1, cukup RSI < rsi_buy di salah satu dari N candle terakhir.
      b) EMA 9 cross ke atas EMA 21: candle sebelumnya EMA9 <= EMA21, candle ini EMA9 > EMA21.
      c) "Volume naik 20%": volume candle ini >= 1.2 x rata-rata volume 20 candle SEBELUMNYA
         (candle ini tidak ikut dihitung dalam rata-rata, supaya adil).
    """
    df = df.copy()
    df["rsi"] = hitung_rsi(df["close"], 14)
    df["ema9"] = df["close"].ewm(span=9, adjust=False).mean()
    df["ema21"] = df["close"].ewm(span=21, adjust=False).mean()
    df["vol_rata20"] = df["volume"].shift(1).rolling(20).mean()

    syarat_rsi = (df["rsi"] < rsi_buy).astype(int).rolling(max(1, int(jendela_rsi)), min_periods=1).max() == 1
    syarat_cross = (df["ema9"] > df["ema21"]) & (df["ema9"].shift(1) <= df["ema21"].shift(1))
    syarat_volume = df["volume"] >= pengali_volume * df["vol_rata20"]

    df["syarat_rsi"] = syarat_rsi
    df["syarat_cross"] = syarat_cross
    df["syarat_volume"] = syarat_volume
    df["sinyal_beli"] = syarat_rsi & syarat_cross & syarat_volume
    return df


# ---------------------------------------------------------------------------
# 3. SIMULASI STRATEGI
# ---------------------------------------------------------------------------

@dataclass
class Pengaturan:
    """Semua parameter strategi (bisa diubah dari sidebar dashboard)."""
    modal_awal: float = 100.0      # USDT
    tp1: float = 2.5               # % profit untuk TP1 (jual 50%)
    tp2: float = 5.0               # % profit untuk TP2 (jual sisa 50%)
    sl: float = 1.5                # % rugi untuk Stop Loss (jual semua)
    pemicu_trailing: float = 1.5   # % profit yang memindahkan SL ke harga modal
    rsi_buy: float = 35.0          # Batas RSI untuk BUY
    rsi_jual: float = 72.0         # Jual semua jika RSI di atas ini
    persen_per_trade: float = 10.0 # % dari saldo kas yang dipakai per trade
    maks_posisi: int = 3           # Maksimal posisi terbuka bersamaan
    fee: float = 0.1               # % fee setiap BUY dan setiap SELL
    jendela_rsi: int = 1           # 1 = RSI harus < batas di candle yang sama (aturan asli)
    pengali_volume: float = 1.2    # 1.2 = volume naik 20% dari rata-rata 20 candle


@dataclass
class Posisi:
    """Satu posisi yang sedang terbuka."""
    id: int
    waktu_beli: pd.Timestamp
    harga_beli: float
    qty_awal: float
    qty_sisa: float
    biaya_total: float             # USDT yang keluar dari kas (termasuk fee beli)
    hasil_jual: float = 0.0        # USDT bersih yang masuk dari penjualan (sudah dipotong fee)
    tp1_kena: bool = False
    sl_ke_modal: bool = False      # True jika trailing aktif (SL = harga modal)
    harga_tertinggi: float = 0.0   # Untuk menghitung MFE (kenaikan maksimal)
    harga_terendah: float = 0.0    # Untuk menghitung MAE (penurunan maksimal)
    alasan: list = field(default_factory=list)
    jual: list = field(default_factory=list)   # daftar (waktu, harga, qty)


def jalankan_backtest(df_mentah: pd.DataFrame, p: Pengaturan) -> dict:
    """
    Menjalankan simulasi strategi di atas data candle asli.

    Aturan eksekusi (dibuat realistis dan konservatif):
    - Sinyal BUY dihitung saat candle ditutup. Pembelian dilakukan di harga OPEN
      candle berikutnya (tidak bisa beli di harga close yang baru diketahui belakangan).
    - TP dan SL dicek memakai HIGH dan LOW candle (bisa kena di tengah candle).
    - Jika dalam SATU candle SL dan TP sama-sama mungkin kena, kita anggap SL kena DULUAN
      (asumsi konservatif / paling merugikan), karena data 5 menit tidak memberi tahu
      mana yang terjadi lebih dulu.
    - Trailing: begitu HIGH candle mencapai +pemicu_trailing%, mulai candle BERIKUTNYA
      SL dipindah ke harga modal (breakeven). Alasan keluar menjadi "BE".
    - Exit RSI: jika RSI saat close > rsi_jual, sisa posisi dijual di harga close.
    - Fee dipotong di setiap BUY dan setiap SELL.
    - Posisi yang masih terbuka di akhir data ditutup di harga close terakhir (alasan "AKHIR").
    """
    df = tambah_indikator(df_mentah, p.rsi_buy, p.jendela_rsi, p.pengali_volume)
    mulai_ms = df_mentah.attrs.get("mulai_periode_ms", int(df["timestamp"].iloc[0]))
    idx_mulai = int(np.searchsorted(df["timestamp"].values, mulai_ms))
    idx_mulai = max(idx_mulai, 1)

    fee = p.fee / 100.0
    tp1 = p.tp1 / 100.0
    tp2 = max(p.tp2, p.tp1) / 100.0       # TP2 tidak boleh lebih kecil dari TP1
    sl = p.sl / 100.0
    pemicu = p.pemicu_trailing / 100.0

    kas = p.modal_awal
    posisi_buka: list[Posisi] = []
    trade_selesai: list[dict] = []
    titik_beli, titik_jual = [], []
    kurva_equity = []
    nomor = 0
    sinyal_menunggu = False
    sinyal_ditolak_penuh = 0               # sinyal yang dilewati karena sudah 3 posisi
    jumlah_sinyal = 0

    o = df["open"].values; h = df["high"].values; l = df["low"].values
    c = df["close"].values; rsi = df["rsi"].values; waktu = df["waktu"]
    sinyal = df["sinyal_beli"].values

    def jual(pos: Posisi, i: int, harga: float, qty: float, alasan: str):
        """Menjual sebagian/semua posisi dan memasukkan uang bersih ke kas."""
        nonlocal kas
        bersih = qty * harga * (1 - fee)
        kas += bersih
        pos.hasil_jual += bersih
        pos.qty_sisa -= qty
        if pos.qty_sisa < 1e-12:
            pos.qty_sisa = 0.0
        pos.alasan.append(alasan)
        pos.jual.append((waktu.iloc[i], harga, qty))
        titik_jual.append({"waktu": waktu.iloc[i], "harga": harga, "alasan": alasan})

    def tutup(pos: Posisi):
        """Memindahkan posisi yang sudah habis ke daftar trade selesai."""
        profit = pos.hasil_jual - pos.biaya_total
        qty_total = sum(q for _, _, q in pos.jual)
        harga_jual_rata = sum(hg * q for _, hg, q in pos.jual) / qty_total if qty_total else 0
        trade_selesai.append({
            "No": pos.id,
            "Tanggal": pos.waktu_beli,
            "Waktu Jual Terakhir": pos.jual[-1][0],
            "Beli": pos.harga_beli,
            "Jual": harga_jual_rata,
            "Modal (USDT)": pos.biaya_total,
            "Profit": profit,
            "Profit %": profit / pos.biaya_total * 100,
            "Alasan": "+".join(pos.alasan),
            "Alasan Akhir": pos.alasan[-1],
            "MFE %": (pos.harga_tertinggi / pos.harga_beli - 1) * 100,
            "MAE %": (pos.harga_terendah / pos.harga_beli - 1) * 100,
        })

    for i in range(idx_mulai, len(df)):
        # --- (a) Eksekusi BUY di harga OPEN dari sinyal candle sebelumnya ---
        if sinyal_menunggu:
            if len(posisi_buka) < p.maks_posisi and kas > 0:
                uang = kas * p.persen_per_trade / 100.0      # 10% dari saldo kas saat ini
                qty = uang * (1 - fee) / o[i]                # fee beli dipotong dari koin yang didapat
                nomor += 1
                kas -= uang
                posisi_buka.append(Posisi(id=nomor, waktu_beli=waktu.iloc[i], harga_beli=o[i],
                                          qty_awal=qty, qty_sisa=qty, biaya_total=uang,
                                          harga_tertinggi=o[i], harga_terendah=o[i]))
                titik_beli.append({"waktu": waktu.iloc[i], "harga": o[i]})
            else:
                sinyal_ditolak_penuh += 1
            sinyal_menunggu = False

        # --- (b) Cek exit setiap posisi terbuka ---
        for pos in list(posisi_buka):
            pos.harga_tertinggi = max(pos.harga_tertinggi, h[i])
            pos.harga_terendah = min(pos.harga_terendah, l[i])
            harga_sl = pos.harga_beli if pos.sl_ke_modal else pos.harga_beli * (1 - sl)

            # 1) SL dicek PALING DULU (konservatif)
            if l[i] <= harga_sl:
                # Jika candle dibuka sudah di bawah SL (gap), jual di harga open
                harga_isi = min(harga_sl, o[i]) if i > 0 else harga_sl
                jual(pos, i, harga_isi, pos.qty_sisa, "BE" if pos.sl_ke_modal else "SL")
            else:
                # 2) TP1: jual 50% dari jumlah awal
                if not pos.tp1_kena and h[i] >= pos.harga_beli * (1 + tp1):
                    jual(pos, i, pos.harga_beli * (1 + tp1), pos.qty_awal * 0.5, "TP1")
                    pos.tp1_kena = True
                # 3) TP2: jual sisa
                if pos.tp1_kena and pos.qty_sisa > 0 and h[i] >= pos.harga_beli * (1 + tp2):
                    jual(pos, i, pos.harga_beli * (1 + tp2), pos.qty_sisa, "TP2")
                # 4) Exit RSI di harga close
                if pos.qty_sisa > 0 and not np.isnan(rsi[i]) and rsi[i] > p.rsi_jual:
                    jual(pos, i, c[i], pos.qty_sisa, "RSI")
                # 5) Aktifkan trailing (berlaku mulai candle berikutnya)
                if pos.qty_sisa > 0 and h[i] >= pos.harga_beli * (1 + pemicu):
                    pos.sl_ke_modal = True

            if pos.qty_sisa <= 0:
                tutup(pos)
                posisi_buka.remove(pos)

        # --- (c) Sinyal BUY baru di close candle ini (dieksekusi candle berikutnya) ---
        if sinyal[i] and i < len(df) - 1:
            jumlah_sinyal += 1
            sinyal_menunggu = True

        # --- (d) Catat equity = kas + nilai pasar posisi terbuka ---
        nilai_posisi = sum(pos.qty_sisa * c[i] for pos in posisi_buka)
        kurva_equity.append({"waktu": waktu.iloc[i], "equity": kas + nilai_posisi})

    # --- Tutup posisi yang tersisa di akhir data ---
    i_akhir = len(df) - 1
    for pos in list(posisi_buka):
        jual(pos, i_akhir, c[i_akhir], pos.qty_sisa, "AKHIR")
        tutup(pos)
        posisi_buka.remove(pos)
    if kurva_equity:
        kurva_equity[-1]["equity"] = kas

    equity = pd.DataFrame(kurva_equity)
    trades = pd.DataFrame(trade_selesai)
    statistik = hitung_statistik(equity, trades, p.modal_awal, kas)
    statistik.update({
        "jumlah_sinyal": jumlah_sinyal,
        "sinyal_dilewati_posisi_penuh": sinyal_ditolak_penuh,
        "jumlah_candle": len(df) - idx_mulai,
        "candle_syarat_rsi": int(df["syarat_rsi"].iloc[idx_mulai:].sum()),
        "candle_syarat_cross": int(df["syarat_cross"].iloc[idx_mulai:].sum()),
        "candle_syarat_volume": int(df["syarat_volume"].iloc[idx_mulai:].sum()),
        "mulai": df["waktu"].iloc[idx_mulai],
        "selesai": df["waktu"].iloc[-1],
    })
    return {
        "statistik": statistik,
        "equity": equity,
        "trades": trades,
        "beli": pd.DataFrame(titik_beli),
        "jual": pd.DataFrame(titik_jual),
        "harga": df.iloc[idx_mulai:][["waktu", "open", "high", "low", "close", "volume"]].reset_index(drop=True),
        "pengaturan": asdict(p),
    }


# ---------------------------------------------------------------------------
# 4. STATISTIK
# ---------------------------------------------------------------------------

def hitung_statistik(equity: pd.DataFrame, trades: pd.DataFrame, modal_awal: float, saldo_akhir: float) -> dict:
    """Menghitung saldo akhir, profit, win rate, dan max drawdown."""
    profit = saldo_akhir - modal_awal
    jumlah = len(trades)
    menang = int((trades["Profit"] > 0).sum()) if jumlah else 0
    win_rate = menang / jumlah * 100 if jumlah else 0.0

    max_dd = 0.0
    if not equity.empty:
        puncak = equity["equity"].cummax()
        dd = (equity["equity"] - puncak) / puncak * 100
        max_dd = float(dd.min())          # angka negatif, mis. -3.2 (%)

    rata_menang = float(trades.loc[trades["Profit"] > 0, "Profit"].mean()) if menang else 0.0
    rata_kalah = float(trades.loc[trades["Profit"] <= 0, "Profit"].mean()) if jumlah - menang else 0.0
    return {
        "modal_awal": modal_awal,
        "saldo_akhir": saldo_akhir,
        "profit": profit,
        "profit_persen": profit / modal_awal * 100 if modal_awal else 0.0,
        "jumlah_trade": jumlah,
        "menang": menang,
        "kalah": jumlah - menang,
        "win_rate": win_rate,
        "max_drawdown": max_dd,
        "rata_menang": rata_menang,
        "rata_kalah": rata_kalah,
    }


# ---------------------------------------------------------------------------
# 5. KESIMPULAN & SARAN (berdasarkan hasil nyata, bukan saran umum)
# ---------------------------------------------------------------------------

def buat_kesimpulan(hasil: dict) -> dict:
    """
    Menentukan kesimpulan (layak / tidak) dan membuat 3 saran perbaikan TP/SL
    yang dihitung dari hasil backtest: distribusi alasan keluar, rata-rata
    menang/kalah, serta MFE (kenaikan maksimal) dan MAE (penurunan maksimal) tiap trade.
    """
    s = hasil["statistik"]
    p = hasil["pengaturan"]
    t = hasil["trades"]
    layak = s["win_rate"] > 55 and s["profit"] > 0
    saran: list[str] = []

    if t.empty:
        saran = [
            f"Tidak ada trade sama sekali dari {s['jumlah_sinyal']} sinyal. Dari {s['jumlah_candle']} candle, "
            f"RSI < {p['rsi_buy']:.0f} terjadi di {s['candle_syarat_rsi']} candle, EMA9 cross ke atas EMA21 "
            f"di {s['candle_syarat_cross']} candle, dan volume naik 20% di {s['candle_syarat_volume']} candle. "
            "Ketiganya jarang terjadi bersamaan, jadi coba naikkan RSI Buy (mis. 40).",
            "Coba isi 'Jendela RSI' lebih dari 1 candle (Pengaturan lanjutan), supaya RSI rendah beberapa "
            "candle sebelum cross tetap dihitung.",
            "Pilih periode 90 hari agar sampel trade lebih banyak sebelum menilai TP/SL.",
        ]
        return {"layak": layak, "saran": saran}

    n = len(t)
    akhir = t["Alasan Akhir"].value_counts()
    alasan_semua = t["Alasan"]
    n_sl = int(akhir.get("SL", 0))
    n_be = int(akhir.get("BE", 0))
    n_tp2 = int(akhir.get("TP2", 0))
    n_rsi = int(akhir.get("RSI", 0))
    n_tp1 = int(alasan_semua.str.contains("TP1").sum())
    mfe = t["MFE %"]
    mae = t["MAE %"]

    # Saran 1: tentang Stop Loss
    if n_sl:
        sl_trades = t[t["Alasan Akhir"] == "SL"]
        sempat_naik = int((sl_trades["MFE %"] >= p["pemicu_trailing"] * 0.66).sum())
        saran.append(
            f"SL: {n_sl} dari {n} trade ({n_sl / n * 100:.0f}%) kena Stop Loss -{p['sl']}%. "
            f"{sempat_naik} di antaranya sempat naik â¥ +{p['pemicu_trailing'] * 0.66:.1f}% dulu sebelum jatuh. "
            + ("Banyak trade sempat profit lalu berbalik: coba turunkan pemicu trailing / TP1 sedikit agar SL lebih cepat pindah ke modal."
               if sempat_naik >= max(1, n_sl // 3) else
               f"Median penurunan terdalam (MAE) semua trade {mae.median():.2f}%. "
               + (f"Coba SL sedikit lebih longgar (mis. {min(3.0, p['sl'] + 0.5):.1f}%) agar tidak terkena goyangan kecil."
                  if mae.median() > -p["sl"] else
                  "Harga memang sering turun jauh setelah entry: filter entry lebih ketat (RSI Buy lebih rendah) lebih berguna daripada melonggarkan SL."))
        )
    else:
        saran.append(f"SL: tidak ada trade yang kena Stop Loss -{p['sl']}%. Median MAE {mae.median():.2f}%, "
                     f"jadi SL bisa sedikit diperketat (mis. {max(0.5, p['sl'] - 0.5):.1f}%) untuk membatasi rugi.")

    # Saran 2: tentang TP1
    pct_mfe_tp1 = (mfe >= p["tp1"]).mean() * 100
    saran.append(
        f"TP1: {n_tp1} dari {n} trade ({n_tp1 / n * 100:.0f}%) mencapai TP1 +{p['tp1']}%. "
        f"Median kenaikan maksimal (MFE) per trade {mfe.median():.2f}%. "
        + (f"TP1 jarang tercapai, coba turunkan ke sekitar {max(1.0, round(mfe.quantile(0.5) * 2) / 2):.1f}% supaya profit lebih sering dikunci."
           if pct_mfe_tp1 < 40 else
           "TP1 cukup sering tercapai, nilai ini sudah masuk akal.")
    )

    # Saran 3: tentang TP2 dan exit lain
    if n_tp1:
        sisa = n_tp1 - n_tp2
        saran.append(
            f"TP2: dari {n_tp1} trade yang kena TP1, {n_tp2} lanjut ke TP2 +{max(p['tp2'], p['tp1'])}%, "
            f"{n_be} ditutup di harga modal (BE), {n_rsi} lewat exit RSI. "
            + (f"Sebagian besar tidak sampai TP2: coba turunkan TP2 ke sekitar {max(3.0, round(mfe[t['Alasan'].str.contains('TP1')].median() * 2) / 2):.1f}%."
               if sisa > n_tp2 else
               "TP2 sering tercapai, coba naikkan TP2 sedikit untuk mengejar profit lebih besar.")
        )
    else:
        rr = abs(s["rata_menang"] / s["rata_kalah"]) if s["rata_kalah"] else 0
        saran.append(
            f"Rata-rata menang {s['rata_menang']:.3f} USDT vs rata-rata kalah {s['rata_kalah']:.3f} USDT "
            f"(rasio {rr:.2f}). Belum ada trade yang mencapai TP1, jadi TP2 belum teruji; "
            "fokus dulu ke TP1 lebih dekat atau entry lebih selektif."
        )

    return {"layak": layak, "saran": saran[:3]}


# ---------------------------------------------------------------------------
# Jalankan langsung dari terminal (tanpa dashboard) untuk tes cepat:
#   python backtest.py 30
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    hari = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    jendela = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    data, sumber = ambil_data_binance(hari)
    hasil = jalankan_backtest(data, Pengaturan(jendela_rsi=jendela))
    s = hasil["statistik"]
    print(f"Sumber data   : {sumber}")
    print(f"Periode       : {s['mulai']} s/d {s['selesai']} ({s['jumlah_candle']} candle)")
    print(f"Sinyal BUY    : {s['jumlah_sinyal']} (dilewati karena 3 posisi penuh: {s['sinyal_dilewati_posisi_penuh']})")
    print(f"Jumlah trade  : {s['jumlah_trade']} (menang {s['menang']}, kalah {s['kalah']})")
    print(f"Win rate      : {s['win_rate']:.1f}%")
    print(f"Saldo akhir   : {s['saldo_akhir']:.4f} USDT")
    print(f"Total profit  : {s['profit']:+.4f} USDT ({s['profit_persen']:+.2f}%)")
    print(f"Max drawdown  : {s['max_drawdown']:.2f}%")
    if not hasil["trades"].empty:
        print(hasil["trades"][["No", "Tanggal", "Beli", "Jual", "Profit", "Alasan"]].to_string(index=False))
    k = buat_kesimpulan(hasil)
    print("Kesimpulan    :", "LAYAK COBA LIVE MODAL KECIL" if k["layak"] else "JANGAN LIVE DULU")
    for nomor_saran, isi in enumerate(k["saran"], 1):
        print(f"  Saran {nomor_saran}: {isi}")
