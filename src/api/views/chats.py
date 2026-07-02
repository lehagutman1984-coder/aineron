import json
import logging
from django.conf import settings
from django.http import StreamingHttpResponse
from django.utils import timezone
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import (
    NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage, FileAttachment,
)
from aitext.tasks import generate_ai_response, get_laozhang_client
from aitext.code_formatter import CodeFormatter
from users.models import UserSpending
from api.serializers.chats import (
    ChatListSerializer, ChatDetailSerializer, ChatUpdateSerializer,
    MessageSerializer, SendMessageSerializer,
)

logger = logging.getLogger(__name__)


class ChatListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        return ChatListSerializer

    def get_queryset(self):
        qs = (
            Chat.objects.filter(user=self.request.user)
            .select_related('network', 'network__category')
            .prefetch_related('messages')
            .order_by('-updated_at')
        )
        project_id = self.request.query_params.get('project_id')
        if project_id is not None:
            qs = qs.filter(project_id=project_id if project_id else None)
        return qs

    def create(self, request, *args, **kwargs):
        network_slug = request.data.get('network_slug')
        message_text = (request.data.get('message') or '').strip()
        files = request.data.get('files', [])
        settings = request.data.get('settings', {})
        attachment_ids = request.data.get('attachment_ids', [])
        web_search = bool(request.data.get('web_search', False))
        project_id = request.data.get('project_id')

        if not network_slug:
            return Response({'error': {'message': 'Не указана нейросеть', 'type': 'invalid_request_error', 'code': None}}, status=400)
        if not message_text and not files:
            return Response({'error': {'message': 'Нет текста или файлов', 'type': 'invalid_request_error', 'code': None}}, status=400)

        network = get_object_or_404(NeuralNetwork, slug=network_slug, is_active=True)
        cost_kopecks = network.cost_kopecks
        deduct_stars = True

        # Медиа-генерация доступна только на платных тарифах
        is_media = network.handle_video or network.handle_photo or (
            (network.config_json or {}).get('metadata', {}).get('output_type') in ('image', 'video')
        )
        if is_media and getattr(request.user.tariff, 'is_free', True):
            return Response({
                'error': {
                    'message': 'Генерация изображений и видео доступна только на платных тарифах.',
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        if (network.unlimited and
                network.tariffs.filter(id=request.user.tariff.id).exists() and
                network.messages_limit > 0):
            today = timezone.now().date()
            usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user, network=network, date=today, defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()

        if deduct_stars and not request.user.has_enough_kopecks(cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': f'Недостаточно средств. Нужно {format_rub(cost_kopecks)}, у вас {format_rub(request.user.balance_kopecks)}.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        from aitext.models import Project
        project = None
        if project_id:
            try:
                project = Project.objects.get(id=project_id, user=request.user)
            except Project.DoesNotExist:
                pass

        chat = Chat.objects.create(
            user=request.user,
            network=network,
            project=project,
            title=message_text[:50] if message_text else f"{network.name} - {timezone.now().strftime('%d.%m.%Y %H:%M')}",
            settings=settings,
        )

        user_message = Message.objects.create(
            chat=chat, role='user', content=message_text,
            files=files, status=Message.Status.COMPLETED, settings=settings,
        )

        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        if network.provider != 'fal-ai' and deduct_stars:
            request.user.spend_kopecks(cost_kopecks, type='spend', reference=f'chat:{assistant_message.id}')
            UserSpending.objects.create(
                user=request.user, amount=max(1, cost_kopecks // 100), amount_kopecks=cost_kopecks,
                description=f"Сообщение в чате с {network.name}",
            )

        # Link pre-uploaded file attachments to this user message
        if attachment_ids:
            FileAttachment.objects.filter(
                id__in=attachment_ids, message__isnull=True
            ).update(message=user_message)

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id, web_search=web_search)

        # Суммаризация последнего чата пользователя (любая нейросеть, фон)
        try:
            from aitext.tasks import generate_chat_summary
            prev_chat = (
                Chat.objects.filter(user=request.user)
                .exclude(id=chat.id)
                .order_by('-updated_at')
                .first()
            )
            if prev_chat and prev_chat.messages.filter(status=Message.Status.COMPLETED).count() >= 4:
                generate_chat_summary.delay(prev_chat.id)
        except Exception:
            pass

        return Response({
            'chat_id': chat.id,
            'user_message_id': user_message.id,
            'assistant_message_id': assistant_message.id,
            'new_balance': request.user.pages_count,
            'new_balance_kopecks': request.user.balance_kopecks,
        }, status=201)


class ChatDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Chat.objects.filter(user=self.request.user).select_related(
            'network', 'network__category', 'project',
        ).prefetch_related('messages', 'messages__deep_research')

    def get_serializer_class(self):
        if self.request.method in ('PATCH', 'PUT'):
            return ChatUpdateSerializer
        return ChatDetailSerializer

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        chat = self.get_object()
        chat.delete()
        return Response(status=204)


class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        serializer = SendMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message_text = serializer.validated_data['message'].strip()
        files = serializer.validated_data['files']
        settings = serializer.validated_data['settings']
        attachment_ids = serializer.validated_data.get('attachment_ids', [])
        web_search = serializer.validated_data.get('web_search', False)

        if not message_text and not files:
            return Response({'error': {'message': 'Нет текста или файлов', 'type': 'invalid_request_error', 'code': None}}, status=400)

        network = chat.network
        cost_kopecks = network.cost_kopecks
        deduct_stars = True

        # Медиа-генерация доступна только на платных тарифах
        is_media = network.handle_video or network.handle_photo or (
            (network.config_json or {}).get('metadata', {}).get('output_type') in ('image', 'video')
        )
        if is_media and getattr(request.user.tariff, 'is_free', True):
            return Response({
                'error': {
                    'message': 'Генерация изображений и видео доступна только на платных тарифах.',
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        if (network.unlimited and
                network.tariffs.filter(id=request.user.tariff.id).exists() and
                network.messages_limit > 0):
            today = timezone.now().date()
            usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user, network=network, date=today, defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()

        if deduct_stars and not request.user.has_enough_kopecks(cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': f'Недостаточно средств. Нужно {format_rub(cost_kopecks)}, у вас {format_rub(request.user.balance_kopecks)}.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        user_message = Message.objects.create(
            chat=chat, role='user', content=message_text,
            files=files, status=Message.Status.COMPLETED, settings=settings,
        )

        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        if network.provider != 'fal-ai' and deduct_stars:
            request.user.spend_kopecks(cost_kopecks, type='spend', reference=f'chat:{assistant_message.id}')
            UserSpending.objects.create(
                user=request.user, amount=max(1, cost_kopecks // 100), amount_kopecks=cost_kopecks,
                description=f"Сообщение в чате с {network.name}",
            )

        # Link pre-uploaded file attachments to this user message
        if attachment_ids:
            FileAttachment.objects.filter(
                id__in=attachment_ids, message__isnull=True
            ).update(message=user_message)

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id, web_search=web_search)

        return Response({
            'user_message_id': user_message.id,
            'assistant_message_id': assistant_message.id,
            'new_balance': request.user.pages_count,
            'new_balance_kopecks': request.user.balance_kopecks,
        }, status=201)


class MessageStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, message_id):
        message = get_object_or_404(
            Message, id=message_id, chat__user=request.user
        )
        return Response(MessageSerializer(message).data)


class StreamMessageView(APIView):
    """SSE streaming endpoint for text models. fal-ai returns 400."""
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        network = chat.network

        if network.provider == 'fal-ai':
            return Response({
                'error': {
                    'message': 'Streaming не поддерживается для моделей генерации изображений',
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        if not network.model_name:
            return Response({
                'error': {'message': 'У нейросети не указана модель', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        message_text = (request.data.get('message') or '').strip()
        files = request.data.get('files', [])
        web_search = bool(request.data.get('web_search', False))
        variants_mode = bool(request.data.get('variants_mode', False))

        if not message_text and not files:
            return Response({
                'error': {'message': 'Нет текста или файлов', 'type': 'invalid_request_error', 'code': None}
            }, status=400)

        cost_kopecks = network.cost_kopecks
        deduct_stars = True

        if (network.unlimited and
                network.tariffs.filter(id=request.user.tariff.id).exists() and
                network.messages_limit > 0):
            today = timezone.now().date()
            usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user, network=network, date=today, defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()

        if deduct_stars and not request.user.has_enough_kopecks(cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': f'Недостаточно средств. Нужно {format_rub(cost_kopecks)}, у вас {format_rub(request.user.balance_kopecks)}.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        attachment_ids = request.data.get('attachment_ids', [])

        user_message = Message.objects.create(
            chat=chat, role='user', content=message_text,
            files=files, status=Message.Status.COMPLETED,
        )
        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        # Link pre-uploaded file attachments to this user message
        if attachment_ids:
            FileAttachment.objects.filter(
                id__in=attachment_ids, message__isnull=True
            ).update(message=user_message)

        if deduct_stars:
            request.user.spend_kopecks(cost_kopecks, type='spend', reference=f'chat:{assistant_message.id}')
            UserSpending.objects.create(
                user=request.user, amount=max(1, cost_kopecks // 100), amount_kopecks=cost_kopecks,
                description=f"Сообщение в чате с {network.name}",
            )

        new_balance = request.user.pages_count
        new_balance_kopecks = request.user.balance_kopecks
        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        # Build message history for API (mirrors tasks.py logic)
        max_input_tokens = network.max_input_tokens

        # ── Persistent Memory: собираем контекст памяти ───────────────────────
        from aitext.memory import (
            build_memory_context, get_history_with_compression, should_compress,
        )
        memory_ctx = build_memory_context(request.user, chat)

        messages_for_api = []

        # 1. Project system prompt + база знаний (если есть)
        kb_sources: list[dict] = []
        if chat.project_id:
            from aitext.models import Project
            from aitext.tasks import build_project_knowledge_context
            try:
                proj = Project.objects.get(id=chat.project_id)
                if proj.system_prompt:
                    messages_for_api.append({"role": "system", "content": proj.system_prompt})
                knowledge_ctx, kb_sources = build_project_knowledge_context(proj, message_text)
                if knowledge_ctx:
                    messages_for_api.append({"role": "system", "content": knowledge_ctx})
                # AI-коммиты: инструкция о FILE-формате (Sprint 4.3)
                if getattr(settings, 'PROJECT_AI_COMMITS', False):
                    from aitext.commit_extract import inject_commit_instruction
                    inject_commit_instruction(proj, messages_for_api)
            except Project.DoesNotExist:
                pass

        # 2. Network prompt (если есть) + A/B тест промтов
        ab_variant = None
        ab_test_id = None
        try:
            from aitext.models import PromptABTest
            ab_test = PromptABTest.objects.filter(
                network=network, is_active=True
            ).first()
            if ab_test:
                ab_variant = ab_test.pick_variant()
                ab_test_id = ab_test.id
                ab_prompt = ab_test.get_prompt(ab_variant)
                messages_for_api.append({"role": "system", "content": ab_prompt})
                PromptABTest.objects.filter(id=ab_test.id).update(
                    **({'sends_a': ab_test.sends_a + 1} if ab_variant == 'a' else {'sends_b': ab_test.sends_b + 1})
                )
            elif network.has_prompt and network.prompt:
                messages_for_api.append({"role": "system", "content": network.prompt})
        except Exception:
            if network.has_prompt and network.prompt:
                messages_for_api.append({"role": "system", "content": network.prompt})

        # 3. Блок памяти пользователя
        if memory_ctx:
            messages_for_api.append({"role": "system", "content": memory_ctx})

        # 4. Умная история: read-only, никаких sync LLM-вызовов (B5 fix)
        history, existing_summary = get_history_with_compression(
            chat,
            exclude_msg_id=user_message.id,
            memory_context=memory_ctx,
            network_prompt=network.prompt or '',
        )
        # Фоновая компрессия если накопилось достаточно новых сообщений
        if should_compress(chat, exclude_msg_id=user_message.id):
            try:
                from aitext.tasks import compress_chat_history
                compress_chat_history.delay(chat.id)
            except Exception:
                pass

        # 5. Summary текущей сессии (если есть готовое сжатие)
        if existing_summary:
            messages_for_api.append({
                "role": "system",
                "content": f"[Начало этой сессии, сжато]: {existing_summary}",
            })

        for msg in history:
            if msg.role == 'user':
                content_text = msg.content or ""
                extracted = msg.extracted_content or ""
                if max_input_tokens > 0:
                    if len(content_text) > max_input_tokens:
                        content_text = content_text[:max_input_tokens] + "..."
                    if extracted and len(extracted) > max_input_tokens:
                        extracted = extracted[:max_input_tokens] + "..."
                if extracted:
                    combined = f"{content_text}\n\n{extracted}" if content_text else extracted
                    messages_for_api.append({"role": "user", "content": combined})
                elif content_text:
                    messages_for_api.append({"role": "user", "content": content_text})
            elif msg.role == 'assistant':
                assistant_text = msg.plain_text or msg.content
                if assistant_text:
                    if max_input_tokens > 0 and len(assistant_text) > max_input_tokens:
                        assistant_text = assistant_text[:max_input_tokens] + "..."
                    messages_for_api.append({"role": "assistant", "content": assistant_text})

        if variants_mode:
            messages_for_api.append({
                "role": "system",
                "content": "Дай КРАТКИЙ ответ — не более 150 слов. Только суть.",
            })

        messages_for_api.append({"role": "user", "content": message_text or "Привет"})

        # ── Шаг 1: веб-поиск СИНХРОННО до генератора ─────────────────────────
        from aitext.tasks import call_web_search, build_web_search_message
        search_context_text = ""
        if web_search:
            search_context_text = call_web_search(
                message_text or "информация",
                log_prefix=f"[chat {chat.id}] ",
            )
            if search_context_text:
                assistant_message.search_context = search_context_text
                assistant_message.save(update_fields=['search_context'])
                # Обрезаем поисковый контекст если KB уже большой (чтобы не превысить лимит)
                ctx_so_far = sum(len(m.get("content", "")) for m in messages_for_api)
                search_limit = 2000 if ctx_so_far > 30_000 else 4500
                # Вставляем прямо перед последним user-сообщением — как делает Perplexity
                insert_pos = max(len(messages_for_api) - 1, 0)
                messages_for_api.insert(
                    insert_pos,
                    build_web_search_message(search_context_text[:search_limit], message_text or ""),
                )

        # Capture values for the generator closure
        user = request.user
        user_msg_id = user_message.id
        assist_msg_id = assistant_message.id
        model_name = network.model_name
        # network.max_tokens == 0 means "no explicit limit in DB" — fall back to
        # laozhang.ai proxy cap (16384). Passing 16384 explicitly is equivalent
        # but makes intent clear and avoids relying on proxy defaults.
        _auto_max = 32000
        max_tokens = network.max_tokens if network.max_tokens > 0 else _auto_max

        def _sse(data):
            return f"data: {json.dumps(data, ensure_ascii=False)}\n\n".encode('utf-8')

        def generate():
            yield _sse({
                "type": "init",
                "user_message_id": user_msg_id,
                "assistant_message_id": assist_msg_id,
                "new_balance": new_balance,
                "new_balance_kopecks": new_balance_kopecks,
            })

            # Сообщаем фронтенду итог поиска (поиск уже выполнен синхронно выше)
            if web_search:
                yield _sse({
                    "type": "search_done",
                    "preview": search_context_text[:400],
                })

            full_text = ""
            try:
                # ── Шаг 2: основная модель (выбранная пользователем) ────────────
                client = get_laozhang_client()
                kwargs = {
                    "model": model_name,
                    "messages": messages_for_api,
                    "temperature": 0.7,
                    "stream": True,
                }
                kwargs["max_tokens"] = max_tokens

                stream = client.chat.completions.create(**kwargs)
                for chunk in stream:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta and delta.content:
                        full_text += delta.content
                        yield _sse({"type": "token", "text": delta.content})

                formatted_html = CodeFormatter.format_ai_response(full_text)
                assistant_message.content = formatted_html
                assistant_message.plain_text = full_text
                assistant_message.status = Message.Status.COMPLETED
                if kb_sources:
                    assistant_message.kb_sources = kb_sources

                # ── Sprint 3: генерация доп. вариантов ответа ─────────────────
                # main bubble = Краткий; variants array holds the two alternatives only
                all_variants = []
                if variants_mode and full_text:
                    _base_msgs = [m for m in messages_for_api if not (
                        m.get("role") == "system" and "КРАТКИЙ ответ" in m.get("content", "")
                    )][:-1]  # all except brief suffix + last user msg

                    def _gen_variant(suffix_text, label):
                        try:
                            _msgs = _base_msgs + [
                                {"role": "system", "content": suffix_text},
                                {"role": "user", "content": message_text or "Привет"},
                            ]
                            _c = get_laozhang_client()
                            _r = _c.chat.completions.create(
                                model=model_name,
                                messages=_msgs,
                                temperature=0.7,
                                max_tokens=min(max_tokens, 2000),
                                stream=False,
                            )
                            _t = _r.choices[0].message.content or ""
                            return {"label": label, "content": CodeFormatter.format_ai_response(_t), "plain_text": _t}
                        except Exception:
                            return None

                    from concurrent.futures import ThreadPoolExecutor, as_completed
                    with ThreadPoolExecutor(max_workers=2) as _ex:
                        _futures = {_ex.submit(_gen_variant, suf, lbl): lbl for suf, lbl in [
                            ("Дай развёрнутый ответ с примерами кода если применимо. Минимум 200 слов.", "Подробный"),
                            ("Структурируй ответ как пошаговое руководство с нумерованными шагами.", "Пошаговый"),
                        ]}
                        for _fut in as_completed(_futures):
                            _v = _fut.result()
                            if _v:
                                all_variants.append(_v)

                    all_variants.sort(key=lambda v: ["Подробный", "Пошаговый"].index(v["label"]) if v["label"] in ["Подробный", "Пошаговый"] else 99)
                    assistant_message.variants = all_variants

                    # Sprint 3: 1.5× billing — charge extra 0.5× for the 2 parallel variant calls
                    if all_variants and deduct_stars:
                        import math as _math
                        _extra_kopecks = max(1, _math.ceil(cost_kopecks * 0.5))
                        try:
                            user.spend_kopecks(_extra_kopecks, type='spend', reference=f'chat-variants:{assist_msg_id}')
                            UserSpending.objects.create(
                                user=user, amount=max(1, _extra_kopecks // 100), amount_kopecks=_extra_kopecks,
                                description=f"Генерация вариантов ответа (×1.5) в чате с {network.name}",
                            )
                        except Exception:
                            pass

                assistant_message.save()

                # ── Persistent Memory: извлечение фактов (фон, каждые 3 ответа) ──
                try:
                    from aitext.tasks import extract_memory_facts
                    completed_count = chat.messages.filter(
                        role='assistant', status=Message.Status.COMPLETED
                    ).count()
                    if completed_count % 3 == 0:
                        extract_memory_facts.delay(chat.id)
                except Exception as _mem_err:
                    logger.error(f'[memory] failed to enqueue extract_memory_facts for chat {chat.id}: {_mem_err}')

                # ── UsageEvent (unified analytics) ──
                try:
                    from aitext.usage import log_usage_event
                    ab_meta = {'ab_test_id': ab_test_id, 'ab_variant': ab_variant} if ab_test_id else {}
                    log_usage_event(
                        user=user,
                        event_type='search' if web_search else 'message',
                        channel='web',
                        network=network,
                        cost_kopecks=cost_kopecks if deduct_stars else 0,
                        **ab_meta,
                    )
                except Exception:
                    pass

                # AI-коммиты из чата (Sprint 4.3)
                commit_event = None
                if getattr(settings, 'PROJECT_AI_COMMITS', False) and chat.project_id and full_text:
                    try:
                        from aitext.models import Project as ProjectModel
                        from aitext.commit_extract import extract_commit_from_response
                        _proj = ProjectModel.objects.get(id=chat.project_id)
                        _commit = extract_commit_from_response(_proj, full_text)
                        if _commit:
                            commit_event = {
                                'id': _commit.id,
                                'commit_message': _commit.commit_message,
                                'files_count': len(_commit.files),
                                'project_id': _commit.project_id,
                            }
                    except Exception:
                        pass

                yield _sse({
                    "type": "done",
                    "content": formatted_html,
                    "plain_text": full_text,
                    "search_context": search_context_text,
                    **({"sources": kb_sources} if kb_sources else {}),
                    **({"variants": all_variants} if all_variants else {}),
                    **({"commit_proposed": commit_event} if commit_event else {}),
                })

            except Exception as e:
                err_type = type(e).__name__
                err_detail = str(e)
                logger.error(
                    f"SSE streaming error for message {assist_msg_id} "
                    f"(web_search={web_search}, model={model_name}): "
                    f"{err_type}: {err_detail}",
                    exc_info=True,
                )
                if deduct_stars:
                    user.add_kopecks(cost_kopecks, type='refund', reference=f'chat:{assist_msg_id}')
                    from core.money import format_rub
                    logger.info(f"Refunded {format_rub(cost_kopecks)} to {user.email} after streaming error")
                user_msg = f"Ошибка при генерации ответа. Попробуйте ещё раз."
                assistant_message.status = Message.Status.FAILED
                assistant_message.error_message = user_msg
                assistant_message.save()
                yield _sse({"type": "error", "message": user_msg})

        resp = StreamingHttpResponse(generate(), content_type='text/event-stream; charset=utf-8')
        resp['Cache-Control'] = 'no-cache'
        resp['X-Accel-Buffering'] = 'no'
        return resp


class RegenerateView(APIView):
    """Reset last assistant message and re-run AI generation."""
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        network = chat.network

        last_user = chat.messages.filter(role='user').order_by('-created_at').first()
        last_assistant = chat.messages.filter(role='assistant').order_by('-created_at').first()

        if not last_user or not last_assistant:
            return Response({
                'error': {
                    'message': 'Нет сообщений для повторной генерации',
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        cost_kopecks = network.cost_kopecks

        if network.provider != 'fal-ai' and not request.user.has_enough_kopecks(cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': f'Недостаточно средств. Нужно {format_rub(cost_kopecks)}, у вас {format_rub(request.user.balance_kopecks)}.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        if network.provider != 'fal-ai':
            request.user.spend_kopecks(cost_kopecks, type='spend', reference=f'chat-regen:{last_assistant.id}')
            UserSpending.objects.create(
                user=request.user, amount=max(1, cost_kopecks // 100), amount_kopecks=cost_kopecks,
                description=f"Повторная генерация в чате с {network.name}",
            )

        last_assistant.content = ''
        last_assistant.plain_text = ''
        last_assistant.status = Message.Status.PENDING
        last_assistant.error_message = None
        last_assistant.save()

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(last_assistant.id)

        return Response({
            'assistant_message_id': last_assistant.id,
            'new_balance': request.user.pages_count,
            'new_balance_kopecks': request.user.balance_kopecks,
        })
