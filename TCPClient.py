#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP客户端通信模块

该模块实现了基于PyQt5的TCP客户端，提供：
- 异步TCP连接和数据传输
- 自动重连机制和错误处理
- 基于信号槽的事件通知
- 消息缓冲和解析功能

主要用于与TCP服务器进行数据交换，支持JSON格式的消息传输。

作者: ivan
创建时间: 2025
版本: v1.0.1
"""

import sys
import socket
from builtins import str

from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QLineEdit, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import threading

from PyQt5.QtCore import QThread, pyqtSignal, QTimer
import socket
import time
import pandas as pd

import queue

class TCPClient(QThread):
    """
    TCP客户端类
    
    基于PyQt5的QThread实现的TCP客户端，支持异步通信和自动重连。
    客户端连接到指定的TCP服务器，可以发送和接收数据，并通过信号
    槽机制通知连接状态和数据接收事件。
    
    Attributes:
        host (str): 服务器主机地址
        port (int): 服务器端口号
        running (bool): 线程运行状态标志
        isconnected (bool): TCP连接状态标志
        socket (socket.socket): TCP套接字对象
        func (callable): 数据处理回调函数
        name (str): 客户端名称标识
        
    Signals:
        connectedSignal (pyqtSignal): 连接状态变化信号
        infoSignal (pyqtSignal): 信息通知信号
    """
    
    # 连接状态信号：(状态, 消息)
    connectedSignal = pyqtSignal([str, str])
    # 信息通知信号：(名称, 信息)
    infoSignal = pyqtSignal([str, str])

    def __init__(self, host, port, name=None, func=lambda x: x):
        """
        初始化TCP客户端
        
        Args:
            host (str): 服务器IP地址
            port (int): 服务器端口号
            name (str, optional): 客户端名称，用于日志标识
            func (callable, optional): 数据处理函数，接收字符串参数
            
        Example:
            >>> def data_handler(data):
            ...     print(f"收到数据: {data}")
            >>> client = TCPClient("127.0.0.1", 8888, "TestClient", data_handler)
        """
        super().__init__()
        self.host = host
        self.port = int(port)
        self.running = False
        self.isconnected = False
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(2)  # 设置超时时间为2秒，更快处理是否链接成功
        self.func = func  # 输入的自定义函数，接收到数据后会调用该函数进行处理
        self.name = name 

    def start(self):
        """
        启动TCP客户端线程
        
        设置运行标志并启动QThread线程，开始TCP连接过程。
        """
        self.running = True
        super().start()

    def run(self):
        """
        线程主运行函数
        
        执行TCP连接和数据接收循环。连接成功后会持续监听服务器数据，
        并调用注册的回调函数处理接收到的消息。支持多行消息的缓冲处理。
        """
        try:
            self.socket.connect((self.host, self.port))
            # logging.info("Connected to server")
            print(f"Connected to server:{self.host},{self.port}\n")
            self.connectedSignal.emit("YES", "链接成功！") # 发送信号，连接成功
            self.socket.settimeout(None) # 取消超时时间，保持链接状态
            self.isconnected = True
            buffer = ""
            
            # 数据接收循环
            while self.running:
                data = self.socket.recv(1024).decode('utf-8')  # Buffer size is 1024 bytes
                # print(f"收到来自{self.socket.getpeername()}的数据:{data}\n")
                # print("received:"+data)
                if not data:
                    # logging.info("Connection closed by server")
                    print("Connection closed by server")
                    self.connectedSignal.emit("NO", "连接断开！")
                    break
                    
                # 处理消息缓冲，支持多行消息
                buffer += data
                if "\n" in buffer:
                    messages = buffer.split("\n")
                    for message in messages[:-1]:
                        if message:
                            self.func(message)  # 调用数据处理函数
                            self.infoSignal.emit(self.name, "received:"+message)
                    buffer = messages[-1]  # 保留未完整的消息
                    
        except ConnectionRefusedError or TimeoutError:
            # logging.error("Connection refused")
            print("Connection filed\n")
            self.connectedSignal.emit("NO", "连接失败！")
            self.isconnected = False
        except Exception as e:
            # logging.error(f"Error: {str(e)}")
            print(f"Error: {str(e)}\n")
            self.connectedSignal.emit("NO", "连接失败！")
            self.isconnected = False

    def send(self, data):
        """
        发送数据到服务器
        
        向已连接的TCP服务器发送文本数据。数据会自动添加换行符作为消息分隔符。
        
        Args:
            data (str): 要发送的数据字符串
            
        Example:
            >>> client = TCPClient("127.0.0.1", 8888)
            >>> client.start()
            >>> client.send("Hello Server")
            
        Note:
            - 数据会自动添加换行符(\n)作为消息结束标志
            - 发送前会等待连接建立完成
            - 发送失败时会发出连接断开信号
        """
        try:
            # 等待连接建立
            while not self.running:
                time.sleep(0.1)
            data = data + "\n"
            self.infoSignal.emit(self.name, "send:"+data)
            self.socket.sendall(data.encode('utf-8'))
            # print("send:"+data)
        except Exception as e:
            # logging.error(f"Error: {str(e)}")
            print(f"Error: {str(e)}")
            self.connectedSignal.emit("NO", "发送失败！")

    def stop(self):
        """
        停止TCP客户端并关闭连接
        
        安全地关闭TCP连接和套接字，设置运行标志为False，
        并发送连接断开信号。
        
        Example:
            >>> client = TCPClient("127.0.0.1", 8888)
            >>> client.start()
            >>> # ... 使用客户端 ...
            >>> client.stop()  # 停止客户端
        """
        if self.isconnected:
            if self.socket:
                print(f"{self.name} shutdown and close socket")
                self.socket.shutdown(socket.SHUT_RDWR)
                # self.socket.close()
            self.running = False
            self.isconnected = False
            self.connectedSignal.emit("NO", "关闭连接！")
            # super().terminate()
        else:
            self.connectedSignal.emit("NO", "未连接！")

if __name__ == '__main__':
    """
    TCP客户端测试代码
    
    创建一个TCP客户端实例，连接到本地服务器并发送JSON格式的测试消息。
    """
    import json
    
    def fun(data):
        """测试数据处理函数"""
        print("func:",data)

    app = QApplication(sys.argv)
    client = TCPClient("127.0.0.1", 10003, func=fun)
    client.start()
    time.sleep(1)
    
    # 发送JSON格式的测试消息
    # str = json.dumps({"opcode":"StartAnalyzing", "parameter":{"FilePath":"D:\文件\工程数据\指向差标校.17下午中国标准时间", "IfUseSheet":True, "Sheet":"ElectricMachinery", "Variable":{"fw":1, "fy":0.1}}})
    str = json.dumps({"opcode":"PortOpen", "parameter":{"FilePath":"", "AutoAnalysis":True, "IfUseSheet":True, "Sheet":"ElectricMachinery", "Variable":{"fw":1, "fy":0.1}}})
    client.send(str)
    
    sys.exit(app.exec_())