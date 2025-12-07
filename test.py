import openai as kolosal
from openai import OpenAI 

API_KEY_TOKEN = "kol_eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VyX2lkIjoiYmM0ZDk2NWItMzBkMC00Mjg5LWJlY2UtODVlNmQwYTIzN2U1Iiwia2V5X2lkIjoiMDgyMGY5MmEtNzY5Ni00ZGJlLWExMmYtNDZhODk4OTYzODZiIiwia2V5X25hbWUiOiJEYW1hZ2VEZXRlY3RpbyIsImVtYWlsIjoicm9kaGlmaXJtYW5zeWFoNjUyN0BnbWFpbC5jb20iLCJyYXRlX2xpbWl0X3JwcyI6bnVsbCwibWF4X2NyZWRpdF91c2UiOm51bGwsImNyZWF0ZWRfYXQiOjE3NjQ5OTE1NDAsImV4cGlyZXNfYXQiOjE3OTY1Mjc1NDAsImlhdCI6MTc2NDk5MTU0MH0.8yqho1apEoyo3bk2FVwDClWZyeOwFdJm4XaaLmY3h6Y"
BASE_URL = "https://api.kolosal.ai/v1"

kolosal_client = OpenAI(
    api_key=API_KEY_TOKEN,
    base_url=BASE_URL
)

try:
    response = kolosal_client.chat.completions.create(
        model="Claude Sonnet 4.5",
        messages=[
            {"role": "user", "content": "Hello, how are you?"}
        ]
    )
    print("Panggilan berhasil!")
    print(response.choices[0].message.content)

except Exception as e:
    print(f"Terjadi kesalahan: {e}")