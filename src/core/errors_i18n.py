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
        'media_requires_paid_plan': 'Генерация изображений и видео доступна только на платных тарифах.',
        'trial_model_locked': 'Модель «{model}» доступна после первого пополнения баланса или покупки тарифа. На стартовом балансе выберите модель попроще.',
        'trial_request_too_large': 'Запрос слишком большой для стартового баланса: ответ модели «{model}» обойдётся примерно в {amount}, а на балансе {have}. Сократите текст или вложения, выберите модель дешевле — или пополните баланс.',
        'trial_reply_truncated': 'Ответ обрезан: на стартовом балансе длина ответа ограничена. Пополните баланс или выберите тариф, чтобы получать ответы полностью.',
        'balance_reply_truncated': 'Ответ обрезан: доплата за длинный ответ на этой модели превысила бы ваш текущий баланс. Пополните баланс, чтобы получать ответы полностью.',
        'no_model_configured': 'У нейросети не указана модель. Обратитесь в поддержку.',
        'provider_billing_issue': 'Проблема с провайдером, обратитесь к администратору сервиса для решения проблем.',
        'media_generation_failed_refunded': 'Произошла ошибка генерации, средства возвращены на ваш баланс, пожалуйста выберите другую нейросеть из каталога, пока мы будем устранять проблему.',
        'content_policy_violation': 'Контент нарушает политику использования',
        'free_model_deprecated': 'Пожалуйста выберите другую бесплатную нейросеть. Эта нейросеть более не предоставляется бесплатно, и скоро пропадет из каталога.',
        'free_model_overloaded': 'Эта бесплатная модель сейчас перегружена (лимит провайдера исчерпан). Попробуйте отправить сообщение ещё раз через минуту или выберите другую бесплатную модель.',
        'generation_error_generic': 'Ошибка при генерации ответа. Попробуйте ещё раз.',
    },
    'en': {
        'media_requires_paid_plan': 'Image and video generation is available on paid plans only.',
        'trial_model_locked': '{model} is available after your first top-up or plan purchase. On the trial balance, please choose a lighter model.',
        'trial_request_too_large': 'This request is too large for your trial balance: a {model} reply would cost about {amount}, and your balance is {have}. Shorten the text or attachments, pick a lighter model, or top up your balance.',
        'trial_reply_truncated': 'Reply shortened: on the trial balance, reply length is limited. Top up your balance or choose a plan to get full replies.',
        'balance_reply_truncated': 'Reply shortened: the extra charge for a full-length reply on this model would exceed your current balance. Top up your balance to get full replies.',
        'no_model_configured': "This AI model isn't configured correctly. Please contact support.",
        'provider_billing_issue': 'There is an issue with the AI provider. Please contact support.',
        'media_generation_failed_refunded': 'Generation failed and your balance has been refunded. Please choose a different model from the catalog while we fix this.',
        'content_policy_violation': 'This content violates our usage policy.',
        'free_model_deprecated': 'Please choose a different free model. This model is no longer available for free and will soon be removed from the catalog.',
        'free_model_overloaded': 'This free model is currently overloaded (provider limit reached). Try again in a minute or choose a different free model.',
        'generation_error_generic': 'Error generating the response. Please try again.',
    },
    'fa': {
        'media_requires_paid_plan': 'تولید تصویر و ویدیو فقط در طرح‌های پولی در دسترس است.',
        'trial_model_locked': 'مدل «{model}» پس از اولین شارژ موجودی یا خرید طرح در دسترس است. با موجودی آزمایشی، مدل سبک‌تری انتخاب کنید.',
        'trial_request_too_large': 'این درخواست برای موجودی آزمایشی شما بزرگ است: پاسخ مدل «{model}» حدود {amount} هزینه دارد، در حالی که موجودی شما {have} است. متن یا پیوست‌ها را کوتاه کنید، مدل سبک‌تری انتخاب کنید یا موجودی را شارژ کنید.',
        'trial_reply_truncated': 'پاسخ کوتاه شد: طول پاسخ در موجودی آزمایشی محدود است. برای دریافت پاسخ کامل، موجودی را شارژ کنید یا طرحی انتخاب کنید.',
        'balance_reply_truncated': 'پاسخ کوتاه شد: هزینه اضافی برای پاسخ کامل در این مدل از موجودی فعلی شما بیشتر است. برای دریافت پاسخ کامل، موجودی را شارژ کنید.',
        'no_model_configured': 'این مدل هوش مصنوعی به‌درستی پیکربندی نشده است. لطفاً با پشتیبانی تماس بگیرید.',
        'provider_billing_issue': 'مشکلی در سرویس‌دهنده هوش مصنوعی وجود دارد. لطفاً با پشتیبانی تماس بگیرید.',
        'media_generation_failed_refunded': 'تولید محتوا با خطا مواجه شد و مبلغ به موجودی شما بازگردانده شد. لطفاً تا رفع مشکل، مدل دیگری از فهرست انتخاب کنید.',
        'content_policy_violation': 'این محتوا با قوانین استفاده ما مغایرت دارد.',
        'free_model_deprecated': 'لطفاً مدل رایگان دیگری انتخاب کنید. این مدل دیگر به‌صورت رایگان در دسترس نیست و به‌زودی از فهرست حذف خواهد شد.',
        'free_model_overloaded': 'این مدل رایگان در حال حاضر با ترافیک بالا مواجه است (محدودیت سرویس‌دهنده). چند دقیقه دیگر دوباره امتحان کنید یا مدل رایگان دیگری انتخاب کنید.',
        'generation_error_generic': 'خطا در تولید پاسخ. لطفاً دوباره امتحان کنید.',
    },
    'tr': {
        'media_requires_paid_plan': 'Görsel ve video üretimi yalnızca ücretli planlarda kullanılabilir.',
        'trial_model_locked': '"{model}" modeli ilk bakiye yüklemenizden veya plan satın almanızdan sonra kullanılabilir. Deneme bakiyesinde lütfen daha hafif bir model seçin.',
        'trial_request_too_large': 'Bu istek deneme bakiyeniz için çok büyük: "{model}" yanıtı yaklaşık {amount} tutacak, bakiyeniz ise {have}. Metni veya ekleri kısaltın, daha hafif bir model seçin ya da bakiyenizi yükleyin.',
        'trial_reply_truncated': 'Yanıt kısaltıldı: deneme bakiyesinde yanıt uzunluğu sınırlıdır. Tam yanıt almak için bakiyenizi yükleyin veya bir plan seçin.',
        'balance_reply_truncated': 'Yanıt kısaltıldı: bu modelde tam uzunlukta bir yanıtın ek ücreti mevcut bakiyenizi aşardı. Tam yanıt almak için bakiyenizi yükleyin.',
        'no_model_configured': 'Bu yapay zeka modeli doğru şekilde yapılandırılmamış. Lütfen destek ekibiyle iletişime geçin.',
        'provider_billing_issue': 'Yapay zeka sağlayıcısında bir sorun var. Lütfen destek ekibiyle iletişime geçin.',
        'media_generation_failed_refunded': 'Üretim başarısız oldu ve bakiyeniz iade edildi. Sorunu çözene kadar lütfen katalogdan başka bir model seçin.',
        'content_policy_violation': 'Bu içerik kullanım politikamızı ihlal ediyor.',
        'free_model_deprecated': 'Lütfen başka bir ücretsiz model seçin. Bu model artık ücretsiz olarak sunulmuyor ve yakında katalogdan kaldırılacak.',
        'free_model_overloaded': 'Bu ücretsiz model şu anda aşırı yüklü (sağlayıcı limiti doldu). Bir dakika sonra tekrar deneyin veya başka bir ücretsiz model seçin.',
        'generation_error_generic': 'Yanıt oluşturulurken hata oluştu. Lütfen tekrar deneyin.',
    },
    'id': {
        'media_requires_paid_plan': 'Pembuatan gambar dan video hanya tersedia pada paket berbayar.',
        'trial_model_locked': 'Model "{model}" tersedia setelah isi saldo pertama atau pembelian paket. Pada saldo percobaan, silakan pilih model yang lebih ringan.',
        'trial_request_too_large': 'Permintaan ini terlalu besar untuk saldo percobaan Anda: balasan "{model}" akan menghabiskan sekitar {amount}, sementara saldo Anda {have}. Persingkat teks atau lampiran, pilih model yang lebih ringan, atau isi ulang saldo.',
        'trial_reply_truncated': 'Balasan dipersingkat: pada saldo percobaan, panjang balasan dibatasi. Isi ulang saldo atau pilih paket untuk mendapatkan balasan lengkap.',
        'balance_reply_truncated': 'Balasan dipersingkat: biaya tambahan untuk balasan lengkap pada model ini akan melebihi saldo Anda saat ini. Isi ulang saldo untuk mendapatkan balasan lengkap.',
        'no_model_configured': 'Model AI ini belum dikonfigurasi dengan benar. Silakan hubungi dukungan.',
        'provider_billing_issue': 'Ada masalah dengan penyedia AI. Silakan hubungi dukungan.',
        'media_generation_failed_refunded': 'Pembuatan gagal dan saldo Anda telah dikembalikan. Silakan pilih model lain dari katalog sementara kami memperbaikinya.',
        'content_policy_violation': 'Konten ini melanggar kebijakan penggunaan kami.',
        'free_model_deprecated': 'Silakan pilih model gratis lain. Model ini tidak lagi tersedia secara gratis dan akan segera dihapus dari katalog.',
        'free_model_overloaded': 'Model gratis ini sedang kelebihan beban (batas penyedia tercapai). Coba lagi dalam satu menit atau pilih model gratis lain.',
        'generation_error_generic': 'Terjadi kesalahan saat membuat respons. Silakan coba lagi.',
    },
    'ar': {
        'media_requires_paid_plan': 'توليد الصور والفيديو متاح فقط في الخطط المدفوعة.',
        'trial_model_locked': 'النموذج «{model}» متاح بعد أول شحن للرصيد أو شراء خطة. في الرصيد التجريبي، يرجى اختيار نموذج أخف.',
        'trial_request_too_large': 'هذا الطلب كبير جدًا بالنسبة لرصيدك التجريبي: ستكلف إجابة «{model}» حوالي {amount}، بينما رصيدك {have}. اختصر النص أو المرفقات، اختر نموذجًا أرخص، أو اشحن رصيدك.',
        'trial_reply_truncated': 'تم تقصير الإجابة: طول الإجابة محدود في الرصيد التجريبي. اشحن رصيدك أو اختر خطة للحصول على إجابات كاملة.',
        'balance_reply_truncated': 'تم تقصير الإجابة: الرسوم الإضافية لإجابة كاملة على هذا النموذج ستتجاوز رصيدك الحالي. اشحن رصيدك للحصول على إجابات كاملة.',
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
