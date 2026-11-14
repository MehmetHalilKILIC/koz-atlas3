"""
KÖZ Atlas — 7 slaytlık jüri sunumu (PPTX) üretici.

    pip install python-pptx
    python presentation/build_presentation.py

Slayt 5'teki doğrulama sayıları, harmonizer.py'deki sentetik senaryo çalıştırılarak her seferinde yeniden
hesaplanır (sabit yazılmaz) ve slaytta "sentetik" olarak etiketlenir.
"""
from __future__ import annotations

import sys
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import harmonizer as hz  # noqa: E402

OUT = ROOT / "presentation" / "KOZ_Atlas_Sunum.pptx"

BG = RGBColor(0x0B, 0x0F, 0x19)
CARD = RGBColor(0x1E, 0x29, 0x3B)
EMBER = RGBColor(0xFF, 0x57, 0x22)
AMBER = RGBColor(0xFF, 0x98, 0x00)
TEXT = RGBColor(0xE2, 0xE8, 0xF0)
MUTED = RGBColor(0x94, 0xA3, 0xB8)

CHALLENGE_URL = "https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/"
FIRMS_GUIDE_URL = "https://github.com/nasa/spaceapps/discussions/2016"
APP_URL = "https://koz-atlas-gbqjscepvmqcaygzbjlxhq.streamlit.app/"
REPO_URL = "https://github.com/MehmetHalilKILIC/koz-atlas"

W, H = Inches(13.333), Inches(7.5)


def synthetic_validation() -> dict:
    raw = hz.SyntheticFIRMSGenerator(seed=42).generate(2000, 2025)
    res = hz.run_pipeline(hz.standardize_firms(raw), hz.PipelineParams())
    dyn_ev = res.events[~res.events["is_static_source"]]
    dyn_pt = res.points[~res.points["is_static_source"]]
    ann = hz.annual_series(dyn_pt, dyn_ev)
    return {
        "raw_break": hz.break_ratio(ann["Ham toplam (MODIS+VIIRS)"]),
        "modis_break": hz.break_ratio(ann["Ham MODIS piksel"]),
        "koz_break": hz.break_ratio(ann["KÖZ MODIS-eşdeğer hücre-günü"]),
        "static_found": len(res.static_sites),
        "static_true": len(hz.SyntheticFIRMSGenerator.STATIC_SITES),
        "dedup": res.stats["dedup_ratio"],
        "cal": res.calibration.describe(),
    }


# ---------------------------------------------------------------------------
# Çizim yardımcıları
# ---------------------------------------------------------------------------
def base_slide(prs, number: int, tag: str, title: str):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    bar = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, W, Inches(0.09))
    bar.fill.solid()
    bar.fill.fore_color.rgb = EMBER
    bar.line.fill.background()
    add_text(s, Inches(0.6), Inches(0.35), Inches(9), Inches(0.4), tag.upper(), 13, AMBER, bold=True)
    add_text(s, Inches(0.6), Inches(0.7), Inches(12), Inches(0.9), title, 32, TEXT, bold=True)
    add_text(s, Inches(0.6), Inches(7.0), Inches(9), Inches(0.35),
             "KÖZ Atlas · Kirvecanlar · 2026 NASA Space Apps Challenge — Batman", 10, MUTED)
    add_text(s, Inches(12.2), Inches(7.0), Inches(0.6), Inches(0.35), f"{number}/7", 10, MUTED, align=PP_ALIGN.RIGHT)
    return s


def add_text(slide, x, y, w, h, text, size=16, color=TEXT, bold=False, align=PP_ALIGN.LEFT, link=None):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    r = p.add_run()
    r.text = text
    r.font.size = Pt(size)
    r.font.bold = bold
    r.font.color.rgb = color
    if link:
        r.hyperlink.address = link
    return tb


