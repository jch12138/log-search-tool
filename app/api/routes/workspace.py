"""工作空间资源管理 API"""
import json
from pathlib import Path
from typing import Dict, Any
from flask import Blueprint, jsonify, request
from app.config.system_settings import Settings

workspace_bp = Blueprint('workspace', __name__)

# 配置文件路径
WORKSPACE_CONFIG_FILE = Path(Settings().WORKSPACE_SITES_FILE)

DEFAULT_CONFIG: Dict[str, Any] = {
    "allowedIds": [],
    "groups": [
        {
            "id": "common-tools",
            "title": "常用工具",
            "shared": {
                "items": [
                    {
                        "name": "GitLab",
                        "url": "https://gitlab.com",
                        "desc": "代码仓库"
                    }
                ],
                "dbs": []
            },
            "useEnvironments": False
        }
    ]
}


def _normalise_config(data: Any) -> Dict[str, Any]:
    """标准化配置结构，确保包含 allowedIds 与 groups"""
    if isinstance(data, list):
        groups = data
        allowed_ids: list[str] = []
    elif isinstance(data, dict):
        groups = data.get("groups", [])
        allowed_ids = data.get("allowedIds", [])
    else:
        groups = []
        allowed_ids = []

    if not isinstance(groups, list):
        groups = []
    if not isinstance(allowed_ids, list):
        allowed_ids = []

    cleaned_ids = []
    for value in allowed_ids:
        if value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned_ids.append(text)

    return {
        "allowedIds": cleaned_ids,
        "groups": groups,
    }


def _load_config() -> Dict[str, Any]:
    """加载工作空间配置"""
    if not WORKSPACE_CONFIG_FILE.exists():
        _save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG
    
    try:
        with open(WORKSPACE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            raw = json.load(f)
            normalised = _normalise_config(raw)
            # 如果历史数据没有 allowedIds 字段则补齐并回写
            if isinstance(raw, list) or not isinstance(raw, dict) or 'allowedIds' not in raw:
                _save_config(normalised)
            return normalised
    except Exception as e:
        print(f"Error loading workspace config: {e}")
        return DEFAULT_CONFIG

def _save_config(config: Dict[str, Any]) -> None:
    """保存工作空间配置"""
    payload = _normalise_config(config)
    try:
        with open(WORKSPACE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving workspace config: {e}")
        raise

@workspace_bp.route('/sites', methods=['GET'])
def get_config():
    """获取工作空间配置"""
    try:
        config = _load_config()
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@workspace_bp.route('/sites', methods=['POST'])
def save_config():
    """保存工作空间配置 (全量覆盖)"""
    try:
        data = request.get_json()
        normalised = _normalise_config(data)
        _save_config(normalised)
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
