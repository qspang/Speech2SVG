from openai import OpenAI

client = OpenAI(
    api_key="sk-3pjhBWGy2expXnpNEwbafnhcDt2NMbAQJETvAuqHTxUKNrag",
    base_url="https://llm.xiaochisaas.com/v1"
)

response = client.chat.completions.create(
    model="gemini-3.1-pro-high",
    messages=[{"role": "user", "content": "你好！"}]
)

print(response.choices[0].message.content)