def add_bullets(slide, x, y, w, h, items, size=17, card=True):
    if card:
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
        box.adjustments[0] = 0.04
        box.fill.solid()
        box.fill.fore_color.rgb = CARD
        box.line.color.rgb = RGBColor(0x5A, 0x2A, 0x1A)
    tb = slide.shapes.add_textbox(x + Inches(0.25), y + Inches(0.18), w - Inches(0.5), h - Inches(0.3))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(8)
        head, _, rest = item.partition("|")
        r0 = p.add_run()
        r0.text = "▸ "
        r0.font.color.rgb = EMBER
        r0.font.size = Pt(size)
        if rest:
            r1 = p.add_run()
            r1.text = head
            r1.font.bold = True
            r1.font.size = Pt(size)
            r1.font.color.rgb = AMBER
            r2 = p.add_run()
            r2.text = rest
            r2.font.size = Pt(size)
            r2.font.color.rgb = TEXT
        else:
            r1 = p.add_run()
            r1.text = head
            r1.font.size = Pt(size)
            r1.font.color.rgb = TEXT
    return tb


def add_table(slide, x, y, w, rows, col_widths=None, size=13, row_h=0.42):
    nr, nc = len(rows), len(rows[0])
    shape = slide.shapes.add_table(nr, nc, x, y, w, Inches(row_h * nr))
    tbl = shape.table
    if col_widths:
        total = sum(col_widths)
        for i, cw in enumerate(col_widths):
            tbl.columns[i].width = Emu(int(w * cw / total))
    for r in range(nr):
        for c in range(nc):
            cell = tbl.cell(r, c)
            cell.text = str(rows[r][c])
            cell.fill.solid()
            cell.fill.fore_color.rgb = EMBER if r == 0 else (CARD if r % 2 else RGBColor(0x16, 0x20, 0x33))
            for p in cell.text_frame.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(size)
                    run.font.bold = r == 0 or c == 0
                    run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if r == 0 else TEXT
    return tbl


def notes(slide, text: str):
    slide.notes_slide.notes_text_frame.text = text


def stage_boxes(slide, y):
    stages = [
        ("1", "Güven filtresi\n& ortak şema", "MODIS 0–100, VIIRS l/n/h\n→ low/nominal/high\nacq_date+acq_time → UTC"),
        ("2", "Haversine\nkümeleme", "Δd ≤ 1.2 km, |Δt| ≤ ±60 dk\nFRP ağırlıklı merkez\nBOTH / VIIRS / MODIS etiketi"),
        ("3", "FRP çapraz\nkalibrasyon", "log FRP_M = a + b·log FRP_V\n(eş-konumlu olaylardan)\nMODIS tespit olasılığı"),
        ("4", "Statik kaynak\nayrıştırma", "~1 km hücre, aynı yıl\n≥ 5 gün ve ≥ 4 ay\n→ gaz bacası / sanayi"),
    ]
    bw, gap, x0 = Inches(2.85), Inches(0.28), Inches(0.6)
    for i, (n, head, body) in enumerate(stages):
        x = x0 + i * (bw + gap)
        box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, bw, Inches(2.75))
        box.adjustments[0] = 0.06
        box.fill.solid()
        box.fill.fore_color.rgb = CARD
        box.line.color.rgb = EMBER
        circ = slide.shapes.add_shape(MSO_SHAPE.OVAL, x + Inches(0.2), y + Inches(0.2), Inches(0.55), Inches(0.55))
        circ.fill.solid()
        circ.fill.fore_color.rgb = EMBER
        circ.line.fill.background()
        circ.text_frame.text = n
        circ.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        circ.text_frame.paragraphs[0].runs[0].font.bold = True
        circ.text_frame.paragraphs[0].runs[0].font.size = Pt(18)
        add_text(slide, x + Inches(0.85), y + Inches(0.12), bw - Inches(0.95), Inches(0.8), head, 15, AMBER, bold=True)
        add_text(slide, x + Inches(0.2), y + Inches(1.05), bw - Inches(0.4), Inches(1.6), body, 13, TEXT)
        if i < 3:
            arr = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, x + bw + Inches(0.03), y + Inches(1.2), Inches(0.22), Inches(0.35))
            arr.fill.solid()
            arr.fill.fore_color.rgb = AMBER
            arr.line.fill.background()


