"""
Django Channels consumers:
  - YjsConsumer  — real-time collaborative editing via y-websocket protocol
  - VoiceConsumer — half-duplex voice (push-to-talk): ASR → LLM → TTS
"""
import json
import logging

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer

from api.error_messages import em

logger = logging.getLogger(__name__)


# ─────────────────────────── Yjs Collaborative Editing ────────────────────────

class YjsConsumer(AsyncWebsocketConsumer):
    """
    Minimal y-websocket broadcast consumer.
    Groups by project_id; broadcasts raw bytes to all connected clients.
    Loads/saves binary snapshot to Project.yjs_state.
    """

    async def connect(self):
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self.group_name = f'yjs_project_{self.project_id}'
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        has_access = await self._check_access()
        if not has_access:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send stored snapshot to new connection
        snapshot = await self._load_snapshot()
        if snapshot:
            await self.send(bytes_data=snapshot)

    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, bytes_data=None, text_data=None):
        if bytes_data is None:
            return
        # Broadcast to all others in group
        await self.channel_layer.group_send(self.group_name, {
            'type': 'yjs.update',
            'bytes': bytes_data.hex(),
            'sender': self.channel_name,
        })
        # Persist snapshot (fire-and-forget — ignore errors)
        try:
            await self._save_snapshot(bytes_data)
        except Exception:
            pass

    async def yjs_update(self, event):
        if event.get('sender') == self.channel_name:
            return
        await self.send(bytes_data=bytes.fromhex(event['bytes']))

    @database_sync_to_async
    def _check_access(self):
        from aitext.models import Project, ProjectCollaborator
        project_id = int(self.project_id)
        if Project.objects.filter(pk=project_id, user=self.user).exists():
            return True
        return ProjectCollaborator.objects.filter(
            project_id=project_id, user=self.user
        ).exists()

    @database_sync_to_async
    def _load_snapshot(self):
        from aitext.models import Project
        try:
            p = Project.objects.get(pk=int(self.project_id))
            return bytes(p.yjs_state) if p.yjs_state else None
        except Project.DoesNotExist:
            return None

    @database_sync_to_async
    def _save_snapshot(self, data: bytes):
        from aitext.models import Project
        Project.objects.filter(pk=int(self.project_id)).update(yjs_state=data)


# ─────────────────────────── Voice Consumer (half-duplex) ─────────────────────

class VoiceConsumer(AsyncWebsocketConsumer):
    """
    Half-duplex voice: client sends audio blob → ASR → LLM → TTS → audio back.
    Pipeline: WebSocket binary frame → Whisper → LLM stream → TTS → bytes.
    """

    async def connect(self):
        self.chat_id = self.scope['url_route']['kwargs']['chat_id']
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        has_access = await self._check_access()
        if not has_access:
            await self.close(code=4403)
            return

        await self.accept()

    async def disconnect(self, code):
        pass

    async def receive(self, bytes_data=None, text_data=None):
        if bytes_data is None:
            return

        # Check balance before processing
        has_balance = await self._check_balance()
        if not has_balance:
            await self.send(text_data=json.dumps({'error': em('insufficient_balance_voice')}))
            return

        try:
            transcript = await self._transcribe(bytes_data)
            if not transcript:
                return
            await self.send(text_data=json.dumps({'transcript': transcript}))

            llm_reply = await self._llm(transcript)
            if not llm_reply:
                return
            await self.send(text_data=json.dumps({'reply': llm_reply}))

            audio_bytes = await self._tts(llm_reply)
            if audio_bytes:
                await self.send(bytes_data=audio_bytes)
        except Exception as e:
            logger.error('VoiceConsumer error: %s', e)
            await self.send(text_data=json.dumps({'error': em('voice_processing_error')}))

    @database_sync_to_async
    def _check_access(self):
        from aitext.models import Chat
        return Chat.objects.filter(pk=int(self.chat_id), user=self.user).exists()

    @database_sync_to_async
    def _check_balance(self):
        self.user.refresh_from_db(fields=['pages_count'])
        return self.user.pages_count > 0

    @database_sync_to_async
    def _transcribe(self, audio_bytes: bytes) -> str:
        import io
        from aitext.tasks import get_laozhang_client
        client = get_laozhang_client()
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = 'voice.webm'
        resp = client.audio.transcriptions.create(
            model='whisper-1',
            file=audio_file,
            language='ru',
        )
        return resp.text.strip()

    @database_sync_to_async
    def _llm(self, text: str) -> str:
        from aitext.tasks import get_laozhang_client
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': text}],
            max_tokens=512,
        )
        return resp.choices[0].message.content.strip()

    @database_sync_to_async
    def _tts(self, text: str) -> bytes:
        from aitext.tasks import get_laozhang_client
        client = get_laozhang_client()
        resp = client.audio.speech.create(
            model='tts-1',
            voice='alloy',
            input=text[:4096],
            response_format='mp3',
        )
        return resp.content
