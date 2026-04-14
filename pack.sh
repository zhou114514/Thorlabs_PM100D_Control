# nuitka编译并打包，速度较慢但程序效率更高，极难反编译,可以用多核编译加快速度
nuitka --jobs=8 --windows-disable-console --include-package=pyvisa --include-package=pyvisa_py --standalone --enable-plugin=pyqt5 PM100D功率计.py
# pyinstaller打包，更快但是有python库依赖问题
pyinstaller --collect-all pyvisa_py --hidden-import=pyvisa_py --windowed PM100D功率计.py
# 根据UI文件生成 python文件
pyuic5 PM100D_Control.ui -o PM100D_Control.py

