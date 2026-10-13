"""启动脚本使用临时数据库验证，不触碰正式运动会数据。"""
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time
from urllib.request import ProxyHandler, build_opener

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('local_launcher', PROJECT_ROOT / 'main.py')
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_reuses_current_service_and_avoids_foreign_service(monkeypatch):
    monkeypatch.setattr(launcher, 'port_available', lambda port: port not in {8000, 8002})
    monkeypatch.setattr(launcher, 'ready_system', lambda port: port == 8002)
    assert launcher.select_port(8000) == (8002, True)
    monkeypatch.setattr(launcher, 'ready_system', lambda port: False)
    assert launcher.select_port(8000) == (8001, False)
    with pytest.raises(RuntimeError):
        launcher.select_port(8000, fallback=False)


def test_frontend_change_triggers_build_but_current_bundle_is_reused(tmp_path):
    src = tmp_path / 'frontend' / 'src'
    src.mkdir(parents=True)
    source = src / 'App.vue'
    source.write_text('<template/>', encoding='utf-8')
    assert launcher.frontend_needs_build(tmp_path)
    dist = tmp_path / 'frontend' / 'dist'
    dist.mkdir()
    index = dist / 'index.html'
    index.write_text('<html/>', encoding='utf-8')
    os.utime(source, (1000, 1000))
    os.utime(index, (2000, 2000))
    assert not launcher.frontend_needs_build(tmp_path)
    os.utime(source, (3000, 3000))
    assert launcher.frontend_needs_build(tmp_path)


@pytest.mark.skipif(os.name != 'nt', reason='Windows双击入口')
def test_both_double_click_entries_pass_environment_check():
    entries = [PROJECT_ROOT / '一键启动.bat']
    if (PROJECT_ROOT.parent / '一键启动.bat').is_file():
        entries.append(PROJECT_ROOT.parent / '一键启动.bat')
    for entry in entries:
        result = subprocess.run(['cmd.exe', '/d', '/c', str(entry), '-Check'], cwd=PROJECT_ROOT.parent,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
        output = result.stdout.decode('utf-8', errors='replace')
        assert result.returncode == 0, output
        assert '环境检查通过' in output


@pytest.mark.skipif(os.name != 'nt', reason='Windows PowerShell启动入口')
def test_starts_real_service_and_second_start_reuses_it(tmp_path):
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    environment = dict(os.environ, DATABASE_URL=f'sqlite:///{(tmp_path / "launcher.db").as_posix()}',
                       EXPORT_DIR=str(tmp_path / 'exports'), AUTO_SEED='false', PYTHONIOENCODING='utf-8')
    command = ['powershell.exe', '-NoLogo', '-NoProfile', '-ExecutionPolicy', 'Bypass',
               '-File', str(PROJECT_ROOT / 'scripts' / 'start-local.ps1'),
               '-NoBrowser', '-Port', str(port), '-NoPortFallback']
    http = build_opener(ProxyHandler({}))
    log = tmp_path / 'launcher.log'
    with log.open('wb') as output:
        process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 90
            while time.monotonic() < deadline:
                try:
                    with http.open(f'http://127.0.0.1:{port}/health', timeout=1) as response:
                        health = json.load(response)
                    break
                except OSError:
                    assert process.poll() is None, log.read_text(encoding='utf-8', errors='replace')
                    time.sleep(.2)
            else:
                pytest.fail(log.read_text(encoding='utf-8', errors='replace'))
            assert 'rope-registration-tables' in health['features']
            with http.open(f'http://127.0.0.1:{port}/', timeout=2) as response:
                assert '<html' in response.read().decode('utf-8')
            repeated = subprocess.run(command, cwd=PROJECT_ROOT, env=environment, stdout=subprocess.PIPE,
                                      stderr=subprocess.STDOUT, timeout=15)
            assert repeated.returncode == 0, repeated.stdout.decode('utf-8', errors='replace')
            assert '已复用现有服务' in repeated.stdout.decode('utf-8', errors='replace')
        finally:
            # PID来自本测试独立启动日志，只结束测试创建的Python和PowerShell。
            started = re.search(r'Started server process \[(\d+)\]', log.read_text(encoding='utf-8', errors='replace'))
            if started:
                try:
                    os.kill(int(started.group(1)), signal.SIGTERM)
                except OSError:
                    pass
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
