# KÖZ Atlas — 7 Slaytlık Jüri Sunumu (5N1K)

> Kurallar: en fazla 7 slayt · her slayt bir 5N1K sorusuna cevap verir · konuşma süresi slayt başına ~40–60 sn.
> Slayt 5'teki sayısal örnek **sentetik doğrulama senaryosundan** gelir ve öyle söylenmelidir.

---

## Slayt 1 — Kapak (Kim & Ne?)

**KÖZ Atlas**
MODIS & VIIRS Termal Anomali ve Aktif Yangın Harmonizasyon Platformu

- 2026 NASA Space Apps Challenge — Batman Yerel Etkinliği (Prof. Dr. Narin Nasıroğlu Bilim ve İnovasyon Merkezi, 14–15 Kasım 2026)
- Görev: *Harmonization of MODIS and VIIRS Hot Spots* (İleri Seviye)
- Takım **Kirvecanlar** — Mehmet Halil Kılıç · İbrahim Halil Birlik · Mirze Kara (Batman Üniversitesi Bilgisayar Mühendisliği)

**Konuşma:** "Biz Kirvecanlar. KÖZ Atlas, NASA'nın iki yangın sensörünün kayıtlarını tek, karşılaştırılabilir bir yangın geçmişine dönüştüren açık kaynak bir platform."

---

## Slayt 2 — Problem ve Aciliyet (Neden & Ne Zaman?)

| | MODIS (Terra / Aqua) | VIIRS (Suomi NPP / NOAA-20 / NOAA-21) |
|---|---|---|
| Piksel | ~1 km × 1 km | 375 m × 375 m |
| Kapsam | 2000 – bugün, ömrü sonuna yaklaşıyor | 2012 – bugün, devamlılık sensörü |
| Duyarlılık | Orta | Küçük / düşük enerjili yangınlara yüksek |

- Tek bir 1 km MODIS yangını VIIRS'te **birden çok 375 m alt piksel** → mükerrer sayım.
- VIIRS, MODIS'in göremediği küçük yangınları da kaydeder → 2012 sonrası **yapay sıçrama**.
- Sonuç: afet yöneticisi bu sezonu 20+ yıllık **tarihsel medyanla** doğru kıyaslayamaz. MODIS emekli olmadan köprü kurulmalı.

**Konuşma:** "Ham sayıları birleştirirseniz 2012'de yangınlar aniden artmış gibi görünür; bu bir sensör etkisi, gerçek bir artış değil."

---

## Slayt 3 — Odak Bölge ve Veri (Nerede?)

- Veri: **NASA FIRMS Area API** — `/api/area/csv/{MAP_KEY}/{SOURCE}/{AREA}/{DAY_RANGE}/{DATE}`; kaynaklar `MODIS_NRT`, `MODIS_SP`, `VIIRS_SNPP_NRT`, `VIIRS_SNPP_SP`, `VIIRS_NOAA20_NRT`; arşiv CSV yükleme.
- **Türkiye geneli** (25.6, 35.8, 44.8, 42.1)
- **Güneydoğu Anadolu & Batman Havzası:** tarımsal anız yangınları ile petrol sahası gaz yakma bacalarının (gas flare) iç içe olduğu test bölgesi.
- **Akdeniz & Ege Orman Kuşağı:** yüksek şiddetli orman yangınlarının tarihsel anomali analizi.

**Konuşma:** "Batman bizim için ideal test alanı: aynı haritada hem gerçek anız yangınları hem de yıl boyu yanan bacalar var. İkisini ayırmayan bir sistem yanlış alarm üretir."

---

## Slayt 4 — 4 Aşamalı Harmonizasyon Mimarisi (Nasıl? — 1)

1. **Güven filtresi ve ortak şema:** MODIS 0–100 ve VIIRS l/n/h → low/nominal/high; `acq_date + acq_time` → UTC.
2. **Haversine mekansal-zamansal kümeleme:** Δd ≤ 1.2 km, |Δt| ≤ ±60 dk (ayarlanabilir) → *Harmonize Yangın Olayı*; FRP ağırlıklı merkez; etiket `BOTH` / `VIIRS_CLUSTER_HARMONIZED` / `MODIS_ONLY`.
3. **FRP çapraz kalibrasyonu:** eş-konumlu olaylardan öğrenilen `log FRP_MODIS = a + b·log FRP_VIIRS`; veriden kestirilen MODIS tespit olasılığı ile *MODIS-eşdeğer* sayım.
4. **Statik kaynak ayrıştırma:** ~1 km hücrede aynı yıl ≥ 5 gün ve ≥ 4 ay sinyal → statik endüstriyel kaynak; diğerleri dinamik biyokütle yangını.

