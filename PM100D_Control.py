#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PM100D功率计主控制模块

该模块实现了PM100D光功率计的主控制界面和业务逻辑，提供：
- 图形化用户界面的控制逻辑
- 实时功率数据采集和显示
- 数据记录和CSV文件导出
- 设备连接管理和状态监控
- 波长和补偿值设置
- 自动量程控制
- TCP服务器自动化接口（可选）

主要功能：
- 设备发现和连接管理
- 实时功率测量显示（LCD数字显示）
- 最大值/最小值统计
- 实时波形绘图
- 数据记录到CSV文件
- 设备参数配置（波长、补偿值、量程）
- 多线程数据采集
- 用户界面事件处理

技术特点：
- 基于PyQt5的多线程架构
- 信号槽机制实现界面更新
- 线程池管理数据采集
- 实时图表显示
- 异常处理和错误恢复

作者: ivan
创建时间: 2025
版本: v1.0.1
"""

import datetime
import json
import os
import socket
import threading
import time
import pandas as pd

from queue import Queue

from PM100D import PM100D
from TCPClient import TCPClient
from utils import showAbout, edit_config, read_config
from concurrent.futures import ThreadPoolExecutor
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QThread, pyqtSignal, Qt, QTimer

from MyPlot import MyPlot
from TCPServer import TCPServer
from Ui_PM100D_Control import Ui_MainWindow

# 从更新文件获取版本号
VERSION = "Unknown" if not os.path.exists("更新内容.csv") or \
                       pd.read_csv("更新内容.csv", header=None, index_col=None, encoding="GBK").iloc[-1, 1] is None \
    else pd.read_csv("更新内容.csv", header=None, index_col=None, encoding="GBK").iloc[-1, 1]


class PM100D_Control(QtWidgets.QMainWindow, Ui_MainWindow):
    """
    PM100D功率计主控制类
    
    继承自QMainWindow和Ui_MainWindow，实现功率计控制界面的完整功能。
    负责设备管理、数据采集、界面更新、用户交互等核心业务逻辑。
    
    Attributes:
        device (PM100D): 功率计设备驱动实例
        pool (ThreadPoolExecutor): 线程池，用于数据采集
        future (Future): 数据采集任务的Future对象
        start_record (bool): 是否正在记录数据
        start_time (str): 记录开始时间
        stop_connection (bool): 是否停止连接
        operation (bool): 是否正在进行设置操作
        value_record (dict): 功率值统计记录
        CH1_plot (MyPlot): 实时绘图控件
        power_buffer (list): 功率数据缓冲区
        
    Signals:
        value_update (pyqtSignal): 数值更新信号
        value_save (pyqtSignal): 数值保存信号
    """
    
    # 数据更新信号槽
    value_update = pyqtSignal(list)
    # 保存数据信号槽
    value_save = pyqtSignal(list)

    def __init__(self, parent=None, device=None):
        """
        初始化主控制窗口
        
        Args:
            parent: 父窗口对象
            device (PM100D): 功率计设备实例
        """
        super(PM100D_Control, self).__init__(parent)
        self.setupUi(self)

        self.setWindowTitle(f"嘉慧功率计控制程序 {VERSION}")

        # TODO 检查版本更新

        self.version.setText(f"版本：{VERSION}")

        # 驱动类
        self.device = device
        self.update_info(f"检测到设备:{self.device.rm.list_resources()}")
        # 设备字典
        self.Com_Dict = {}
        # 读取配置
        self.config = read_config()
        # 初始化一个线程池供后续采集数据
        self.pool = None
        self.future = None
        # 是否开始记录
        self.start_record = False
        # 开始记录的时间
        self.start_time = None
        # 开始记录的数据下标
        self.startIndex = 0
        # 是否断开连接
        self.stop_connection = False
        # 是否在进行设置操作
        self.operation = False
        # 自动化服务器端口
        self.auto_port = 1235
        # 启动自动化服务器
        self.auto_server = TCPServer(port=self.auto_port, func=self.auto_server_controller)
        self.auto_server.start()
        # 客户端用于接收消息的队列
        # 数据记录表
        self.value_record = {"max": -60.0, "min": None, "value": 0.0}
        # 画图类
        self.CH1_plot = MyPlot({"功率": [0.0]})
        self.CH1_Plot_layout.addWidget(self.CH1_plot)
        # 禁止用户修改端口信息
        self.portInfo.setReadOnly(True)
        # 连接信号槽到对应函数
        self.value_update.connect(self.update_value)
        self.value_save.connect(self.save_value)
        self.power_buffer = []
        # 当前设备功率单位（W 或 DBM），用于界面自动缩放
        self.current_unit = 'W'

        self.init_btn()

        self.check_port_callback()

    def init_btn(self):
        """
        初始化用户界面按钮和控件
        
        设置各种按钮的点击事件处理函数，建立信号槽连接，
        配置初始的按钮状态。
        """

        self.version.clicked.connect(lambda: showAbout(self))

        self.ComCheck.clicked.connect(self.check_port_callback)

        self.Com.currentTextChanged.connect(self.current_port_callback)

        self.Connect.clicked.connect(self.connect_pm)
        self.Disconnect.clicked.connect(lambda: self.disconnect_pm())
        self.Clean.clicked.connect(self.clean_callback)
        self.startRecordBtn.clicked.connect(self.start_record_callback)
        self.stopRecordBtn.clicked.connect(self.stop_record_callback)
        self.startRecordBtn.setEnabled(False)
        self.stopRecordBtn.setEnabled(False)
        self.enableAutoRange.clicked.connect(self.enable_auto_range)
        self.disableAutoRange.clicked.connect(self.disable_auto_range)
        # 绑定波长设置按键
        self.setCH1wave.clicked.connect(self.set_wavelength)
        # 绑定功率单位设置按键
        self.setCH1unit.clicked.connect(self.set_power_unit_callback)
        # self.setCH1comp.clicked.connect(self.set_compensation)

        self.btn_group_enable(False)

    def btn_group_enable(self, enable):
        """
        批量启用/禁用按钮组
        
        Args:
            enable (bool): True为启用，False为禁用
        """
        self.Connect.setEnabled(enable)
        self.Disconnect.setEnabled(enable)
        self.Clean.setEnabled(enable)
        self.setCH1wave.setEnabled(enable)
        self.setCH1unit.setEnabled(enable)

    def check_port_callback(self):
        """
        检查设备端口回调函数
        
        扫描系统中可用的VISA设备，填充到设备选择下拉框中，
        并启用相关的控制按钮。
        """
        if self.device is None:
            self.device = PM100D()

        self.Com.clear()
        self.Com_Dict.clear()
        devices = self.device.heartbeat()
        for device in devices:
            self.Com_Dict["%s" % device] = "%s" % device
            self.Com.addItem(device)
        self.btn_group_enable(True)

    def connect_sig(self, sig, info):
        """
        TCP连接信号处理
        :param sig 接收到的信号
        :param info 接收到的消息
        """
        if sig == "NO":
            self.tcp_disconnect_callback()
            self.update_info(f"TCP连接断开！{info}")

    def current_port_callback(self):
        """
        显示当前选中的设备名称
        """
        device = self.Com.currentText()
        if device in self.Com_Dict:
            self.ComName.setText(self.Com_Dict[device])
        else:
            self.ComName.setText("")

    def connect_pm(self):
        """
        连接功率计
        :return: success
        """
        if self.device.inst is not None:
            self.update_info("已连接！")
            return True
        if self.pool:
            # 如果连接过
            print("重连")
            a = self.device.reconnect_device(self.Com.currentText(), 3)
        else:
            print("首次连接")
            # 连接用户选中的设备
            a = self.device.connect(self.Com.currentText())
        if a:
            try:
                # 更新自动量程状态
                if self.auto_range_status():
                    self.CH1_range.setText("自动量程" + ": 开启")
                    self.enableAutoRange.setEnabled(False)
                    self.disableAutoRange.setEnabled(True)
                else:
                    self.CH1_range.setText("自动量程" + ": 关闭")
                    self.enableAutoRange.setEnabled(True)
                    self.disableAutoRange.setEnabled(False)
                # 更新波长
                wavelength = self.wavelength()
                self.CH1_wave.setText("波长值: " + str(wavelength))

                # 更新补偿值
                comp = self.compensation()
                self.CH1_comp_2.setText("补偿值: " + str(comp))

                # 更新功率单位
                unit = self.power_unit()
                self.current_unit = unit.strip() if isinstance(unit, str) else 'W'
                self.CH1_unit.setText("功率单位: " + str(unit))

                # 开启采集线程
                self.pool = ThreadPoolExecutor(max_workers=2)
                future = self.pool.submit(self.power_record)
                self.future = future
            except Exception as e:
                print(self, "警告", f"连接失败！{e}")
                return False
            self.Connect.setEnabled(False)
            self.Disconnect.setEnabled(True)
            self.startRecordBtn.setEnabled(True)
            self.update_info("连接成功！")
            return True
        else:
            self.update_info("连接失败！")
            return False

    def auto_server_controller(self, data):
        data = json.loads(data)
        # 获取功率接口
        if data['opcode'] == "GetPower":
            res_dict = {"CH1": str(self.CH1_Value.value())}
            return self.make_pack(True, res_dict, "Null")
        # 记录控制接口
        elif data['opcode'] == 'RecordCon':
            # 开始记录
            if data['parameter']['Con'] == 'Start':
                success = self.start_record_callback()
                error_msg = ""
                if not success:
                    error_msg = "开启记录错误!"
                return self.make_pack(success, '', error_msg)
            # 停止记录
            elif data['parameter']['Con'] == 'Stop':
                success = self.stop_record_callback()
                error_msg = ""
                if not success:
                    error_msg = "关闭记录错误!"
                return self.make_pack(success, '', error_msg)
            else:
                return self.make_pack(False, '', f'command not supported:{data}')
        # 连接设备接口
        elif data['opcode'] == 'ConnectDevice':
            # 自动化连接的时候串口还没有打开，所以还要先打开串口
            a = self.PortOpen_callback(alert=False)
            b = False
            time.sleep(0.01)
            if a:
                b = self.connect_pm()
            error_msg = ""
            if not a or not b:
                error_msg = "连接设备错误!"
            return self.make_pack(a & b, "", error_msg)
        # 检查版本号接口
        elif data['opcode'] == 'check':
            return self.make_pack(True, self.VERSION, 'Null')
        else:
            return self.make_pack(False, "", "Unknown command!")

    def make_pack(self, isSuccess, Value, ErrorMessage):
        """
        打包响应体
        :param isSuccess: 操作是否成功
        :param Value:     响应值
        :param ErrorMessage: 错误信息
        :return: 响应体
        """
        data = {"isSuccess": isSuccess, "Value": Value, "ErrorMessage": ErrorMessage}
        return json.dumps(data)

    def disconnect_pm(self):
        """
        断开和设备的连接。

        采集线程每 7ms 检查一次 stop_connection 标志，设置后最多等待 3s
        让其自然退出，再执行 VISA 断开操作，避免资源被占用时写入
        *RST/*CLS 引发 VI_ERROR_RSRC_LOCKED。
        """
        self.stop_connection = True
        # 立即禁用相关按钮，给用户反馈
        self.Disconnect.setEnabled(False)
        self.startRecordBtn.setEnabled(False)
        self.stopRecordBtn.setEnabled(False)
        self.update_info("正在断开连接，请稍候...")
        # 断开连接前先停止记录以保存数据
        self.stop_record_callback()

        future_snapshot = self.future

        def _wait_and_disconnect():
            # 等待采集线程退出，最多等 3 秒，避免 VISA 资源锁冲突
            if future_snapshot is not None:
                try:
                    future_snapshot.result(timeout=3.0)
                except Exception:
                    pass
            self.device.disconnect()
            self.stop_connection = False
            # 通过 QTimer 将 UI 更新调度回主线程
            QTimer.singleShot(0, self._on_disconnect_done)

        threading.Thread(target=_wait_and_disconnect, daemon=True).start()

    def _on_disconnect_done(self):
        """断开完成后在主线程更新 UI 状态。"""
        # 等待系统释放 USB 资源后再启用连接按钮
        QTimer.singleShot(2000, lambda: self.Connect.setEnabled(True))
        self.update_info("断开连接成功!")

    def power_record(self):
        if not os.path.exists("./Record"):
            os.mkdir("./Record")
        counter = 0
        self.last_time = 0
        #start = int(round(time.time() * 1000))
        #speed_counter = 0
        while True:
            try:
                now = int(round(time.time() * 1000))
                #if (now - start) >= 1000:
                    #start = now
                    # print(f"PowerRecord: {speed_counter}次/秒")
                    # 100个/s
                    #speed_counter = 0

                if (now - self.last_time) >= 7:  # 7ms采集一次
                    counter += 1
                    #speed_counter += 1
                    if self.stop_connection:
                        break
                    if self.operation:
                        continue
                    result = self.device.read_power()

                    if result is not None:
                        self.power_buffer.append(result)
                        if counter % 10 == 0:  # 每采集10次才更新UI显示
                            counter = 0
                            self.value_update.emit(self.power_buffer)
                    if self.start_record:  # 持久化速率和采集速率一致
                        self.value_save.emit(result)  # 更改为在按下开始记录后才开始保存
                    self.last_time = now
            except Exception as e:
                print(f"PowerRecord Error: {e}")

    def update_value(self, value_list: list):
        # 取缓冲区最新一个值
        value = value_list[-1]
        if value is None:
            return

        # 更新统计值（使用原始未缩放的值，保证比较精度）
        self.value_record["value"] = value
        if value > self.value_record["max"]:
            self.value_record["max"] = value
        if self.value_record["min"] is None:
            self.value_record["min"] = value
        elif value < self.value_record["min"]:
            self.value_record["min"] = value

        # 根据当前值的量级自动选择单位，三个 LCD 使用同一单位前缀
        scaled, unit_label = self.format_power_for_display(value)
        # 推导缩放因子：避免除以零，value==0 时因子为 1
        scale_factor = (scaled / value) if value != 0 else 1.0

        self.CH1_Value.display(self._format_lcd(scaled))
        self.CH1_max.display(self._format_lcd(self.value_record["max"] * scale_factor))
        self.CH1_min.display(self._format_lcd(self.value_record["min"] * scale_factor))

        # 实时更新单位标签，反映当前自动选择的前缀
        self.CH1_unit.setText(f"功率单位: {unit_label}")

        if self.start_record:
            self.CH1_plot.update_signal.emit({'功率': value})

    def start_record_callback(self):
        """
        开始记录
        :return: True
        :return: False
        """
        if self.start_record:
            print("已经开始记录，请勿重复开始！")
            return False
        self.start_record = True
        self.startTime = time.strftime('%Y-%m-%d %H-%M-%S')
        self.startRecordBtn.setEnabled(False)
        self.stopRecordBtn.setEnabled(True)
        self.update_info("开始记录！")
        self.clean_callback()
        return True

    def stop_record_callback(self):
        """
        停止记录并保存文件
        :return: 停止是否成功
        """
        if not self.start_record:
            # print("还未开始记录！")
            return False
        self.start_record = False
        self.startRecordBtn.setEnabled(True)
        self.stopRecordBtn.setEnabled(False)
        self.update_info("停止记录！")
        # 停止图像更新

        # 更改文件名
        try:
            os.rename(f"./Record/PowerRecord_{self.startTime}.csv",
                      f"./Record/PowerRecord_{self.startTime}_{time.strftime('%Y-%m-%d %H-%M-%S')}.csv")
        except FileNotFoundError:
            print(f"错误：找不到文件 ./Record/PowerRecord_{self.startTime}.csv")
            return False
        except PermissionError:
            print("错误：没有权限更改文件名")
            return False
        except OSError as e:
            print(f"错误：无法重命名文件 - {e}")
            return False
        return True

    def save_value(self, value):
        if not os.path.exists(f"./Record/PowerRecord_{self.startTime}.csv"):
            with open(f"./Record/PowerRecord_{self.startTime}.csv", "w", encoding="GBK"
                      ) as f:
                f.write(f"时间,功率,波长,补偿值\n")
        with open(f"./Record/PowerRecord_{self.startTime}.csv", "a") as f:
            f.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + ","
                    + str(value) + "," + str(self.CH1_wave.text()[4:]) + "," + str(self.CH1_comp_2.text()[4:]) + "\n")

    def wavelength(self) -> float:
        """
        设置波长
        """

        if self.device.inst is None:
            self.update_info("未连接功率计, 无法获取波长!")
            return -1
        # 读取波长前先设置信号量让数据采集停止，不然会指令错误
        self.operation = True

        wavelength = self.device.get_wavelength()

        self.operation = False

        return wavelength

    def compensation(self) -> float:
        """
        设置波长
        """

        if self.device.inst is None:
            self.update_info("未连接功率计, 无法获取补偿值!")
            return -1
        # 读取波长前先设置信号量让数据采集停止，不然会指令错误
        self.operation = True

        comp = self.device.get_comp()

        self.operation = False

        return comp

    def power_unit(self) -> str:
        """
        获取当前功率单位
        """
        if self.device.inst is None:
            self.update_info("未连接功率计, 无法获取功率单位!")
            return "未知"
        # 读取单位前先设置信号量让数据采集停止，不然会指令错误
        self.operation = True

        unit = self.device.get_power_unit()

        self.operation = False

        return unit

    def set_power_unit_callback(self) -> bool:
        """
        设置功率单位回调函数
        """
        if self.device.inst is None:
            self.update_info("未连接功率计, 无法设置功率单位!")
            return False

        # 获取用户选择的单位
        selected_unit = self.CH1TUnit.currentText()
        
        # 设置前先停止采集
        self.operation = True
        
        try:
            success = self.device.set_power_unit(selected_unit)
            if success:
                # 更新显示并同步 current_unit 用于界面缩放
                unit = self.device.get_power_unit()
                self.current_unit = unit.strip() if isinstance(unit, str) else selected_unit
                self.CH1_unit.setText("功率单位: " + str(unit))
                self.update_info(f"功率单位设置成功: {unit}")
                return True
            else:
                self.update_info("功率单位设置失败!")
                return False
        except Exception as e:
            self.update_info(f"设置功率单位时发生错误: {e}")
            return False
        finally:
            self.operation = False

    def set_compensation(self) -> bool:
        """
        设置补偿值
        """
        # 设置补偿值前先设置信号量让数据采集停止，不然会指令错误
        if self.device.inst is None:
            self.update_info("未连接功率计, 无法设置补偿值!")
            return False
        self.operation = True

        # 获取下拉框选择的补偿值
        comp = float(self.CH1_comp.text())
        success = self.device.set_comp(comp)
        self.operation = False

        if success:
            self.CH1_comp_2.setText("补偿值值: " + self.CH1_comp.text())
            self.update_info(f"补偿值设置成功！")
            # print(f"补偿值设置成功！")
            return True
        else:
            self.update_info(f"补偿值设置失败！")
            # print(f"补偿值设置失败！")
            return False

    def set_wavelength(self):
        """
        设置波长
        """
        # 设置波长前先设置信号量让数据采集停止，不然会指令错误
        if self.device.inst is None:
            self.update_info("未连接功率计, 无法设置波长!")
            return
        self.operation = True
        # time.sleep(0.1)
        # 获取下拉框选择的波长
        wavelength = int(self.CH1Twave.currentText()[:-2])
        success = self.device.set_wavelength(wavelength)
        if success:
            self.CH1_wave.setText("波长值: " + self.CH1Twave.currentText()[:-2])
            self.update_info(f"波长设置成功！")
            # print(f"波长设置成功！")
        else:
            self.update_info(f"波长设置失败！")
            # print(f"波长设置失败！")
        self.operation = False

    def auto_range_status(self):
        # 设置前先停止采集
        self.operation = True
        # time.sleep(0.1)
        auto = self.device.get_auto_range_status()
        self.operation = False

        if auto:
            return True
        else:
            return False

    def enable_auto_range(self):
        """
        启动自动范围
        """
        # 设置前先停止采集
        self.operation = True
        # time.sleep(0.1)
        success = self.device.start_auto_range()
        if success:
            self.CH1_range.setText("自动量程" + ": 开启")
            self.update_info(f"自动范围已开启！")
            # print(f"自动范围已开启！")
            self.enableAutoRange.setEnabled(False)
            self.disableAutoRange.setEnabled(True)
        else:
            self.CH1_range.setText("自动量程" + ": 关闭")
            self.update_info(f"自动范围开启失败！")
            # print(f"自动范围开启失败！")
            self.enableAutoRange.setEnabled(True)
            self.disableAutoRange.setEnabled(False)
        self.operation = False

    def disable_auto_range(self):
        """
        关闭自动范围
        """
        self.operation = True
        # time.sleep(0.1)
        success = self.device.stop_auto_range()
        if success:
            self.CH1_range.setText("自动量程" + ": 关闭")
            self.update_info(f"自动范围已关闭！")
            # print(f"自动范围已关闭！")
            self.enableAutoRange.setEnabled(True)
            self.disableAutoRange.setEnabled(False)
        else:
            self.CH1_range.setText("自动量程" + ": 开启")
            self.update_info(f"自动范围关闭失败！")
            # print(f"自动范围关闭失败！")
            self.enableAutoRange.setEnabled(False)
            self.disableAutoRange.setEnabled(True)
        self.operation = False

    def clean_callback(self):
        """
        清空数据显示
        :return:
        """
        self.CH1_Value.display("0")
        self.CH1_max.display("0")
        self.CH1_min.display("0")
        self.value_record = {"max": -60, "min": None, "value": 0}
        self.CH1_plot.clearData()

    def format_power_for_display(self, value: float) -> tuple:
        """
        根据当前功率单位和数值大小，自动选择合适的 SI 前缀进行缩放。

        DBM 模式：直接返回原始值和 'dBm' 标签，不做量级缩放。
        W 模式：按照 W / mW / µW / nW / pW 自动选择最合适的前缀，
                使显示值落在 [1, 1000) 区间内（零值特殊处理）。

        Returns:
            (scaled_value: float, unit_label: str)
        """
        unit = self.current_unit.strip().upper()
        if unit == 'DBM':
            return value, 'dBm'

        abs_val = abs(value)
        if abs_val == 0:
            return 0.0, 'W'
        elif abs_val >= 1:
            return value, 'W'
        elif abs_val >= 1e-3:
            return value * 1e3, 'mW'
        elif abs_val >= 1e-6:
            return value * 1e6, 'µW'
        elif abs_val >= 1e-9:
            return value * 1e9, 'nW'
        else:
            return value * 1e12, 'pW'

    @staticmethod
    def _format_lcd(value: float) -> str:
        """
        将已缩放后的数值格式化为适合 7 位 LCD 的字符串。

        整数位越多，保留的小数位越少，始终保持 6 位有效数字以内，
        避免超出 QLCDNumber 的显示位数。
        """
        if value == 0:
            return "0"
        abs_val = abs(value)
        if abs_val >= 1e5:
            return f"{value:.0f}"
        elif abs_val >= 1e4:
            return f"{value:.1f}"
        elif abs_val >= 1e3:
            return f"{value:.2f}"
        elif abs_val >= 1e2:
            return f"{value:.3f}"
        elif abs_val >= 10:
            return f"{value:.4f}"
        elif abs_val >= 1:
            return f"{value:.5f}"
        else:
            return f"{value:.6f}"

    def update_info(self, info):
        self.portInfo.append(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " " + info)
        self.portInfo.append("\n")
        self.portInfo.moveCursor(QtGui.QTextCursor.End)

    def closeEvent(self, event):
        reply = QtWidgets.QMessageBox.question(self,
                                               'PM100D功率计',
                                               "是否要退出程序？",
                                               QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            event.accept()
            os._exit(0)

        else:
            event.ignore()
