# ROS 2 Yocto Recipe Generator

一个基于AI的自动化工具，用于从ROS 2包仓库生成Yocto BitBake recipe文件。

## 功能特性

- 🤖 **AI驱动生成**：使用QGenie AI自动生成符合标准的Yocto recipe文件
- 📦 **多包支持**：自动识别并处理仓库中的所有ROS 2包（支持monorepo结构）
- 🔍 **智能依赖解析**：自动从package.xml解析并转换ROS依赖为Yocto格式
- 🏷️ **版本管理**：自动获取Git仓库的最新tag或commit作为版本
- 🎯 **ROS 2 Jazzy支持**：专门针对ROS 2 Jazzy发行版优化
- 📝 **标准化输出**：生成的recipe遵循meta-ros项目规范

## 前置要求

### 系统依赖
- Python 3.7+
- Git（必须在系统PATH中）

### Python依赖
```bash
pip install qgenie python-dotenv
```

### 环境配置
创建`.env`文件并配置QGenie API密钥：
```env
QGENIE_API_KEY=your_api_key_here
QGENIE_BASE_URL=your_api_base_url_here
```

## 安装

1. 克隆或下载本项目
2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```
3. 配置`.env`文件

## 使用方法

### 基本用法

```bash
python generatebb.py --ros-git <ROS_PACKAGE_GIT_URL>
```

### 参数说明

- `--ros-git`：（必需）ROS包的Git仓库URL

### 示例

```bash
# 为单个ROS包生成recipe
python generatebb.py --ros-git https://github.com/ros2/example_interfaces.git

# 为包含多个包的仓库生成recipes
python generatebb.py --ros-git https://github.com/ros-perception/vision_opencv.git
```

## 工作原理

### 1. 版本获取
- 首先尝试获取仓库的语义化版本标签（如v1.2.3）
- 如果没有标签，则使用main/master分支的最新commit
- 版本格式：
  - 标签版本：`1.2.3`
  - Commit版本：`0.0.0_git<短hash>`

### 2. 包发现与解析
- 克隆仓库到临时目录
- 递归搜索所有`package.xml`文件
- 解析每个包的元数据：
  - 包名
  - 描述
  - 许可证
  - 依赖关系
  - 构建系统类型（CMake/ament）

### 3. Recipe生成
对每个发现的ROS包：
- 构建包含完整上下文的AI提示
- 调用QGenie API生成recipe内容
- 保存到标准目录结构：`meta-ros/recipes-ros/<package_name>/`

### 4. 输出结构
```
meta-ros/
└── recipes-ros/
    └── <package_name>/
        └── <package_name>_<version>.bb
```

## 生成的Recipe特性

生成的recipe文件包含：

- ✅ 标准Yocto变量（SUMMARY, DESCRIPTION, LICENSE等）
- ✅ Git源码URI配置（包含SUBDIR支持）
- ✅ ROS 2 Jazzy特定配置
- ✅ 继承`ros_distro_jazzy`类
- ✅ 正确的依赖前缀（`ros-jazzy-*`）
- ✅ ROS构建类型设置（ROS_BUILD_TYPE）
- ✅ ROS特定依赖变量（ROS_BUILDTOOL_DEPENDS等）

## 示例输出

```bitbake
SUMMARY = "Example ROS 2 package"
DESCRIPTION = "A sample ROS 2 package for demonstration"
HOMEPAGE = "https://github.com/example/ros2_package"
LICENSE = "Apache-2.0"

SRC_URI = "git://github.com/example/ros2_package.git;protocol=https;branch=main;subdir=${BPN}"
SRCREV = "abc123def456..."

DEPENDS = "ros-jazzy-rclcpp ros-jazzy-std-msgs"

ROS_BUILD_TYPE = "ament_cmake"

inherit ros_distro_jazzy
inherit cmake
```

## 注意事项

### 依赖处理
- 所有ROS依赖自动添加`ros-jazzy-`前缀
- 依赖从package.xml的`<depend>`, `<build_depend>`, `<exec_depend>`标签提取
- 重复依赖会自动去重

### Git访问
- 确保有权限访问目标Git仓库
- 私有仓库可能需要配置SSH密钥或访问令牌
- 工具使用浅克隆（depth=1）以提高性能

### 临时文件
- 工具会创建临时目录克隆仓库
- 执行完成后自动清理临时文件
- 如果中断，可能需要手动清理`/tmp`目录

### AI生成质量
- 生成的recipe基于AI模型，建议人工审查
- 复杂的构建配置可能需要手动调整
- 特殊依赖关系可能需要额外配置

## 故障排除

### Git命令失败
```
错误：Git命令失败
解决：确保Git已安装并在PATH中，检查仓库URL是否正确
```

### 未找到package.xml
```
错误：仓库中未找到任何包含package.xml的ROS包
解决：确认仓库确实包含ROS 2包，检查是否在正确的分支
```

### API调用失败
```
错误：QGenie API调用失败
解决：检查.env文件配置，确认API密钥有效，检查网络连接
```

## 高级用法

### 自定义ROS发行版
如需支持其他ROS发行版（如Humble），修改代码中的：
- 依赖前缀：`ros-jazzy-` → `ros-humble-`
- 继承类：`ros_distro_jazzy` → `ros_distro_humble`
- 提示词中的发行版名称

### 批量处理
可以编写脚本批量处理多个仓库：
```bash
#!/bin/bash
repos=(
    "https://github.com/ros2/repo1.git"
    "https://github.com/ros2/repo2.git"
    "https://github.com/ros2/repo3.git"
)

for repo in "${repos[@]}"; do
    python generatebb.py --ros-git "$repo"
done
```

## 贡献

欢迎提交Issue和Pull Request来改进这个工具！

## 许可证

本项目采用 BSD-3-Clause 许可证。详见 [LICENSE](../LICENSE) 文件。

## 相关资源

- [ROS 2 Documentation](https://docs.ros.org/)
- [Yocto Project](https://www.yoctoproject.org/)
- [meta-ros](https://github.com/ros/meta-ros)
- [QGenie Documentation](https://qgenie.ai/docs)
