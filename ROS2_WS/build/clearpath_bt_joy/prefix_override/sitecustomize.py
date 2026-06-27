import sys
if sys.prefix == '/usr':
    sys.real_prefix = sys.prefix
    sys.prefix = sys.exec_prefix = '/home/sjk/DISSERTATION/ROS2_WS/install/clearpath_bt_joy'
