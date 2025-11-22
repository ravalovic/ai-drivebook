from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from config import MODEL_NAME
from models import CityList


def get_candidate_cities_from_llm(start_city: str) -> List[str]:
    """
    Zavolá LLM a vráti zoznam 10 miest nad 5000 obyvateľov
    v okruhu cca 300 km od východzieho mesta.
    """
    print(f"--- LLM: HĽADANIE MIEST OKOLO {start_city} ---")
    llm = ChatOpenAI(model=MODEL_NAME, temperature=0)

    system = (
        "Si expert na geografiu Slovenska. Poznáš všetky mestá a obce prioritne na Slovensku. "
        "Poznáš mestá a obce s počtom obyvateľov a vzdialenosti medzi nimi. "
        "Tvojou úlohou je vybrať vhodné mestá pre služobné cesty."
    )

    human = f"""
    Vygeneruj zoznam 10 reálnych miest nad 5000 obyvateľov,
    ktoré sa nachádzajú v okruhu približne 300 km od mesta "{start_city}".
    Vždy vyber do zoznamu Bratislavu.
    Neuvádzaj mestské časti, iba samostatné mestá.
    Vyberaj aj dlhšie trasy.
    Vráť iba zoznam názvov miest.
    """

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system),
            ("human", human),
        ]
    )

    structured_llm = llm.with_structured_output(CityList)
    chain = prompt | structured_llm
    response: CityList = chain.invoke({})

    cities = [c.strip() for c in response.cities if c.strip()]
    print(f"LLM vybralo kandidátske mestá: {cities}")
    return cities[:10]
