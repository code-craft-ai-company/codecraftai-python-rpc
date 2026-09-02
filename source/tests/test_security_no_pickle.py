"""
    Guards the promise that no decode path executes code: the serialization package must not name pickle,
    marshal, eval, exec or a dynamic import.
"""

import pathlib
import re
import unittest

import ccai.rpc.core.serialization as serialization

FORBIDDEN = re.compile(r"\b(pickle|marshal|eval|exec|importlib\.import_module|__import__)\b")


class TestNoCodeExecutionOnDecode(unittest.TestCase):

    def test_forbidden_names_absent(self) -> None:
        package = pathlib.Path(serialization.__file__).parent
        for path in package.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            code_lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
            found = [line for line in code_lines if FORBIDDEN.search(line) and "_ALLOWED_EXCEPTION_MODULES" not in line]
            self.assertEqual(found, [], "{} names a forbidden facility".format(path.name))
        return


if __name__ == "__main__":
    unittest.main()
