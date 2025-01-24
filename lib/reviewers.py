import typing

from lib.clients import BaseClient, YandexGPTClient, OpenAIClient
from lib.parser import NotebookCell, merge_task_into_single_string
from lib.prompts import PROMPTS_GENERATOR


class StepByStepTaskReviewer:
    def __init__(self, client: BaseClient) -> None:
        self.client = client

    def review(
            self,
            cells: typing.List[NotebookCell],
            maximum_possible_score: typing.Optional[int] = None,
            prompt: typing.Optional[str] = None
    ) -> str:

        if maximum_possible_score is None:
            maximum_possible_score = 10

        if prompt is None:
            prompt = PROMPTS_GENERATOR["advanced_prompt"](maximum_possible_score)

        context: typing.List[typing.Dict[str, str]] = []

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
    def __init__(self, yandex_client) -> None:
        self.client = yandex_client

    def review(
            self,
            cells: typing.List[NotebookCell],
            maximum_possible_score: typing.Optional[int] = None,
            prompt: typing.Optional[str] = None
    ) -> str:
        if maximum_possible_score is None:
            maximum_possible_score = 10

        if prompt is None:
            prompt = PROMPTS_GENERATOR["advanced_prompt"](maximum_possible_score)

        solved_task = merge_task_into_single_string(cells)
        return self.client.call(prompt, solved_task)
