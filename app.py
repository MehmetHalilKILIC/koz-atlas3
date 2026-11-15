"""
KÖZ Atlas — MODIS & VIIRS Termal Anomali ve Aktif Yangın Harmonizasyon Platformu
2026 NASA Space Apps Challenge · Harmonization of MODIS and VIIRS Hot Spots · Takım: Kirvecanlar

Çalıştırma:  streamlit run app.py
"""
from __future__ import annotations

import io
import json
from datetime import date, timedelta
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from folium.plugins import Fullscreen, MiniMap
from streamlit_folium import st_folium

import harmonizer as hz

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------
APP_URL = "https://koz-atlas-gbqjscepvmqcaygzbjlxhq.streamlit.app/"
REPO_URL = "https://github.com/MehmetHalilKILIC/koz-atlas"
CHALLENGE_URL = "https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/"
FIRMS_GUIDE_URL = "https://github.com/nasa/spaceapps/discussions/2016"
FIRMS_KEY_URL = "https://firms.modaps.eosdis.nasa.gov/api/map_key/"

BG, CARD, EMBER, AMBER = "#0B0F19", "#1E293B", "#FF5722", "#FF9800"
C_MODIS, C_VIIRS, C_KOZ, C_STATIC = "#38BDF8", "#FACC15", "#FF5722", "#A855F7"
MONTHS_TR = ["Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
CONF_OPTIONS = {"low (tümü)": 0, "nominal": 1, "high": 2}
MAP_LAYER_CAP = 800
CUSTOM_AOI = "Özel Koordinat Kutusu"
DARK_TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"
SAT_TILES = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"

st.set_page_config(page_title="KÖZ Atlas — MODIS & VIIRS Harmonizasyonu", page_icon="🔥", layout="wide")

st.markdown(
    f"""
<style>
.stApp {{ background: radial-gradient(ellipse at top, #131a2e 0%, {BG} 55%); }}
section[data-testid="stSidebar"] {{ background: #0E1424; border-right: 1px solid #1f2a44; }}
.block-container {{ padding-top: 1.6rem; }}
.koz-title {{ font-size: 2.3rem; font-weight: 800; letter-spacing: .5px; margin: 0;
    background: linear-gradient(90deg, {EMBER}, {AMBER}); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
.koz-sub {{ color: #94A3B8; font-size: .95rem; margin-top: .1rem; }}
.koz-sub a {{ color: {AMBER}; text-decoration: none; }}
.kpi {{ background: rgba(30,41,59,.72); border: 1px solid rgba(255,87,34,.25); border-radius: 14px;
    padding: 14px 16px; height: 100%; backdrop-filter: blur(6px); }}
.kpi .lbl {{ color: #94A3B8; font-size: .78rem; text-transform: uppercase; letter-spacing: .6px; }}
.kpi .val {{ color: #F8FAFC; font-size: 1.75rem; font-weight: 700; line-height: 1.25; }}
.kpi .det {{ color: {AMBER}; font-size: .8rem; }}
.note {{ background: rgba(30,41,59,.6); border-left: 3px solid {EMBER}; border-radius: 6px; padding: 10px 14px;
    color: #CBD5E1; font-size: .88rem; }}
.stTabs [data-baseweb="tab"] {{ font-weight: 600; }}
.stTabs [aria-selected="true"] {{ color: {EMBER} !important; }}
</style>
""",
    unsafe_allow_html=True,
)


def kpi(col, label: str, value: str, detail: str = "") -> None:
    col.markdown(
        f'<div class="kpi"><div class="lbl">{label}</div><div class="val">{value}</div><div class="det">{detail}</div></div>',
        unsafe_allow_html=True,
    )


def style_fig(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(30,41,59,.35)",
        height=height,
        margin=dict(l=10, r=10, t=60, b=10),
        legend=dict(orientation="h", yanchor="top", y=-0.18, x=0),
        font=dict(color="#E2E8F0"),
    )
    return fig


def fmt_int(x) -> str:
    return f"{int(round(x)):,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Veri yükleme (önbellekli)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Demo verisi yükleniyor…")
def load_synthetic(y0: int, y1: int, seed: int = 42) -> pd.DataFrame:
    p = Path(__file__).resolve().parent / "data" / "demo_firms.parquet"
    if p.exists() and seed == 42:
        df = pd.read_parquet(p)
        return df[(df["acq_date"].dt.year >= y0) & (df["acq_date"].dt.year <= y1)].reset_index(drop=True)
    return hz.standardize_firms(hz.SyntheticFIRMSGenerator(seed=seed).generate(y0, y1))


@st.cache_data(show_spinner="NASA FIRMS Area API'den veri çekiliyor…", ttl=3600)
def load_firms(map_key: str, sources: tuple, bbox: tuple, d0: date, d1: date) -> tuple[pd.DataFrame, list]:
    raw, errors = hz.FIRMSClient(map_key).fetch(list(sources), bbox, d0, d1)
    return hz.standardize_firms(raw), errors


