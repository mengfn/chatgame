from openai import OpenAI
import os


def ask_llm(
    prompt: str,
    system_prompt: str = "You are a strategic decision-making agent."
) -> str:
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    completion = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        temperature=0.7,
        max_tokens=512,
    )
    return completion.choices[0].message.content