"""
Пилот SEO-статей для id/ar (GLOBAL_EXPANSION_PLAN.md G5 Tier 3).

Генерирует ЧЕРНОВИКИ (is_published=False) оригинальных статей под конкретный
рынок — НЕ переводы русских статей (см. §4.3 плана: блог должен получить
самостоятельный контент на язык, а не modeltranslation-подстановку). Каждая
статья проходит два LLM-вызова: draft (полный текст + FAQ) и self-critique
(редакторская правка, поиск генерик-фраз/галлюцинаций), плюс короткий
english_gloss в конце — краткое изложение по-английски, чтобы можно было
проверить факты, не читая id/ar свободно.

Публикация — намеренно НЕ часть этой команды. Ни разработчик, ни пользователь
не читают индонезийский/арабский свободно, поэтому единственная безопасная
QC здесь — структурная (длина, HTML, FAQ, факты по english_gloss). Реальное
качество прозы должен подтвердить носитель языка перед is_published=True —
Google прямо предупреждает про "scaled content abuse" при публикации
низкокачественного AI-контента большими партиями.

Запуск:
  python manage.py generate_seo_articles --pilot          # 2 статьи на язык
  python manage.py generate_seo_articles                  # весь список брифов
  python manage.py generate_seo_articles id                # только id
  python manage.py generate_seo_articles --force            # перегенерировать существующие slug'и
"""
import logging
import re

from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)

MODEL = 'claude-sonnet-5'

LOCALE_META = {
    'id': {'name': 'Indonesian', 'market': 'Indonesia'},
    'ar': {'name': 'Modern Standard Arabic (MENA-neutral, readable across Egypt/Gulf/Levant/Morocco)', 'market': 'MENA (Egypt, Gulf states, Morocco)'},
    'fa': {'name': 'Persian (contemporary standard Persian, the register of tech media like Digiato/Zoomit)', 'market': 'Persian-speaking users (Iran and diaspora)'},
    'tr': {'name': 'Turkish (contemporary tech-journalism register like Webrazzi/ShiftDelete)', 'market': 'Turkey'},
}

DO_NOT_TRANSLATE = ['GPT-4o', 'Claude', 'Gemini', 'Sora', 'Veo', 'Kling', 'DALL-E', 'Flux', 'aineron', 'Telegram', 'USDT', 'TON']

