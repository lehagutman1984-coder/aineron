"""
§7.5 Model Arena — Elo-рейтинг.

POST /v1/arena/vote/
    { winner_slug, loser_slug, compare_chat_ids: [int, int] }
    Обновляет elo_rating и elo_matches обеих моделей.
    Анти-абьюз: один compare_chat_id не может участвовать дважды.

GET /v1/arena/leaderboard/
    Список моделей, отсортированный по elo_rating (убывание).
"""
import logging
from django.core.cache import cache
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response

from aitext.models import NeuralNetwork, ModelMatch

logger = logging.getLogger(__name__)

_K = 32  # стандартный K-фактор Elo


def _expected(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def _update_elo(winner: NeuralNetwork, loser: NeuralNetwork):
    ew = _expected(winner.elo_rating, loser.elo_rating)
    el = _expected(loser.elo_rating, winner.elo_rating)
    winner.elo_rating = round(winner.elo_rating + _K * (1 - ew), 2)
    loser.elo_rating = round(loser.elo_rating + _K * (0 - el), 2)
    winner.elo_matches += 1
    loser.elo_matches += 1
    winner.save(update_fields=['elo_rating', 'elo_matches'])
    loser.save(update_fields=['elo_rating', 'elo_matches'])


class ArenaVoteView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        winner_slug = (request.data.get('winner_slug') or '').strip()
        loser_slug = (request.data.get('loser_slug') or '').strip()
        compare_chat_ids = request.data.get('compare_chat_ids') or []

        if not winner_slug or not loser_slug:
            return Response({'error': 'winner_slug и loser_slug обязательны'}, status=400)
        if winner_slug == loser_slug:
            return Response({'error': 'winner и loser должны быть разными моделями'}, status=400)
        if not isinstance(compare_chat_ids, list) or len(compare_chat_ids) < 1:
            return Response({'error': 'compare_chat_ids должен содержать хотя бы один chat_id'}, status=400)

        # Anti-abuse: each compare chat can only vote once
        already_voted = ModelMatch.objects.filter(
            compare_chat_ids__overlap=compare_chat_ids
        ).exists()
        if already_voted:
            return Response({'error': 'Вы уже голосовали по этому сравнению'}, status=400)

        try:
            winner = NeuralNetwork.objects.get(slug=winner_slug, is_active=True)
            loser = NeuralNetwork.objects.get(slug=loser_slug, is_active=True)
        except NeuralNetwork.DoesNotExist:
            return Response({'error': 'Одна из моделей не найдена'}, status=404)

        with transaction.atomic():
            match = ModelMatch.objects.create(
                winner=winner,
                loser=loser,
                prompt_snippet='',
                user=request.user,
                compare_chat_ids=compare_chat_ids,
            )
            _update_elo(winner, loser)

        cache.delete(_LEADERBOARD_CACHE_KEY)  # рейтинг обновился — сбросить кэш

        return Response({
            'match_id': match.id,
            'winner': {
                'slug': winner.slug,
                'name': winner.name,
                'elo_rating': winner.elo_rating,
                'elo_matches': winner.elo_matches,
            },
            'loser': {
                'slug': loser.slug,
                'name': loser.name,
                'elo_rating': loser.elo_rating,
                'elo_matches': loser.elo_matches,
            },
        }, status=201)


_LEADERBOARD_CACHE_KEY = 'arena:leaderboard'
_LEADERBOARD_CACHE_TTL = 60


class ArenaLeaderboardView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        cached = cache.get(_LEADERBOARD_CACHE_KEY)
        if cached is not None:
            return Response(cached)
        networks = (
            NeuralNetwork.objects
            .filter(is_active=True, provider='openrouter')
            .order_by('-elo_rating')
            .values('slug', 'name', 'elo_rating', 'elo_matches', 'avatar_url', 'description')
        )
        data = {'results': list(networks)}
        cache.set(_LEADERBOARD_CACHE_KEY, data, _LEADERBOARD_CACHE_TTL)
        return Response(data)
