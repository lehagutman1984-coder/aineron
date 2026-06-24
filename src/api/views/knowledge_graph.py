"""
§7.4 Knowledge Graph — cosine-similarity graph of project chunks.

GET /v1/projects/<pk>/graph/
    Returns nodes (files) and edges (cos-similarity > threshold) from pgvector.
    Frontend renders with react-force-graph or vis-network.
"""
import logging
from django.db import connection
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from aitext.models import Project, ProjectFile
from api.views._project_access import get_project_for_user

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.75
MAX_EDGES = 200


class KnowledgeGraphView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_project_for_user(request, pk)

        # Build nodes from files with at least one embedded chunk
        files = list(
            ProjectFile.objects.filter(
                project=project, embed_status='done', enabled=True
            ).values('id', 'filename', 'file_type')
        )
        if not files:
            return Response({'nodes': [], 'edges': []})

        file_ids = [f['id'] for f in files]
        nodes = [
            {
                'id': f['id'],
                'label': f['filename'],
                'type': f['file_type'],
            }
            for f in files
        ]

        # Compute pairwise cosine similarity via pgvector — average embedding per file
        if len(file_ids) < 2:
            return Response({'nodes': nodes, 'edges': []})

        # Build per-file average embedding then compute pairwise similarity
        sql = """
            WITH avg_emb AS (
                SELECT file_id, avg(embedding) AS emb
                FROM aitext_projectchunk
                WHERE file_id = ANY(%s) AND embedding IS NOT NULL
                GROUP BY file_id
            )
            SELECT
                a.file_id AS src,
                b.file_id AS dst,
                1 - (a.emb <=> b.emb) AS similarity
            FROM avg_emb a
            CROSS JOIN avg_emb b
            WHERE a.file_id < b.file_id
              AND 1 - (a.emb <=> b.emb) >= %s
            ORDER BY similarity DESC
            LIMIT %s
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute(sql, [file_ids, SIMILARITY_THRESHOLD, MAX_EDGES])
                rows = cursor.fetchall()
            edges = [
                {'source': row[0], 'target': row[1], 'weight': round(float(row[2]), 3)}
                for row in rows
            ]
        except Exception as e:
            logger.warning(f'[KnowledgeGraph] pgvector query failed: {e}')
            edges = []

        return Response({'nodes': nodes, 'edges': edges})
