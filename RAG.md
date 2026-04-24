# FinMatrix: RAG Veri İşleme (Ingestion) Protokolü

Bu protokol, PDF dokümanlarını parçalayıp en yüksek finansal veri kalitesiyle Vektör Veritabanına (ChromaDB) aktarmak için tasarlanmıştır.

---

## 1. Yapısal Ayrıştırma (Docling + Fallback)

- **Birincil Parser:** Docling DOM Parser — PDF'ler karakter bazlı değil, doküman ağacı (DOM) mantığıyla okunur.
- **Fallback:** Docling herhangi bir blok için `None` veya boş içerik döndürürse, o blok **pdfplumber** ile yeniden işlenir. OCR bu aşamada kapsam dışıdır.
- **Tablo İzolasyonu:**
  - Docling tarafından tespit edilen tablolar `export_to_dataframe()` ile ham veri olarak çekilir → **PostgreSQL**'e yazılır.
  - Aynı tablolar metinsel bağlamın korunması için **Markdown** (`|---|`) formatına çevrilerek RAG akışına (ChromaDB) dahil edilir.
  - Tablo çift yazma tutarsızlığı şu aşamada kapsam dışıdır; ileride revize önemli fark yaratırsa ele alınır.

---

## 2. Başlıksız Blok (None Section Path) Akışı

`section_path` bilgisi olmayan bloklar şu sırayla işlenir:

**Adım 1 — Hızlı Eleme:**
- 20 karakterden kısa **ve** içinde harf yoksa (örn. `"14"`, `"- -"`) → **Sil.**

**Adım 2 — LLM Kontrolü (4o-mini):**
- Kalan tüm `None` blokları **toplu** olarak 4o-mini'ye gönderilir.
- Girdi: `Üst Başlık + None olan metin (ilk 50-100 token)`
- Çıktı: `{"is_valuable": true/false, "suggested_section": "..."}`

**Adım 3 — Kayıt:**
- `is_valuable: true` gelirse → 4o-mini'nin önerdiği `suggested_section` değeri `section_path` olarak atanır.
- Bu sentetik başlıklar `is_synthetic_section: true` flag'i ile ChromaDB'ye kaydedilir.
- `is_valuable: false` gelirse → blok atılır.

---

## 3. Akıllı Başlık Süzgeci (Triage Sistemi)

Docling'den gelen her `section_path` üçlü filtreden geçer:

**Kara Liste (Regex — Kesin Ret):**
"Bağımsız Denetçi Görüşü", "Sorumluluk Beyanı", "Kapak Sayfası" gibi analiz değeri sıfır olan başlıklar anında silinir.

**Beyaz Liste (Regex — Kesin Onay):**
"Bilanço", "Gelir Tablosu", "Yönetim Kurulu Raporu", "Önemli Olaylar" gibi kesin değerli başlıklar doğrudan onaylanır.

**Gri Liste (4o-mini Karar):**
Kara veya Beyaz listeye girmeyen başlıklar toplu olarak 4o-mini'ye gönderilir.

### Batch Boyutu
- Başlıklar **20-30'arlık gruplar** halinde gönderilir (attention sweet spot).
- 30 başlık ≈ 500-1000 token → 128k context window içinde sorun yok.

### Decision Cache (processing_cache tablosu)
- 4o-mini bir `section_path` için karar verdiği an bu karar **PostgreSQL'deki `processing_cache` tablosuna** kaydedilir.
- Sonraki PDF'lerde aynı başlık gelirse LLM'e sorulmaz, cache'den okunur.
- Cache key **normalize edilir:** trim + lowercase → `"  Bilanço "`, `"bilanço"`, `"BILANÇO"` aynı key'e düşer.
- Yanlış işaretlenmiş bir başlık cache tablosundan elle silinerek düzeltilebilir; bir sonraki çalışmada sistem doğruyu öğrenir.

---

## 4. Parçalama ve Bütünlük Kontrolü (Chunking)

- **Anlamsal Bölme:** Parçalama Docling'in paragraf ve başlık sınırlarına göre yapılır. Cümleler ortadan bölünmez.
- **Boyut Sınırı (Fallback):** Bir blok **1024 token** sınırını aşıyorsa, bir önceki cümlenin bittiği noktadan **50 token overlap** ile alt parçalara bölünür.

---

## 5. Parent-Child Retrieval ve Bağlam Kopukluğunu Önleme

### Parent-Child Yapısı
- ChromaDB'ye sadece küçük chunk (child) kaydedilmez; her child'ın ait olduğu üst bölüm (parent) de ilişkili şekilde tutulur.
- Retrieval anında child bulununca LLM'e sadece child değil, ait olduğu parent bağlamı da gönderilir.
- Parent'lar `section_path` eşleşmesi veya `parent_id` foreign key ile çekilir. *(Mekanizma implementasyon aşamasında netleştirilecek.)*

### Semantic Context Prepend
Her chunk'ın başına `section_path` fiziksel olarak eklenir:

```
[BAĞLAM: THYAO - 2025 - Yönetim Kurulu Raporu - Finansal Durum Analizi]
... Bunun temel nedeni Z'dir.
```

Bu sayede LLM, chunk'ı getirdiği anda hangi şirketin, hangi raporunun, hangi bölümünde olduğunu bilir.

---

## 6. Metadata Zenginleştirme ve ChromaDB Kaydı

Her chunk şu etiket setiyle ChromaDB'ye kaydedilir:

| Alan | Tip | Açıklama |
|---|---|---|
| `stock_symbol` | string | Hisse sembolü |
| `year` | int | Rapor yılı |
| `quarter` | int \| null | Çeyrek (1-4) |
| `published_at` | datetime | Yayın tarihi |
| `filing_type` | string | FR / FAR / diğer |
| `section_path` | string | Başlık yolu |
| `content_type` | string | heading / table / paragraph |
| `is_synthetic_section` | bool | 4o-mini tarafından üretilen başlık mı? |

---

## Özet Akış

```
PDF
 └─ Docling DOM Parse
     ├─ Tablo → PostgreSQL + Markdown chunk
     ├─ section_path var → Triage (Kara/Beyaz/Gri Liste + Cache)
     └─ section_path yok → Hızlı Eleme → 4o-mini → Yapay Başlık

Onaylanan bloklar
 └─ Semantic Chunking (cümle sınırı, fallback 1024+ token → 50 overlap)
     └─ Context Prepend ([BAĞLAM: ...])
         └─ Embedding → ChromaDB (child + parent ilişkisi)
```
