import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from elasticsearch import Elasticsearch, NotFoundError

from app.config import get_settings
from app.services.phonetic import african_soundex, combined_match_score

logger = logging.getLogger(__name__)
settings = get_settings()

INDEX_MAPPING = {
    "settings": {
        "analysis": {
            "analyzer": {
                "name_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "asciifolding"],
                },
                "arabic_analyzer": {
                    "type": "arabic",
                },
            }
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "official_name": {
                "type": "text",
                "analyzer": "name_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "phonetic": {"type": "keyword"},
                },
            },
            "arabic_name": {
                "type": "text",
                "analyzer": "arabic_analyzer",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "variants": {"type": "text", "analyzer": "name_analyzer"},
            "language": {"type": "keyword"},
            "region": {"type": "keyword"},
            "phonetic_code": {"type": "keyword"},
        }
    },
}


class ElasticsearchService:
    def __init__(self) -> None:
        self._client: Optional[Elasticsearch] = None
        self._available = False

    @property
    def client(self) -> Optional[Elasticsearch]:
        return self._client

    @property
    def available(self) -> bool:
        return self._available

    def connect(self) -> bool:
        if not settings.elasticsearch_enabled:
            logger.info("Elasticsearch desactive (ELASTICSEARCH_ENABLED=false).")
            self._available = False
            return False

        try:
            self._client = Elasticsearch(
                settings.elasticsearch_url,
                request_timeout=2,
                max_retries=0,
                retry_on_timeout=False,
            )
            if self._client.ping():
                self._available = True
                self.ensure_index()
                logger.info("Elasticsearch connected.")
                return True
        except Exception as exc:
            logger.warning("Elasticsearch indisponible: %s", exc)
        self._available = False
        self._client = None
        return False

    def ensure_index(self) -> None:
        if not self._client:
            return
        index = settings.elasticsearch_index
        if not self._client.indices.exists(index=index):
            self._client.indices.create(index=index, body=INDEX_MAPPING)
            logger.info("Created index %s", index)

    def index_citizen(self, citizen_data: Dict[str, Any]) -> None:
        if not self._available or not self._client:
            return
        doc = {
            **citizen_data,
            "phonetic_code": african_soundex(citizen_data.get("official_name", "")),
        }
        self._client.index(
            index=settings.elasticsearch_index,
            id=str(citizen_data["id"]),
            document=doc,
        )

    def delete_citizen(self, citizen_id: UUID) -> None:
        if not self._available or not self._client:
            return
        try:
            self._client.delete(index=settings.elasticsearch_index, id=str(citizen_id))
        except NotFoundError:
            pass

    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if not self._available or not self._client:
            return []

        phonetic = african_soundex(query)
        body = {
            "size": limit,
            "query": {
                "bool": {
                    "should": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "official_name^3",
                                    "official_name.keyword^2",
                                    "variants^2",
                                    "arabic_name^2",
                                ],
                                "fuzziness": "AUTO",
                                "prefix_length": 1,
                            }
                        },
                        {
                            "match": {
                                "official_name": {
                                    "query": query,
                                    "fuzziness": 2,
                                }
                            }
                        },
                        {"term": {"phonetic_code": phonetic}},
                        {
                            "wildcard": {
                                "official_name.keyword": f"*{query.lower()}*"
                            }
                        },
                    ],
                    "minimum_should_match": 1,
                }
            },
        }

        try:
            response = self._client.search(index=settings.elasticsearch_index, body=body)
            hits = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                source["score"] = hit["_score"]
                source["match_type"] = "elasticsearch"
                hits.append(source)
            return hits
        except Exception as exc:
            logger.error("ES search failed: %s", exc)
            return []

    def autocomplete(self, prefix: str, limit: int = 8) -> List[str]:
        if not self._available or not self._client or len(prefix) < 2:
            return []
        body = {
            "size": limit,
            "query": {
                "match_phrase_prefix": {
                    "official_name": {"query": prefix}
                }
            },
            "_source": ["official_name"],
        }
        try:
            response = self._client.search(index=settings.elasticsearch_index, body=body)
            return [h["_source"]["official_name"] for h in response["hits"]["hits"]]
        except Exception:
            return []


es_service = ElasticsearchService()
