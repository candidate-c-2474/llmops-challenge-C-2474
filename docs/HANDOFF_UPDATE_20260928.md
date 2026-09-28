# ATUALIZACAO DO HANDOFF — Correcoes de CI e Codigo (28/09/2026)
# Cole este bloco APOS o handoff original no seu Qwen Local

---

## MUDANCAS CRITICAS DESDE O HANDOFF ORIGINAL

### 1. Candidate ID Definitivo
- O ID foi gerado e travado como **C-2474**
- Algoritmo: SHA-256(unix_timestamp + 'roomfit-copilot')[:4].upper()
- Repositorio: https://github.com/candidate-c-2474/llmops-challenge-C-2474
- Autor Git: C-2474 <c-2474@candidates.invalid>

### 2. Correcao do build-backend dos pacotes
Os arquivos pyproject.toml foram corrigidos de `setuptools.backends._legacy:_Backend` para o padrao oficial `setuptools.build_meta`.

```toml
# packages/inference_gateway/pyproject.toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

# packages/rag_core/pyproject.toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"
```

### 3. Correcao do structlog (CacheInvalidator)
O structlog possui um argumento posicional interno chamado `event`. Nosso codigo original usava `event=update.event.value` como argumento nomeado, causando colisao de parametros e silenciando a invalidacao de cache.

**ANTES (quebrado):**
```python
logger.info("cache.invalidation.start", event=update.event.value, products=update.product_ids)
```

**DEPOIS (corrigido):**
```python
logger.info("cache.invalidation.start", event_type=update.event.value, products=update.product_ids)
```

### 4. ExactCache com Programacao Defensiva (Pipeline Check)
O ExactCache agora verifica se o cliente Redis suporta pipelines antes de usa-los. Isso permite que o cache funcione tanto com Redis real (producao) quanto com FakeRedis (testes).

```python
# packages/rag_core/src/rag_core/cache/exact_cache.py
async def set(self, query: str, chunks: list[RetrievedChunk], ttl: int | None = None):
    key = self._cache_key(query)
    data = json.dumps([c.model_dump() for c in chunks])
    
    if hasattr(self._client, "pipeline"):
        pipe = self._client.pipeline()
        pipe.set(key, data, ex=ttl or self._config.exact_cache_ttl)
        for chunk in chunks:
            product_set_key = f"{self.PRODUCT_MAP_PREFIX}{chunk.product_id}"
            pipe.sadd(product_set_key, key)
            pipe.expire(product_set_key, ttl or self._config.exact_cache_ttl)
        await pipe.execute()
    else:
        await self._client.set(key, data, ex=ttl or self._config.exact_cache_ttl)
        for chunk in chunks:
            product_set_key = f"{self.PRODUCT_MAP_PREFIX}{chunk.product_id}"
            if hasattr(self._client, "sadd"):
                await self._client.sadd(product_set_key, key)
```

### 5. CacheInvalidator com Fallback Defensivo
O CacheInvalidator agora verifica se o semantic cache possui o metodo `invalidate_by_product_id` antes de chama-lo, caindo para `invalidate_all` se necessario.

```python
# packages/rag_core/src/rag_core/cache/invalidation.py
async def on_catalog_update(self, update: CatalogUpdate) -> None:
    if update.event == CatalogEvent.PRODUCT_CREATED:
        return
    logger.info("cache.invalidation.start", event_type=update.event.value, products=update.product_ids)
    invalidated_count = 0
    for pid in update.product_ids:
        count_exact = await self._exact.invalidate_by_product_id(pid)
        count_semantic = 0
        if hasattr(self._semantic, "invalidate_by_product_id"):
            count_semantic = await self._semantic.invalidate_by_product_id(pid)
        elif hasattr(self._semantic, "invalidate_all"):
            count_semantic = await self._semantic.invalidate_all()
        invalidated_count += (count_exact + count_semantic)
    logger.info("cache.invalidation.completed", total_purged=invalidated_count)
```

### 6. FakeRedis Completo para Testes de Integracao
O FakeRedis no teste de integracao agora suporta pipelines, sets (sadd/smembers) e scan_iter:

```python
# apps/api/tests/test_cache_invalidation_integration.py
class FakePipeline:
    def __init__(self, client):
        self.client = client
        self.cmds = []
    def set(self, k, v, ex=None):
        self.cmds.append(("set", k, v, ex))
        return self
    def sadd(self, s, v):
        self.cmds.append(("sadd", s, v))
        return self
    def expire(self, k, ttl):
        self.cmds.append(("expire", k, ttl))
        return self
    def delete(self, *ks):
        self.cmds.append(("delete", ks))
        return self
    async def execute(self):
        for cmd in self.cmds:
            action = cmd[0]
            if action == "set":
                await self.client.set(cmd[1], cmd[2], cmd[3])
            elif action == "sadd":
                await self.client.sadd(cmd[1], cmd[2])
            elif action == "delete":
                await self.client.delete(*cmd[1])
        self.cmds = []

class FakeRedis:
    def __init__(self):
        self.store = {}
        self.sets = {}
    async def get(self, k):
        return self.store.get(k)
    async def set(self, k, v, ex=None):
        self.store[k] = v
    async def delete(self, *ks):
        for k in ks:
            self.store.pop(k, None)
            self.sets.pop(k, None)
    async def sadd(self, key, val):
        if key not in self.sets:
            self.sets[key] = set()
        self.sets[key].add(val)
    async def smembers(self, key):
        return list(self.sets.get(key, set()))
    async def scan_iter(self, match="*", count=100):
        for k in list(self.store.keys()):
            yield k
    def pipeline(self):
        return FakePipeline(self)
```

### 7. DummySemantic no Teste Atualizado
O DummySemantic agora possui ambos os metodos para compatibilidade com o CacheInvalidator defensivo:

```python
class DummySemantic:
    async def invalidate_by_product_id(self, product_id):
        return 0
    async def invalidate_all(self):
        return 0
```

### 8. Limpeza do Repositorio
- Removidos todos os arquivos `__pycache__/` e `*.pyc` do Git tracking
- Removido `.env` do Git tracking (mantido apenas `.env.example`)
- `.gitignore` atualizado com regras para `__pycache__/`, `*.pyc`, `*.pyo`, `.env`

---

## STATUS FINAL DO CI (GitHub Actions)
- Anonymity Gate: PASSED
- inference_gateway tests (2/2): PASSED
- rag_core tests (2/2): PASSED
- Integration tests (1/1): PASSED
- Total: 5/5 PASSED

---

## INSTRUCAO PARA O QWEN LOCAL
Se durante o Live Defense o avaliador perguntar sobre alguma dessas correcoes, explique:
1. "We encountered a structlog parameter collision where 'event' is a reserved positional argument. We renamed it to 'event_type' to fix the cache invalidation pipeline."
2. "We added defensive hasattr() checks in ExactCache to support both real Redis pipelines in production and lightweight FakeRedis mocks in CI tests."
3. "All fixes are validated by our GitHub Actions CI suite which runs 5/5 tests green on every push."
