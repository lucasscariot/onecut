from onecut import cli


def test_no_command_prints_command_list(capsys) -> None:
    assert cli.main([]) == 0

    output = capsys.readouterr().out
    assert "Commands:" in output
    assert "render [output.mp4]" in output
    assert "captions" in output
    assert "trim-start" in output


def test_render_command_is_dispatched_explicitly(monkeypatch) -> None:
    received: list[str] = []

    def fake_render(arguments: list[str]) -> int:
        received.extend(arguments)
        return 0

    monkeypatch.setattr(cli.render, "run", fake_render)

    assert cli.main(["render", "holiday.mp4"]) == 0
    assert received == ["holiday.mp4"]


def test_output_filename_without_render_is_not_a_command(capsys) -> None:
    assert cli.main(["holiday.mp4"]) == 2
    assert "Unknown command: holiday.mp4" in capsys.readouterr().err