$$d = 2R \arcsin\sqrt{\sin^2\tfrac{\Delta\phi}{2} + \cos\phi_1\cos\phi_2\sin^2\tfrac{\Delta\lambda}{2}},\ R = 6371.0\text{ km}$$

**Konuşma:** "Katsayıları biz uydurmuyoruz; iki sensörün aynı anda gördüğü yangınlardan, seçilen bölgenin kendi verisinden öğreniyoruz."

---

## Slayt 5 — Yanma Aktivitesi Takvimi ve Karşılaştırma (Nasıl? — 2)

| Ölçüt | MODIS | VIIRS | KÖZ Atlas |
|---|---|---|---|
| Birim | 1 km piksel | 375 m piksel | Harmonize olay / aktif yangın hücre-günü |
| Mükerrer piksel | — | Var | Kümelemeyle birleştirilir |
| Uydu sayısı etkisi | — | Var | Hücre-gün tekilleştirmesi |
| FRP | Referans | Farklı ölçek | MODIS eşdeğerine kalibre |
| Gaz bacaları | Karışık | Karışık | Ayrı katman |

- **Yanma Aktivitesi Takvimi:** Yıl × Ay ısı matrisi; seçilen ay → tarihsel medyana oran, yüzdelik, Ç1–Ç3 bandı.
- **CSV çıktısı:** `koz_atlas_harmonized_hotspots.csv` (olay kimliği, sensör etiketi, birleşen piksel, kalibre FRP, MODIS-eşdeğer ağırlık, statik/dinamik sınıf).
- *Sentetik doğrulama senaryosu (gerçek veri değil):* 2012 öncesi/sonrası ortalama oranı ham toplamda 3.8×, KÖZ MODIS-eşdeğer seride 1.11×; tasarlanan 6 statik kaynağın 6'sı ayrıştırıldı.

**Konuşma:** "Takvim görevin ana çıktısı: 'Bu temmuz normal mi?' sorusuna sensörden bağımsız cevap verir."

---

## Slayt 6 — Canlı Ürün ve Etki (Ne Kazandırır?)

- Canlı uygulama: koz-atlas-gbqjscepvmqcaygzbjlxhq.streamlit.app · Açık kaynak: github.com/MehmetHalilKILIC/koz-atlas
- Mimari: Python · Pandas/NumPy/SciPy (KD-ağacı, seyrek grafik) · Streamlit · Folium · Plotly
- 4 sekme: CBS haritası · Yanma Aktivitesi Takvimi · Harmonizasyon kanıtı · CSV indirme
- Anahtarsız demo modu + canlı FIRMS API + arşiv CSV yükleme
- **Kimin işine yarar:** afet yöneticileri (sezon kıyası), erken uyarı birimleri (statik kaynak yanlış alarmlarını ayıklama), araştırmacılar (2000'den bugüne tutarlı seri).

**Konuşma:** "Uygulama şu an çalışıyor; jüri kendi bölgesini ve tarih aralığını seçip sonucu CSV olarak indirebilir."

---

## Slayt 7 — Kaynakça ve Erişim

1. NASA Space Apps Challenge 2026 — Harmonization of MODIS and VIIRS Hot Spots: https://www.spaceappschallenge.org/2026/challenges/modis-and-viirs-hot-spots/
2. NASA Space Apps GitHub tartışması ve FIRMS Area API kılavuzu (#2016): https://github.com/nasa/spaceapps/discussions/2016
3. KÖZ Atlas canlı web uygulaması: https://koz-atlas-gbqjscepvmqcaygzbjlxhq.streamlit.app/
4. KÖZ Atlas açık kaynak deposu: https://github.com/MehmetHalilKILIC/koz-atlas

**Konuşma:** "Teşekkürler. Sorularınızı canlı uygulama üzerinde cevaplayabiliriz."
