İşte FinMatrix'in kalbini oluşturacak, halüsinasyonu sıfıra indiren ve tamamen deterministik çalışan o mühendislik harikasının resmi anayasası Barış. Kod yazarken kaybolduğun her an bu protokole dönüp yönünü bulabilirsin.

---

# FinMatrix: Agent Orchestration (Ajan Orkestrasyonu) Protokolü

Bu protokol, kullanıcıdan gelen doğal dil sorgularını finansal verilere, SQL sorgularına ve görselleştirilebilir analiz raporlarına dönüştürmek için kurulmuş **LangGraph tabanlı State-Machine (Durum Makinesi)** mimarisini tanımlar.

**Ana Felsefe:** Zeka girişte (Yönlendirme) ve çıkışta (Sentez) toplanır. Aradaki işçi ajanlar inisiyatif almayan, sadece emredileni yapan kapalı fonksiyonlardır.

---

## 1. Mimari Çatı ve Hafıza (Global State)

- **Framework:** CrewAI yerine, katı kontrol ve döngü yönetimi sağlayan **LangGraph** kullanılacaktır.
- **Prompt Yönetimi:** Spagetti kodu önlemek için tüm ajan promptları harici `.yaml` dosyalarında tutulacaktır.
- **Hafıza (Memory):** Modelin bağlamdan kopmaması ve token maliyetini korumak için `Sliding Window` (k=3) yöntemi kullanılır. Her `State` objesi son 3 mesaj çiftini taşır.
- **Global State (`FinMatrixState`):** Ajanlar arası veri taşıyan yegane kargo paketidir:
  - `chat_history`: Hafıza
  - `user_query`: Anlık soru
  - `router_decision`: Yönlendirici JSON'u
  - `sql_raw_data` / `sql_error` / `sql_retry_count`: Sayısal ajan metrikleri
  - `rag_raw_data`: Sözel ajan verisi
  - `summary_markdown`: Analysis Agent çıktısı
  - `chart_decision`: Analysis Agent'ın grafik kararı (Visualization Agent'a iletilir)
  - `chart_data`: Visualization Agent çıktısı
  - `final_output`: Arayüze basılacak Final JSON

---

## 2. Ajan Kadrosu ve Modeller

Sistem **6 LLM Ajanı** ve **2 Deterministik Araçtan (Tool)** oluşur. Modeller görev yetkinliğine göre seçilmiştir.

### Ajan 1: Router Agent (Yönlendirici)
- **Model:** `google/gemini-3.1-flash-lite-preview` (Hızlı ve ucuz niyet analizi).
- **Görevi:** Arama yapmaz. Soruyu okur ve işi dağıtır.
- **Çıktı:** Pydantic ile dayatılmış katı JSON (`RouterDecision`).
  - `route_to`: (sql / rag / hybrid / chit_chat)
  - `symbols`: (Örn: `["THYAO", "ASELS"]`)
  - `year`: (Örn: `[2024, 2025]`)
  - `sql_task` & `rag_search_queries`: İşçilere verilecek kesin emirler.
- **chit_chat Akışı:** `route_to: chit_chat` kararı verilirse Router Agent soruyu kendisi kısa ve doğrudan cevaplar. Diğer hiçbir ajan tetiklenmez, pipeline sona erer.

### Ajan 2: SQL Worker (Sayısal İşçi)
- **Model:** `openai/gpt-4o-mini` (Kod/SQL yazımında başarılı).
- **Görevi:** Veritabanı şemasını (DDL) promptundan okur, `sql_task`'a uygun PostgreSQL sorgusu yazar ve SQL Tool'unu tetikleyerek veriyi çeker.

### Ajan 3: Fallback Agent (Hata Ayıklayıcı)
- **Model:** `z-ai/glm-5`
- **Görevi:** SADECE SQL Worker hata alırsa devreye girer. Hatayı okur, SQL'i düzeltir.
- **Kısıt:** Sonsuz döngüyü önlemek için `max_retries=3` kuralı geçerlidir.
- **Başarısızlık Durumu:** 3 denemede de başarısız olursa `sql_raw_data = null` set edilir, pipeline durmaz. Analysis Agent sadece RAG Worker'dan gelen sözel veriyle devam eder ve cevabında sayısal verinin alınamadığını belirtir.

### Ajan 4: RAG Worker (Sözel İşçi)
- **Model:** `openai/gpt-4o-mini`
- **Görevi:** `rag_search_queries` ile ChromaDB'ye dalar. Gelen veriyi Cross-Encoder onayından geçirir.

