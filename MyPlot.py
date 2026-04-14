#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时数据绘图模块

该模块基于pyqtgraph提供实时数据绘图功能，支持：
- 多数据序列的实时更新显示
- 鼠标双击切换显示不同的数据序列
- 自动缩放和数据清理功能
- 白色背景和黑色线条的显示风格

作者: ivan
创建时间: 2025
版本: v1.0.1
"""

import numpy as np
import pyqtgraph as pg
from PyQt5.QtCore import QThread, pyqtSignal, Qt

# 设置pyqtgraph的显示风格：白底黑线
pg.setConfigOption('background', 'w')  # 白底黑线
pg.setConfigOption('foreground', 'k')


class MyPlot(pg.GraphicsLayoutWidget):
    """
    自定义实时数据绘图控件
    
    基于pyqtgraph.GraphicsLayoutWidget的实时数据绘图控件，
    支持多数据序列的实时更新和显示切换。
    
    Attributes:
        dataDict (dict): 存储各数据序列的数据字典
        posDict (dict): 存储各数据序列的位置偏移字典
        NowPlotNo (int): 当前显示的数据序列索引
        update_signal (pyqtSignal): 数据更新信号
    """
    
    # 类属性：存储数据和位置信息
    dataDict = {}
    posDict = {}
    NowPlotNo = 0
    
    # 数据更新信号，接收包含新数据的字典
    update_signal = pyqtSignal(dict)

    def __init__(self, dataDict, dataLen=30):
        """
        初始化绘图控件
        
        Args:
            dataDict (dict): 初始数据字典，键为数据序列名称，值为数据数组或列表
            dataLen (int): 显示的数据最大个数（当前版本中未使用，保留参数）
            
        Example:
            >>> plot = MyPlot({'功率': [1, 2, 3], '电压': [0.1, 0.2, 0.3]})
        """
        super(MyPlot, self).__init__()
        self.dataDict = dataDict

        # 初始化位置字典和数据转换
        for k, v in dataDict.items():
            self.posDict[k] = 0
            if type(v) == list:
                self.dataDict[k] = np.array(v)
            elif type(v) == np.ndarray:
                self.dataDict[k] = v

        # 创建绘图区域
        self.plot1 = self.addPlot()
        
        # 设置初始显示的数据序列
        key = list(self.dataDict.keys())[self.NowPlotNo]
        self.plot1.setTitle(key, **{"font-family": "微软雅黑", 'font-size': '12pt'})
        
        # 连接更新信号到更新方法
        self.update_signal.connect(self.updateData)
        
        # 创建绘图曲线，使用蓝色4像素宽度的线条
        self.curve = self.plot1.plot(self.dataDict[key], pen=pg.mkPen({'color': (0, 0, 255), 'width': 4}))

    def mousePressEvent(self, ev):
        """
        鼠标按下事件处理
        
        当前版本中未实现具体功能，保留接口供后续扩展。
        
        Args:
            ev: 鼠标事件对象
        """
        return

    def mouseDoubleClickEvent(self, ev):
        """
        鼠标双击事件处理
        
        双击图表时切换显示不同的数据序列。依次循环显示dataDict中的各个数据序列。
        
        Args:
            ev: 鼠标双击事件对象
        """
        # 切换到下一个数据序列
        self.NowPlotNo = (self.NowPlotNo + 1) % len(self.dataDict)
        key = list(self.dataDict.keys())[self.NowPlotNo]
        
        # 更新图表标题
        self.plot1.setTitle(key, **{"font-family": "微软雅黑", 'font-size': '20pt'})

        # 更新显示的数据
        data1 = self.dataDict[key]
        self.curve.setData(data1)
        
        # 重置位置偏移
        self.posDict[key] = 0
        self.curve.setPos(self.posDict[key], 0)

    def updateData(self, dataAddDict):
        """
        更新图表数据
        
        接收新的数据并更新到对应的数据序列中，然后刷新当前显示的图表。
        
        Args:
            dataAddDict (dict): 包含新数据的字典，键为数据序列名称，值为新的数据点
            
        Example:
            >>> plot.updateData({'功率': 4.5, '电压': 0.4})
        """
        # 将新数据添加到对应的数据序列中
        for k, v in dataAddDict.items():
            # 将新数据追加到现有数据数组的末尾
            self.dataDict[k] = np.append(self.dataDict[k], v)
            
            # 注释的代码是用于限制数据长度的滑动窗口实现
            # if len(self.dataDict[k]) < self.dataLen:
            #     self.dataDict[k] = np.append(self.dataDict[k], v)
            # else:
            #     self.dataDict[k][:-1] = self.dataDict[k][1:]
            #     self.dataDict[k][-1] = v
            #     self.posDict[k] += 1

        # 更新当前显示的数据序列
        key = list(self.dataDict.keys())[self.NowPlotNo]
        data1 = self.dataDict[key]
        self.curve.setData(data1)
        self.curve.setPos(self.posDict[key], 0)
        
        # 自动调整显示范围
        self.plot1.autoRange()

    def clearData(self):
        """
        清空所有数据
        
        清空所有数据序列的数据，重置位置偏移，并刷新图表显示。
        通常在开始新的测量或重置系统时调用。
        """
        # 清空所有数据序列
        for k, v in self.dataDict.items():
            self.dataDict[k] = np.array([])
            self.posDict[k] = 0
            
        # 更新显示
        key = list(self.dataDict.keys())[self.NowPlotNo]
        self.curve.setData(self.dataDict[key])
        self.curve.setPos(self.posDict[key], 0)
        self.plot1.autoRange()


if __name__ == '__main__':
    """
    模块测试代码
    
    创建一个测试窗口，演示MyPlot的基本功能，包括数据更新和清空操作。
    """
    import sys
    import time
    from PyQt5.QtWidgets import QApplication
    from PyQt5 import QtCore, QtGui, QtWidgets

    app = QApplication(sys.argv)
    
    # 创建主窗口
    win = QtWidgets.QMainWindow()
    win.resize(800, 600)
    win.setWindowTitle('MyPlot')
    
    # 创建中心部件和布局
    central_widget = QtWidgets.QWidget(win)
    layout = QtWidgets.QHBoxLayout(central_widget)
    
    # 创建绘图控件并添加到布局
    plot = MyPlot({'A': [1, 2, 3, 4, 5], 'B': [2, 3, 4, 5, 6]})
    layout.addWidget(plot)
    
    win.setCentralWidget(central_widget)
    win.show()
    
    # 演示数据更新
    time.sleep(5)
    plot.updateData({'A': [6, 7, 8, 9, 10], 'B': [3, 4, 5, 6, 7]})
    
    # 演示数据清空
    time.sleep(10)
    plot.clearData()
    
    sys.exit(app.exec_())
