from types import SimpleNamespace

from onecut import config as config_module
from onecut.config import Config, choose_quality


def test_choose_quality_reprompts_after_invalid_input(monkeypatch, capsys) -> None:
    answers = iter(["invalid", "2"])
    monkeypatch.setattr(
        config_module.sys,
        "stdin",
        SimpleNamespace(isatty=lambda: True),
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    assert choose_quality("youtube-4k") == "youtube-1440"
    assert "Please choose 1, 2, or 3." in capsys.readouterr().err


def test_empty_quality_override_still_prompts(monkeypatch) -> None:
    monkeypatch.setenv("EXPORT_QUALITY", "")
    monkeypatch.setattr(
        config_module,
        "choose_quality",
        lambda current: "youtube-1080" if current == "youtube-4k" else current,
    )

    assert Config.load(prompt_for_quality=True).quality == "youtube-1080"