@st.cache_data(show_spinner="CSV okunuyor…")
def load_csv(blobs: tuple) -> pd.DataFrame:
    frames = [pd.read_csv(io.BytesIO(b)) for b in blobs]
    return hz.standardize_firms(pd.concat(frames, ignore_index=True))


@st.cache_data(show_spinner="Harmonizasyon boru hattı çalışıyor (Aşama 1–4)…")
def run_cached(std: pd.DataFrame, bbox: tuple, d0: date, d1: date, params: dict) -> hz.PipelineResult:
    data = hz.filter_dates(hz.filter_aoi(std, bbox), d0, d1) if not std.empty else std
    return hz.run_pipeline(data, hz.PipelineParams(**params))


# ---------------------------------------------------------------------------
# Kenar çubuğu
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### 🔥 KÖZ Atlas Kontrol Paneli")

    st.markdown("**1 · Odak bölge (AOI)**")
    aoi_name = st.selectbox("Bölge", list(hz.AOI_PRESETS) + [CUSTOM_AOI], index=0, label_visibility="collapsed")
    if aoi_name == CUSTOM_AOI:
        c1, c2 = st.columns(2)
        west = c1.number_input("Batı (lon)", value=40.0, format="%.3f")
        east = c2.number_input("Doğu (lon)", value=42.5, format="%.3f")
        south = c1.number_input("Güney (lat)", value=37.0, format="%.3f")
        north = c2.number_input("Kuzey (lat)", value=38.5, format="%.3f")
        bbox = (min(west, east), min(south, north), max(west, east), max(south, north))
    else:
        bbox = hz.AOI_PRESETS[aoi_name]
    st.caption(f"Kutu (W,S,E,N): `{hz.FIRMSClient.area_string(bbox)}`")

    st.markdown("**2 · Veri kaynağı**")
    mode = st.radio(
        "Veri kaynağı",
        ["Yerleşik sentetik demo (anahtarsız)", "Canlı NASA FIRMS Area API", "FIRMS CSV dosyası yükle"],
        label_visibility="collapsed",
    )

    std = pd.DataFrame()
    fetch_errors: list[str] = []
    if mode.startswith("Yerleşik"):
        y0, y1 = st.slider("Simülasyon yılları", 2000, 2025, (2000, 2025))
        std = load_synthetic(y0, y1)
    elif mode.startswith("Canlı"):
        map_key = st.text_input("FIRMS MAP_KEY", type="password", help="Ücretsiz anahtar: " + FIRMS_KEY_URL)
        sources = st.multiselect("FIRMS kaynakları", hz.FIRMS_SOURCES, default=["MODIS_NRT", "VIIRS_NOAA20_NRT", "VIIRS_SNPP_NRT"])
        today = date.today()
        rng_api = st.date_input("API tarih aralığı", (today - timedelta(days=9), today), max_value=today)
        d_api = rng_api if isinstance(rng_api, tuple) and len(rng_api) == 2 else (rng_api, rng_api)
        n_req = sum(len(hz.FIRMSClient("x").request_plan(s, bbox, d_api[0], d_api[1])) for s in sources)
        st.caption(f"Plan: {n_req} istek (NASA Area API en fazla 5 günlük parçalar kabul eder). NRT kaynakları son günleri kapsar.")
        if st.button("Veriyi çek", type="primary", disabled=not (map_key and sources)):
            st.session_state["api_args"] = (map_key, tuple(sources), bbox, d_api[0], d_api[1])
        if "api_args" in st.session_state:
            std, fetch_errors = load_firms(*st.session_state["api_args"])
    else:
        files = st.file_uploader("FIRMS CSV (MODIS ve/veya VIIRS)", type=["csv"], accept_multiple_files=True)
        if files:
            std = load_csv(tuple(f.getvalue() for f in files))

    if not std.empty:
        dmin, dmax = std["acq_date"].min().date(), std["acq_date"].max().date()
        dr = st.date_input("Analiz tarih aralığı", (dmin, dmax), min_value=dmin, max_value=dmax)
        d0, d1 = dr if isinstance(dr, tuple) and len(dr) == 2 else (dmin, dmax)
    else:
        d0 = d1 = date.today()

    st.markdown("**3 · Harmonizasyon parametreleri**")
    distance_km = st.slider("Mekansal eşik Δd (km)", 0.5, 2.5, 1.2, 0.1, help="MODIS ~1 km ayak izi")
    window_min = st.slider("Zamansal pencere ±Δt (dakika)", 10, 180, 60, 5)
    conf_label = st.select_slider("Minimum güven eşiği", list(CONF_OPTIONS), value="nominal")
    hide_static = st.toggle("Statik endüstriyel kaynakları (gaz bacalarını) gizle", value=True)

    with st.expander("Gelişmiş: kalibrasyon ve statik kaynak"):
        cal_method = st.selectbox(
            "FRP kalibrasyon modeli",
            ["loglog", "linear", "identity"],
            format_func={"loglog": "Güç yasası (log-log EKK)", "linear": "Doğrusal (orijinden)", "identity": "Kalibrasyonsuz"}.get,
        )
        static_days = st.number_input("Statik: yıl içi min. farklı gün", 2, 60, 5)
        static_months = st.number_input("Statik: yıl içi min. farklı ay", 1, 12, 4)
        static_cell = st.slider("Statik grid hücresi (km)", 0.5, 2.0, 1.0, 0.1)

    params = dict(
        distance_km=float(distance_km),
        window_min=float(window_min),
        min_conf_level=CONF_OPTIONS[conf_label],
        calibration_method=cal_method,
        static_cell_km=float(static_cell),
        static_min_days=int(static_days),
        static_min_months=int(static_months),
    )

