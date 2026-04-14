#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
嘉慧功率计控制程序主入口

该文件是嘉慧功率计控制程序的主启动脚本，用于：
- 初始化PyQt5应用程序
- 创建PM100D功率计驱动实例
- 启动主控制界面
- 配置多进程支持

程序功能：
- 连接和控制Thorlabs PM100D系列功率计
- 实时功率测量和数据记录
- 图形化用户界面操作
- TCP服务器自动化接口（可选）

运行要求：
- Windows 10/11系统
- Python 3.7+
- PyQt5界面库
- pyvisa通信库
- Thorlabs设备驱动

作者: ivan
创建时间: 2025
版本: v1.0.1

使用说明:
直接运行此文件启动程序：
    python PM100D功率计.py
"""

from PyQt5 import QtWidgets, QtCore
import multiprocessing, sys

from PM100D import PM100D
from PM100D_Control import PM100D_Control

if __name__ == '__main__':
    # 支持多进程打包（PyInstaller等工具需要）
    multiprocessing.freeze_support()

    # 注释掉的高DPI缩放设置
    # 不加这一行就会界面很小（在高DPI显示器上）
    # QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)

    # 创建PyQt5应用程序实例
    app = QtWidgets.QApplication(sys.argv)
    
    # 创建主控制窗口，并传入PM100D功率计驱动实例
    mainWind = PM100D_Control(device=PM100D())
    
    # 显示主窗口
    mainWind.show()

    # 启动事件循环，等待用户交互
    sys.exit(app.exec_())
