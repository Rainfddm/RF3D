"""发布包自检（部署前必跑）。

覆盖 5 条验收：
1. 全新副本删掉 instance/ 后 create_app()，instance/ 必须被自动创建；
2. SQLALCHEMY_DATABASE_URI 反推的目录与实际创建目录必须一致；
3. import suFabEngine 的 __file__ 必须落在**本包**内（防止外部 .pth / editable 安装顶替）；
4. 包内不得存在 .env、__pycache__、*.pyc；
5. create_app() 成功且路由数 >= 20。

为什么用「临时副本 + 子进程」而不是直接 in-process 调 create_app：
    pytest 进程里 application/suFabEngine 已经从**当前包**导入过了，
    sys.modules 里是既成事实，无法验证「全新解压后能否自举」。
    只有把包复制到临时目录、用干净子进程导入，才是真实部署路径。

运行：
    cd <发布包根>
    PYTHONDONTWRITEBYTECODE=1 pytest tests/test_release_smoke.py -p no:cacheprovider
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

PKG_ROOT = Path(__file__).resolve().parent.parent

# 这些不进副本：instance/ 是要验证「自动创建」的；缓存入副本只会污染结论
COPY_IGNORE = shutil.ignore_patterns(
    ".env", "instance", "__pycache__", "*.pyc", ".pytest_cache", "*.egg-info"
)

SUB_ENV_DROP = ("PYTHONPATH", "DATABASE_URL", "AI_PROVIDER", "AI_MODEL")


def _clean_env():
    env = os.environ.copy()
    for key in SUB_ENV_DROP:
        env.pop(key, None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"   # 别在包里留 .pyc
    env["FLASK_SECRET_KEY"] = "smoke-test-secret"
    return env


def _run(code, cwd, args=()):
    """在干净子进程里执行一段 Python，返回解析后的 JSON 或抛错。"""
    proc = subprocess.run(
        [sys.executable, "-c", code, *args],
        cwd=str(cwd),
        env=_clean_env(),
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"子进程失败 rc={proc.returncode}\n--- stdout ---\n{proc.stdout}\n"
            f"--- stderr ---\n{proc.stderr[-3000:]}"
        )
    return json.loads(proc.stdout.strip().splitlines()[-1])


BOOTSTRAP_CODE = r"""
import json, os, sys
root = sys.argv[1]
sys.path.insert(0, root)
for rel in ("suFabEngine/src", "suFabUI/src"):
    sys.path.insert(0, os.path.join(root, *rel.split("/")))

from application import create_app, sqlite_dir_from_uri
from application.config import Config

instance_dir = os.path.join(root, "instance")
pre_existing = os.path.isdir(instance_dir)

app = create_app(Config)

uri = app.config["SQLALCHEMY_DATABASE_URI"]
created = os.path.join(root, "instance")
dir_from_uri = sqlite_dir_from_uri(uri)

import suFabEngine, suFabUI
print(json.dumps({
    "pre_existing": pre_existing,
    "uri": uri,
    "created_exists": os.path.isdir(created),
    "dir_from_uri": dir_from_uri,
    "dirs_equal": os.path.normcase(os.path.abspath(dir_from_uri or ""))
                  == os.path.normcase(os.path.abspath(created)),
    "routes": len(list(app.url_map.iter_rules())),
    "engine_file": os.path.abspath(suFabEngine.__file__ or ""),
    "ui_file": os.path.abspath(suFabUI.__file__ or ""),
}))
"""


@pytest.fixture(scope="module")
def fresh_copy():
    """把发布包整份复制到一个全新临时目录（模拟解压后首次运行）。"""
    tmp = Path(tempfile.mkdtemp(prefix="rf3d_release_smoke_"))
    target = tmp / "pkg"
    shutil.copytree(PKG_ROOT, target, ignore=COPY_IGNORE)
    assert not (target / "instance").exists(), "副本里不该有 instance/"
    yield target
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture(scope="module")
def boot(fresh_copy):
    return _run(BOOTSTRAP_CODE, fresh_copy, args=[str(fresh_copy)])


class TestBootstrapInFreshCopy:
    def test_instance_dir_created_automatically(self, boot):
        """验收 1：删掉 instance/ 后 create_app() 必须自己把目录建出来。"""
        assert boot["pre_existing"] is False, "前提不成立：副本里本来就有 instance/"
        assert boot["created_exists"] is True, (
            "create_app() 之后 instance/ 仍不存在 —— _ensure_sqlite_dir 没生效"
        )

    def test_uri_dir_matches_created_dir(self, boot):
        """验收 2：URI 反推目录 == 实际创建目录。"""
        assert boot["dirs_equal"] is True, (
            f"URI 反推目录 {boot['dir_from_uri']} 与实际创建目录不一致\nURI={boot['uri']}"
        )

    def test_routes_registered(self, boot):
        """验收 5：应用创建成功且路由 >= 20 条。"""
        assert boot["routes"] >= 20, f"路由数不足：{boot['routes']}"


class TestImportsComeFromPackage:
    def test_engine_import_resolves_inside_package(self, boot, fresh_copy):
        """验收 3：suFabEngine 必须来自副本，不能是外部安装。"""
        root = os.path.abspath(str(fresh_copy))
        assert boot["engine_file"].startswith(root), (
            f"suFabEngine 来自包外：{boot['engine_file']}\n期望前缀：{root}"
        )

    def test_ui_import_resolves_inside_package(self, boot, fresh_copy):
        root = os.path.abspath(str(fresh_copy))
        assert boot["ui_file"].startswith(root), (
            f"suFabUI 来自包外：{boot['ui_file']}"
        )


class TestPackageIsClean:
    """验收 4：包内不得有 .env / __pycache__ / *.pyc。

    注意：这条检查的是**原始包**，不是副本。所以跑本用例时必须
    PYTHONDONTWRITEBYTECODE=1，并且不要带 -p cacheprovider，
    否则 pytest 自己会造出 __pycache__ 让结论失真。
    """

    def test_no_dotenv(self):
        assert not (PKG_ROOT / ".env").exists(), (
            "包内发现 .env —— 可能带真实密钥，必须删除"
        )

    def test_no_pycache_and_pyc(self):
        offenders = []
        for path in PKG_ROOT.rglob("*"):
            if "__pycache__" in path.parts and path.is_dir():
                offenders.append(str(path.relative_to(PKG_ROOT)))
            elif path.suffix in (".pyc", ".pyo"):
                offenders.append(str(path.relative_to(PKG_ROOT)))
        assert not offenders, f"包内存在字节码缓存：{offenders[:10]}"

    def test_env_example_has_server_settings(self):
        """P1-3 回归锁：模板里必须包含这三项服务端配置。"""
        text = (PKG_ROOT / ".env.example").read_text(encoding="utf-8")
        for key in ("FLASK_SECRET_KEY", "DATABASE_URL", "CORS_ALLOWED_ORIGINS"):
            assert key in text, f".env.example 缺少 {key}"

    def test_no_hardcoded_api_keys(self):
        """P1-1 回归锁：包内不得出现形如 sk-xxxx 的密钥字面量。"""
        import re

        pattern = re.compile(r"sk-[A-Za-z0-9]{16,}")
        hits = []
        for path in PKG_ROOT.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {
                ".py", ".md", ".txt", ".toml", ".json", ".html", ".js", ".css",
                ".yaml", ".yml", ".cfg", ".ini", ".conf", ".example", ".in",
            }:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if pattern.search(text):
                hits.append(str(path.relative_to(PKG_ROOT)))
        assert not hits, f"包内发现疑似密钥：{hits}"
