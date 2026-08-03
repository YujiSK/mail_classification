from pathlib import Path
import os
import subprocess
import sys


def test_import_has_no_file_generation_or_network_setup(tmp_path: Path) -> None:
    project_root = Path(__file__).parents[1]
    source = project_root / "src"
    # reporting imports tools.pdf_renderer, which lives at the project root
    # (not an installed package), so it needs the root on PYTHONPATH too.
    env = {**os.environ, "PYTHONPATH": f"{source}{os.pathsep}{project_root}"}
    command = [
        sys.executable,
        "-c",
        (
            "import sys; import mail_classification; "
            "import mail_classification.schemas; "
            "import mail_classification.preprocessing; "
            "import mail_classification.generation; "
            "import mail_classification.quality; "
            "import mail_classification.evaluation; "
            "import mail_classification.models; "
            "import mail_classification.explain; "
            "import mail_classification.extensions; "
            "import mail_classification.reporting; "
            "import mail_classification.analysis; "
            # 'socket' is excluded: scikit-learn's joblib backend imports the
            # stdlib socket module for local multiprocessing plumbing, not
            # network I/O. 'requests'/'urllib.request' remain a real signal.
            "assert not any(name in sys.modules for name in "
            "('requests', 'urllib.request'))"
        ),
    ]
    completed = subprocess.run(
        command,
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert list(tmp_path.iterdir()) == []
