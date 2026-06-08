#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具函数模块

该模块提供了项目中使用的各种工具函数，包括：
- 数据类型转换函数（16进制转整数、浮点数等）
- 配置文件读写操作
- 关于窗口显示
- USB设备重置功能

作者: ivan
创建时间: 2025
版本: v1.0.1
"""

import configparser
import os
import socket
import struct

import pandas as pd
import usb
from PyQt5 import QtWidgets


def ToI32(hex_str: str) -> int:
    """
    将16进制字符串转换为32位有符号整数
    
    该函数将输入的16进制字符串按小端字节序转换为32位有符号整数。
    如果最高位为1，则将其视为负数并进行补码转换。
    
    Args:
        hex_str (str): 16进制字符串，如 "1A2B3C4D"
        
    Returns:
        int: 转换后的32位有符号整数
        
    Example:
        >>> ToI32("1A2B3C4D")
        1291394586
        >>> ToI32("FFFFFFFF")
        -1
    """
    hex_str = hex_str.upper()
    # 按字节反序（小端字节序）
    temp = ""
    for i in range(len(hex_str), 0, -2):
        temp += hex_str[i-2:i]
    hex_str = temp
    # 转换为有符号32位整数
    unsigned_num = int(hex_str, 16)
    if unsigned_num & 0x80000000:  # 检查符号位
        signed_num = unsigned_num - 0x100000000  # 补码转换
    else:
        signed_num = unsigned_num
    return signed_num


def ToI16(hex_str: str) -> int:
    """
    将4字节16进制字符串转换为16位有符号整数
    
    该函数将输入的16进制字符串按小端字节序转换为16位有符号整数。
    如果最高位为1，则将其视为负数并进行补码转换。
    
    Args:
        hex_str (str): 4字节16进制字符串，如 "1A2B"
        
    Returns:
        int: 转换后的16位有符号整数
        
    Example:
        >>> ToI16("1A2B")
        11290
        >>> ToI16("FFFF")
        -1
    """
    hex_str = hex_str.upper()
    # 按字节反序（小端字节序）
    temp = ""
    for i in range(len(hex_str), 0, -2):
        temp += hex_str[i-2:i]
    hex_str = temp
    # 转换为有符号16位整数
    unsigned_num = int(hex_str, 16)
    if unsigned_num & 0x8000:  # 检查符号位
        signed_num = unsigned_num - 0x10000  # 补码转换
    else:
        signed_num = unsigned_num
    return signed_num


def ToFloat(hex_str: str) -> float:
    """
    将4字节16进制字符串转换为IEEE 754单精度浮点数
    
    该函数将输入的8位16进制字符串转换为32位IEEE 754标准的
    单精度浮点数，使用小端字节序。
    
    Args:
        hex_str (str): 8位16进制字符串，如 "41200000"
        
    Returns:
        float: 转换后的浮点数
        
    Example:
        >>> ToFloat("41200000")
        10.0
        >>> ToFloat("00000000")
        0.0
    """
    hex_str = hex_str.upper()
    bytes_data = bytes.fromhex(hex_str)
    float_data = struct.unpack('<f', bytes_data)[0]  # 小端字节序解包
    return float_data


def ToHex(num: int, size: int) -> str:
    """
    将整数转换为指定长度的16进制字符串
    
    该函数将输入的整数转换为指定字节长度的16进制字符串，
    使用小端字节序和补码表示法处理负数。
    
    Args:
        num (int): 要转换的整数
        size (int): 字节长度
        
    Returns:
        str: 转换后的16进制字符串（大写）
        
    Example:
        >>> ToHex(255, 2)
        'FF00'
        >>> ToHex(-1, 4)
        'FFFFFFFF'
    """
    hex_str = num.to_bytes(size, byteorder='little', signed=True).hex().upper()
    return hex_str


def showAbout(self):
    """
    显示关于窗口
    
    创建并显示一个包含更新内容的关于对话框。从"更新内容.csv"文件
    读取版本更新信息，并以HTML表格形式在对话框中显示。
    
    Args:
        self: 父窗口对象，用于设置对话框的父级
        
    Note:
        需要确保项目根目录下存在"更新内容.csv"文件
    """
    # 读取 CSV 文件
    df = pd.read_csv("更新内容.csv", header=None, names=None, encoding="utf-8")
    # 将 DataFrame 转换为 HTML 表格字符串
    html_table = df.to_html(index=False, border=1)
    # 创建关于窗口
    aboutWin = QtWidgets.QDialog(self)
    aboutWin.setWindowTitle("关于")
    aboutWin.resize(400, 300)
    aboutWin.setStyleSheet("background-color: #FFFFFF;color: #000000;font: 12pt \"微软雅黑\";")
    # 创建 QTextEdit 控件
    aboutText = QtWidgets.QTextEdit(aboutWin)
    aboutText.setReadOnly(True)
    aboutText.setHtml(html_table)  # 设置 HTML 内容
    # 使用布局管理器
    layout = QtWidgets.QVBoxLayout(aboutWin)
    layout.addWidget(aboutText)  # 将 QTextEdit 添加到布局中
    # 设置布局的边距（可选）
    layout.setContentsMargins(10, 10, 10, 10)
    # 显示窗口
    aboutWin.show()


# 配置文件路径
config_path = "./config.ini"

# 默认配置项（首次运行或缺少字段时自动补全）
DEFAULT_CONFIG = {
    "RemoteServer": {
        "host": "",
        "port": "10012",
    },
    "Device": {
        "last_resource": "",
    },
}


def get_local_ip():
    """获取本机 IP 地址，供远程客户端连接使用。"""
    try:
        return socket.gethostbyname(socket.gethostname())
    except Exception:
        return "127.0.0.1"


def _write_config(config):
    with open(config_path, "w", encoding="utf-8") as configfile:
        config.write(configfile)


def ensure_config():
    """
    确保配置文件存在；若不存在则按默认值创建。

    Returns:
        configparser.ConfigParser: 配置对象
    """
    config = configparser.ConfigParser()
    if not os.path.exists(config_path):
        for section, options in DEFAULT_CONFIG.items():
            config.add_section(section)
            for key, value in options.items():
                config.set(section, key, value)
        if not config.get("RemoteServer", "host"):
            config.set("RemoteServer", "host", get_local_ip())
        _write_config(config)
        return config

    config.read(config_path, encoding="utf-8")
    changed = False
    for section, options in DEFAULT_CONFIG.items():
        if not config.has_section(section):
            config.add_section(section)
            changed = True
        for key, value in options.items():
            if not config.has_option(section, key):
                config.set(section, key, value)
                changed = True
    if changed:
        _write_config(config)
    return config


def read_config():
    """
    读取配置文件，若文件不存在则自动创建默认配置。

    Returns:
        configparser.ConfigParser: 包含配置数据的对象
    """
    try:
        return ensure_config()
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
        config = configparser.ConfigParser()
        for section, options in DEFAULT_CONFIG.items():
            config.add_section(section)
            for key, value in options.items():
                config.set(section, key, value)
        return config


def get_config_value(section, key, default=None):
    """
    读取单个配置项。

    Args:
        section (str): 配置节名
        key (str): 配置键名
        default: 默认值；省略时使用 DEFAULT_CONFIG 中的定义

    Returns:
        str: 配置值
    """
    if default is None and section in DEFAULT_CONFIG and key in DEFAULT_CONFIG[section]:
        default = DEFAULT_CONFIG[section][key]
    config = read_config()
    try:
        return config.get(section, key)
    except (configparser.NoSectionError, configparser.NoOptionError):
        return default if default is not None else ""


def edit_config(section, key, value):
    """
    编辑配置文件中的指定项。

    Args:
        section (str): 配置节名
        key (str): 配置键名
        value (str): 要设置的值

    Returns:
        bool: 操作是否成功
    """
    try:
        config = read_config()
        if not config.has_section(section):
            config.add_section(section)
        config.set(section, key, str(value))
        _write_config(config)
        return True
    except Exception as e:
        print(f"编辑配置文件时出错: {e}")
        return False


def force_reset_usb(vendor_id=0x1313, product_id=0x8078):
    """
    强制重置USB设备
    
    通过设备的厂商ID和产品ID查找并重置指定的USB设备。
    主要用于解决USB设备连接异常的问题。
    
    Args:
        vendor_id (int): USB设备厂商ID，默认为0x1313（Thorlabs）
        product_id (int): USB设备产品ID，默认为0x8078
        
    Note:
        - 默认参数适用于Thorlabs公司的USB设备
        - 需要安装pyusb库和相应的USB驱动
        - 重置可能会导致设备短暂断开连接
        
    Example:
        >>> force_reset_usb()  # 使用默认参数重置Thorlabs设备
        >>> force_reset_usb(0x1234, 0x5678)  # 重置特定设备
    """
    dev = usb.core.find(idVendor=vendor_id, idProduct=product_id)
    if dev:
        dev.reset()
        print("USB设备已强制重置")
    else:
        print("未找到USB设备")