# ---------------------------------------------------------------------------
# Başlık
# ---------------------------------------------------------------------------
st.markdown('<p class="koz-title">KÖZ Atlas</p>', unsafe_allow_html=True)
st.markdown(
    f'<p class="koz-sub">MODIS &amp; VIIRS Termal Anomali ve Aktif Yangın Harmonizasyon Platformu · '
    f'<a href="{CHALLENGE_URL}" target="_blank">2026 NASA Space Apps Challenge — Harmonization of MODIS and VIIRS Hot Spots</a> · '
    f'Takım <b>Kirvecanlar</b> · <a href="{REPO_URL}" target="_blank">GitHub</a></p>',
    unsafe_allow_html=True,
)

if mode.startswith("Yerleşik"):
    st.warning(
        "Demo modu: Gösterilen veriler FIRMS CSV şemasında üretilmiş **sentetik simülasyondur, gerçek uydu gözlemi değildir.** "
        "Gerçek analiz için kenar çubuğundan FIRMS MAP_KEY girin veya FIRMS arşiv CSV dosyası yükleyin.",
        icon="⚠️",
    )
for err in fetch_errors[:5]:
    st.error(err)

if std.empty:
    st.info("Analiz için bir veri kaynağı seçin: canlı FIRMS API (MAP_KEY gerekir) veya FIRMS CSV yükleme.")
    st.stop()

res = run_cached(std, tuple(bbox), d0, d1, params)
if res.events.empty:
    st.info("Seçilen bölge / tarih / güven eşiğinde sıcak nokta bulunamadı.")
    st.stop()

events_all, points_all = res.events, res.points
events_view = events_all[~events_all["is_static_source"]] if hide_static else events_all
points_view = points_all[~points_all["is_static_source"]] if hide_static else points_all

# ---------------------------------------------------------------------------
# KPI kartları
# ---------------------------------------------------------------------------
s = res.stats
k1, k2, k3, k4, k5 = st.columns(5)
kpi(k1, "Ham sıcak nokta (MODIS+VIIRS)", fmt_int(s["raw_points"]), f"MODIS {fmt_int(s['raw_modis'])} · VIIRS {fmt_int(s['raw_viirs'])}")
kpi(k2, "KÖZ harmonize olay", fmt_int(s["events"]), f"Dinamik {fmt_int(s['events'] - s['static_events'])}")
kpi(k3, "Duplikasyon azaltma", f"%{s['dedup_ratio'] * 100:.1f}", f"{fmt_int(s['raw_points'] - s['events'])} mükerrer piksel birleştirildi")
kpi(k4, "Statik endüstriyel kaynak", fmt_int(s["static_sites"]), f"{fmt_int(s['static_events'])} olay ayrıştırıldı")
kpi(k5, "Ort. kalibre FRP (dinamik)", f"{s['mean_calibrated_frp']:.1f} MW", res.calibration.method)
st.write("")

tab_map, tab_cal, tab_proof, tab_dl = st.tabs(
    ["🗺️ İnteraktif KÖZ CBS Haritası", "📅 Yanma Aktivitesi Takvimi", "🔬 Sensör Harmonizasyon Kanıtı", "⬇️ Veri İndirme Merkezi"]
)

