import pytest
from pydantic import ValidationError

from lsh.schema import parse_plan


def test_schema_rejects_unknown_action() -> None:
    with pytest.raises(ValidationError):
        parse_plan(
            {
                "intent": "summarize",
                "risk": "low",
                "requires_confirmation": False,
                "steps": [
                    {
                        "action": "summarize_file",
                        "args": {"path": "README.md"},
                    }
                ],
            }
        )
