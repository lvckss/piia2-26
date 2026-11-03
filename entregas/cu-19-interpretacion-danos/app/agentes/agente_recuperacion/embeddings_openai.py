"""Explicitly budgeted embeddings; spec 32, AC-002/005/012."""

from dataclasses import dataclass
import math
import os
from pathlib import Path

import openai
import tiktoken

from normativa_rag import EmbeddingBatch, RagError


@dataclass
class SpendingBudget:
    limit_usd: float
    reserved_usd: float = 0.0
    reported_usd: float = 0.0

    def reserve(self, tokens, model):
        if not math.isfinite(self.limit_usd) or self.limit_usd < 0:
            raise ValueError("Presupuesto no válido")
        amount = tokens * model.usd_per_million / 1_000_000
        if self.reserved_usd + amount > self.limit_usd:
            raise PermissionError("La siguiente llamada supera el presupuesto autorizado")
        self.reserved_usd += amount


def count_tokens(text):
    os.environ.setdefault("TIKTOKEN_CACHE_DIR",str(Path(__file__).resolve().parents[3]/".cache-rag/tiktoken"))
    return len(tiktoken.get_encoding("cl100k_base").encode(text, disallowed_special=()))


class OpenAIEmbeddings:
    def __init__(self, budget, client=None):
        self.budget, self.client = budget, client

    def embed(self, texts, model):
        if not 1 <= len(texts) <= 2048 or not all(isinstance(t,str) and t.strip() for t in texts):
            raise ValueError("Lote vacío o entradas de embeddings no válidas")
        counts = [count_tokens(text) for text in texts]
        if max(counts) > 8192 or sum(counts) > 300_000:
            raise ValueError("El lote supera el límite de tokens de embeddings")
        self.budget.reserve(sum(counts), model)
        if self.client is None:
            if not os.environ.get("OPENAI_API_KEY"):
                raise RagError("EMBEDDINGS_AUTENTICACION", "Falta OPENAI_API_KEY", stage="embeddings")
            self.client = openai.OpenAI(base_url="https://api.openai.com/v1", max_retries=0, timeout=30.0)
        try:
            response = self.client.embeddings.create(input=texts, model=model.name,
                dimensions=model.dimensions, encoding_format="float")
        except (openai.AuthenticationError, openai.PermissionDeniedError) as error:
            raise RagError("EMBEDDINGS_AUTENTICACION", "OpenAI ha rechazado las credenciales o el acceso al modelo", stage="embeddings") from error
        except openai.RateLimitError as error:
            quota = error.code in ("insufficient_quota", "billing_hard_limit_reached")
            raise RagError("EMBEDDINGS_CUOTA" if quota else "EMBEDDINGS_LIMITE_TEMPORAL",
                "Cuota de OpenAI agotada" if quota else "Límite temporal de OpenAI alcanzado",
                stage="embeddings", retryable=not quota) from error
        except openai.APITimeoutError as error:
            raise RagError("EMBEDDINGS_TIMEOUT", "OpenAI no ha respondido a tiempo", stage="embeddings", retryable=True) from error
        except (openai.APIConnectionError, openai.APIStatusError) as error:
            raise RagError("EMBEDDINGS_RESPUESTA_INVALIDA", "No se pudo completar la petición de embeddings",
                stage="embeddings", retryable=getattr(error,"status_code",500)>=500) from error
        usage = getattr(getattr(response,"usage",None),"prompt_tokens",None)
        if type(usage) is not int or usage < 0:
            raise RagError("EMBEDDINGS_RESPUESTA_INVALIDA", "OpenAI no ha devuelto un consumo válido", stage="embeddings")
        self.budget.reported_usd += usage * model.usd_per_million / 1_000_000
        data = getattr(response,"data",None)
        if (response.model != model.name or not isinstance(data,list) or len(data)!=len(texts)
                or any(type(item.index) is not int for item in data)
                or sorted(item.index for item in data)!=list(range(len(texts)))
                or any(not isinstance(item.embedding,list) for item in data)):
            raise RagError("EMBEDDINGS_RESPUESTA_INVALIDA", "Respuesta incompleta o incompatible con el modelo solicitado", stage="embeddings")
        return EmbeddingBatch([item.embedding for item in sorted(data,key=lambda item:item.index)],
                              usage,str(getattr(response,"_request_id","") or ""))
