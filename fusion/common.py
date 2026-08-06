"""融合流程公共模块：配置/DNA 加载、IO、步骤日志。

所有 step 模块共享此文件，避免重复代码。
WEWRITE_HOME 默认 ~/.wewrite，可用环境变量 WEWRITE_HOME 覆盖。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# 引擎根目录：优先包内自包含（fusion/ 同目录），否则回退 ~/.wewrite
# 包内自包含：本文件在 wechat-automation-weme/fusion/common.py → 根 = 上一级
_PKG_ROOT = Path(__file__).resolve().parent.parent
if (_PKG_ROOT / "fusion" / "common.py").exists():
    # 包内布局：<skill>/fusion/common.py → 引擎根 = <skill>/fusion
    FUSION_ROOT = Path(__file__).resolve().parent
    WEWRITE_HOME = _PKG_ROOT
else:
    # 独立部署：~/.wewrite/fusion/common.py → 引擎根 = ~/.wewrite/fusion
    FUSION_ROOT = Path(__file__).resolve().parent
    WEWRITE_HOME = Path(os.environ.get("WEWRITE_HOME", Path.home() / ".wewrite")).expanduser()

CONFIG_PATH = WEWRITE_HOME / "config.yaml"
STYLE_PATH = WEWRITE_HOME / "style.yaml"
DNA_PATH = WEWRITE_HOME / "style-dna.yaml"
COMPLIANCE_RULES = WEWRITE_HOME / "compliance-rules.yaml"
COMPLIANCE_CHECKER = WEWRITE_HOME / "compliance-checker.py"
HISTORY_PATH = WEWRITE_HOME / "history.yaml"
# sample 数据源：优先包内 fusion/sample，回退 WEWRITE_HOME/fusion/sample
SAMPLE_TOPICS = FUSION_ROOT / "sample" / "topics.json"

# ===== 多用户支持：用户配置目录（通用版 Skill 用）=====
def load_yaml(path) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_config() -> dict:
    return load_yaml(CONFIG_PATH)


class ConfigError(RuntimeError):
    """配置缺失/未填写错误——用户必须先用 init.sh 完成初始化。"""


# 优先级：环境变量 WECHAT_USER_DIR（pipeline.sh 注入）> WECHAT_USER 推导 > 默认无
def user_dir() -> Path | None:
    """返回当前用户的配置目录（users/<id>/），未启用多用户返回 None。"""
    d = os.environ.get("WECHAT_USER_DIR")
    if d:
        p = Path(d).expanduser()
        return p if p.exists() else None
    uid = os.environ.get("WECHAT_USER")
    if uid:
        # 尝试 skill 布局（兼容新旧目录名）
        for base in (Path.home() / ".workbuddy" / "skills" / "wechat-automation-weme" / "users",
                     Path.home() / ".workbuddy" / "skills" / "wechat-automation" / "users",
                     Path.cwd() / "users"):
            p = base / uid
            if p.exists():
                return p
    return None


def require_user_config(name: str) -> dict:
    """【严格模式】读取用户配置，缺失/空字段直接抛错。

    仅当多用户模式激活（WECHAT_USER_DIR 或 WECHAT_USER 已设置）时严格；
    无多用户（旧版回退模式）回退 WEWRITE_HOME，保持兼容。

    规则：
      - 用户目录存在但缺 <name>.yaml → ConfigError（提示运行 init.sh）
      - 文件存在但内容为空 dict → ConfigError（提示填写）
      - 字段值仍为模板占位（含"请填""你的""待补充"等）→ ConfigError
    """
    ud = user_dir()
    if ud is None:
        # 旧版回退模式：回退 WEWRITE_HOME
        fallback = WEWRITE_HOME / f"{name}.yaml"
        if fallback.exists():
            return load_yaml(fallback)
        return {}

    # 多用户模式：找配置文件
    candidates = [ud / f"{name}.yaml", ud / f"{name}s.yaml"]
    found = next((f for f in candidates if f.exists()), None)
    if found is None:
        raise ConfigError(
            f"✗ 用户配置缺失：{ud}/{name}.yaml 不存在。\n"
            f"  请先运行：bash init.sh {os.environ.get('WECHAT_USER', '') or '你的用户名'}"
        )

    data = load_yaml(found)
    if not data:
        raise ConfigError(
            f"✗ 用户配置为空：{found}。\n"
            f"  请填写后再运行（参考 templates/{name}.template.yaml 的注释）"
        )

    # 检查是否还是模板占位（未真正填写）
    if _is_template_placeholder(data):
        raise ConfigError(
            f"✗ 用户配置仍是模板占位（未填写）：{found}。\n"
            f"  请填写真实内容（参考 templates/{name}.template.yaml 的注释）"
        )
    return data


_TEMPLATE_MARKERS = ("请填", "你的", "待补充", "模板", "TODO", "xxx", "XXX", "名称",
                     "关键词1", "关键词 1", "例子", "例：", "示例")


def _is_template_placeholder(data: dict, depth: int = 0) -> bool:
    """递归检查配置里是否还有未填写的模板占位值。"""
    if depth > 6:
        return False
    if isinstance(data, dict):
        for v in data.values():
            if _is_template_placeholder(v, depth + 1):
                return True
        return False
    if isinstance(data, list):
        # 列表为空或全占位视为未填
        if not data:
            return True
        return all(_is_template_placeholder(x, depth + 1) for x in data)
    if isinstance(data, str):
        if not data.strip():
            return True
        return any(m in data for m in _TEMPLATE_MARKERS)
    if data is None:
        return True
    return False


def load_user_config(name: str) -> dict:
    """读取当前用户的 <name>.yaml（identity/topics/style/style-dna/lark）。
    多用户模式（通用版）走严格检查；无多用户（旧版回退）回退 WEWRITE_HOME。
    """
    ud = user_dir()
    if ud is not None:
        return require_user_config(name)
    # 回退到 WEWRITE_HOME（旧版兼容）
    fallback = WEWRITE_HOME / f"{name}.yaml"
    if fallback.exists():
        return load_yaml(fallback)
    fallback2 = WEWRITE_HOME / f"{name}s.yaml"
    if fallback2.exists():
        return load_yaml(fallback2)
    return {}


def load_dna() -> dict:
    """优先读用户 style-dna.yaml，回退 WEWRITE_HOME。"""
    return load_user_config("style-dna") or load_yaml(DNA_PATH)


def load_style() -> dict:
    """优先读用户 style.yaml，回退 WEWRITE_HOME。"""
    return load_user_config("style") or load_yaml(STYLE_PATH)


def read_json(path: Path) -> Any:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_history() -> dict:
    """读取已发文章历史，用于选题去重。"""
    return load_yaml(HISTORY_PATH)


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def log(step: str, msg: str, level: str = "info") -> None:
    """统一步骤日志，写到 stdout 并可选落盘。"""
    prefix = {"info": "-", "ok": "OK", "warn": "!", "err": "X"}.get(level, "-")
    line = f"  {prefix} [{step}] {msg}"
    print(line, flush=True)


def run_dir() -> Path:
    """本轮运行的工作目录，按时间戳创建。"""
    d = WEWRITE_HOME / "runs" / f"fusion-{stamp()}"
    d.mkdir(parents=True, exist_ok=True)
    return d


def class_from_dict(obj: Any, cls):
    """简易：把 dict 覆盖到 dataclass 实例（仅占位，未强依赖）。"""
    return cls(**{k: v for k, v in obj.items() if k in cls.__annotations__}) \
        if hasattr(cls, "__annotations__") else obj