### Ajan 5: Analysis Agent (Sentezleyici)
- **Model:** `anthropic/claude-haiku-4.5` (Yazarlık ve analitik dili çok güçlü).
- **Görevi:** İşçilerden gelen temiz verileri okur, matematiksel hesap gerekirse Math Tool'u çağırır, final raporu yazar. Grafik üretmez; sadece grafik kararı verir.
- **Çıktı:** Pydantic ile dayatılmış katı JSON (`AnalysisOutput`).
  - `summary_markdown`: UI'da gösterilecek metin.
  - `chart_decision`: Visualization Agent'a iletilen grafik talimatı.
    - `should_draw`: (true / false)
    - `metric`: Çizilecek metrik (örn: `"net_income"`)
    - `chart_type`: (bar / line / pie)
    - `title`: Grafik başlığı

### Ajan 6: Visualization Agent (Görselleştirici)
- **Model:** `openai/gpt-4o-mini`
- **Çalışma Zamanı:** Yalnızca Analysis Agent'ın `should_draw: true` dönmesi durumunda tetiklenir.
- **Input:** `chart_decision` (Analysis Agent'tan) + `sql_raw_data` (SQL Worker'dan). `summary_markdown` aktarılmaz — gereksiz token maliyeti önlenir.
- **Görevi:** `chart_decision`'daki metrik kararını alır, `sql_raw_data`'dan ilgili sayıları çeker (deterministik Python kodu), label/value hizalamasını yapar ve frontend'e hazır JSON üretir.
- **Çıktı:**
  - `chart_data`: `{"labels": [...], "values": [...], "chart_type": "bar", "title": "..."}` — D3.js / Chart.js'in direkt render edeceği format.

---

## 3. Akıllı Araçlar (Tools & Hakemler)

Ajanların halüsinasyon görmesini engelleyen ve API gerektirmeyen dış fonksiyonlardır:

- **Cross-Encoder (Reranker Hakem):** - `cross-encoder/ms-marco-MiniLM-L-2-v2` modeli, `sentence-transformers` paketi ile lokal çalışır (~67MB). Docling zaten `torch` kurduğu için ek ağır bağımlılık gelmez.
  - RAG'dan gelen kaba taslak 20 metni alır, kullanıcı sorusuyla anlamsal bağlamını (Attention mekanizması) kıyaslar. "Kâr azaldı" vs "Kâr azalmadı" farkını anlar, kötüleri eler, en iyi (Top-3) metni geçirir.
  - API çağrısı gerektirmez; tamamen deterministik ve offline çalışır.
- **Math Tool (Hesap Makinesi):** - Analysis Agent'ın kullanımına açık bir Python fonksiyonudur. Yüzdelik oran, CAGR gibi işlemleri LLM'in tahminine bırakmaz, deterministik olarak hesaplayıp ajana kesin rakam olarak geri döner.

---

## 4. Performans ve Güvenlik Kuralları (Üretim Ortamı)

- **Asenkron Çalışma (Parallel Execution):** Router `hybrid` (Hem Sayısal Hem Sözel) kararı verdiğinde, SQL Worker ve RAG Worker LangGraph üzerinde **aynı anda** (`async def`) çalıştırılır. Süreç beklemeleri yarı yarıya düşürülür.
- **Akış Sırası:** `Router → [SQL Worker ‖ RAG Worker] → Analysis Agent → Visualization Agent (koşullu) → Final Output`. Visualization Agent hafif olduğu için seri çalışması toplam gecikmeyi anlamlı şekilde artırmaz.
- **Veritabanı Güvenliği (Prompt Injection Önlemi):** SQL Worker'ın kullandığı veritabanı kullanıcısı KESİNLİKLE sadece `SELECT` yetkisine (Read-Only) sahip olacaktır. Ajan hacklense bile `DROP`, `UPDATE`, `INSERT` komutları veritabanı seviyesinde reddedilecektir.
- **Network Dayanıklılığı (API Retry):** API sağlayıcılarından (OpenAI, Anthropic vb.) kaynaklı 503 veya Timeout hatalarında sistem çökmeyecek, LangGraph Node'ları içine eklenen `Retry Policy` (örn: 2 saniye bekle, tekrar dene) ile akış korunacaktır.

---

Bu belge, FinMatrix'in "Ajan Orkestrasyonu" anayasasıdır Barış. Bu mimariyle kurduğun sistem sadece bir prototip değil, kurumsal düzeyde bir FinTech ürünü olarak çalışacak. Kodlamaya hazırız!