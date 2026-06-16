export interface Feature {
  id: string;
  label: string;
  category: string;
}

export const FEATURE_CATEGORIES = [
  { key: 'nav', label: 'Навигация' },
  { key: 'content', label: 'Контент' },
  { key: 'forms', label: 'Формы' },
  { key: 'ecom', label: 'E-commerce' },
  { key: 'auth', label: 'Авторизация' },
  { key: 'extra', label: 'Дополнительно' },
  { key: 'integrations', label: 'Интеграции' },
];

export const ALL_FEATURES: Feature[] = [
  { id: 'header_menu', label: 'Header с меню', category: 'nav' },
  { id: 'footer', label: 'Footer', category: 'nav' },
  { id: 'breadcrumbs', label: 'Breadcrumbs', category: 'nav' },
  { id: 'sidebar', label: 'Sidebar', category: 'nav' },
  { id: 'hero', label: 'Hero-секция', category: 'content' },
  { id: 'gallery', label: 'Галерея / карточки', category: 'content' },
  { id: 'blog', label: 'Блог / статьи', category: 'content' },
  { id: 'faq', label: 'FAQ-раздел', category: 'content' },
  { id: 'reviews', label: 'Отзывы', category: 'content' },
  { id: 'contact_form', label: 'Форма обратной связи', category: 'forms' },
  { id: 'booking_form', label: 'Форма записи / бронирования', category: 'forms' },
  { id: 'order_form', label: 'Форма заказа', category: 'forms' },
  { id: 'quiz', label: 'Квиз', category: 'forms' },
  { id: 'cart', label: 'Корзина', category: 'ecom' },
  { id: 'catalog', label: 'Каталог товаров', category: 'ecom' },
  { id: 'product_card', label: 'Карточка товара', category: 'ecom' },
  { id: 'checkout', label: 'Чекаут', category: 'ecom' },
  { id: 'auth', label: 'Регистрация / вход', category: 'auth' },
  { id: 'account', label: 'Личный кабинет', category: 'auth' },
  { id: 'profile', label: 'Профиль пользователя', category: 'auth' },
  { id: 'dark_mode', label: 'Тёмная тема', category: 'extra' },
  { id: 'animations', label: 'Анимации', category: 'extra' },
  { id: 'responsive', label: 'Адаптив мобильный', category: 'extra' },
  { id: 'i18n', label: 'Мультиязычность', category: 'extra' },
  { id: 'search', label: 'Поиск по странице', category: 'extra' },
  { id: 'yandex_maps', label: 'Яндекс.Карты', category: 'integrations' },
  { id: 'telegram_btn', label: 'Telegram-кнопка', category: 'integrations' },
  { id: 'whatsapp_btn', label: 'WhatsApp-кнопка', category: 'integrations' },
  { id: 'instagram', label: 'Instagram-ссылки', category: 'integrations' },
];
