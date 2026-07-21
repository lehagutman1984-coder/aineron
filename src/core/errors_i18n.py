"""
Локализованные сообщения об ошибках AI-генерации (веб-чат/медиа), показываемые
через SSE (api/views/chats.py) и в Message.error_message (aitext/tasks.py).

До этого модуля эти строки были захардкожены по-русски без учёта языка —
на .ru это no-op (ru — единственная локаль), но на aineron.net (INTL_MODE=1)
любой intl-пользователь при сбое генерации видел русский текст. CustomUser
не хранит язык нигде в request-цикле для Celery-задач, поэтому язык берётся
через CustomUser.get_language() (users/models.py) — заполняется при
регистрации, с фолбэком на INTL_DEFAULT_LOCALE/'ru'.

Формат — тот же, что у telegram_bot/i18n.py: плоский словарь на локаль,
None/отсутствующий ключ возвращает ru-текст (единственная гарантированно
заполненная локаль).
"""
DEFAULT_LOCALE = 'ru'

ERROR_MESSAGES = {
    'ru': {
        'no_model_configured': 'У нейросети не указана модель. Обратитесь в поддержку.',
        'provider_billing_issue': 'Проблема с провайдером, обратитесь к администратору сервиса для решения проблем.',
        'media_generation_failed_refunded': 'Произошла ошибка генерации, средства возвращены на ваш баланс, пожалуйста выберите другую нейросеть из каталога, пока мы будем устранять проблему.',
        'content_policy_violation': 'Контент нарушает политику использования',
        'free_model_deprecated': 'Пожалуйста выберите другую бесплатную нейросеть. Эта нейросеть более не предоставляется бесплатно, и скоро пропадет из каталога.',
        'free_model_overloaded': 'Эта бесплатная модель сейчас перегружена (лимит провайдера исчерпан). Попробуйте отправить сообщение ещё раз через минуту или выберите другую бесплатную модель.',
        'generation_error_generic': 'Ошибка при генерации ответа. Попробуйте ещё раз.',
    },
    'en': {
        'no_model_configured': "This AI model isn't configured correctly. Please contact support.",
        'provider_billing_issue': 'There is an issue with the AI provider. Please contact support.',
        'media_generation_failed_refunded': 'Generation failed and your balance has been refunded. Please choose a different model from the catalog while we fix this.',
        'content_policy_violation': 'This content violates our usage policy.',
        'free_model_deprecated': 'Please choose a different free model. This model is no longer available for free and will soon be removed from the catalog.',
        'free_model_overloaded': 'This free model is currently overloaded (provider limit reached). Try again in a minute or choose a different free model.',
        'generation_error_generic': 'Error generating the response. Please try again.',
    },
    'fa': {
        'no_model_configured': 'این مدل هوش مصنوعی به‌درستی پیکربندی نشده است. لطفاً با پشتیبانی تماس بگیرید.',
        'provider_billing_issue': 'مشکلی در سرویس‌دهنده هوش مصنوعی وجود دارد. لطفاً با پشتیبانی تماس بگیرید.',
        'media_generation_failed_refunded': 'تولید محتوا با خطا مواجه شد و مبلغ به موجودی شما بازگردانده شد. لطفاً تا رفع مشکل، مدل دیگری از فهرست انتخاب کنید.',
        'content_policy_violation': 'این محتوا با قوانین استفاده ما مغایرت دارد.',
        'free_model_deprecated': 'لطفاً مدل رایگان دیگری انتخاب کنید. این مدل دیگر به‌صورت رایگان در دسترس نیست و به‌زودی از فهرست حذف خواهد شد.',
        'free_model_overloaded': 'این مدل رایگان در حال حاضر با ترافیک بالا مواجه است (محدودیت سرویس‌دهنده). چند دقیقه دیگر دوباره امتحان کنید یا مدل رایگان دیگری انتخاب کنید.',
        'generation_error_generic': 'خطا در تولید پاسخ. لطفاً دوباره امتحان کنید.',
    },
    'tr': {
        'no_model_configured': 'Bu yapay zeka modeli doğru şekilde yapılandırılmamış. Lütfen destek ekibiyle iletişime geçin.',
        'provider_billing_issue': 'Yapay zeka sağlayıcısında bir sorun var. Lütfen destek ekibiyle iletişime geçin.',
        'media_generation_failed_refunded': 'Üretim başarısız oldu ve bakiyeniz iade edildi. Sorunu çözene kadar lütfen katalogdan başka bir model seçin.',
        'content_policy_violation': 'Bu içerik kullanım politikamızı ihlal ediyor.',
        'free_model_deprecated': 'Lütfen başka bir ücretsiz model seçin. Bu model artık ücretsiz olarak sunulmuyor ve yakında katalogdan kaldırılacak.',
        'free_model_overloaded': 'Bu ücretsiz model şu anda aşırı yüklü (sağlayıcı limiti doldu). Bir dakika sonra tekrar deneyin veya başka bir ücretsiz model seçin.',
        'generation_error_generic': 'Yanıt oluşturulurken hata oluştu. Lütfen tekrar deneyin.',
    },
    'id': {
        'no_model_configured': 'Model AI ini belum dikonfigurasi dengan benar. Silakan hubungi dukungan.',
        'provider_billing_issue': 'Ada masalah dengan penyedia AI. Silakan hubungi dukungan.',
        'media_generation_failed_refunded': 'Pembuatan gagal dan saldo Anda telah dikembalikan. Silakan pilih model lain dari katalog sementara kami memperbaikinya.',
        'content_policy_violation': 'Konten ini melanggar kebijakan penggunaan kami.',
        'free_model_deprecated': 'Silakan pilih model gratis lain. Model ini tidak lagi tersedia secara gratis dan akan segera dihapus dari katalog.',
        'free_model_overloaded': 'Model gratis ini sedang kelebihan beban (batas penyedia tercapai). Coba lagi dalam satu menit atau pilih model gratis lain.',
        'generation_error_generic': 'Terjadi kesalahan saat membuat respons. Silakan coba lagi.',
    },
    'ar': {
        'no_model_configured': 'لم يتم تكوين نموذج الذكاء الاصطناعي هذا بشكل صحيح. يرجى التواصل مع الدعم.',
        'provider_billing_issue': 'توجد مشكلة لدى مزوّد الذكاء الاصطناعي. يرجى التواصل مع الدعم.',
        'media_generation_failed_refunded': 'فشل التوليد وتم استرداد المبلغ إلى رصيدك. يرجى اختيار نموذج آخر من الكتالوج ريثما نحل المشكلة.',
        'content_policy_violation': 'هذا المحتوى يخالف سياسة الاستخدام لدينا.',
        'free_model_deprecated': 'يرجى اختيار نموذج مجاني آخر. لم يعد هذا النموذج متاحًا مجانًا وسيُزال قريبًا من الكتالوج.',
        'free_model_overloaded': 'هذا النموذج المجاني مزدحم حاليًا (تم بلوغ حد المزوّد). حاول مرة أخرى بعد دقيقة أو اختر نموذجًا مجانيًا آخر.',
        'generation_error_generic': 'حدث خطأ أثناء توليد الرد. يرجى المحاولة مرة أخرى.',
    },
}


def t_error(key: str, lang: str = DEFAULT_LOCALE) -> str:
    locale = lang if lang in ERROR_MESSAGES else DEFAULT_LOCALE
    value = ERROR_MESSAGES[locale].get(key)
    if value is None:
        value = ERROR_MESSAGES[DEFAULT_LOCALE].get(key)
    return value if value is not None else key
