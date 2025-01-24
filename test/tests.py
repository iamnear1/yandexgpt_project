import unittest

import lib.parser
from lib import parser


class TestParser(unittest.TestCase):
    def test_parser_simple(self):
        tasks, marks = parser.ParsingPipeline(
            "solved.ipynb", "original.ipynb", parser.MergeKind.BY_CHANGE, 1
        )

        self.assertEqual(len(tasks), 1)

        task = tasks[0]

        self.assertEqual(len(task), 4)

        # check, that cell types alternate
        for i in range(len(task)):
            cell = task[i]

            if i & 1 == 1:
                self.assert_(lib.parser.SPECIAL_MARK in cell.cell_text)

            self.assertEqual(cell.is_cell_changed, bool(i & 1))

        # there is one tasks, which costs 10 points
        self.assertEqual(marks, [10])


if __name__ == '__main__':
    unittest.main()
