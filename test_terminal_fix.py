#!/usr/bin/env python3
"""
测试终端修复效果的脚本
"""
import os
import sys

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_terminal_changes():
    """测试终端相关的修复"""
    print("=== 终端显示修复测试 ===")
    
    # 1. 测试终端服务是否有 resize_terminal 方法
    try:
        from services.terminal_service import TerminalService
        terminal_service = TerminalService()
        
        # 检查方法是否存在
        if hasattr(terminal_service, 'resize_terminal'):
            print("✓ resize_terminal 方法已添加")
        else:
            print("✗ resize_terminal 方法缺失")
    except Exception as e:
        print(f"✗ 终端服务导入失败: {e}")
    
    # 2. 检查HTML文件的修改
    try:
        html_path = os.path.join(os.path.dirname(__file__), 'templates', 'terminals.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 检查关键修复点
        checks = [
            ('position:absolute', '终端容器绝对定位'),
            ('min-height:0', '最小高度设置'),
            ('fitAddon.fit()', '尺寸自适应'),
            ('socket.emit(\'resize\'', '尺寸变化通知'),
            ('防抖延迟', '窗口大小变化防抖'),
        ]
        
        for check, desc in checks:
            if check in content:
                print(f"✓ {desc} - 已修复")
            else:
                print(f"✗ {desc} - 未找到")
                
    except Exception as e:
        print(f"✗ HTML文件检查失败: {e}")
    
    # 3. 检查主程序的Socket事件处理
    try:
        main_path = os.path.join(os.path.dirname(__file__), 'main.py')
        with open(main_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if '@socketio.on(\'resize\')' in content:
            print("✓ Socket resize 事件处理器已添加")
        else:
            print("✗ Socket resize 事件处理器缺失")
            
    except Exception as e:
        print(f"✗ 主程序检查失败: {e}")
    
    print("\n=== 修复要点总结 ===")
    print("1. 终端容器使用绝对定位，确保完全填充父容器")
    print("2. 添加了 min-height:0 防止 flex 布局问题")
    print("3. 改进了终端尺寸自适应逻辑，包含防抖处理")
    print("4. 添加了服务端终端尺寸调整支持")
    print("5. 优化了字体设置，提高兼容性")
    
    print("\n=== 使用建议 ===")
    print("1. 重启应用后测试终端功能")
    print("2. 测试窗口大小变化时的自适应")
    print("3. 测试长文本的自动换行")
    print("4. 检查不同浏览器的兼容性")

if __name__ == '__main__':
    test_terminal_changes()
