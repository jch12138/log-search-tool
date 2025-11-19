"""工作空间资源管理 API"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from flask import Blueprint, jsonify, request
from app.config.system_settings import Settings

workspace_bp = Blueprint('workspace', __name__)

# 配置文件路径
WORKSPACE_CONFIG_FILE = Path(Settings().WORKSPACE_SITES_FILE)

def _load_config() -> List[Dict[str, Any]]:
    """加载工作空间配置"""
    if not WORKSPACE_CONFIG_FILE.exists():
        # 默认配置结构
        default_config = [
            {
                "id": "common-tools",
                "title": "常用工具",
                "icon": "fa-solid fa-toolbox",
                "color": "text-indigo-600",
                "type": "links",
                "items": [
                    { "name": "GitLab", "url": "https://gitlab.com", "icon": "fa-brands fa-gitlab", "desc": "代码仓库" }
                ]
            }
        ]
        _save_config(default_config)
        return default_config
    
    try:
        with open(WORKSPACE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading workspace config: {e}")
        return []

def _save_config(config: List[Dict[str, Any]]) -> None:
    """保存工作空间配置"""
    try:
        with open(WORKSPACE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
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
        if not isinstance(data, list):
            return jsonify({'error': 'Invalid configuration format, expected a list'}), 400
        
        _save_config(data)
        return jsonify({'success': True, 'message': 'Configuration saved successfully'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
