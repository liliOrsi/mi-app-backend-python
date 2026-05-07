from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    ENVIRONMENT: str = "development"
    
    DATABASE_URL: str = ""

    OPENAI_API_KEY: str = ""

    SUPABASE_URL: str = ""

    SUPABASE_ANON_KEY: str = ""

    ANTHROPIC_API_KEY: str = ""

    TAVILY_API_KEY: str = ""

    NESTJS_BASE_URL: str = "http://localhost:3000"
    
    class Config:
        env_file = ".env"

settings = Settings()