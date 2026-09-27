from pydantic_settings import BaseSettings

class PostgresConfig(BaseSettings):
    host: str = "postgres"
    port: int = 5432
    user: str = "roomfit"
    password: str = "roomfit"
    database: str = "roomfit"
    min_pool_size: int = 2
    max_pool_size: int = 10

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

    model_config = {"env_prefix": "POSTGRES_"}

class RedisConfig(BaseSettings):
    host: str = "redis"
    port: int = 6379
    db: int = 0
    password: str | None = None
    exact_cache_ttl: int = 3600
    semantic_cache_ttl: int = 1800
    semantic_similarity_threshold: float = 0.92

    @property
    def url(self) -> str:
        auth = f":{self.password}@" if self.password else ""
        return f"redis://{auth}{self.host}:{self.port}/{self.db}"

    model_config = {"env_prefix": "REDIS_"}

class RetrievalConfig(BaseSettings):
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L6-v2"
    bm25_weight: float = 0.4
    dense_weight: float = 0.6
    rrf_k: int = 60
    top_k_retrieve: int = 20
    top_k_rerank: int = 5
    embedding_dim: int = 384
    model_config = {"env_prefix": "RETRIEVAL_"}

class AgentConfig(BaseSettings):
    max_tool_rounds: int = 5
    max_context_tokens: int = 2048
    temperature: float = 0.3
    system_prompt_template: str = "roomfit_copilot"
    model_config = {"env_prefix": "AGENT_"}

class RAGConfig(BaseSettings):
    postgres: PostgresConfig = PostgresConfig()
    redis: RedisConfig = RedisConfig()
    retrieval: RetrievalConfig = RetrievalConfig()
    agent: AgentConfig = AgentConfig()
