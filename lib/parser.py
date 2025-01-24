import dataclasses
import enum
import itertools
import os
import re
import typing

import nbformat

SPECIAL_MARK = "[ИЗМЕНЕНО СТУДЕНТОМ]."


@dataclasses.dataclass
class Cell:
    is_cell_changed: bool
    cell_type: str
    cell_text: str

    def iter(self):
        return iter((self.is_cell_changed, self.cell_type, self.cell_text))


def get_notebooks_filenames_from_directory(path_dir: str) -> typing.List[str]:
    out = []
    for file in os.listdir(os.fsencode(path_dir)):
        filename = os.fsdecode(file)
        if filename.endswith(".ipynb"):
            out.append(os.path.join(path_dir, filename))
    return out


def get_filtered_notebook_cells_from_notebook(file_path: str) -> typing.List[Cell]:
    """
    Pulls all cells out of the notebook, discarding any unnecessary ones (pictures/other attachments).
    """
    cells = []
    with open(file_path, 'r', encoding='utf-8') as file:
        notebook = nbformat.read(file, as_version=4)

        for cell in notebook.cells:
            if cell.cell_type == 'code':
                cells.append(Cell(False, 'code', cell.source))

            elif cell.cell_type == 'markdown':
                if 'attachments' not in cell and 'base64' not in cell.source:
                    cells.append(Cell(False, 'markdown', cell.source))

    return cells


def mark_modified_cells(orig_cells: typing.List[Cell],
                        modified_cells: typing.List[Cell]) -> typing.List[Cell]:
    """
    Compares empty and done cells. Adds marks (Cell.is_changed=true) to the cells in the done work,
    that the student has changed.
    """

    original_content = set(c.cell_text for c in orig_cells)

    for cell_ in modified_cells:
        # TODO: there are cases when only a line break was added (or some extra symbol),
        #  and in this case you don't need to consider the cell changed either. handle this case

        if cell_.cell_text not in original_content:
            cell_.is_cell_changed = True

    return modified_cells


def parse_and_mark_cells_by_tasks(cells: typing.List[Cell], expected_task_count: int) \
        -> typing.Tuple[typing.List[typing.List[Cell]], typing.List[int | None]]:
    """
    Takes a list of Cells as input. It splits it into tasks, i.e. the output is a list of length equal to the number of
    tasks. Expected_task_count is set by the caller, if there are not so many tasks it throws an exception. Also
    for each large task it looks for a mention of points (if there is one, otherwise None).
    """

    tasks = [[] for _ in range(expected_task_count)]
    current_task_index = -1

    scores: typing.List[int | None] = [None] * expected_task_count

    for cell_ in cells:
        match = re.search(pattern=r"##\s*([Зз])адача\s*(\d+)", string=cell_.cell_text)

        if match:
            task_number = int(match.group(2))

            if 1 <= task_number <= expected_task_count:
                current_task_index = task_number - 1
                tasks[current_task_index].append(cell_)

                score_match = re.search(pattern=r"(\d+)\s*([Бб]аллов)", string=cell_.cell_text)

                if score_match:
                    scores[current_task_index] = int(score_match.group(1))

                continue
            else:
                raise RuntimeError(f"{task_number} > {expected_task_count}")

        if current_task_index != -1:
            tasks[current_task_index].append(cell_)

    return tasks, scores


def combine_modified_cells_by_type(tasks: typing.List[typing.List[Cell]]) -> typing.List[typing.List[Cell]]:
    """
    Group cells by (Cell.is_cell_changed, Cell.cell_type)
    """
    combined_tasks = []

    for task in tasks:
        combined_task = []
        for key, group in itertools.groupby(task, key=lambda c: (c.is_cell_changed, c.cell_type)):
            is_changed, cell_type = key
            group_list = list(group)
            combined_text = "\n".join(cell_.cell_text for cell_ in group_list)
            if is_changed:
                combined_task.append(Cell(is_changed, cell_type, f"{SPECIAL_MARK}\n" + combined_text))
            else:
                combined_task.append(Cell(is_changed, cell_type, combined_text))
        combined_tasks.append(combined_task)

    return combined_tasks


def combine_modified_cells_v2(tasks: typing.List[typing.List[Cell]]) -> typing.List[typing.List[Cell]]:
    """
    Group cells by Cell.is_cell_changed
    """
    combined_tasks = []

    for task in tasks:
        combined_task = []

        for key, group in itertools.groupby(task, key=lambda c: c.is_cell_changed):
            is_changed = key
            group_list = list(group)
            combined_text = "\n".join(c.cell_text for c in group_list)
            if is_changed:
                combined_task.append(Cell(is_changed, "mixed", f"{SPECIAL_MARK}\n" + combined_text))
            else:
                combined_task.append(Cell(is_changed, "mixed", combined_text))
        combined_tasks.append(combined_task)

    return combined_tasks


def merge_task_into_single_string(task: typing.List[Cell], delim: str = "\n\n\n") -> str:
    return delim.join(map(lambda cell_: cell_.cell_text, task))


class MergeKind(enum.Enum):
    BY_CHANGE = 1
    BY_CHANGE_AND_CELL_TYPE = 2


def ParsingPipeline(notebook_path: str, original_notebook_path: str, kind: MergeKind,
                    tasks_count: int) -> typing.Tuple[typing.List[typing.List[Cell]], typing.List[int | None]]:
    """takes as input the path to the student's work, the path to an empty paper, the MergeKind type and the number of assignments.
    returns a list of assignments (each assignment is a list of Cell's) and a list of possible grades for the assignment,
    if any are specified in the original task.
    """
    orig_cells = get_filtered_notebook_cells_from_notebook(original_notebook_path)
    student_cells = get_filtered_notebook_cells_from_notebook(notebook_path)
    marked_cells = mark_modified_cells(orig_cells, student_cells)

    cleaned_tasks, max_marks = parse_and_mark_cells_by_tasks(marked_cells, tasks_count)

    if kind == MergeKind.BY_CHANGE_AND_CELL_TYPE:
        combined_tasks = combine_modified_cells_by_type(cleaned_tasks)
    elif kind == MergeKind.BY_CHANGE:
        combined_tasks = combine_modified_cells_v2(cleaned_tasks)
    else:
        raise RuntimeError(f"{kind} is not a valid MergeKind. Unsupported for now")

    return combined_tasks, max_marks
