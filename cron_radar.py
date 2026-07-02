from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


LOG_PATH = Path("data/cron_log.txt")


def log(message: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().isoformat(timespec='seconds')} {message}"
    print(line)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(line + "\n")


def run_step(args: list[str]) -> None:
    log(f"rodando: {' '.join(args)}")
    result = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    if result.stdout:
        log(result.stdout.strip())
    if result.stderr:
        log(result.stderr.strip())
    if result.returncode:
        log(f"etapa falhou com código {result.returncode}; continuando próxima etapa")


def main() -> None:
    praca = "Piabetá"
    uf = "RJ"
    segmento = "odontologia"

    run_step(["motor.py", "--praca", praca, "--uf", uf, "--segmento", segmento, "--fonte", "vagas", "--limite", "50", "--sync-admin"])
    time.sleep(30)
    run_step(["motor.py", "--praca", praca, "--uf", uf, "--segmento", segmento, "--fonte", "cnpj", "--limite", "100", "--sync-admin"])
    time.sleep(30)
    run_step(["motor.py", "--praca", praca, "--uf", uf, "--segmento", segmento, "--fonte", "maps", "--limite", "30", "--sync-admin"])
    time.sleep(30)
    run_step(["motor.py", "--praca", praca, "--uf", uf, "--segmento", segmento, "--fonte", "social", "--limite", "30", "--sync-admin"])


if __name__ == "__main__":
    main()
