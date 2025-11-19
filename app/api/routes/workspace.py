"""工作空间站点管理 API"""
import json
import os
from pathlib import Path
from typing import List, Dict, Any
from flask import Blueprint, jsonify, request

workspace_bp = Blueprint('workspace', __name__)

# 站点配置文件路径
WORKSPACE_CONFIG_FILE = Path('workspace_sites.json')

def _load_sites() -> List[Dict[str, Any]]:
    """加载站点配置"""
    if not WORKSPACE_CONFIG_FILE.exists():
        # 默认站点配置
        default_sites = [
            {
                "id": "1",
                "name": "日志搜索",
                "url": "/",
                "description": "日志聚合搜索系统",
                "group": "内部工具",
                "icon": "🔍",
                "order": 1
            },
            {
                "id": "2",
                "name": "SFTP管理",
                "url": "/sftp",
                "description": "远程文件管理",
                "group": "内部工具",
                "icon": "📁",
                "order": 2
            },
            {
                "id": "3",
                "name": "终端管理",
                "url": "/terminals",
                "description": "在线终端",
                "group": "内部工具",
                "icon": "💻",
                "order": 3
            },
            {
                "id": "4",
                "name": "账户查询",
                "url": "/account",
                "description": "ESB账户查询",
                "group": "内部工具",
                "icon": "🏦",
                "order": 4
            }
        ]
        _save_sites(default_sites)
        return default_sites
    
    try:
        with open(WORKSPACE_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading sites: {e}")
        return []

def _save_sites(sites: List[Dict[str, Any]]) -> None:
    """保存站点配置"""
    try:
        with open(WORKSPACE_CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(sites, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving sites: {e}")
        raise

def _generate_id() -> str:
    """生成唯一ID"""
    import time
    return str(int(time.time() * 1000))

@workspace_bp.route('/sites', methods=['GET'])
def get_sites():
    """获取所有站点"""
    try:
        sites = _load_sites()
        # 按 order 排序
        sites.sort(key=lambda x: x.get('order', 999))
        return jsonify({
            'success': True,
            'data': {'sites': sites}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {'message': str(e)}
        }), 500

@workspace_bp.route('/sites', methods=['POST'])
def create_site():
    """创建新站点"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        if not data.get('name'):
            return jsonify({
                'success': False,
                'error': {'message': '站点名称不能为空'}
            }), 400
        
        if not data.get('url'):
            return jsonify({
                'success': False,
                'error': {'message': '站点URL不能为空'}
            }), 400
        
        sites = _load_sites()
        
        # 创建新站点
        new_site = {
            'id': _generate_id(),
            'name': data['name'],
            'url': data['url'],
            'description': data.get('description', ''),
            'group': data.get('group', '默认分组'),
            'icon': data.get('icon', '🌐'),
            'order': data.get('order', len(sites) + 1)
        }
        
        sites.append(new_site)
        _save_sites(sites)
        
        return jsonify({
            'success': True,
            'data': {'site': new_site}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {'message': str(e)}
        }), 500

@workspace_bp.route('/sites/<site_id>', methods=['PUT'])
def update_site(site_id: str):
    """更新站点"""
    try:
        data = request.get_json()
        sites = _load_sites()
        
        # 查找站点
        site_index = None
        for i, site in enumerate(sites):
            if site['id'] == site_id:
                site_index = i
                break
        
        if site_index is None:
            return jsonify({
                'success': False,
                'error': {'message': '站点不存在'}
            }), 404
        
        # 更新站点信息
        site = sites[site_index]
        site['name'] = data.get('name', site['name'])
        site['url'] = data.get('url', site['url'])
        site['description'] = data.get('description', site['description'])
        site['group'] = data.get('group', site['group'])
        site['icon'] = data.get('icon', site['icon'])
        site['order'] = data.get('order', site['order'])
        
        _save_sites(sites)
        
        return jsonify({
            'success': True,
            'data': {'site': site}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {'message': str(e)}
        }), 500

@workspace_bp.route('/sites/<site_id>', methods=['DELETE'])
def delete_site(site_id: str):
    """删除站点"""
    try:
        sites = _load_sites()
        
        # 查找并删除站点
        original_length = len(sites)
        sites = [site for site in sites if site['id'] != site_id]
        
        if len(sites) == original_length:
            return jsonify({
                'success': False,
                'error': {'message': '站点不存在'}
            }), 404
        
        _save_sites(sites)
        
        return jsonify({
            'success': True,
            'data': {'message': '删除成功'}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {'message': str(e)}
        }), 500

@workspace_bp.route('/sites/reorder', methods=['POST'])
def reorder_sites():
    """重新排序站点"""
    try:
        data = request.get_json()
        site_orders = data.get('orders', [])  # [{'id': '1', 'order': 1}, ...]
        
        sites = _load_sites()
        
        # 更新顺序
        order_map = {item['id']: item['order'] for item in site_orders}
        for site in sites:
            if site['id'] in order_map:
                site['order'] = order_map[site['id']]
        
        _save_sites(sites)
        
        return jsonify({
            'success': True,
            'data': {'message': '排序成功'}
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': {'message': str(e)}
        }), 500