# ---------------------------------------------------------------------------
# Sekme 1 — Harita
# ---------------------------------------------------------------------------
with tab_map:
    months = events_view["acq_date"].dt.to_period("M")
    month_counts = months.value_counts().sort_index()
    if month_counts.empty:
        st.info("Haritada gösterilecek olay yok.")
    else:
        options = [str(p) for p in month_counts.index]
        last_year = month_counts.index.max().year
        recent = month_counts[[p.year == last_year for p in month_counts.index]]
        default = str(recent.idxmax())
        c1, c2 = st.columns([1, 3])
        sel_month = c1.selectbox("Harita dönemi (ay)", options[::-1], index=options[::-1].index(default))
        basemap = c1.radio("Altlık", ["Koyu (Esri Dark Gray)", "Uydu (Esri World Imagery)"])
        c1.markdown(
            f"""<div class="note">
            <b style="color:{C_MODIS}">●</b> Ham MODIS (1 km çember)<br>
            <b style="color:{C_VIIRS}">●</b> Ham VIIRS (375 m çember)<br>
            <b style="color:{C_KOZ}">●</b> KÖZ harmonize olay (boyut ∝ FRP)<br>
            <b style="color:{C_STATIC}">★</b> Statik endüstriyel kaynak (tüm dönem)<br>
            Katmanlar sağ üstteki menüden açılıp kapatılır.</div>""",
            unsafe_allow_html=True,
        )

        per = pd.Period(sel_month)
        ev_m = events_view[events_view["acq_date"].dt.to_period("M") == per]
        pt_m = points_view[points_view["acq_date"].dt.to_period("M") == per]
        if len(ev_m) > MAP_LAYER_CAP:
            ev_m = ev_m.nlargest(MAP_LAYER_CAP, "calibrated_frp_mw")
            pt_m = pt_m[pt_m["unified_hotspot_id"].isin(ev_m["unified_hotspot_id"])]
            c1.caption(f"Performans için en yüksek FRP'li {MAP_LAYER_CAP} olay gösteriliyor.")

        center = [(bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2]
        zoom = 6 if (bbox[2] - bbox[0]) > 8 else 8
        tile_url, tile_attr = (DARK_TILES, "Esri, HERE, Garmin, OpenStreetMap contributors") if basemap.startswith("Koyu") \
            else (SAT_TILES, "Esri World Imagery")
        fmap = folium.Map(location=center, zoom_start=zoom, tiles=None, control_scale=True)
        folium.TileLayer(tiles=tile_url, attr=tile_attr, name=basemap, max_zoom=16 if basemap.startswith("Koyu") else 19).add_to(fmap)
        folium.Rectangle([[bbox[1], bbox[0]], [bbox[3], bbox[2]]], color=EMBER, weight=1, fill=False, dash_array="6").add_to(fmap)

        lyr_m = folium.FeatureGroup(name="Ham MODIS (1 km)", show=True)
        lyr_v = folium.FeatureGroup(name="Ham VIIRS (375 m)", show=True)
        lyr_k = folium.FeatureGroup(name="KÖZ harmonize olaylar", show=True)
        lyr_s = folium.FeatureGroup(name="Statik endüstriyel kaynaklar", show=True)

        for r in pt_m.itertuples(index=False):
            is_m = r.instrument == "MODIS"
            folium.Circle(
                [r.latitude, r.longitude],
                radius=500 if is_m else 187.5,
                color=C_MODIS if is_m else C_VIIRS,
                weight=1,
                fill=True,
                fill_opacity=0.15 if is_m else 0.45,
                tooltip=f"{r.instrument} · {r.satellite} · {r.utc_timestamp:%Y-%m-%d %H:%M}Z · FRP {r.frp:.1f} MW",
            ).add_to(lyr_m if is_m else lyr_v)

        frp_ref = max(float(ev_m["calibrated_frp_mw"].quantile(0.95)) if len(ev_m) else 1.0, 1.0)
        for r in ev_m.itertuples(index=False):
            popup = f"""
            <div style="font-family:sans-serif;font-size:12px;min-width:240px">
            <b style="color:{EMBER}">{r.unified_hotspot_id}</b><br>
            <b>Sınıf:</b> {r.event_class}<br>
            <b>Sensör:</b> {r.sensor_label}<br>
            <b>Birleşen piksel:</b> {r.merged_pixel_count} (MODIS {r.n_modis}, VIIRS {r.n_viirs})<br>
            <b>Uydular:</b> {r.satellites}<br>
            <b>Zaman (UTC):</b> {r.utc_timestamp:%Y-%m-%d %H:%M} – {r.utc_end:%H:%M}<br>
            <b>FRP MODIS / VIIRS:</b> {r.frp_modis_mw:.1f} / {r.frp_viirs_mw:.1f} MW<br>
            <b>Kalibre FRP:</b> {r.calibrated_frp_mw:.1f} MW<br>
            <b>MODIS-eşdeğer ağırlık:</b> {r.modis_eq_weight:.2f}<br>
            <b>Güven:</b> {r.conf_class}<br>
            <b>Konum:</b> {r.latitude:.4f}, {r.longitude:.4f}
            </div>"""
            folium.CircleMarker(
                [r.latitude, r.longitude],
                radius=float(4 + 10 * min(r.calibrated_frp_mw / frp_ref, 1.0)),
                color=C_STATIC if r.is_static_source else C_KOZ,
                weight=1.5,
                fill=True,
                fill_color=AMBER if not r.is_static_source else C_STATIC,
                fill_opacity=0.75,
                popup=folium.Popup(popup, max_width=320),
                tooltip=f"{r.unified_hotspot_id} · {r.calibrated_frp_mw:.1f} MW",
            ).add_to(lyr_k)

        for r in res.static_sites.itertuples(index=False):
            folium.Marker(
                [r.latitude, r.longitude],
                icon=folium.Icon(color="purple", icon="industry", prefix="fa"),
                popup=folium.Popup(
                    f"<b>{r.static_site_id}</b> — Statik Endüstriyel Termal Kaynak<br>"
                    f"Olay: {r.event_count} · Aktif gün: {r.active_days}<br>"
                    f"Yıl içi en fazla: {r.max_days_in_year} gün / {r.max_months_in_year} ay<br>"
                    f"İlk–son: {r.first_seen:%Y-%m-%d} – {r.last_seen:%Y-%m-%d}<br>"
                    f"Ort. kalibre FRP: {r.mean_calibrated_frp_mw:.1f} MW",
                    max_width=300,
                ),
                tooltip=r.static_site_id,
            ).add_to(lyr_s)

        for lyr in (lyr_m, lyr_v, lyr_k, lyr_s):
            lyr.add_to(fmap)
        folium.LayerControl(collapsed=False).add_to(fmap)
        Fullscreen().add_to(fmap)
        MiniMap(toggle_display=True, tile_layer=folium.TileLayer(tiles=DARK_TILES, attr="Esri")).add_to(fmap)
        with c2:
            st_folium(fmap, height=640, use_container_width=True, returned_objects=[], key=f"map_{sel_month}_{basemap}")
            st.caption(
                f"{sel_month}: {fmt_int(len(pt_m))} ham piksel → {fmt_int(len(ev_m))} KÖZ olayı · "
                f"Δd ≤ {distance_km:.1f} km, |Δt| ≤ {window_min} dk"
            )

# ---------------------------------------------------------------------------
# Sekme 2 — Yanma Aktivitesi Takvimi
# ---------------------------------------------------------------------------
with tab_cal:
    c1, c2, c3 = st.columns([2, 1, 1])
    metric = c1.selectbox("Takvim ölçüsü", list(hz.CALENDAR_METRICS), format_func=hz.CALENDAR_METRICS.get)
    mat = hz.monthly_matrix(events_view, metric, cell_km=params["static_cell_km"])
    years = list(mat.index)
    sel_year = c2.selectbox("Yıl", years[::-1])
    sel_mon = c3.selectbox("Ay", list(range(1, 13)), index=int(events_view["acq_date"].dt.month.mode().iloc[0]) - 1,
                           format_func=lambda m: MONTHS_TR[m - 1])

    st.markdown(
        f"""<div class="note"><b>Ölçü tanımı.</b> <i>MODIS-eşdeğer aktif yangın hücre-günü</i>: olaylar ~{params['static_cell_km']:.1f} km
        grid hücresi × UTC gün düzeyinde toplanır (aynı gün farklı uydu geçişleri tekrar sayılmaz); her hücre-gün,
        MODIS tespit olasılığı ile ağırlıklandırılır (MODIS gözlemi varsa 1, yalnız VIIRS ise kalibre FRP'ye bağlı
        veriden kestirilen olasılık). Böylece 2000–2012 (yalnız MODIS) ve 2012 sonrası (MODIS+VIIRS) aynı ölçekte
        karşılaştırılır.{' Statik kaynaklar hariç.' if hide_static else ' Statik kaynaklar dahil.'}</div>""",
        unsafe_allow_html=True,
    )

    zfmt = ".0f" if metric != "frp" else ".3s"
    fig = px.imshow(
        mat.values,
        x=MONTHS_TR,
        y=[str(y) for y in mat.index],
        color_continuous_scale=[[0, "#0B0F19"], [0.15, "#3b1408"], [0.45, "#b8350f"], [0.75, EMBER], [1, "#FFD08A"]],
        aspect="auto",
        labels=dict(color=hz.CALENDAR_METRICS[metric]),
        text_auto=zfmt if len(mat) <= 30 else False,
    )
    fig.update_layout(title=f"Yanma Aktivitesi Takvimi — {hz.CALENDAR_METRICS[metric]} (Yıl × Ay)")
    fig.add_shape(type="rect", x0=sel_mon - 1.5, x1=sel_mon - 0.5, y0=years.index(sel_year) - 0.5,
                  y1=years.index(sel_year) + 0.5, line=dict(color="#FFFFFF", width=2))
    st.plotly_chart(style_fig(fig, height=max(380, 24 * len(mat) + 120)), width="stretch")

    an = hz.month_anomaly(mat, sel_year, sel_mon)
    a1, a2, a3, a4 = st.columns(4)
    val_fmt = (lambda v: f"{v:,.0f}".replace(",", ".")) if metric != "frp" else (lambda v: f"{v:,.0f} MW".replace(",", "."))
    kpi(a1, f"{MONTHS_TR[sel_mon - 1]} {sel_year}", val_fmt(an["current"]), hz.CALENDAR_METRICS[metric])
    kpi(a2, "Tarihsel medyan", val_fmt(an["median"]) if an["n_years"] else "—", f"{an['n_years']} yıl (seçilen yıl hariç)")
    ratio_txt = f"{an['ratio']:.2f}×" if np.isfinite(an.get("ratio", np.nan)) else "—"
    kpi(a3, "Medyana oran", ratio_txt, "1.00× = tarihsel normal")
    pct = an.get("percentile", np.nan)
    status = "—" if not np.isfinite(pct) else ("Normalin üstü" if an["current"] > an["q75"] else "Normalin altı" if an["current"] < an["q25"] else "Normal aralık (Ç1–Ç3)")
    kpi(a4, "Yüzdelik / durum", f"%{pct:.0f}" if np.isfinite(pct) else "—", status)
    st.write("")

    b1, b2 = st.columns(2)
    hist = mat[sel_mon]
    colors = [EMBER if y == sel_year else "#475569" for y in hist.index]
    fig_b = go.Figure(go.Bar(x=[str(y) for y in hist.index], y=hist.values, marker_color=colors, name=MONTHS_TR[sel_mon - 1]))
    if an["n_years"]:
        fig_b.add_hline(y=an["median"], line=dict(color=AMBER, dash="dash"), annotation_text="tarihsel medyan")
        fig_b.add_hrect(y0=an["q25"], y1=an["q75"], fillcolor=AMBER, opacity=0.08, line_width=0)
    fig_b.update_layout(title=f"{MONTHS_TR[sel_mon - 1]} ayı — yıllar arası karşılaştırma")
    b1.plotly_chart(style_fig(fig_b, 380), width="stretch")

    clim = mat.drop(index=sel_year, errors="ignore")
    fig_c = go.Figure()
    fig_c.add_trace(go.Scatter(x=MONTHS_TR, y=clim.quantile(0.75).values, line=dict(width=0), showlegend=False, hoverinfo="skip"))
    fig_c.add_trace(go.Scatter(x=MONTHS_TR, y=clim.quantile(0.25).values, fill="tonexty", fillcolor="rgba(255,152,0,.15)",
                               line=dict(width=0), name="Ç1–Ç3 aralığı"))
    fig_c.add_trace(go.Scatter(x=MONTHS_TR, y=clim.median().values, line=dict(color=AMBER, dash="dash"), name="Tarihsel medyan"))
    fig_c.add_trace(go.Scatter(x=MONTHS_TR, y=mat.loc[sel_year].values, line=dict(color=EMBER, width=3), mode="lines+markers", name=str(sel_year)))
    fig_c.update_layout(title=f"Mevsimsel profil — {sel_year} ve tarihsel dağılım")
    b2.plotly_chart(style_fig(fig_c, 380), width="stretch")

    daily = events_view[events_view["acq_date"].dt.year == sel_year].groupby("acq_date").agg(
        olay=("unified_hotspot_id", "size"), frp=("calibrated_frp_mw", "sum")
    )
    if not daily.empty:
        fig_d = go.Figure(go.Bar(x=daily.index, y=daily["olay"], marker_color=EMBER, name="Günlük KÖZ olayı"))
        fig_d.update_layout(title=f"{sel_year} — günlük harmonize olay sayısı")
        st.plotly_chart(style_fig(fig_d, 300), width="stretch")

# ---------------------------------------------------------------------------
# Sekme 3 — Sensör harmonizasyon kanıtı
# ---------------------------------------------------------------------------
with tab_proof:
    ann = hz.annual_series(points_view, events_view, cell_km=params["static_cell_km"])
    series_cols = {
        "Ham toplam (MODIS+VIIRS)": "#64748B",
        "Ham MODIS piksel": C_MODIS,
        "KÖZ harmonize olay": AMBER,
        "KÖZ MODIS-eşdeğer hücre-günü": EMBER,
    }
    fig_a = go.Figure()
    for col, color in series_cols.items():
        fig_a.add_trace(go.Scatter(x=ann.index, y=ann[col], name=col, mode="lines+markers",
                                   line=dict(color=color, width=3 if "MODIS-eşdeğer" in col else 2)))
    fig_a.add_bar(x=ann.index, y=ann["Ham VIIRS piksel"], name="Ham VIIRS piksel", marker_color=C_VIIRS, opacity=0.25)
    if ann.index.min() < 2012 <= ann.index.max():
        fig_a.add_vline(x=2011.5, line=dict(color="#F8FAFC", dash="dot"), annotation_text="VIIRS verisi başlar (2012)")
    fig_a.update_layout(title="Harmonizasyon öncesi / sonrası yıllık seri", xaxis_title="Yıl", yaxis_title="Sayı")
    st.plotly_chart(style_fig(fig_a, 460), width="stretch")

    if ann.index.min() < 2012 <= ann.index.max():
        br = pd.DataFrame(
            {
                "Seri": list(series_cols),
                "2012+ ort. / 2012 öncesi ort.": [hz.break_ratio(ann[c]) for c in series_cols],
            }
        )
        c1, c2 = st.columns([1, 1.4])
        c1.markdown("**Sensör kırılma oranı** (1.00 = kırılma yok)")
        c1.dataframe(br.style.format({"2012+ ort. / 2012 öncesi ort.": "{:.2f}"}), hide_index=True, width="stretch")
        c2.markdown(
            f"""<div class="note">Ham toplam seri 2012'de VIIRS'in eklenmesiyle sıçrar. KÖZ boru hattı
            (i) 375 m VIIRS alt piksellerini ve eşzamanlı MODIS pikselini tek olayda birleştirir,
            (ii) farklı uydu geçişlerini hücre-gün düzeyinde tekilleştirir,
            (iii) yalnız VIIRS'in gördüğü düşük enerjili olayları MODIS tespit olasılığıyla ağırlıklandırır.
            Yalnız-MODIS ham serisi referans çizgisidir.</div>""",
            unsafe_allow_html=True,
        )
    else:
        st.caption("2012 kırılma oranı için analiz aralığı 2012 öncesi ve sonrasını kapsamalıdır.")

    st.markdown("---")
    c1, c2 = st.columns(2)
    both = events_all[(events_all["frp_modis_mw"] > 0) & (events_all["frp_viirs_mw"] > 0)]
    with c1:
        if len(both):
            sample = both.sample(min(len(both), 4000), random_state=0)
            fig_s = go.Figure(go.Scattergl(
                x=sample["frp_viirs_mw"], y=sample["frp_modis_mw"], mode="markers",
                marker=dict(size=5, color=EMBER, opacity=0.35), name="BOTH olayları",
            ))
            xs = np.logspace(np.log10(max(both["frp_viirs_mw"].min(), 0.1)), np.log10(both["frp_viirs_mw"].max()), 60)
            fig_s.add_trace(go.Scatter(x=xs, y=res.calibration.apply(xs), line=dict(color=AMBER, width=3), name="Kalibrasyon"))
            fig_s.add_trace(go.Scatter(x=xs, y=xs, line=dict(color="#94A3B8", dash="dot"), name="1:1"))
            fig_s.update_xaxes(type="log", title="VIIRS küme FRP (MW, geçiş içi toplam)")
            fig_s.update_yaxes(type="log", title="MODIS FRP (MW)")
            fig_s.update_layout(title="MODIS vs VIIRS FRP korelasyonu (eş-konumlu olaylar)")
            st.plotly_chart(style_fig(fig_s, 420), width="stretch")
        st.code(res.calibration.describe(), language=None)
    with c2:
        curve = res.detection_curve
        if curve.available:
            fig_p = go.Figure()
            fig_p.add_trace(go.Scatter(x=10 ** curve.log_frp_centers, y=curve.raw_ratio, mode="markers",
                                       marker=dict(color=C_MODIS, size=9), name="P(MODIS da gördü | VIIRS)"))
            fig_p.add_trace(go.Scatter(x=10 ** curve.log_frp_centers, y=curve.p_detect, line=dict(color=EMBER, width=3),
                                       name="Normalize MODIS tespit olasılığı"))
            fig_p.update_xaxes(type="log", title="Kalibre FRP (MW)")
            fig_p.update_yaxes(range=[0, 1.05], title="Olasılık")
            fig_p.update_layout(title="Veriden kestirilen MODIS tespit eğrisi")
            st.plotly_chart(style_fig(fig_p, 420), width="stretch")
            st.caption(f"Plato (yüksek FRP'de eşzamanlı gözlem oranı): {curve.plateau:.2f} · n = {fmt_int(curve.n_events)} VIIRS olayı")
        else:
            st.info("MODIS tespit eğrisi için yeterli eş-konumlu olay yok; VIIRS-only olaylar ağırlık 1 ile sayılır.")

    lab = events_view["sensor_label"].value_counts().rename_axis("sensor_label").reset_index(name="olay")
    pix = events_view.groupby("sensor_label")["merged_pixel_count"].mean().round(2).rename("ort. birleşen piksel")
    lab = lab.merge(pix, on="sensor_label")
    fig_l = px.bar(lab, x="sensor_label", y="olay", text="ort. birleşen piksel", color="sensor_label",
                   color_discrete_map={hz.SENSOR_BOTH: EMBER, hz.SENSOR_VIIRS: C_VIIRS, hz.SENSOR_MODIS: C_MODIS})
    fig_l.update_traces(texttemplate="ort. %{text} piksel/olay", textposition="outside")
    fig_l.update_layout(title="Harmonize olayların sensör etiketi dağılımı", showlegend=False, xaxis_title="")
    st.plotly_chart(style_fig(fig_l, 360), width="stretch")

# ---------------------------------------------------------------------------
# Sekme 4 — İndirme
# ---------------------------------------------------------------------------
with tab_dl:
    out = hz.export_table(events_view)
    st.markdown(f"**Harmonize sıcak nokta tablosu** — {fmt_int(len(out))} satır · {d0} – {d1} · {aoi_name}")
    st.dataframe(out.head(500), width="stretch", hide_index=True)
    st.download_button(
        "⬇️ koz_atlas_harmonized_hotspots.csv",
        out.to_csv(index=False).encode("utf-8"),
        file_name="koz_atlas_harmonized_hotspots.csv",
        mime="text/csv",
        type="primary",
    )
    c1, c2, c3 = st.columns(3)
    if not res.static_sites.empty:
        sites = res.static_sites.copy()
        for c in ("first_seen", "last_seen"):
            sites[c] = sites[c].dt.strftime("%Y-%m-%d")
        c1.download_button("Statik kaynak listesi (CSV)", sites.to_csv(index=False).encode("utf-8"),
                           file_name="koz_atlas_static_sources.csv", mime="text/csv")
    raw_cols = ["point_id", "unified_hotspot_id", "latitude", "longitude", "utc_timestamp", "instrument", "satellite",
                "source", "frp", "brightness_k", "brightness_2_k", "scan", "track", "conf_class", "daynight", "is_static_source"]
    raw_out = points_view[raw_cols].copy()
    raw_out["utc_timestamp"] = raw_out["utc_timestamp"].dt.strftime("%Y-%m-%dT%H:%MZ")
    c2.download_button("Ham piksel → olay eşleme tablosu (CSV)", raw_out.to_csv(index=False).encode("utf-8"),
                       file_name="koz_atlas_pixel_event_map.csv", mime="text/csv")
    meta = {
        "project": "KÖZ Atlas",
        "team": "Kirvecanlar",
        "challenge": CHALLENGE_URL,
        "data_mode": mode,
        "aoi_name": aoi_name,
        "aoi_bbox_wsen": list(bbox),
        "date_range": [str(d0), str(d1)],
        "params": params,
        "static_sources_hidden": hide_static,
        "frp_calibration": res.calibration.describe(),
        "modis_detection_curve": {
            "frp_mw": (10 ** res.detection_curve.log_frp_centers).round(3).tolist(),
            "p_detect": res.detection_curve.p_detect.round(4).tolist(),
        },
        "stats": {k: v for k, v in s.items() if k != "label_counts"} | {"label_counts": s["label_counts"]},
    }
    c3.download_button("Çalıştırma meta verisi (JSON)", json.dumps(meta, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
                       file_name="koz_atlas_run_metadata.json", mime="application/json")

    with st.expander("CSV sütun sözlüğü"):
        st.markdown(
            """
| Sütun | Açıklama |
|---|---|
| `unified_hotspot_id` | Harmonize Yangın Olayı kimliği (`KOZ-YYYYMMDD-sıra`) |
| `latitude`, `longitude` | FRP ağırlıklı küme merkezi |
| `utc_timestamp`, `utc_end` | Kümedeki ilk / son gözlem zamanı (UTC) |
| `sensor_label` | `BOTH (MODIS+VIIRS)`, `VIIRS_CLUSTER_HARMONIZED`, `MODIS_ONLY` |
| `merged_pixel_count` | Birleştirilen ham piksel sayısı (`n_modis` + `n_viirs`) |
| `frp_modis_mw`, `frp_viirs_mw` | Sensör bazında FRP: geçiş içi toplam, geçişler arası ortalama (MW) |
| `frp_viirs_calibrated_mw` | VIIRS FRP'sinin MODIS eşdeğeri (öğrenilen kalibrasyon) |
| `calibrated_frp_mw` | Harmonize FRP: MODIS gözlemi varsa MODIS, yoksa kalibre VIIRS |
| `modis_eq_weight` | MODIS tarafından tespit edilme olasılığı (MODIS gözlemi varsa 1) |
| `modis_equivalent` | `modis_eq_weight ≥ 0.5` |
| `is_static_source`, `event_class` | Statik endüstriyel kaynak / dinamik biyokütle yangını |
"""
        )

st.markdown("---")
st.caption(
    f"KÖZ Atlas · Kirvecanlar (Mehmet Halil KILIÇ, İbrahim Halil BİRLİK, Mirze KARA) · Batman Üniversitesi Bilgisayar Mühendisliği · "
    f"Veri: NASA FIRMS ([Area API kılavuzu]({FIRMS_GUIDE_URL})) · [Görev tanımı]({CHALLENGE_URL}) · [Canlı uygulama]({APP_URL}) · [GitHub]({REPO_URL})"
)