# ---------------------------------------------------------------------------
# Slaytlar
# ---------------------------------------------------------------------------
def build(v: dict) -> Path:
    prs = Presentation()
    prs.slide_width, prs.slide_height = W, H

    # 1 — Kapak
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = BG
    glow = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(8.4), Inches(-1.8), Inches(7), Inches(7))
    glow.fill.solid()
    glow.fill.fore_color.rgb = RGBColor(0x3B, 0x14, 0x08)
    glow.line.fill.background()
    add_text(s, Inches(0.8), Inches(0.7), Inches(8), Inches(0.4), "KİM & NE?", 14, AMBER, bold=True)
    add_text(s, Inches(0.8), Inches(1.3), Inches(10), Inches(1.4), "KÖZ Atlas", 72, EMBER, bold=True)
    add_text(s, Inches(0.8), Inches(2.65), Inches(11), Inches(0.9),
             "MODIS & VIIRS Termal Anomali ve Aktif Yangın Harmonizasyon Platformu", 26, TEXT)
    add_bullets(s, Inches(0.8), Inches(3.75), Inches(11.7), Inches(2.6), [
        "Etkinlik: |2026 NASA Space Apps Challenge — Batman Yerel Etkinliği (Prof. Dr. Narin Nasıroğlu Bilim ve İnovasyon Merkezi, 14–15 Kasım 2026)",
        "Görev: |Harmonization of MODIS and VIIRS Hot Spots (İleri Seviye)",
        "Takım Kirvecanlar: |Mehmet Halil Kılıç · İbrahim Halil Birlik · Mirze Kara",
        "Kurum: |Batman Üniversitesi Bilgisayar Mühendisliği",
    ], size=17)
    notes(s, "Biz Kirvecanlar. KÖZ Atlas, NASA'nın iki yangın sensörünün kayıtlarını tek, karşılaştırılabilir "
             "bir yangın geçmişine dönüştüren açık kaynak bir platform.")

    # 2 — Problem
    s = base_slide(prs, 2, "Neden & Ne zaman?", "İki sensör, tek yangın geçmişi olmadan")
    add_table(s, Inches(0.6), Inches(1.75), Inches(7.4), [
        ["", "MODIS (Terra / Aqua)", "VIIRS (S-NPP / NOAA-20 / NOAA-21)"],
        ["Piksel", "~1 km × 1 km", "375 m × 375 m"],
        ["Kapsam", "2000 – bugün\nömrünün sonuna yaklaşıyor", "2012 – bugün\ndevamlılık sensörü"],
        ["Duyarlılık", "Orta", "Küçük, düşük enerjili\nyangınlara yüksek"],
    ], col_widths=[1.2, 2.2, 2.6], size=14, row_h=0.62)
    add_bullets(s, Inches(8.3), Inches(1.75), Inches(4.45), Inches(4.9), [
        "Mükerrer sayım: |1 km'lik MODIS yangını VIIRS'te birden çok 375 m alt piksel.",
        "Yapay sıçrama: |VIIRS küçük yangınları da görür; 2012 sonrası sayılar sensör kaynaklı artar.",
        "Sonuç: |Bu sezon 20+ yıllık tarihsel medyanla doğru kıyaslanamaz.",
        "Aciliyet: |MODIS emekli olmadan iki kayıt arasında köprü kurulmalı.",
    ], size=15)
    notes(s, "Ham sayıları birleştirirseniz 2012'de yangınlar aniden artmış gibi görünür; bu bir sensör etkisi, gerçek bir artış değil.")

    # 3 — Bölge ve veri
    s = base_slide(prs, 3, "Nerede?", "Odak bölgeler ve veri kaynağı")
    add_bullets(s, Inches(0.6), Inches(1.75), Inches(6.0), Inches(4.9), [
        "NASA FIRMS Area API: |/api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}/{DATE}",
        "Kaynaklar: |MODIS_NRT, MODIS_SP, VIIRS_SNPP_NRT, VIIRS_SNPP_SP, VIIRS_NOAA20_NRT",
        "Arşiv: |FIRMS CSV dosyaları doğrudan yüklenebilir",
        "Ortak şema: |latitude, longitude, brightness / bright_ti4, scan, track, acq_date, acq_time, satellite, instrument, confidence, frp, daynight",
    ], size=15)
    add_table(s, Inches(6.9), Inches(1.75), Inches(5.85), [
        ["Ön ayar", "Kutu (W,S,E,N)", "Amaç"],
        ["Türkiye geneli", "25.6, 35.8, 44.8, 42.1", "Ulusal tarihsel seri"],
        ["GD Anadolu & Batman", "38.5, 36.6, 43.5, 38.8", "Anız yangını ↔ gaz bacası ayrımı"],
        ["Akdeniz & Ege", "26.0, 36.0, 36.5, 40.0", "Orman yangını anomali analizi"],
    ], col_widths=[1.6, 1.8, 2.2], size=13, row_h=0.7)
    add_text(s, Inches(6.9), Inches(4.9), Inches(5.85), Inches(1.4),
             "Batman havzası: tarımsal anız yangınları ile Batman / Raman / Garzan petrol sahası gaz yakma bacaları "
             "aynı bölgede; ayrıştırılmazsa yanlış alarm üretir.", 14, MUTED)
    notes(s, "Batman bizim için ideal test alanı: aynı haritada hem anız yangınları hem de yıl boyu yanan bacalar var.")

    # 4 — Mimari
    s = base_slide(prs, 4, "Nasıl? — 1", "KÖZ Atlas 4 aşamalı harmonizasyon boru hattı")
    stage_boxes(s, Inches(1.8))
    add_text(s, Inches(0.6), Inches(4.85), Inches(12.2), Inches(0.6),
             "d = 2R·arcsin √( sin²(Δφ/2) + cos φ₁ · cos φ₂ · sin²(Δλ/2) ),   R = 6371.0 km", 18, AMBER, bold=True,
             align=PP_ALIGN.CENTER)
    add_text(s, Inches(0.6), Inches(5.5), Inches(12.2), Inches(1.2),
             "Aday çiftler 4 boyutlu KD-ağacında (birim küre x, y, z + ölçeklenmiş zaman) aranır, tam Haversine ve |Δt| ile "
             "doğrulanır; bağlı bileşenler Harmonize Yangın Olayı olur. Kalibrasyon katsayıları sabit değildir, seçilen "
             "bölgenin eş-konumlu MODIS+VIIRS olaylarından öğrenilir.", 14, MUTED, align=PP_ALIGN.CENTER)
    notes(s, "Katsayıları biz uydurmuyoruz; iki sensörün aynı anda gördüğü yangınlardan, seçilen bölgenin kendi verisinden öğreniyoruz.")

    # 5 — Takvim ve karşılaştırma
    s = base_slide(prs, 5, "Nasıl? — 2", "Yanma Aktivitesi Takvimi ve sensör karşılaştırması")
    add_table(s, Inches(0.6), Inches(1.7), Inches(7.3), [
        ["Ölçüt", "MODIS", "VIIRS", "KÖZ Atlas"],
        ["Birim", "1 km piksel", "375 m piksel", "Olay / aktif yangın hücre-günü"],
        ["Mükerrer piksel", "—", "Var", "Kümelemeyle birleştirilir"],
        ["Uydu sayısı etkisi", "—", "Var", "Hücre-gün tekilleştirmesi"],
        ["FRP", "Referans", "Farklı ölçek", "MODIS eşdeğerine kalibre"],
        ["Gaz bacaları", "Karışık", "Karışık", "Ayrı katman"],
    ], col_widths=[1.6, 1.1, 1.2, 2.4], size=13, row_h=0.55)
    add_bullets(s, Inches(8.15), Inches(1.7), Inches(4.6), Inches(3.3), [
        "Takvim: |Yıl × Ay ısı matrisi; seçilen ay → tarihsel medyana oran, yüzdelik, Ç1–Ç3 bandı.",
        "CSV: |koz_atlas_harmonized_hotspots.csv — olay kimliği, sensör etiketi, birleşen piksel, kalibre FRP, statik/dinamik sınıf.",
    ], size=14)
    box = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.6), Inches(5.25), Inches(12.15), Inches(1.5))
    box.adjustments[0] = 0.08
    box.fill.solid()
    box.fill.fore_color.rgb = RGBColor(0x2A, 0x14, 0x0C)
    box.line.color.rgb = AMBER
    add_text(s, Inches(0.85), Inches(5.33), Inches(11.7), Inches(0.4),
             "SENTETİK DOĞRULAMA SENARYOSU (gerçek gözlem değildir; yerleşik simülasyon, 2000–2025)", 12, AMBER, bold=True)
    add_text(s, Inches(0.85), Inches(5.72), Inches(11.7), Inches(1.0),
             f"2012 sonrası / öncesi ortalama oranı → ham MODIS+VIIRS: {v['raw_break']:.2f}×  ·  KÖZ MODIS-eşdeğer: "
             f"{v['koz_break']:.2f}×  ·  yalnız-MODIS referansı: {v['modis_break']:.2f}×\n"
             f"Statik kaynak: simülasyondaki {v['static_true']} kaynağın {v['static_found']}'i ayrıştırıldı  ·  "
             f"Duplikasyon azaltma: %{v['dedup'] * 100:.1f}", 15, TEXT)
    notes(s, "Takvim görevin ana çıktısı: 'Bu temmuz normal mi?' sorusuna sensörden bağımsız cevap verir. "
             "Alttaki kutudaki sayılar sentetik senaryodandır; yöntemin kırılmayı giderdiğini kontrollü ortamda gösterir.")

    # 6 — Ürün ve etki
    s = base_slide(prs, 6, "Ne kazandırır?", "Canlı ürün (MVP) ve etki")
    add_bullets(s, Inches(0.6), Inches(1.75), Inches(6.2), Inches(4.9), [
        "Canlı uygulama: |koz-atlas-gbqjscepvmqcaygzbjlxhq.streamlit.app",
        "Açık kaynak: |github.com/MehmetHalilKILIC/koz-atlas",
        "Yığın: |Python · Pandas / NumPy / SciPy · Streamlit · Folium · Plotly",
        "4 sekme: |CBS haritası · Yanma Aktivitesi Takvimi · Harmonizasyon kanıtı · CSV indirme",
        "Veri modları: |anahtarsız demo · canlı FIRMS API · arşiv CSV yükleme",
    ], size=15)
    add_table(s, Inches(7.1), Inches(1.75), Inches(5.65), [
        ["Kullanıcı", "Kazanım"],
        ["Afet yöneticileri", "Mevcut sezonu 2000'den bu yana tarihsel medyanla kıyaslama"],
        ["Erken uyarı birimleri", "Gaz bacası / sanayi kaynaklı yanlış alarmların ayıklanması"],
        ["Araştırmacılar", "Sensörden bağımsız, indirilebilir harmonize seri"],
    ], col_widths=[1.6, 3.2], size=14, row_h=0.85)
    add_text(s, Inches(0.6), Inches(6.45), Inches(6), Inches(0.4), "▶ Canlı uygulamayı aç", 14, EMBER, bold=True, link=APP_URL)
    notes(s, "Uygulama şu an çalışıyor; jüri kendi bölgesini ve tarih aralığını seçip sonucu CSV olarak indirebilir.")

    # 7 — Kaynakça
    s = base_slide(prs, 7, "Kaynakça", "Doğrulanmış kaynaklar ve erişim")
    refs = [
        ("NASA Space Apps Challenge 2026 — Harmonization of MODIS and VIIRS Hot Spots", CHALLENGE_URL),
        ("NASA Space Apps GitHub tartışması ve FIRMS Area API kılavuzu (#2016)", FIRMS_GUIDE_URL),
        ("KÖZ Atlas canlı web uygulaması (Streamlit Cloud)", APP_URL),
        ("KÖZ Atlas açık kaynak deposu (MehmetHalilKILIC/koz-atlas)", REPO_URL),
    ]
    for i, (label, url) in enumerate(refs):
        y = Inches(1.85 + i * 1.2)
        add_text(s, Inches(0.6), y, Inches(0.6), Inches(0.5), f"{i + 1}", 26, EMBER, bold=True)
        add_text(s, Inches(1.25), y, Inches(11.4), Inches(0.45), label, 18, TEXT, bold=True)
        add_text(s, Inches(1.25), y + Inches(0.45), Inches(11.4), Inches(0.4), url, 14, AMBER, link=url)
    notes(s, "Teşekkürler. Sorularınızı canlı uygulama üzerinde cevaplayabiliriz.")

    assert len(prs.slides) <= 7
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    return OUT


if __name__ == "__main__":
    print("Sentetik doğrulama senaryosu çalıştırılıyor…")
    vals = synthetic_validation()
    print({k: (round(x, 3) if isinstance(x, float) else x) for k, x in vals.items()})
    print("Kaydedildi:", build(vals))
