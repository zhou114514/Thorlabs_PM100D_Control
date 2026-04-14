#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Thorlabs PM100D功率计驱动模块

该模块实现了Thorlabs PM100D系列光功率计的Python驱动程序，提供：
- USB VISA接口的设备连接和通信
- 功率测量、调零、波长设置等核心功能
- 自动量程控制和功率单位设置
- 设备状态监控和错误处理
- 断线重连机制

支持的设备：
- Thorlabs PM100D系列光功率计
- USB接口连接（需要VISA驱动支持）

依赖要求：
- pyvisa和pyvisa-py库
- libusb1.0.dll（需放置在C:/windows/system32/目录下）

作者: ivan
创建时间: 2025
版本: v1.0.1
"""

import time
import pyvisa


class PM100D:
    """
    Thorlabs PM100D光功率计驱动类
    
    提供与Thorlabs PM100D系列光功率计通信的完整接口。支持USB VISA连接，
    可进行功率测量、设备配置、调零校准等操作。
    
    设备地址格式：USB0::4883::32888::P0047129::0::INSTR
    - 厂商ID: 4883 (0x1313, Thorlabs)
    - 产品ID: 32888 (0x8078)
    
    Attributes:
        rm (pyvisa.ResourceManager): VISA资源管理器
        devices (list): 检测到的VISA设备列表
        inst (pyvisa.Resource): 当前连接的设备实例
    """

    def __init__(self):
        """
        初始化PM100D功率计驱动实例
        
        创建VISA资源管理器，使用pyvisa-py后端以支持纯Python实现。
        初始化设备列表和连接实例为None。
        """
        self.rm = pyvisa.ResourceManager('@py')  # 使用pyvisa-py后端
        self.devices = None
        self.inst = None
        self.user_power_unit = 'DBM'  # 记录用户选择的功率单位

    def heartbeat(self):
        """
        设备心跳检测
        
        扫描并返回当前系统中可用的VISA设备列表。如果资源管理器
        为空，会重新创建。这个方法用于检测设备连接状态。
        
        Returns:
            list: 检测到的VISA设备地址列表
            
        Example:
            >>> pm = PM100D()
            >>> devices = pm.heartbeat()
            >>> print(devices)
            ['USB0::4883::32888::P0047129::0::INSTR']
        """
        if self.rm is None:
            self.rm = pyvisa.ResourceManager('@py')
        devices = self.rm.list_resources()
        # print("检测到设备: ", self.rm.list_resources())
        return devices

    def connect(self, device_name):
        """
        建立与功率计设备的连接
        
        连接到指定的功率计设备并进行初始化配置。连接成功后会自动
        设置功率单位为μW，并配置通信超时时间。
        
        Args:
            device_name (str): 设备VISA地址，格式如"USB0::4883::32888::P0047129::0::INSTR"
            
        Returns:
            bool: 连接是否成功
            
        Example:
            >>> pm = PM100D()
            >>> success = pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> if success:
            ...     print("连接成功")
            
        Note:
            - 仅支持Thorlabs设备（设备地址包含"USB0::4883::32888"）
            - 连接成功后会自动设置功率单位为μW
            - 设置通信超时时间为5000毫秒
        """
        try:
            # 关闭连接后需要重新创建资源管理器
            if self.rm is None:
                self.rm = pyvisa.ResourceManager('@py')
            if self.devices is None:
                self.devices = self.rm.list_resources()
                # print("检测到的设备:", self.devices)

            # 检查是否为Thorlabs设备
            if "USB0::4883::32888" in device_name:
                self.inst = self.rm.open_resource(device_name)
                # self.inst.write('*RST')  # 发送硬件复位命令
                # self.inst.write('*CLS')  # 清除状态
                self.inst.timeout = 5000  # 设置超时（毫秒）
                # print(self.inst.query("*IDN?"))  # 查询设备标识
                
                # 连接成功后设置默认功率单位为微瓦
                self.set_power_unit('μW')
                return True

            return False
        except Exception as e:
            print(f"连接失败: {e}")
            self.disconnect()
            return False

    def read_power(self) -> list:
        """
        读取功率测量值
        
        从功率计读取当前的光功率测量值。使用SCPI命令":MEAS:POW?"
        获取测量结果，并处理可能的错误情况。
        
        Returns:
            list: 包含单个功率值的列表，精度为两位小数；
                 如果读取失败或设备未连接，返回空列表
                 
        Example:
            >>> pm = PM100D()
            >>> pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> power = pm.read_power()
            >>> if power:
            ...     print(f"当前功率: {power[0]} dBm")
            
        Note:
            - 返回值格式为列表，包含一个浮点数
            - 当功率计返回"9.91E37"时表示设备出错，此时返回空列表
            - 功率值保留两位小数
        """
        # 如果检测到已经断开连接，则停止读取
        if self.inst is None:
            return []
        inst = self.inst

        try:
            # power = inst.query(":READ?")  # 直接读取当前功率值的替代方法
            power = inst.query(":MEAS:POW?")
            # print(f"当前功率: {power}W")  # 科学计数法显示
            
            # 当返回这个数值时说明功率计出错
            if power == "9.91E37":
                return []
                
            power_value = float(power)
            
            # 如果用户选择的单位是微瓦，需要进行单位转换
            if hasattr(self, 'user_power_unit') and self.user_power_unit == 'μW':
                # 将瓦特转换为微瓦 (1W = 1,000,000μW)
                power_value = power_value * 1_000_000
                
        except Exception as e:
            # print("读取错误: ", e)
            return []
        return [float('%.2f' % power_value)]

    def zero_adjustment(self, timeout=3.0, poll_interval=0.1) -> bool:
        """
        执行功率计的调零操作
        
        对功率计进行调零校准，消除系统暗电流和噪声的影响。
        调零前请确保探测器未接收任何光信号。
        
        Args:
            timeout (float): 调零操作的超时时间（秒），默认为3.0秒
            poll_interval (float): 状态查询间隔（秒），默认为0.1秒
            
        Returns:
            bool: True表示调零成功，False表示失败或超时
            
        Example:
            >>> pm = PM100D()
            >>> pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> if pm.zero_adjustment():
            ...     print("调零成功")
            
        Note:
            - 调零前请确保探测器处于无光照射状态
            - 调零过程中请勿移动或触碰探测器
            - 如果调零失败，设备连接将被断开
        """
        try:
            # 发送调零初始化命令
            self.inst.write("SENS:CORR:COLL:ZERO:INIT")

            start_time = time.time()
            while time.time() - start_time < timeout:
                # 查询调零状态（返回 '0'=进行中，'1'=完成）
                status = self.inst.query("SENS:CORR:COLL:ZERO:STAT?").strip()

                if status == '1':
                    # print("设备调零成功！")
                    return True
                elif status == '0':
                    time.sleep(poll_interval)
                else:
                    # print(f"警告：未知状态码 '{status}'")
                    break

            # print(f"错误：调零操作超时（{timeout}秒）")
            self.disconnect()
            return False

        except pyvisa.VisaIOError as e:
            print(f"通信错误：{e}")
            self.disconnect()
            return False
        except Exception as e:
            print(f"未知错误：{e}")
            self.disconnect()
            return False

    def get_wavelength(self) -> float:
        """
        获取当前设置的工作波长
        
        读取功率计当前配置的工作波长。不同波长下功率计的响应度不同，
        因此准确的波长设置对测量精度很重要。
        
        Returns:
            float: 当前波长值（纳米）
            
        Example:
            >>> pm = PM100D()
            >>> pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> wavelength = pm.get_wavelength()
            >>> print(f"当前波长: {wavelength} nm")
            
        Note:
            功率计支持的波长范围通常为800-1700纳米
        """
        return float(self.inst.query("SENS:CORR:WAV?"))

    def set_wavelength(self, wavelength) -> bool:
        """
        设置功率计的工作波长
        
        设置功率计的工作波长以确保测量精度。功率计会根据设置的波长
        自动应用相应的响应度校正系数。
        
        Args:
            wavelength (float): 要设置的波长值（纳米），范围800-1700nm
            
        Returns:
            bool: 设置是否成功
            
        Example:
            >>> pm = PM100D()
            >>> pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> if pm.set_wavelength(850):
            ...     print("波长设置成功")
            
        Note:
            - 支持的波长范围：800-1700纳米
            - 波长设置会影响功率测量的准确性
            - 设置超出范围的波长将返回False并打印错误信息
        """
        # 设备支持的波长范围 [800, 1700]
        # 可以通过查询设备获取实际范围：
        # min = float(self.inst.query("SENS:CORR:WAV? MIN"))
        # max = float(self.inst.query("SENS:CORR:WAV? MAX"))
        min = 800
        max = 1700
        # print("min: ", min)
        # print("max: ", max)

        if wavelength < min or wavelength > max:
            print("波长超出仪器范围！")
            return False

        self.inst.write(f"SENS:CORR:WAV {wavelength}")
        return True

    def disconnect(self):
        """
        安全断开设备连接
        
        正确地断开与功率计的连接并释放所有资源。断开前会执行硬件复位
        和状态清除，确保设备能够被重新连接。
        
        Note:
            - 断开连接前必须调用此方法，否则会占用资源导致无法重新连接
            - 方法会自动执行硬件复位和状态清除
            - 关闭设备实例和资源管理器
            
        Example:
            >>> pm = PM100D()
            >>> pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> # ... 进行测量操作 ...
            >>> pm.disconnect()  # 必须调用以释放资源
        """
        # 关闭连接实例
        # time.sleep(0.1)

        if self.inst:
            # 关闭连接前一定要复位硬件和清除状态，不然无法重新连接！！！
            self.inst.write('*RST')  # 发送硬件复位命令
            self.inst.write('*CLS')  # 清除状态

            self.inst.close()
            self.inst = None
            # print("设备已断开连接!")
            
        # 关闭资源管理器
        if self.rm:
            self.rm.close()
            self.rm = None
        # time.sleep(0.1)

    def check_device_status(self) -> bool:
        try:
            if self.inst:
                idn = self.inst.query('*IDN?')  # 标准SCPI命令
                return bool(idn.strip())
            return False
        except:
            return False

    def reconnect_device(self, device_name, max_retries=3):
        for attempt in range(max_retries):
            try:
                self.disconnect()  # 先确保断开
                # print(self.check_device_status())
                success = self.connect(device_name)  # 您的初始化方法
                if success:
                    print(f"第{attempt + 1}次重连成功")
                    return True
                else:
                    print(f"第{attempt + 1}次重连失败")
            except Exception as e:
                print(f"重连尝试{attempt + 1}失败: {str(e)}")
        return False

    def set_power_unit(self, unit='μW') -> bool:
        """
        设置功率测量单位
        
        设置功率计显示和返回测量结果的单位。支持三种单位：
        微瓦(μW)、分贝毫瓦(DBM)和分贝(DB)。
        
        Args:
            unit (str): 功率单位，可选值：
                       - 'μW': 微瓦（线性单位，1W = 1,000,000μW）
                       - 'DBM': 分贝毫瓦（对数单位，参考1mW）
                       - 'DB': 分贝（相对单位）
                       
        Returns:
            bool: 设置是否成功
            
        Example:
            >>> pm = PM100D()
            >>> pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> pm.set_power_unit('μW')   # 设置为微瓦
            >>> pm.set_power_unit('DBM')  # 设置为分贝毫瓦
            
        Note:
            - 单位参数不区分大小写
            - μW单位在设备上实际设置为W，软件层面进行转换
            - DBM单位便于显示小功率值
            - 设置成功后会打印确认信息
        """
        if self.inst is None:
            return False
            
        valid_units = {'μW', 'DBM', 'DB'}
        if unit.upper() not in [u.upper() for u in valid_units]:
            print(f"无效单位，可选: {valid_units}")
            return False

        # 如果选择微瓦，实际在设备上设置为瓦特
        if unit.upper() == 'μW':
            device_unit = 'W'
        else:
            device_unit = unit.upper()
            
        self.inst.write(f":POW:UNIT {device_unit}")
        # 记录用户选择的单位
        self.user_power_unit = unit
        print(f"单位已设置为: {unit}")
        return True

    def get_power_unit(self) -> str:
        """
        获取当前设置的功率测量单位
        
        返回用户选择的功率测量单位。可能的返回值包括：
        微瓦(μW)、分贝毫瓦(DBM)或分贝(DB)。
        
        Returns:
            str: 当前功率单位，可能的值：
                 - 'μW': 微瓦（线性单位，1W = 1,000,000μW）
                 - 'DBM': 分贝毫瓦（对数单位，参考1mW）
                 - 'DB': 分贝（相对单位）
                 如果设备未连接，返回空字符串
                 
        Example:
            >>> pm = PM100D()
            >>> pm.connect("USB0::4883::32888::P0047129::0::INSTR")
            >>> unit = pm.get_power_unit()
            >>> print(f"当前功率单位: {unit}")
            
        Note:
            返回用户选择的单位，如果选择μW则返回μW而非设备的W单位
        """
        if self.inst is None:
            print("未连接设备!")
            return ""
            
        try:
            # 返回用户选择的单位，而不是设备的实际单位
            return self.user_power_unit
        except Exception as e:
            print(f"获取功率单位失败: {e}")
            return ""

    def set_range(self, meas_range):
        """
        设置设备的测量上限
        :param meas_range:
        :return: success
        """
        if self.inst is None:
            print("未连接设备!")
            return False
        # 获取设备支持的测量范围大小
        min = float(self.inst.query("SENS:CURR:RANG:UPP? MIN"))
        max = float(self.inst.query("SENS:CURR:RANG:UPP? MAX"))

        if meas_range < min or meas_range > max:
            print("测量上限超出仪器范围！")
            return False
        self.inst.write(f"SENS:CURR:RANG:UPP {meas_range}")
        return True

    def get_range(self):
        """
        获取仪器当前量程
        :return: range
        """
        if self.inst is None:
            print("未连接设备!")
            return None
        return self.inst.query("SENS:CURR:RANG:UPP?")

    def get_auto_range_status(self) -> bool:
        """
        获取当前是否开启自动量程
        :return: bool
        """

        if self.inst is None:
            print("未连接设备!")
            return False
        return self.inst.query("SENS:CURR:RANG:AUTO?") == 1

    def start_auto_range(self):
        """
        开启自动量程功能
        :return: success
        """
        if self.inst is None:
            print("未连接设备!")
            return False
        self.inst.write("SENS:RANG:AUTO 1")
        return True

    def stop_auto_range(self):
        """
        关闭自动量程功能
        :return: success
        """

        if self.inst is None:
            print("未连接设备!")
            return False
        self.inst.write("SENS:RANG:AUTO 0")
        return True

    def get_comp(self):
        """
        获取仪器当前补偿值(-60db - 60db)
        :return: range
        """
        if self.inst is None:
            print("未连接设备!")
            return None
        return float(self.inst.query("SENS:CORR:LOSS:INP:MAGN?"))

    def set_comp(self, comp) -> bool:
        """
        设置功率补偿值
        :param comp:
        :return: success
        """
        # 设备支持的波长范围 [800, 1700]

        # min = float(self.inst.query("SENS:CORR:WAV? MIN"))
        # max = float(self.inst.query("SENS:CORR:WAV? MAX"))
        min = -60
        max = 60
        # print("min: ", min)
        # print("max: ", max)

        if comp < min or comp > max:
            # print("补偿值超出仪器范围！")
            return False

        self.inst.write(f"SENS:CORR:LOSS:INP:MAGN {comp}")

        return True


if __name__ == "__main__":
    pm = PM100D()
    #rm = pyvisa.ResourceManager('@py')
    #devices = rm.list_resources()
    #print("检测到的设备:", devices)
    #inst = rm.open_resource(devices[0])
    # print(usb.core.find())
    pm.connect("USB0::4883::32888::P0048741::0::INSTR")
    print(pm.read_power())
    # print(pm.start_auto_range())
    # print(pm.get_auto_range_status())
    # pm.zero_adjustment()
    # pm.set_power_unit('DBM')  # 设置为 dBm
    # print(pm.inst.query(":MEAS:POW?"))

    #print(pm.get_wavelength())
    #pm.set_wavelength(850.0)
    #print(pm.get_wavelength())

    #print(pm.get_range())
    #print(pm.set_range(5.5e-05))
    #print(pm.get_range())

    # print(pm.start_auto_range())
    #print(pm.stop_auto_range())

    # print(pm.get_comp())

    pm.reconnect_device(5)
