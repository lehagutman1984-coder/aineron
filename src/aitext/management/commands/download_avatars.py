import io
import requests
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageFont
from aitext.models import NeuralNetwork

# Официальные логотипы: slug -> URL. GitHub org avatars — стабильный источник
# (PNG, автоматически следит за редиректами).
#
# ВАЖНО (2026-09-08): каждый URL в этом словаре проверен ВИЗУАЛЬНО перед
# добавлением — GitHub отдаёт 200 image/png даже для несуществующих
# org/user, просто с generic identicon-заглушкой вместо реального лого
# (это НЕ ошибка HTTP, легко принять заглушку за настоящий логотип, если
# не посмотреть глазами). Отклонены как заглушки при проверке 2026-09-08:
# github.com/{Kwaishou,kuaishou,KwaiVGI,pixverse}.png — ни один не дал
# настоящий логотип Kling/Kuaishou или Pixverse, поэтому у моделей Kling
# и Pixverse ниже сознательно нет записи — остаются на ui-avatars.com
# fallback (get_avatar() в aitext/models.py), а не на угаданной картинке.
# logo.clearbit.com не резолвится из этого окружения вообще — не используется.
#
# Список слагов актуализирован под текущий каталог 68 моделей (2026-09-08) —
# старые слаги вроде gpt-4o/gpt-5/claude-sonnet-4-5/gemini-2-5-pro и т.п. из
# предыдущей версии этого файла удалены, их давно нет в каталоге.
SLUG_TO_LOGO_URL = {
    # OpenAI
    'gpt-6-astra':       'https://github.com/openai.png?size=200',
    'gpt-5-5':           'https://github.com/openai.png?size=200',
    'gpt-5-5-pro':       'https://github.com/openai.png?size=200',
    'gpt-5-6-luna':      'https://github.com/openai.png?size=200',
    'gpt-5-6-sol':       'https://github.com/openai.png?size=200',
    'gpt-5-6-terra':     'https://github.com/openai.png?size=200',
    'gpt-image-1':       'https://github.com/openai.png?size=200',
    'gpt-image-2':       'https://github.com/openai.png?size=200',
    'gpt-image-1-mini':  'https://github.com/openai.png?size=200',
    'gpt-image-1-5':     'https://github.com/openai.png?size=200',
    # Anthropic / Claude
    'claude-opus-5':     'https://github.com/anthropics.png?size=200',
    'claude-fable-5':    'https://github.com/anthropics.png?size=200',
    'claude-fable-5-1':  'https://github.com/anthropics.png?size=200',
    'claude-sonnet-5':   'https://github.com/anthropics.png?size=200',
    'claude-sonnet-4-6': 'https://github.com/anthropics.png?size=200',
    'claude-opus-4-8':   'https://github.com/anthropics.png?size=200',
    'claude-haiku-4-5':  'https://github.com/anthropics.png?size=200',
    # Google DeepMind (Gemini + Veo — оба продукта Google DeepMind)
    'gemini-2-5-flash-image': 'https://github.com/google-deepmind.png?size=200',
    'gemini-3-pro-image':     'https://github.com/google-deepmind.png?size=200',
    'gemini-3-1-flash-image': 'https://github.com/google-deepmind.png?size=200',
    'gemini-3-1-pro':         'https://github.com/google-deepmind.png?size=200',
    'gemini-3-6-flash':       'https://github.com/google-deepmind.png?size=200',
    'gemini-3-7-flash':       'https://github.com/google-deepmind.png?size=200',
    'veo-3-1':                'https://github.com/google-deepmind.png?size=200',
    'veo-3-1-fast':           'https://github.com/google-deepmind.png?size=200',
    'veo-3-1-lite':           'https://github.com/google-deepmind.png?size=200',
    'veo-3':                  'https://github.com/google-deepmind.png?size=200',
    'veo-3-fast':             'https://github.com/google-deepmind.png?size=200',
    # DeepSeek
    'deepseek-v4-pro':   'https://github.com/deepseek-ai.png?size=200',
    'deepseek-v4-flash': 'https://github.com/deepseek-ai.png?size=200',
    # Qwen / Alibaba
    'qwen3-6-max':          'https://github.com/QwenLM.png?size=200',
    'qwen3-8-max':          'https://github.com/QwenLM.png?size=200',
    'qwen-image-2-0':       'https://github.com/QwenLM.png?size=200',
    'qwen-image-3-0':       'https://github.com/QwenLM.png?size=200',
    'qwen-image-3-0-pro':   'https://github.com/QwenLM.png?size=200',
    # Grok / xAI
    'grok-4-5':                   'https://github.com/xai-org.png?size=200',
    'grok-4-6':                   'https://github.com/xai-org.png?size=200',
    'grok-imagine-image':         'https://github.com/xai-org.png?size=200',
    'grok-imagine-image-quality': 'https://github.com/xai-org.png?size=200',
    'grok-imagine-1-5':           'https://github.com/xai-org.png?size=200',
    # Flux / Black Forest Labs
    'flux-2-pro':        'https://github.com/black-forest-labs.png?size=200',
    'flux-2-max':        'https://github.com/black-forest-labs.png?size=200',
    'flux-kontext-pro':  'https://github.com/black-forest-labs.png?size=200',
    'flux-kontext-max':  'https://github.com/black-forest-labs.png?size=200',
    'flux-2-flex':       'https://github.com/black-forest-labs.png?size=200',
    # ByteDance (Seedream/Seedance)
    'seedream-5-0':      'https://github.com/bytedance.png?size=200',
    'seedream-4-5':      'https://github.com/bytedance.png?size=200',
    'seedream-4-0':      'https://github.com/bytedance.png?size=200',
    'seedance-1-5-pro':  'https://github.com/bytedance.png?size=200',
    'seedance-2-0':      'https://github.com/bytedance.png?size=200',
    'seedance-2-0-fast': 'https://github.com/bytedance.png?size=200',
    'seedance-2-5':      'https://github.com/bytedance.png?size=200',
    # Tongyi (Alibaba) — Wan видео + Z-Image (подтверждено вживую: Z-Image
    # Turbo сделан командой Tongyi-MAI при Alibaba, не отдельным стартапом)
    'wan-2-6':           'https://github.com/Tongyi-MAI.png?size=200',
    'wan-2-7':           'https://github.com/Tongyi-MAI.png?size=200',
    'wan-2-7-image':     'https://github.com/Tongyi-MAI.png?size=200',
    'z-image-turbo':     'https://github.com/Tongyi-MAI.png?size=200',
    # MiniMax (Hailuo)
    'hailuo-2-3':        'https://github.com/MiniMax-AI.png?size=200',
    'hailuo-2-3-fast':   'https://github.com/MiniMax-AI.png?size=200',
    # Shengshu AI (Vidu)
    'vidu-q3':           'https://github.com/shengshu-ai.png?size=200',
    'vidu-q3-turbo':     'https://github.com/shengshu-ai.png?size=200',
    'vidu-q3-pro':       'https://github.com/shengshu-ai.png?size=200',
    # Midjourney
    'midjourney':        'https://github.com/midjourney.png?size=200',
    # Kling/Kuaishou и Pixverse сознательно отсутствуют — см. комментарий
    # в начале файла (ни один проверенный GitHub org не дал настоящий логотип).
}

