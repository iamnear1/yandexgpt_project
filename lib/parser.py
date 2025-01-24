import dataclasses
import enum
import itertools
import re
from pathlib import Path
from typing import List, Tuple, Callable, Optional

import nbformat

from lib.constants import SPECIAL_MARK


class MergeKind(enum.Enum):
    BY_CHANGE = 1
    BY_CHANGE_AND_CELL_TYPE = 2


class CellType(enum.Enum):
    CODE = 1
    MARKDOWN = 2

    # Used for grouped cells of mixed types
    OTHER = 3


@dataclasses.dataclass
class NotebookCell:
    is_changed: bool
    cell_type: CellType
    raw_text: str


def get_notebooks_filenames_from_directory(directory: str) -> List[str]:
    path = Path(directory)
    return [str(p) for p in path.glob("*.ipynb")]


def normalize_text(text: str) -> str:
    text = text.strip()
    text = re.sub(r'\r\n', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text


def get_filtered_notebook_cells_from_notebook(file_path: str) -> List[NotebookCell]:
    """
    Extract code and markdown cells, filtering those with (attachments | base64 images).
    """
    cells = []
    with open(file_path, 'r', encoding='utf-8') as file:
        notebook = nbformat.read(file, as_version=4)

        for cell in notebook.cells:
            if cell.cell_type == 'code':
                cells.append(NotebookCell(False, CellType.CODE, cell.source))
            elif cell.cell_type == 'markdown':
                has_attachments = 'attachments' in cell.get('metadata', {})
                has_base64 = 'base64' in cell.source
                if not has_attachments and not has_base64:
                    cells.append(NotebookCell(False, CellType.MARKDOWN, cell.source))
    return cells


def mark_modified_cells(
        orig_cells: List[NotebookCell],
        modified_cells: List[NotebookCell]
) -> List[NotebookCell]:
    """
    Mark cells as changed if their normalized content isn't in the original.
    Creates new NotebookCell instances to avoid mutating inputs.
    """
    original_content = {normalize_text(c.raw_text) for c in orig_cells}
    marked_cells = []
    for cell in modified_cells:
        normalized = normalize_text(cell.raw_text)
        is_changed = normalized not in original_content
        marked_cells.append(dataclasses.replace(cell, is_changed=is_changed))
    return marked_cells


def parse_and_mark_cells_by_tasks(
        cells: List[NotebookCell],
        expected_task_count: int
) -> Tuple[List[List[NotebookCell]], List[Optional[int]]]:
    """
    Split cells into tasks based on headers. Returns tasks and scores.

    Raises ValueError if task number exceeds expected count.
    """
    tasks = [[] for _ in range(expected_task_count)]
    scores: List[Optional[int]] = [None] * expected_task_count
    current_task_index = -1

    for cell in cells:
        header_match = re.search(
            # todo: better pattern?
            r"##\s*([Зз])адача\s*(\d+)",
            cell.raw_text,
            flags=re.IGNORECASE
        )
        if header_match:
            task_number = int(header_match.group(2))
            if not (1 <= task_number <= expected_task_count):
                raise ValueError(
                    f"Found task {task_number} but expected {expected_task_count} tasks"
                )
            current_task_index = task_number - 1
            tasks[current_task_index].append(cell)

            score_match = re.search(r"(\d+)\s*([Бб]аллов)", cell.raw_text)
            if score_match:
                scores[current_task_index] = int(score_match.group(1))
            continue

        if current_task_index != -1:
            tasks[current_task_index].append(cell)

    if len(tasks) != expected_task_count:
        raise RuntimeError(
            f"Parsed {len(tasks)} tasks but expected {expected_task_count}"
        )
    return tasks, scores


def _combine_cells(
        tasks: List[List[NotebookCell]],
        key_func: Callable[[NotebookCell], tuple],
        cell_type_func: Callable[[tuple], CellType]
) -> List[List[NotebookCell]]:
    """
    Helper to group cells by key function and combine into single cells.
    """
    combined_tasks = []
    for task in tasks:
        combined = []
        for key, group in itertools.groupby(task, key=key_func):
            group_cells = list(group)
            combined_text = "\n\n".join(c.raw_text for c in group_cells)
            is_changed = group_cells[0].is_changed
            if is_changed:
                combined_text = f"{SPECIAL_MARK}\n{combined_text}"
            combined.append(NotebookCell(
                is_changed=is_changed,
                cell_type=cell_type_func(key),
                raw_text=combined_text
            ))
        combined_tasks.append(combined)
    return combined_tasks


def combine_modified_cells_by_type(
        tasks: List[List[NotebookCell]]
) -> List[List[NotebookCell]]:
    """
    Group cells by (is_changed, cell_type).
    """
    return _combine_cells(
        tasks,
        key_func=lambda c: (c.is_changed, c.cell_type),
        cell_type_func=lambda key: key[1]
    )


def combine_modified_cells_by_change(
        tasks: List[List[NotebookCell]]
) -> List[List[NotebookCell]]:
    """
    Group cells by is_changed only, using CellType.OTHER for resulting cell
    """
    return _combine_cells(
        tasks,
        key_func=lambda c: c.is_changed,
        cell_type_func=lambda _: CellType.OTHER
    )


def merge_task_into_single_string(task: List[NotebookCell], delim: str = "\n\n\n") -> str:
    return delim.join(map(lambda cell_: cell_.raw_text, task))


def parsing_pipeline(
        notebook_path: str,
        original_notebook_path: str,
        kind: MergeKind,
        tasks_count: int
) -> Tuple[List[List[NotebookCell]], List[Optional[int]]]:
    """
    Main pipeline. Returns combined tasks and maximum scores.
    """
    orig_cells = get_filtered_notebook_cells_from_notebook(original_notebook_path)
    student_cells = get_filtered_notebook_cells_from_notebook(notebook_path)
    marked_cells = mark_modified_cells(orig_cells, student_cells)

    tasks, max_marks = parse_and_mark_cells_by_tasks(marked_cells, tasks_count)

    if kind == MergeKind.BY_CHANGE_AND_CELL_TYPE:
        combined_tasks = combine_modified_cells_by_type(tasks)
    elif kind == MergeKind.BY_CHANGE:
        combined_tasks = combine_modified_cells_by_change(tasks)
    else:
        raise ValueError(f"Unsupported MergeKind, FIX ME!: {kind}")

    return combined_tasks, max_marks
