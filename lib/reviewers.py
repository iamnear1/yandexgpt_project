from typing import List, Dict, Optional

from lib.clients import BaseClient, YandexGPTClient, OpenAIClient
from lib.parser import NotebookCell, merge_task_into_single_string
from lib.prompts import PROMPTS_GENERATOR


class StepByStepTaskReviewer:
    def __init__(self, client: BaseClient) -> None:
        self.client = client

    def review(
            self,
            cells: List[NotebookCell],
            maximum_possible_score: Optional[int] = None,
            prompt: Optional[str] = None
    ) -> str:

        if maximum_possible_score is None:
            maximum_possible_score = 10

        if prompt is None:
            prompt = PROMPTS_GENERATOR["advanced_prompt"](maximum_possible_score)

        context: List[Dict[str, str]] = []

        output: str = ""
        query_json_field_name: str

        if isinstance(self.client, YandexGPTClient):
            query_json_field_name = "text"
        elif isinstance(self.client, OpenAIClient):
            query_json_field_name = "content"
        else:
            raise NotImplementedError("unsupported model, fix me!")

        for i in range(0, (len(cells) // 2) * 2, 2):
            question_cell, answer_cell = cells[i], cells[i + 1]

            merged_cell = f"{question_cell.raw_text} \n {answer_cell.raw_text}"

            context.append(
                {
                    "role": "user",
                    query_json_field_name: merged_cell
                }
            )

            response = self.client.call(prompt, merged_cell, context=context)

            context.append(
                {
                    "role": "assistant",
                    query_json_field_name: response
                }
            )

            output += f"\nVerdict for question {i // 2 + 1}:\n{response}\n"

        return output


class FullTaskReviewer:
    def __init__(self, client: BaseClient) -> None:
        self.client = client

    def review(
            self,
            cells: List[NotebookCell],
            maximum_possible_score: Optional[int] = None,
            prompt: Optional[str] = None
    ) -> str:
        if maximum_possible_score is None:
            maximum_possible_score = 10

        if prompt is None:
            prompt = PROMPTS_GENERATOR["advanced_prompt"](maximum_possible_score)

        solved_task = merge_task_into_single_string(cells)
        return self.client.call(prompt, solved_task)


class CollaborativeTaskReviewer:
    def __init__(
            self,
            primary_client: BaseClient,
            secondary_client: BaseClient,
            iterations: int = 2,
            final_client: Optional[BaseClient] = None
    ) -> None:
        self.primary_client = primary_client
        self.secondary_client = secondary_client
        self.iterations = iterations
        self.final_client = final_client or primary_client

    def _build_context(self, client: BaseClient, text: str, history: list, feedback: Optional[str] = None) -> list:
        context_key = 'text' if isinstance(client, YandexGPTClient) else 'content'
        new_entry = f"Feedback: {feedback}\n\n{text}" if feedback else text
        return history + [{'role': 'user', context_key: new_entry}]

    def _format_response(self, client: BaseClient, response: str) -> dict:
        return {'role': 'assistant', 'text': response} if isinstance(client, YandexGPTClient) else {'role': 'assistant',
                                                                                                    'content': response}

    def review(
            self,
            cells: List[NotebookCell],
            maximum_possible_score: Optional[int] = None,
            prompt: Optional[str] = None
    ) -> str:
        if not cells:
            raise ValueError("No cells provided")

        solved_task = merge_task_into_single_string(cells)

        maximum_possible_score = maximum_possible_score or 10
        prompt = prompt or PROMPTS_GENERATOR["advanced_prompt"](maximum_possible_score)

        history = []
        last_feedback = None

        for i in range(self.iterations):
            current_client = self.secondary_client if i % 2 else self.primary_client
            context = self._build_context(current_client, solved_task, history, last_feedback)

            response = current_client.call(
                prompt=prompt,
                user_message=solved_task,
                context=context
            )

            formatted = self._format_response(current_client, response)
            history.append(formatted)
            last_feedback = response

        aggregation_prompt = PROMPTS_GENERATOR["aggregation_prompt"](
            maximum_possible_score,
            self.iterations
        )

        return self.final_client.call(
            prompt=aggregation_prompt,
            user_message=solved_task,
            context=history
        )