# Цвет фона для fallback аватара (если URL не работает при скачивании)
FALLBACK_COLORS = {
    'gpt': '#10a37f',
    'claude': '#d97757',
    'gemini': '#4285f4',
    'veo': '#4285f4',
    'deepseek': '#1a6dff',
    'qwen': '#ff6a00',
    'grok': '#000000',
    'flux': '#8b5cf6',
    'seedream': '#ff4d00',
    'seedance': '#ff4d00',
    'wan': '#ff6a00',
    'z-image': '#ff6a00',
    'hailuo': '#e6007a',
    'vidu': '#1656f5',
    'midjourney': '#1a1a1a',
    'kling': '#a4c639',
    'pixverse': '#d64fc0',
}


def get_fallback_color(slug):
    for prefix, color in FALLBACK_COLORS.items():
        if slug.startswith(prefix):
            return color
    return '#6366f1'


def make_fallback_avatar(slug, size=200):
    """Создаёт цветной аватар с буквой модели (fallback)."""
    color = get_fallback_color(slug)
    img = Image.new('RGB', (size, size), color)
    draw = ImageDraw.Draw(img)
    letter = slug[0].upper()
    font_size = size // 2
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', font_size)
    except Exception:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), letter, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2 - bbox[0]
    y = (size - text_h) // 2 - bbox[1]
    draw.text((x, y), letter, fill='white', font=font)
    return img


def download_image(url, size=200, timeout=15):
    """Скачивает и ресайзит изображение. Возвращает PIL.Image или None."""
    try:
        resp = requests.get(url, timeout=timeout, allow_redirects=True,
                            headers={'User-Agent': 'Mozilla/5.0'})
        resp.raise_for_status()
        ct = resp.headers.get('content-type', '')
        if 'image' not in ct:
            return None
        img = Image.open(io.BytesIO(resp.content)).convert('RGBA')
        bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg.convert('RGB')
        img = img.resize((size, size), Image.LANCZOS)
        return img
    except Exception:
        return None


def save_avatar(img, slug):
    """Сохраняет PIL.Image в media/neural_avatars/ и возвращает путь."""
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    path = f'neural_avatars/{slug}.png'
    if default_storage.exists(path):
        default_storage.delete(path)
    default_storage.save(path, ContentFile(buf.getvalue()))
    return path


class Command(BaseCommand):
    help = 'Скачивает официальные логотипы нейросетей и сохраняет в media/neural_avatars/'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Перекачать даже уже скачанные аватары')

    def handle(self, *args, **options):
        force = options['force']
        url_cache = {}

        networks = list(NeuralNetwork.objects.filter(slug__in=SLUG_TO_LOGO_URL.keys()))
        if not force:
            networks = [n for n in networks if not n.avatar]

        self.stdout.write(f'Найдено нейросетей к обработке: {len(networks)}')

        ok = 0
        fallback = 0

        for network in sorted(networks, key=lambda n: n.slug):
            url = SLUG_TO_LOGO_URL.get(network.slug)

            if url not in url_cache:
                self.stdout.write(f'  Скачиваю: {url}')
                img = download_image(url)
                url_cache[url] = img

            img = url_cache[url]

            if img is None:
                self.stdout.write(f'  [WARN] Не удалось скачать для {network.slug}, использую fallback')
                img = make_fallback_avatar(network.slug)
                fallback += 1
            else:
                ok += 1

            path = save_avatar(img, network.slug)
            network.avatar = path
            network.save(update_fields=['avatar'])
            self.stdout.write(f'  {network.name} -> {path}')

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово! Официальных: {ok}, fallback (цветные): {fallback}'
        ))
