# Capability Extractor Usage

Run from the repository root:

```bash
python3 main.py --urdf capability_extractor/examples/robot.urdf
```

By default this uses:

```text
capability_extractor/rules/rules.json
capability_extractor/outputs/capabilities.json
```

## Direct URDF

```bash
python3 main.py \
  --urdf /path/to/robot.urdf \
  --output /path/to/capabilities.json
```

## Direct Xacro

```bash
python3 main.py \
  --robot-description /path/to/robot.urdf.xacro \
  --xacro-arg prefix:=robot1_ \
  --output /path/to/capabilities.json
```

The extractor uses the Python `xacro` package when available, otherwise it
tries the `xacro` command on `PATH`.

## Existing ROS 2 Description Package

Source ROS 2 and your workspace first:

```bash
source /opt/ros/humble/setup.bash
source ~/ros2_ws/install/setup.bash
```

List candidate robot description files:

```bash
python3 main.py \
  --ros-package turtlebot3_description \
  --list-package-files
```

Extract capabilities from a package-relative URDF/Xacro:

```bash
python3 main.py \
  --ros-package turtlebot3_description \
  --package-file urdf/turtlebot3_waffle.urdf.xacro \
  --output outputs/turtlebot3_waffle_capabilities.json
```

If the package is not in `AMENT_PREFIX_PATH`, add a package search directory:

```bash
python3 main.py \
  --ros-package my_robot_description \
  --package-file urdf/my_robot.urdf.xacro \
  --ros-package-path ~/ros2_ws/src \
  --output outputs/my_robot_capabilities.json
```

## Debug Rule Evaluation

```bash
python3 main.py \
  --urdf capability_extractor/examples/robot.urdf \
  --log-level DEBUG \
  --debug-rules
```
