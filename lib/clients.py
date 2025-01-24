import time
from typing import List, Dict, Optional

import jwt
import requests
from openai import OpenAI


class BaseClient:
    def __init__(self, api_key: Optional[str]):
        self.api_key = api_key

    def call(
            self,
            prompt: str,
            user_message: str,
            context: Optional[List[Dict[str, str]]] = None,
            max_tokens: int = 500,
            temperature: float = 0.5,
    ) -> str:
        raise NotImplementedError("It's base class, you can't call this method")


class YandexGPTClient(BaseClient):
    def __init__(self, service_account_id: str, key_id: str, private_key: str,
                 model_url: str = "gpt://b1glbb4lnvrf7787ki53/yandexgpt/latest"):
        super().__init__(api_key=None)

        self.service_account_id = service_account_id
        self.key_id = key_id
        self.private_key = private_key
        self.token = self._generate_iam_token()
        self.model_url = model_url

    def _generate_iam_token(self) -> str:
        now = int(time.time())

        payload = {
            "aud": "https://iam.api.cloud.yandex.net/iam/v1/tokens",
            "iss": self.service_account_id,
            "iat": now,
            "exp": now + 360,
        }

        encoded_token = jwt.encode(
            payload, self.private_key, algorithm="PS256", headers={"kid": self.key_id}
        )

        url = "https://iam.api.cloud.yandex.net/iam/v1/tokens"

        response = requests.post(
            url, headers={"Content-Type": "application/json"}, json={"jwt": encoded_token}
        ).json()

        return response["iamToken"]

    def call(
            self,
            prompt: str,
            user_message: str,
            context: Optional[List[Dict[str, str]]] = None,
            max_tokens: int = 500,
            temperature: float = 0.5,
    ) -> str:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        messages = [
            {
                "role": "system",
                "text": prompt,
            }
        ]

        if context:
            messages.extend(context)

        messages.append(
            {
                "role": "user",
                "text": user_message,
            }
        )

        data = {
            "modelUri": self.model_url,
            "completionOptions": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
            "messages": messages,
        }

        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {self.token}"},
            json=data,
        ).json()

        return response["result"]["alternatives"][0]["message"]["text"]


class OpenAIClient(BaseClient):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        super().__init__(api_key=api_key)

        self.model = model
        self.client = OpenAI(api_key=self.api_key)

    def call(
            self,
            prompt: str,
            user_message: str,
            context: Optional[List[Dict[str, str]]] = None,
            max_tokens: int = 500,
            temperature: float = 0.5,
    ) -> str:
        messages = [
            {
                "role": "system",
                "content": prompt,
            }
        ]

        if context:
            messages.extend(context)

        messages.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        return completion.choices[0].message.content
