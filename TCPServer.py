#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TCP服务器通信模块

该模块实现了基于PyQt5的多线程TCP服务器，提供：
- 多客户端并发连接支持
- 异步消息处理和响应
- 优雅的服务器关闭机制
- 基于信号槽的状态通知
- 自动端口占用检测

主要用于接收TCP客户端的连接请求，处理JSON格式的命令消息，
并返回相应的响应数据。

作者: ivan
创建时间: 2025
版本: v1.0.1
"""

import sys
import socket
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget, QPushButton, QLineEdit, QTextEdit
from PyQt5.QtCore import QThread, pyqtSignal, Qt
import threading
from queue import Queue
import json

class TCPServer(QThread):
    """
    TCP服务器类
    
    基于PyQt5的QThread实现的多线程TCP服务器。支持多个客户端同时连接，
    每个客户端连接都在独立的线程中处理。服务器可以接收客户端消息，
    调用自定义处理函数，并返回响应数据。
    
    Attributes:
        host (str): 服务器绑定的IP地址
        port (int): 服务器监听端口
        func (callable): 消息处理回调函数
        recQueues (dict): 接收队列字典（保留属性）
        _is_running (bool): 服务器运行状态标志
        server_socket (socket.socket): 服务器套接字
        client_threads (dict): 客户端线程字典
        client_sockets (list): 客户端套接字列表
        
    Signals:
        cmd_send_signal (pyqtSignal): 命令发送信号
        ready_signal (pyqtSignal): 服务器就绪信号
    """
    
    # 命令发送信号：(命令, 参数)
    cmd_send_signal = pyqtSignal([str, str])
    # 服务器就绪信号：(状态, 消息)
    ready_signal = pyqtSignal([bool, str])

    def __init__(self, port=8888, func=lambda x: print(x)):
        """
        初始化TCP服务器
        
        Args:
            port (int): 服务器监听端口，默认8888
            func (callable): 消息处理函数，接收字符串参数并返回响应字符串
            
        Example:
            >>> def message_handler(data):
            ...     return f"Echo: {data}"
            >>> server = TCPServer(8888, message_handler)
            >>> server.start()
        """
        super(TCPServer, self).__init__()
        self.host = socket.gethostbyname(socket.gethostname())
        self.port = int(port)
        self.func = func
        self.recQueues = {}
        
        # 用于服务器关闭的标志
        self._is_running = True
        self.server_socket = None
        self.client_threads = {}  # 存储所有客户端线程
        self.client_sockets = []  # 存储所有客户端socket

    def handle_client_connection(self, client_socket, addr):
        """
        处理单个客户端连接
        
        在独立线程中处理客户端的连接和消息接收。支持消息缓冲和
        自动响应机制。当服务器关闭或客户端断开时，会自动清理资源。
        
        Args:
            client_socket (socket.socket): 客户端套接字对象
            addr (tuple): 客户端地址信息 (IP, port)
        """
        try:
            buffer = b""
            while self._is_running:
                try:
                    client_socket.settimeout(1)  # 设置超时以便定期检查关闭标志
                    data = client_socket.recv(1024)
                    if not data:  # 连接关闭
                        break
                    
                    # print(f"接收到来自{addr}的数据: {data.decode('utf-8')}")
                    buffer += data
                    
                    # 处理完整的消息（以换行符分隔）
                    if b'\n' in buffer:
                        messages = buffer.split(b'\n')
                        for message in messages[:-1]:
                            response = self.func(message.decode('utf-8'))
                            self.send(client_socket, response)  
                        buffer = messages[-1]  # 保留未完整的消息
                        
                except socket.timeout:
                    continue  # 超时后继续循环以检查关闭标志
                except Exception as e:
                    print(f"{addr}:客户端连接异常: {e}")
                    break
                    
            # 处理剩余未处理的消息
            if buffer:
                self.server_handler(client_socket, buffer)
                
        finally:
            print(f"关闭来自{addr}的连接")
            self.cleanup_client(client_socket, addr)

    def server_handler(self, client_socket, buffer):
        """
        处理客户端数据
        
        解码并处理客户端发送的缓冲数据，调用注册的处理函数，
        并将响应发送回客户端。
        
        Args:
            client_socket (socket.socket): 客户端套接字
            buffer (bytes): 待处理的数据缓冲区
        """
        try:
            data = buffer.decode('utf-8')
            if data:
                response = self.func(data)
                self.send(client_socket, response)
        except Exception as e:
            print(f"处理客户端数据时出错: {e}")

    def cleanup_client(self, client_socket, addr):
        """
        清理客户端资源
        
        安全地关闭客户端连接并清理相关资源，包括从客户端列表
        和线程字典中移除记录。
        
        Args:
            client_socket (socket.socket): 要清理的客户端套接字
            addr (tuple): 客户端地址信息
        """
        try:
            if client_socket in self.client_sockets:
                self.client_sockets.remove(client_socket)
            if addr in self.client_threads:
                del self.client_threads[addr]
            client_socket.shutdown(socket.SHUT_RDWR)
            client_socket.close()
        except Exception as e:
            print(f"清理客户端{addr}资源时出错: {e}")

    def run(self):
        """
        服务器主运行函数
        
        启动TCP服务器，绑定端口并开始监听客户端连接。对每个新的
        客户端连接创建独立的处理线程。包含端口占用检测和优雅关闭机制。
        """
        print("启动TCP服务器")
        print(f"本机IP地址: {self.host}")
        print(f"端口号: {self.port}")

        # 检查端口是否被占用
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex((self.host, self.port))
            if result == 0:
                print(f"端口{self.port}已被占用，请更换端口")
                self.ready_signal.emit(False, "端口已被占用，请更换端口")
                return

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(('', self.port))
        self.server_socket.settimeout(1)  # 设置超时以便定期检查关闭标志
        self.server_socket.listen(5)
        print(f"服务器正在{self.host}:{self.port}上监听...")
        self.ready_signal.emit(True, f"服务器正在{self.host}:{self.port}上监听...")

        self._is_running = True
        
        try:
            while self._is_running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    print(f"接受到来自{addr}的连接")
                    
                    # 存储客户端socket
                    self.client_sockets.append(client_socket)
                    
                    # 为每个客户端连接创建一个单独的线程来处理
                    client_thread = threading.Thread(
                        target=self.handle_client_connection, 
                        args=(client_socket, addr),
                        daemon=True
                    )
                    self.client_threads[addr] = client_thread
                    client_thread.start()
                    
                except socket.timeout:
                    continue  # 超时后继续循环以检查关闭标志
                except Exception as e:
                    print(f"连接异常: {e}")
        finally:
            self.cleanup_server()

    def cleanup_server(self):
        """
        清理服务器资源
        
        关闭所有客户端连接，清理线程和套接字资源，
        最后关闭服务器套接字。确保资源得到正确释放。
        """
        print("正在关闭服务器...")
        
        # 关闭所有客户端连接
        for client_socket in self.client_sockets[:]:  # 使用副本遍历
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
                client_socket.close()
            except Exception as e:
                print(f"关闭客户端socket时出错: {e}")
        
        # 清空客户端列表
        self.client_sockets.clear()
        self.client_threads.clear()
        
        # 关闭服务器socket
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception as e:
                print(f"关闭服务器socket时出错: {e}")
            finally:
                self.server_socket = None
        
        print("服务器已关闭")

    def close_tcp_server(self):
        """
        关闭TCP服务器
        
        请求关闭TCP服务器。设置运行标志为False，并通过创建临时连接
        来解除accept()的阻塞状态，确保服务器能够优雅地关闭。
        
        Example:
            >>> server = TCPServer(8888)
            >>> server.start()
            >>> # ... 服务器运行一段时间 ...
            >>> server.close_tcp_server()  # 关闭服务器
        """
        print("正在请求关闭TCP服务器...")
        self._is_running = False
        
        # 如果服务器socket阻塞在accept()，需要先关闭它
        if self.server_socket:
            try:
                # 创建一个临时socket连接到服务器以解除accept()阻塞
                temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_socket.connect((self.host, self.port))
                temp_socket.close()
            except Exception as e:
                print(f"创建临时连接时出错: {e}")

    def send(self, client_socket, data):
        """
        向客户端发送数据
        
        向指定的客户端套接字发送文本数据。数据会自动添加换行符
        作为消息结束标志。
        
        Args:
            client_socket (socket.socket): 目标客户端套接字
            data (str): 要发送的数据字符串
            
        Note:
            发送失败时会打印错误信息但不会抛出异常
        """
        try:
            data = data + "\n"
            # print(f"向{client_socket.getpeername()}发送数据: {data}")
            client_socket.sendall(data.encode('utf-8'))
        except Exception as e:
            print(f"向{client_socket.getpeername()}发送数据异常: {e}")

# 注释掉的测试代码
# if __name__ == '__main__':
#     app = QApplication(sys.argv)
#     server = TCPServer()
#     server.start()
#     re = server.check_login_log(datetime.datetime(2025, 1, 14, 9, 30, 14), datetime.datetime(2025, 1, 14, 9, 30, 18), 4)
#     print(re)
#     sys.exit(app.exec_())