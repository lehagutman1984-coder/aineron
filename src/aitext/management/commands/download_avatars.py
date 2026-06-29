import io
import os
import requests
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageFont
from aitext.models import NeuralNetwork

# Официальные логотипы: slug -> URL
# GitHub org avatars — стабильный источник (PNG, автоматически следит за редиректами)
SLUG_TO_LOGO_URL = {
    # OpenAI
    'gpt-4o':            'https://github.com/openai.png?size=200',
    'gpt-4o-mini':       'https://github.com/openai.png?size=200',
    'gpt-4-1':           'https://github.com/openai.png?size=200',
    'gpt-4-1-mini':      'https://github.com/openai.png?size=200',
    'gpt-5':             'https://github.com/openai.png?size=200',
    'chatgpt-4o-latest': 'https://github.com/openai.png?size=200',
    'o3':                'https://github.com/openai.png?size=200',
    'o4-mini':           'https://github.com/openai.png?size=200',
    'o1':                'https://github.com/openai.png?size=200',
    'o3-mini':           'https://github.com/openai.png?size=200',
    'dall-e-3':          'https://github.com/openai.png?size=200',
    'gpt-image-1':       'https://github.com/openai.png?size=200',
    'gpt-image-2':       'https://github.com/openai.png?size=200',
    'gpt-image-1-mini':  'https://github.com/openai.png?size=200',
    'gpt-3-5-turbo':     'https://github.com/openai.png?size=200',
    # Anthropic / Claude
    'claude-sonnet-4-6': 'https://github.com/anthropics.png?size=200',
    'claude-opus-4-8':   'https://github.com/anthropics.png?size=200',
    'claude-haiku-4-5':  'https://github.com/anthropics.png?size=200',
    'claude-sonnet-4-5': 'https://github.com/anthropics.png?size=200',
    # Google / Gemini
    'gemini-2-5-flash':  'https://github.com/google-deepmind.png?size=200',
    'gemini-2-5-pro':    'https://github.com/google-deepmind.png?size=200',
    'gemini-3-flash':    'https://github.com/google-deepmind.png?size=200',
    # DeepSeek
    'deepseek-v3':       'https://github.com/deepseek-ai.png?size=200',
    'deepseek-r1':       'https://github.com/deepseek-ai.png?size=200',
    'deepseek-v3-1':     'https://github.com/deepseek-ai.png?size=200',
    # Qwen / Alibaba
    'qwen3-235b':        'https://github.com/QwenLM.png?size=200',
    'qwen3-max':         'https://github.com/QwenLM.png?size=200',
    'qwq-plus':          'https://github.com/QwenLM.png?size=200',
    # Grok / xAI
    'grok-4':            'https://github.com/xai-org.png?size=200',
    'grok-3':            'https://github.com/xai-org.png?size=200',
    'grok-4-fast':       'https://github.com/xai-org.png?size=200',
    # Kimi / Moonshot AI
    'kimi-k2':           'https://github.com/MoonshotAI.png?size=200',
    # GLM / Zhipu AI
    'glm-4-5':           'https://github.com/THUDM.png?size=200',
    # Flux / Black Forest Labs
    'flux-2-pro':        'https://github.com/black-forest-labs.png?size=200',
    'flux-2-max':        'https://github.com/black-forest-labs.png?size=200',
    'flux-kontext-pro':  'https://github.com/black-forest-labs.png?size=200',
    'flux-kontext-max':  'https://github.com/black-forest-labs.png?size=200',
    'flux-2-flex':       'https://github.com/black-forest-labs.png?size=200',
    # Seedream / ByteDance
    'seedream-5-0':      'https://github.com/bytedance.png?size=200',
    'seedream-4-5':      'https://github.com/bytedance.png?size=200',
    'seedream-4-0':      'https://github.com/bytedance.png?size=200',
    # Google Gemini Image
    'gemini-3-1-flash-image': 'https://github.com/google-deepmind.png?size=200',
    'gemini-3-pro-image':     'https://github.com/google-deepmind.png?size=200',
    'gemini-2-5-flash-image': 'https://github.com/google-deepmind.png?size=200',
    'gemini-3-5-flash':       'https://github.com/google-deepmind.png?size=200',
    'gemini-3-1-pro':         'https://github.com/google-deepmind.png?size=200',
    # OpenAI новые
    'gpt-image-1-5':     'https://github.com/openai.png?size=200',
    'gpt-5-mini':        'https://github.com/openai.png?size=200',
    'gpt-5-pro':         'https://github.com/openai.png?size=200',
    'gpt-5-1':           'https://github.com/openai.png?size=200',
    # DeepSeek новые
    'deepseek-v3-2':     'https://github.com/deepseek-ai.png?size=200',
    'deepseek-v4-flash': 'https://github.com/deepseek-ai.png?size=200',
    'deepseek-v4-pro':   'https://github.com/deepseek-ai.png?size=200',
    # GLM новые
    'glm-5':             'https://github.com/THUDM.png?size=200',
    'glm-4-6':           'https://github.com/THUDM.png?size=200',
    # Grok новый
    'grok-4-3':          'https://github.com/xai-org.png?size=200',
    # Kimi новые
    'kimi-k2-5':         'https://github.com/MoonshotAI.png?size=200',
    'kimi-k2-6':         'https://github.com/MoonshotAI.png?size=200',
    # Qwen новые
    'qwen3-5-flash':     'https://github.com/QwenLM.png?size=200',
    'qwen3-5-plus':      'https://github.com/QwenLM.png?size=200',
    # MiniMax
    'minimax-m2-7':      'https://github.com/MiniMaxAI.png?size=200',
    'minimax-m2-5':      'https://github.com/MiniMaxAI.png?size=200',
}

# Цвет фона для fallback аватара (если URL не работает)
FALLBACK_COLORS = {
    'gpt': '#10a37f',        # OpenAI зелёный
    'o3': '#10a37f',
    'o4': '#10a37f',
    'o1': '#10a37f',
    'chatgpt': '#10a37f',
    'dall': '#10a37f',
    'claude': '#d97757',     # Anthropic оранжевый
    'gemini': '#4285f4',     # Google синий
    'deepseek': '#1a6dff',   # DeepSeek синий
    'qwen': '#ff6a00',       # Alibaba оранжевый
    'qwq': '#ff6a00',
    'grok': '#000000',       # xAI чёрный
    'kimi': '#7c3aed',       # Moonshot фиолетовый
    'glm': '#06b6d4',        # Zhipu голубой
    'flux': '#8b5cf6',       # BFL фиолетовый
    'seedream': '#ff4d00',   # ByteDance оранжевый
    'minimax': '#0ea5e9',    # MiniMax голубой
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
    # Рисуем букву по центру
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
        # Создаём белый фон для прозрачных PNG
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

    def handle(self, *args, **options):
        # Кэш: URL -> PIL.Image чтобы не качать одно и то же несколько раз
        url_cache = {}

        networks = NeuralNetwork.objects.filter(slug__in=SLUG_TO_LOGO_URL.keys())
        self.stdout.write(f'Найдено нейросетей: {networks.count()}')

        ok = 0
        fallback = 0

        for network in networks.order_by('slug'):
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
            self.stdout.write(f'  {network.name} → {path}')

        self.stdout.write(self.style.SUCCESS(
            f'\nГотово! Официальных: {ok}, fallback (цветные): {fallback}'
        ))
