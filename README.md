# yandexgpt_project

Данный проект создан в основном в помощь ассистентам, проверяющим домашние задания курса по математической статистике в МФТИ, с целью автоматизации и упрощения проверки. Однако также он несложно расширяется на другие подобные задачи.

### Преобразование jupyter-ноутбуков к удобному виду, который в дальнейшем подается LLM-модели.

```python
tasks, marks = parser.parsing_pipeline(
    notebook_path: str, original_notebook_path: str, kind: MergeKind, expected_task_count: int
)

# tasks: List[List[NotebookCell]] - список обработанных ячеек для каждого задания.
# marks: List[Optional[int]] - баллы за задание, если таковые были указаны в работе.
```

Поддерживаемые типы объединения ячеек можно посмотреть в [lib/parser.py](lib/parser.py). <br> <br>
Пример использования: <br>

```python
tasks, _ = parser.parsing_pipeline(
    "solved.ipynb", "original.ipynb", parser.MergeKind.BY_CHANGE, 1
)
task = tasks[0]

# вторая ячейка первого задания
task[1].raw_text
```

```python
'Решение: Поскольку величина имеет симметричное распределение, то матожидание равно 0. Давайте проверим это кодом ...'
```

Также можно посмотреть использование в [lib/test/tests.py](test/tests.py)

### Клиенты 

Для экспериметнов удобно было реализовать клиентов для моделей `YandexGPT` и `ChatGPT`, для того чтобы можно было легко
заменять модели. Их можно найти в [lib/clients.py](lib/clients.py)

```python
class YandexGPTClient(BaseClient):
    def __init__(
            self,
            service_account_id: str,
            key_id: str,
            private_key: str,
            folder: str,
            model_url: str = "/yandexgpt/latest"
    ) -> None:
        ...

    def call(
            self,
            prompt: str,
            user_message: str,
            context: Optional[List[Dict[str, str]]] = None,
            max_tokens: int = 500,
            temperature: float = 0.5,
    ) -> str:
        ...


class OpenAIClient(BaseClient):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        ...

    def call(...) -> str:
        ...
```

### Схемы проверки работ: <br> <br>

Экспериментами было опробовано несколько разных способов проверки работ (их можно найти в [lib/reviewers.py](lib/reviewers.py)) <br>

`FullTaskReviewer` проверяет одно задание целиком, самая наивная возможная проверка. Несмотря на простоту, качество получается не самым плохим.

```python
class FullTaskReviewer:
    def __init__(self, client: BaseClient) -> None:
        ...

    def review(
            self,
            cells: typing.List[NotebookCell],
            maximum_possible_score: typing.Optional[int] = None,
            prompt: typing.Optional[str] = None
    ) -> str:
        ...
```

`StepByStepTaskReviewer` делает хитрее: <br> <br> 
Поддерживает только ячейки, полученные `MergeKind.BY_CHANGE`. Тогда гарантируется, что ячейки чередуются, значит, можно объединять подряд идущие пары ячеек с вопросом и предполагаемым ответом на него.
Тогда можно просить оценку конкретной пары ячеек у модели, а всё остальное положить в контекст. Предполагается что так модель будет забывать меньше информации, сосредоточится на небольшом тексте и качественнее его оценит. <br>
Имеет те же сигнатуры <br>
```python
class StepByStepTaskReviewer:
    ...
```

### Промпты

Поддерживаются разные промпты. Специально для проверки домашних заданий по математической статистике было найдено несколько, качество которых выше, чем у других.
Их можно посмотреть в [lib/prompts.py](lib/prompts.py)
