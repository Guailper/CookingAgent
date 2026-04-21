from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

class BaseAgent(base_url: str, api_key: str, model: str):
    self.agent = ChatOpenAI(
        openai_base_url=base_url,
        api_key=api_key,
        model=model
    )