# --------------------------------------------------------------------------
# Брифы (GLOBAL_EXPANSION_PLAN.md §4.3, §6). Для ar/fa сознательно НЕ
# используем рамку "обход блокировки/цензуры/санкций" — юридический вопрос
# по санкционным регионам не решён (см. project_telegram_supremacy §7).
# Для fa дополнительно НЕТ отдельной статьи про оплату: платёжная тема для
# Ирана упирается в санкционный вопрос напрямую, кредитная модель упоминается
# только нейтрально внутри других статей. Фокус ar: оплата без международной
# карты, сравнение по цене/гибкости, студенческие/бизнес-кейсы. Фокус tr:
# экономика подписок в валюте vs оплата по использованию (без конкретных цен).
# Без конкретных цифр цен в тексте нигде (дрейфуют).
# --------------------------------------------------------------------------
BRIEFS = {
    'id': [
        dict(
            slug='chatgpt-vs-claude-vs-gemini-2026-perbandingan',
            title_hint='ChatGPT vs Claude vs Gemini: mana yang terbaik untuk kebutuhanmu di 2026',
            keywords=['ChatGPT vs Claude vs Gemini', 'AI terbaik 2026', 'perbandingan model AI Indonesia'],
            search_intent='comparison',
            angle='Bukan sekadar daftar spesifikasi — kerangka keputusan praktis: kualitas bahasa Indonesia per model, jenis tugas (menulis, coding, riset), dan model harga (langganan vs bayar-per-pakai).',
            must_include_facts=[
                'aineron menyediakan akses ke GPT-4o, Claude, dan Gemini dalam satu antarmuka',
                'sistem kredit bayar-per-pesan, tanpa keharusan langganan bulanan',
                'pembayaran kripto (USDT/TON) tersedia sebagai alternatif',
                'tidak perlu VPN untuk mengakses',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='cara-membayar-ai-tanpa-kartu-kredit-internasional',
            title_hint='Cara membayar layanan AI premium tanpa kartu kredit internasional',
            keywords=['bayar ChatGPT tanpa kartu kredit', 'AI tanpa kartu internasional', 'pembayaran kripto AI'],
            search_intent='transactional/informational',
            angle='Masalah nyata: banyak pengguna Indonesia kesulitan mendapatkan kartu kredit berdenominasi USD untuk langganan AI luar negeri. Solusi praktis lewat kredit prabayar dan kripto, bukan janji generik.',
            must_include_facts=[
                'aineron menerima pembayaran kripto (USDT/TON) selain metode lain',
                'sistem kredit — beli sesuai kebutuhan, tanpa kartu internasional',
                'tidak ada penguncian langganan bulanan',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5'],
        ),
        dict(
            slug='ai-generator-gambar-untuk-umkm-panduan-praktis',
            title_hint='Panduan AI generator gambar untuk UMKM: foto produk, konten sosial, iklan',
            keywords=['AI generator gambar UMKM', 'AI foto produk', 'AI untuk bisnis kecil'],
            search_intent='how-to',
            angle='Studi kasus konkret UMKM (kuliner, fashion, kerajinan) — bukan tutorial generik "cara pakai AI", tapi alur kerja nyata dari brief ke hasil siap posting.',
            must_include_facts=[
                'aineron menyediakan beberapa model generator gambar (mis. Flux, DALL-E, GPT-image) dalam satu platform',
                'biaya dihitung per generasi, bisa disesuaikan skala kebutuhan UMKM',
            ],
            related_model_hints=['flux', 'dall-e', 'gpt-image'],
        ),
        dict(
            slug='sora-veo-kling-perbandingan-ai-video-2026',
            title_hint='Sora vs Veo vs Kling: AI video mana yang cocok untuk kebutuhanmu',
            keywords=['Sora vs Veo vs Kling', 'AI video terbaik 2026', 'bikin video AI'],
            search_intent='comparison',
            angle='Perbandingan berbasis use-case: video pendek media sosial vs iklan profesional vs eksperimen kreatif, termasuk pertimbangan durasi dan resolusi tiap model.',
            must_include_facts=[
                'aineron memberi akses ke Sora, Veo, dan Kling dalam satu platform',
                'biaya per generasi video, bukan langganan',
            ],
            related_model_hints=['sora', 'veo-3-1', 'kling'],
        ),
        dict(
            slug='ai-untuk-tugas-kuliah-dan-riset-panduan-etis',
            title_hint='Menggunakan AI untuk tugas kuliah dan riset secara etis dan efektif',
            keywords=['AI untuk tugas kuliah', 'AI riset akademik', 'AI untuk skripsi'],
            search_intent='informational/FAQ',
            angle='Posisi jelas: AI sebagai asisten riset/ringkasan/brainstorming, bukan alat plagiarisme. Format FAQ padat menjawab pertanyaan praktis mahasiswa.',
            must_include_facts=[
                'aineron mendukung pencarian web terintegrasi untuk riset berbasis sumber terkini',
                'akses ke beberapa model LLM untuk membandingkan sudut pandang/analisis',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='chatgpt-plus-vs-aineron-mana-lebih-hemat',
            title_hint='ChatGPT Plus vs platform multi-model: mana yang lebih hemat dan fleksibel',
            keywords=['ChatGPT Plus alternatif', 'AI lebih murah', 'bayar AI per pemakaian'],
            search_intent='comparison/transactional',
            angle='Trade-off jujur: langganan tetap satu vendor vs bayar-sesuai-pakai lintas banyak model. Kapan masing-masing masuk akal, bukan klaim "selalu lebih murah".',
            must_include_facts=[
                'aineron menawarkan akses ke banyak model (bukan satu vendor) dengan sistem kredit',
                'tanpa komitmen bulanan — kredit dipakai sesuai kebutuhan',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
    ],
    'ar': [
        dict(
            slug='chatgpt-vs-claude-vs-gemini-2026-comparison-ar',
            title_hint='مقارنة شاملة بين ChatGPT وClaude وGemini في 2026: أيها الأنسب لك',
            keywords=['مقارنة ChatGPT وClaude وGemini', 'أفضل نموذج ذكاء اصطناعي 2026', 'الذكاء الاصطناعي باللغة العربية'],
            search_intent='comparison',
            angle='التركيز على معيار غالبًا ما يُهمل: جودة التعامل مع اللغة العربية الفصحى واللهجات لكل نموذج، إضافة لمعايير عملية (الكتابة، البرمجة، البحث) بدل سرد المواصفات فقط.',
            must_include_facts=[
                'توفر aineron الوصول إلى GPT-4o وClaude وGemini من واجهة واحدة',
                'نظام رصيد يُدفع فيه حسب الاستخدام، دون اشتراك شهري إلزامي',
                'إمكانية الدفع بالعملات الرقمية (USDT/TON) كخيار إضافي',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='ai-payment-without-international-card-mena',
            title_hint='كيف تدفع مقابل أدوات الذكاء الاصطناعي بدون بطاقة ائتمان دولية',
            keywords=['الدفع بدون بطاقة ائتمان دولية', 'دفع مقابل ChatGPT بالعملات الرقمية', 'اشتراك AI بدون فيزا دولية'],
            search_intent='transactional/informational',
            angle='مشكلة واقعية لمستخدمي مصر ودول الخليج والمغرب: صعوبة إصدار بطاقة دولية أو قيود العملة. الحل عملي عبر الرصيد المسبق والعملات الرقمية، دون وعود عامة.',
            must_include_facts=[
                'aineron يقبل الدفع بالعملات الرقمية (USDT/TON) بديلاً عن البطاقات الدولية',
                'نظام رصيد — تشتري ما تحتاجه فقط، دون التزام شهري',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5'],
        ),
        dict(
            slug='sora-veo-kling-video-ai-comparison-ar',
            title_hint='مقارنة بين Sora وVeo وKling لإنشاء الفيديو بالذكاء الاصطناعي',
            keywords=['مقارنة Sora وVeo وKling', 'أفضل أداة فيديو بالذكاء الاصطناعي', 'إنشاء فيديو بالذكاء الاصطناعي 2026'],
            search_intent='comparison',
            angle='مقارنة حسب حالة الاستخدام: محتوى قصير لوسائل التواصل مقابل إعلانات احترافية مقابل تجارب إبداعية، مع فروقات المدة والدقة الفعلية لكل نموذج.',
            must_include_facts=[
                'توفر aineron الوصول إلى Sora وVeo وKling ضمن منصة واحدة',
                'التكلفة تُحتسب لكل عملية إنشاء فيديو، دون اشتراك ثابت',
            ],
            related_model_hints=['sora', 'veo-3-1', 'kling'],
        ),
        dict(
            slug='ai-image-generation-tools-arabic-business',
            title_hint='أفضل أدوات الذكاء الاصطناعي لتوليد الصور للأعمال الصغيرة والتسويق',
            keywords=['أدوات الذكاء الاصطناعي لتوليد الصور', 'صور منتجات بالذكاء الاصطناعي', 'تسويق بالذكاء الاصطناعي'],
            search_intent='how-to',
            angle='أمثلة عملية لأصحاب المشاريع الصغيرة (مطاعم، أزياء، حرف يدوية) — سير عمل فعلي من الفكرة إلى صورة جاهزة للنشر، وليس شرحًا عامًا.',
            must_include_facts=[
                'aineron يوفر عدة نماذج لتوليد الصور (مثل Flux وDALL-E وGPT-image) في مكان واحد',
                'التكلفة محسوبة لكل صورة، مما يناسب الميزانيات الصغيرة',
            ],
            related_model_hints=['flux', 'dall-e', 'gpt-image'],
        ),
        dict(
            slug='chatgpt-plus-alternative-mena-2026',
            title_hint='بديل ChatGPT Plus في 2026: كيف تصل لعدة نماذج ذكاء اصطناعي بمرونة أكبر',
            keywords=['بديل ChatGPT Plus', 'الدفع حسب الاستخدام بدل الاشتراك', 'مقارنة أسعار الذكاء الاصطناعي'],
            search_intent='comparison/transactional',
            angle='مقارنة صادقة بين الاشتراك الثابت لمزود واحد والدفع حسب الاستخدام عبر عدة نماذج — متى يكون كل خيار منطقيًا، دون ادعاء أن أحدهما "أرخص دائمًا".',
            must_include_facts=[
                'aineron يتيح الوصول لعدة نماذج عبر نظام رصيد واحد',
                'لا يوجد التزام شهري — الرصيد يُستخدم حسب الحاجة الفعلية',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='ai-tools-for-students-arabic',
            title_hint='أفضل أدوات الذكاء الاصطناعي للطلاب الجامعيين والباحثين',
            keywords=['الذكاء الاصطناعي للطلاب', 'أدوات بحث أكاديمي بالذكاء الاصطناعي', 'الذكاء الاصطناعي وكتابة الأبحاث'],
            search_intent='informational/FAQ',
            angle='موقف واضح: الذكاء الاصطناعي كمساعد بحث وتلخيص وعصف ذهني، وليس أداة للانتحال. قسم أسئلة شائعة كثيف يجيب عن استفسارات الطلاب العملية.',
            must_include_facts=[
                'aineron يدعم البحث المدمج على الويب لأبحاث تعتمد على مصادر حديثة',
                'إمكانية مقارنة إجابات عدة نماذج LLM لنفس السؤال البحثي',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
    ],
    'fa': [
        dict(
            slug='chatgpt-vs-claude-vs-gemini-2026-farsi-comparison',
            title_hint='مقایسه ChatGPT و Claude و Gemini در ۲۰۲۶: کدام برای شما مناسب‌تر است',
            keywords=['مقایسه ChatGPT و Claude و Gemini', 'بهترین هوش مصنوعی ۲۰۲۶', 'هوش مصنوعی به زبان فارسی'],
            search_intent='comparison',
            angle='تمرکز بر معیاری که مقایسه‌های انگلیسی‌زبان پوشش نمی‌دهند: کیفیت درک و تولید متن فارسی در هر مدل، به‌علاوه چارچوب تصمیم عملی بر اساس نوع کار (نوشتن، برنامه‌نویسی، پژوهش).',
            must_include_facts=[
                'aineron دسترسی به GPT-4o و Claude و Gemini را از یک رابط واحد فراهم می‌کند',
                'سیستم اعتباری پرداخت به‌ازای استفاده، بدون اجبار به اشتراک ماهانه',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='sora-veo-kling-video-ai-farsi-comparison',
            title_hint='مقایسه Sora و Veo و Kling برای ساخت ویدیو با هوش مصنوعی',
            keywords=['مقایسه Sora و Veo و Kling', 'ساخت ویدیو با هوش مصنوعی', 'بهترین ابزار ویدیوی هوش مصنوعی ۲۰۲۶'],
            search_intent='comparison',
            angle='مقایسه بر اساس کاربرد واقعی: محتوای کوتاه شبکه‌های اجتماعی در برابر تبلیغات حرفه‌ای در برابر تجربه‌های خلاقانه، با تفاوت‌های عملی هر مدل.',
            must_include_facts=[
                'aineron دسترسی به Sora و Veo و Kling را در یک پلتفرم فراهم می‌کند',
                'هزینه به‌ازای هر تولید ویدیو محاسبه می‌شود، نه اشتراک ثابت',
            ],
            related_model_hints=['sora', 'veo-3-1', 'kling'],
        ),
        dict(
            slug='ai-image-generation-small-business-farsi',
            title_hint='ابزارهای هوش مصنوعی تولید تصویر برای کسب‌وکارهای کوچک',
            keywords=['تولید تصویر با هوش مصنوعی', 'عکس محصول با هوش مصنوعی', 'هوش مصنوعی برای کسب‌وکار کوچک'],
            search_intent='how-to',
            angle='سیر کار عملی برای صاحبان کسب‌وکارهای کوچک (رستوران، پوشاک، صنایع‌دستی) از ایده تا تصویر آماده انتشار در اینستاگرام و تلگرام — نه توضیح نظری.',
            must_include_facts=[
                'aineron چند مدل تولید تصویر (مانند Flux و DALL-E و GPT-image) را در یک پلتفرم ارائه می‌دهد',
                'هزینه به‌ازای هر تصویر محاسبه می‌شود و با بودجه‌های کوچک سازگار است',
            ],
            related_model_hints=['flux', 'dall-e', 'gpt-image'],
        ),
        dict(
            slug='ai-tools-for-students-farsi',
            title_hint='بهترین ابزارهای هوش مصنوعی برای دانشجویان و پژوهشگران',
            keywords=['هوش مصنوعی برای دانشجویان', 'هوش مصنوعی و پایان‌نامه', 'ابزار پژوهش با هوش مصنوعی'],
            search_intent='informational/FAQ',
            angle='موضع روشن: هوش مصنوعی به‌عنوان دستیار پژوهش و خلاصه‌سازی و ایده‌پردازی، نه ابزار تقلب. بخش پرسش‌های متداول فشرده برای سوالات عملی دانشجویان.',
            must_include_facts=[
                'aineron جستجوی وب یکپارچه برای پژوهش مبتنی بر منابع به‌روز را پشتیبانی می‌کند',
                'امکان مقایسه پاسخ چند مدل LLM برای یک پرسش پژوهشی واحد',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='chatgpt-plus-alternative-pay-per-use-farsi',
            title_hint='جایگزین ChatGPT Plus در ۲۰۲۶: پرداخت به‌ازای استفاده به‌جای اشتراک ثابت',
            keywords=['جایگزین ChatGPT Plus', 'پرداخت به‌ازای استفاده هوش مصنوعی', 'مقایسه هزینه مدل‌های هوش مصنوعی'],
            search_intent='comparison/transactional',
            angle='مقایسه صادقانه بین اشتراک ثابت یک شرکت و پرداخت به‌ازای استفاده از چند مدل — چه زمانی هر گزینه منطقی است، بدون ادعای اینکه یکی همیشه ارزان‌تر است.',
            must_include_facts=[
                'aineron دسترسی به چند مدل را با یک سیستم اعتباری واحد فراهم می‌کند',
                'تعهد ماهانه وجود ندارد — اعتبار بر اساس نیاز واقعی مصرف می‌شود',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='ai-content-creation-instagram-telegram-farsi',
            title_hint='تولید محتوا با هوش مصنوعی برای اینستاگرام و تلگرام: راهنمای عملی',
            keywords=['تولید محتوا با هوش مصنوعی', 'هوش مصنوعی برای اینستاگرام', 'ساخت محتوای فارسی با هوش مصنوعی'],
            search_intent='how-to',
            angle='سیر کار واقعی تولیدکنندگان محتوای فارسی‌زبان: از ایده تا کپشن و تصویر و ویدیوی کوتاه، با تمرکز بر کیفیت خروجی فارسی و اشتباهات رایجی که محتوا را مصنوعی جلوه می‌دهد.',
            must_include_facts=[
                'aineron مدل‌های متن و تصویر و ویدیو را در یک پلتفرم گرد هم می‌آورد',
                'سیستم اعتباری اجازه می‌دهد فقط به اندازه نیاز واقعی هزینه شود',
            ],
            related_model_hints=['gpt-4o', 'flux', 'sora'],
        ),
    ],
    'tr': [
        dict(
            slug='chatgpt-vs-claude-vs-gemini-2026-karsilastirma',
            title_hint='ChatGPT vs Claude vs Gemini: 2026\'da hangisi size daha uygun',
            keywords=['ChatGPT vs Claude vs Gemini', 'en iyi yapay zeka 2026', 'yapay zeka karşılaştırma Türkçe'],
            search_intent='comparison',
            angle='İngilizce karşılaştırmaların atladığı kriter: her modelin Türkçe anlama ve yazma kalitesi, artı görev tipine göre pratik karar çerçevesi (yazı, kod, araştırma).',
            must_include_facts=[
                'aineron, GPT-4o, Claude ve Gemini\'ye tek arayüzden erişim sağlar',
                'kullandıkça öde kredi sistemi, zorunlu aylık abonelik yok',
                'kripto ödeme (USDT/TON) ek seçenek olarak mevcut',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='yapay-zeka-abonelik-mi-kullandikca-ode-mi',
            title_hint='Yapay zeka için abonelik mi, kullandıkça ödeme mi? Dürüst bir hesaplaşma',
            keywords=['ChatGPT Plus alternatifi', 'kullandıkça öde yapay zeka', 'yapay zeka abonelik fiyatları'],
            search_intent='comparison/transactional',
            angle='Döviz kuruna bağlı sabit aboneliklerin öngörülemezliği ile kullandıkça ödemenin esnekliği arasında dürüst bir kıyas — hangi kullanım profiline hangisi mantıklı, "her zaman daha ucuz" iddiası olmadan.',
            must_include_facts=[
                'aineron birden fazla modele tek kredi sistemiyle erişim sunar',
                'aylık taahhüt yok — kredi gerçek ihtiyaca göre harcanır',
                'kripto ödeme (USDT/TON) ek seçenek olarak mevcut',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='sora-veo-kling-video-yapay-zeka-karsilastirma',
            title_hint='Sora vs Veo vs Kling: yapay zeka ile video üretiminde hangisi ne zaman',
            keywords=['Sora vs Veo vs Kling', 'yapay zeka video oluşturma', 'en iyi AI video aracı 2026'],
            search_intent='comparison',
            angle='Kullanım senaryosuna göre kıyas: kısa sosyal medya içeriği vs profesyonel reklam vs yaratıcı deneyler — her modelin pratik farklarıyla.',
            must_include_facts=[
                'aineron, Sora, Veo ve Kling\'e tek platformdan erişim sağlar',
                'ücret video üretimi başına hesaplanır, sabit abonelik yok',
            ],
            related_model_hints=['sora', 'veo-3-1', 'kling'],
        ),
        dict(
            slug='kobiler-icin-yapay-zeka-gorsel-uretimi-rehberi',
            title_hint='KOBİ\'ler için yapay zeka ile görsel üretimi: üründen paylaşıma pratik rehber',
            keywords=['yapay zeka görsel oluşturma', 'ürün fotoğrafı yapay zeka', 'KOBİ için yapay zeka'],
            search_intent='how-to',
            angle='Küçük işletme sahipleri (yemek, moda, el sanatları, e-ticaret) için gerçek iş akışı: fikirden Instagram/Trendyol\'a hazır görsele — teorik anlatım değil.',
            must_include_facts=[
                'aineron birden fazla görsel üretim modelini (ör. Flux, DALL-E, GPT-image) tek platformda sunar',
                'ücret görsel başına hesaplanır, küçük bütçelere uygundur',
            ],
            related_model_hints=['flux', 'dall-e', 'gpt-image'],
        ),
        dict(
            slug='ogrenciler-icin-yapay-zeka-etik-rehber',
            title_hint='Öğrenciler için yapay zeka: tezde ve ödevde etik ve etkili kullanım',
            keywords=['öğrenciler için yapay zeka', 'yapay zeka ile tez yazımı', 'akademik yapay zeka araçları'],
            search_intent='informational/FAQ',
            angle='Net duruş: yapay zeka araştırma asistanı, özetleyici ve beyin fırtınası ortağı — intihal aracı değil. Öğrencilerin pratik sorularına yoğun SSS bölümü.',
            must_include_facts=[
                'aineron güncel kaynaklara dayalı araştırma için entegre web aramasını destekler',
                'aynı araştırma sorusu için birden fazla LLM\'in yanıtını karşılaştırma imkânı',
            ],
            related_model_hints=['gpt-4o', 'claude-sonnet-5', 'gemini-3-pro'],
        ),
        dict(
            slug='icerik-ureticileri-icin-yapay-zeka-is-akisi',
            title_hint='İçerik üreticileri için yapay zeka iş akışı: fikirden yayına',
            keywords=['yapay zeka ile içerik üretimi', 'sosyal medya için yapay zeka', 'yapay zeka içerik araçları'],
            search_intent='how-to',
            angle='Türk içerik üreticilerinin gerçek iş akışı: fikir, başlık, görsel ve kısa video üretiminde yapay zekanın yeri — ve içeriği yapay gösteren yaygın hatalar.',
            must_include_facts=[
                'aineron metin, görsel ve video modellerini tek platformda bir araya getirir',
                'kredi sistemi yalnızca gerçek ihtiyaç kadar harcama yapmayı sağlar',
            ],
            related_model_hints=['gpt-4o', 'flux', 'sora'],
        ),
    ],
}


# --------------------------------------------------------------------------
# Формат ответа LLM: разделители-сентинелы, НЕ JSON.
#
# Изначально draft/critique просили JSON с content_html (многоабзацный HTML,
# 1500-2500 слов) внутри JSON-строки. claude-sonnet-5 через laozhang не
# гарантирует валидный json_object для такого объёма прозы — на практике
# ловили то ```json-обёртку поверх ответа, то обрыв по max_tokens, то
# неэкранированные кавычки/переводы строк внутри HTML, ломающие JSON
# (Invalid control character / Expecting ',' delimiter). Пост-хок починка
# парсера JSON с кавычками в прозе — путь без дна: probability одной
# сломанной статьи из N не падает к нулю с любым количеством патчей парсера.
# Решение — вообще не заворачивать прозу в JSON: точки-сентинелы, текст
# между ними берётся как есть, никакого экранирования не требуется.
# --------------------------------------------------------------------------
_SECTION_RE = re.compile(r'^===([A-Z_]+)===\s*$', re.MULTILINE)


def _split_sections(text):
    matches = list(_SECTION_RE.finditer(text))
    if not matches:
        raise RuntimeError(f'в ответе не найдено ни одного ===MARKER=== разделителя. Начало ответа: {text[:300]!r}')
    sections = {}
    for i, m in enumerate(matches):
        name = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[name] = text[start:end].strip()
    return sections


def _parse_faq(text):
    items = []
    question, answer_lines = None, []

    def _flush():
        if question and answer_lines:
            items.append({'question': question.strip(), 'answer': ' '.join(answer_lines).strip()})

    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('Q:'):
            _flush()
            question, answer_lines = stripped[2:].strip(), []
        elif stripped.startswith('A:'):
            answer_lines.append(stripped[2:].strip())
        elif stripped and answer_lines:
            answer_lines.append(stripped)
    _flush()
    return items


def _required(sections, response, *names):
    missing = [n for n in names if n not in sections]
    if missing:
        raise RuntimeError(
            f'в ответе отсутствуют секции {missing} (finish_reason={response.choices[0].finish_reason}). '
            f'Найденные секции: {list(sections)}'
        )


class Command(BaseCommand):
    help = 'Генерирует черновики SEO-статей (is_published=False) для id/ar через laozhang'

    def add_arguments(self, parser):
        parser.add_argument('locales', nargs='*', default=list(BRIEFS.keys()))
        parser.add_argument('--pilot', action='store_true', help='Только первые 2 брифа на язык (проверка перед полным батчем)')
        parser.add_argument('--force', action='store_true', help='Перегенерировать, даже если slug уже существует')

    def handle(self, *args, **options):
        from blog.models import Post
        from aitext.models import NeuralNetwork
        from aitext.providers import _get_raw_client

        locales = options['locales']
        unknown = [loc for loc in locales if loc not in BRIEFS]
        if unknown:
            self.stderr.write(f'Неизвестные локали: {unknown}. Доступны: {list(BRIEFS)}')
            return

        client = _get_raw_client('laozhang')

        for locale in locales:
            meta = LOCALE_META[locale]
            briefs = BRIEFS[locale]
            if options['pilot']:
                briefs = briefs[:2]

            self.stdout.write(f'[{locale}] брифов к обработке: {len(briefs)}')

            for brief in briefs:
                slug = brief['slug']
                if Post.objects.filter(slug=slug).exists() and not options['force']:
                    self.stdout.write(f'  [{locale}] {slug} — уже существует, пропуск (--force для перегенерации)')
                    continue

                try:
                    article = self._generate_article(client, locale, meta, brief)
                except Exception as e:
                    self.stderr.write(f'  [{locale}] {slug} — ошибка генерации: {e}')
                    continue

                related_ids = []
                for hint in brief.get('related_model_hints', []):
                    match = NeuralNetwork.objects.filter(slug__icontains=hint).first()
                    if match:
                        related_ids.append(match.id)

                post, created = Post.objects.update_or_create(
                    slug=slug,
                    defaults=dict(
                        title=article['title'],
                        language=locale,
                        category=None,
                        preview_text=article['preview_text'][:300],
                        content=article['content_html'],
                        is_published=False,
                        show_on_main=False,
                        seo_title=article.get('seo_title', '')[:200],
                        seo_description=article.get('seo_description', ''),
                        seo_keywords=article.get('seo_keywords', '')[:500],
                        faq_items=article.get('faq_items', []),
                    ),
                )
                if related_ids:
                    post.neural_networks.set(related_ids)

                self.stdout.write(self.style.SUCCESS(
                    f'  [{locale}] {slug} — {"создан" if created else "обновлён"} черновик (is_published=False)'
                ))
                gloss = article.get('english_gloss', '').strip()
                if gloss:
                    self.stdout.write(f'    english_gloss: {gloss}')
                issues = article.get('critique_issues', [])
                if issues:
                    self.stdout.write(f'    self-critique нашёл и исправил: {"; ".join(issues)}')

        self.stdout.write(self.style.WARNING(
            'Все статьи созданы как ЧЕРНОВИКИ (is_published=False). '
            'Публикация требует нативной вычитки — команда её не выполняет.'
        ))

    def _generate_article(self, client, locale, meta, brief):
        draft = self._call_draft(client, locale, meta, brief)
        return self._call_critique(client, locale, meta, brief, draft)

    def _call_draft(self, client, locale, meta, brief):
        system_prompt = (
            f"You are a native {meta['name']} content strategist and senior writer for {meta['market']}, "
            f"writing for an AI-platform blog that must compete with the top-ranking articles in this niche. "
            f"Write ENTIRELY in {meta['name']} (title, body, FAQ) — never mix in English or Russian except "
            f"for these verbatim product/brand terms: {', '.join(DO_NOT_TRANSLATE)}.\n\n"
            f"E-E-A-T requirements: concrete, specific claims — no generic AI filler phrases ('in today's fast-paced "
            f"world', 'unlock the power of', etc.), no keyword stuffing, natural voice a real expert in this market "
            f"would use, genuinely useful and comprehensive (aim for depth over length padding).\n\n"
            f"Structure: one strong H1-worthy title, 4-7 <h2> sections (some with <h3> subsections), "
            f"1500-2500 words total, semantic HTML only (<h2><h3><p><ul><ol><li><strong><blockquote> — no <h1>, "
            f"no inline styles, no <script>), plus a FAQ block of 4-6 genuinely useful question/answer pairs "
            f"(not restating the article, answering real follow-up questions a reader would have).\n\n"
            f"Must naturally incorporate these facts (do not invent other product facts, do not state specific "
            f"prices since they drift — describe the payment/credit model qualitatively only): "
            f"{'; '.join(brief['must_include_facts'])}.\n\n"
            f"CRITICAL — output format: do NOT use JSON, do NOT use markdown code fences. Respond with PLAIN TEXT "
            f"split into these exact sections, each starting on its own line with the marker shown (three equals "
            f"signs, marker name, three equals signs), in this order:\n"
            f"===TITLE===\n(article title)\n"
            f"===SEO_TITLE===\n(<=60 chars)\n"
            f"===SEO_DESCRIPTION===\n(150-160 chars)\n"
            f"===SEO_KEYWORDS===\n(comma-separated keywords)\n"
            f"===PREVIEW_TEXT===\n(<=280 chars, compelling summary, not truncated mid-sentence)\n"
            f"===CONTENT_HTML===\n(the full article body HTML)\n"
            f"===FAQ===\n(pairs of lines: 'Q: question' then 'A: answer', one pair per Q/A, 4-6 pairs)\n"
            f"===END===\n"
            f"Do not add any other text before ===TITLE=== or after ===END==="
        )
        user_prompt = (
            f"title_hint: {brief['title_hint']}\n"
            f"target_keywords: {', '.join(brief['keywords'])}\n"
            f"search_intent: {brief['search_intent']}\n"
            f"unique_angle: {brief['angle']}"
        )
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.7,
            max_tokens=16000,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        )
        text = resp.choices[0].message.content or ''
        sections = _split_sections(text)
        _required(sections, resp, 'TITLE', 'CONTENT_HTML', 'FAQ')
        return {
            'title': sections.get('TITLE', ''),
            'seo_title': sections.get('SEO_TITLE', ''),
            'seo_description': sections.get('SEO_DESCRIPTION', ''),
            'seo_keywords': sections.get('SEO_KEYWORDS', ''),
            'preview_text': sections.get('PREVIEW_TEXT', ''),
            'content_html': sections.get('CONTENT_HTML', ''),
            'faq_items': _parse_faq(sections.get('FAQ', '')),
        }

    def _call_critique(self, client, locale, meta, brief, draft):
        system_prompt = (
            f"You are a skeptical senior editor reviewing a draft {meta['name']} article before publication. "
            f"Find: generic AI-sounding phrases/clichés, any invented or unverifiable product claims beyond what "
            f"was explicitly provided as facts, unnatural phrasing for a native {meta['name']} reader in "
            f"{meta['market']}, and structural issues (weak FAQ, thin sections, HTML errors). "
            f"Rewrite the content and FAQ to fix everything you find, keeping the same facts and length "
            f"target (do not shorten meaningfully). Keep the same HTML tag conventions.\n\n"
            f"Facts that are allowed to appear (nothing else product-related): "
            f"{'; '.join(brief['must_include_facts'])}.\n\n"
            f"CRITICAL — output format: do NOT use JSON, do NOT use markdown code fences. Respond with PLAIN TEXT "
            f"split into these exact sections, each starting on its own line with the marker shown:\n"
            f"===CONTENT_HTML===\n(revised full article body HTML, in {meta['name']})\n"
            f"===FAQ===\n(revised pairs: 'Q: question' then 'A: answer')\n"
            f"===CRITIQUE_ISSUES===\n(one short issue per line, in English, prefixed with '- ', describing what "
            f"you fixed, for an internal reviewer who does not read {meta['name']})\n"
            f"===ENGLISH_GLOSS===\n(3-5 sentence English summary of what the final article actually says, so a "
            f"non-{meta['name']}-speaking reviewer can sanity-check the facts and tone)\n"
            f"===END===\n"
            f"Do not add any other text before ===CONTENT_HTML=== or after ===END==="
        )
        user_prompt = f"draft_content_html:\n{draft['content_html']}\n\ndraft_faq:\n" + '\n'.join(
            f"Q: {item['question']}\nA: {item['answer']}" for item in draft.get('faq_items', [])
        )
        resp = client.chat.completions.create(
            model=MODEL,
            temperature=0.3,
            max_tokens=16000,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt},
            ],
        )
        text = resp.choices[0].message.content or ''
        sections = _split_sections(text)
        _required(sections, resp, 'CONTENT_HTML')
        merged = dict(draft)
        if sections.get('CONTENT_HTML'):
            merged['content_html'] = sections['CONTENT_HTML']
        faq = _parse_faq(sections.get('FAQ', ''))
        if faq:
            merged['faq_items'] = faq
        merged['critique_issues'] = [
            line.strip().lstrip('- ').strip()
            for line in sections.get('CRITIQUE_ISSUES', '').splitlines()
            if line.strip()
        ]
        merged['english_gloss'] = sections.get('ENGLISH_GLOSS', '')
        return merged
