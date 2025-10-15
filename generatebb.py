import argparse
import subprocess
import xml.etree.ElementTree as ET
import re
from qgenie import QGenieClient, ChatMessage, StreamOptions
import os
import tempfile
import shutil
from dotenv import load_dotenv

load_dotenv()

def get_latest_tag(repo_url):
    try:
        tags_output = subprocess.check_output(['git', 'ls-remote', '--tags', repo_url], stderr=subprocess.STDOUT).decode('utf-8')
        all_tags = []
        for line in tags_output.splitlines():
            if 'refs/tags/' in line:
                tag = line.split('refs/tags/')[-1].replace('^{}', '')
                all_tags.append(tag)
        
        # 筛选符合语义化版本的标签（如v1.2.3或1.2.3）
        semantic_tags = []
        for tag in all_tags:
            if re.match(r'v?\d+\.\d+\.\d+$', tag):
                semantic_tags.append(tag)
        
        if not semantic_tags:
            try:
                # 尝试获取默认分支（main或master）的最新提交
                branch_output = subprocess.check_output(
                    ['git', 'ls-remote', '--heads', repo_url, 'main'],
                    stderr=subprocess.STDOUT
                ).decode('utf-8')
                if not branch_output.strip():
                    branch_output = subprocess.check_output(
                        ['git', 'ls-remote', '--heads', repo_url, 'master'],
                        stderr=subprocess.STDOUT
                    ).decode('utf-8')
                    if not branch_output.strip():
                        raise ValueError("仓库中没有找到main或master分支")
                
                # 提取提交哈希
                commit_hash = branch_output.split()[0]
                return commit_hash
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"获取默认分支失败: {e.output.decode('utf-8')}")
        
        # 按版本号排序（去掉v前缀后按数字排序）
        semantic_tags.sort(key=lambda t: [int(x) for x in re.sub(r'^v', '', t).split('.')], reverse=True)
        return semantic_tags[0]
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git命令失败: {e.output.decode('utf-8')}")
    except OSError as e:
        raise RuntimeError("Git未安装或不在PATH中。请安装Git并确保它在系统PATH中。") from e

def find_and_parse_packages(repo_root):
    """在仓库根目录中查找所有package.xml文件并解析"""
    packages = []
    for root_dir, _, files in os.walk(repo_root):
        if 'package.xml' in files:
            package_xml_path = os.path.join(root_dir, 'package.xml')
            try:
                with open(package_xml_path, 'r', encoding='utf-8') as f:
                    xml_data = f.read()
                
                root = ET.fromstring(xml_data)
                package_name = root.find('name').text
                dependencies = []
                for dep_type in ['depend', 'build_depend', 'exec_depend']:
                    for dep in root.findall(dep_type):
                        dependencies.append(f"ros-jazzy-{dep.text}")
                
                description = root.find('description').text if root.find('description') is not None else ""
                license_elem = root.find('license')
                license = license_elem.text if license_elem is not None else "Unknown"
                
                # 计算相对于仓库根目录的路径
                rel_path = os.path.relpath(root_dir, repo_root)
                cmake_exists = os.path.exists(os.path.join(root_dir, 'CMakeLists.txt'))
                packages.append({
                    'name': package_name,
                    'path': rel_path,
                    'dependencies': ' '.join(set(dependencies)),
                    'description': description,
                    'license': license,
                    'is_cmake': cmake_exists
                })
            except Exception as e:
                print(f"[WARNING] 解析 {package_xml_path} 失败: {str(e)}")
                continue
    return packages

def generate_ros_recipe(repo_url):
    repo_name = repo_url.split('/')[-1].replace('.git', '')
    try:
        latest_tag = get_latest_tag(repo_url)
        # 处理提交哈希作为版本参考的情况
        if re.fullmatch(r'[0-9a-f]{40}', latest_tag):
            version = f"0.0.0_git{latest_tag[:7]}"
        else:
            version = re.sub(r'^v', '', latest_tag)
        
        print(f"[INFO] Using version: {version}")
        
        # 创建临时仓库
        temp_dir = tempfile.mkdtemp()
        print(f"[INFO] Created temporary directory: {temp_dir}")
        
        try:
            # 初始化临时仓库
            subprocess.run(['git', 'init', temp_dir], check=True, capture_output=True)
            subprocess.run(['git', '-C', temp_dir, 'remote', 'add', 'origin', repo_url], check=True, capture_output=True)
            # 获取指定的tag/commit
            subprocess.run(['git', '-C', temp_dir, 'fetch', '--depth', '1', 'origin', latest_tag], check=True, capture_output=True)
            subprocess.run(['git', '-C', temp_dir, 'checkout', 'FETCH_HEAD'], check=True, capture_output=True)
            print("[INFO] Successfully fetched and checked out repository")
            
            # 查找并解析所有ROS包
            packages = find_and_parse_packages(temp_dir)
            print(f"[INFO] Found {len(packages)} ROS packages: {[pkg['name'] for pkg in packages]}")
            if not packages:
                raise ValueError("仓库中未找到任何包含package.xml的ROS包")
            
            # 为每个包生成recipe
            for pkg in packages:
                print(f"[INFO] Generating recipe for {pkg['name']}...")
                # 构建AI提示
                build_rule = "4. Inherit cmake class and use CMake for compilation" if pkg['is_cmake'] else "4. Use appropriate build system (not CMake)"
                prompt = f"""
You are a Yocto expert generating ROS 2 Jazzy recipes. Create a complete .bb recipe file for ROS 2 package '{pkg['name']}' using:
- Git URL: {repo_url}
- Latest tag: {latest_tag}
- Package path: {pkg['path']}
- Package description: {pkg['description']}
- Dependencies: {pkg['dependencies']}
- License: {pkg['license']}

This is a ROS 2 Jazzy package recipe. Follow these rules:
1. Output path: meta-ros/recipes-ros/{pkg['name']}/{pkg['name']}_{version}.bb
2. MUST inherit 'ros_distro_jazzy' class for ROS 2 Jazzy support
3. Use 'ros-jazzy-' prefix for all ROS dependencies in DEPENDS
4. Set ROS_BUILD_TYPE appropriately (ament_cmake, ament_python, or cmake)
5. SRC_URI must use git protocol with tag reference and include SUBDIR={pkg['path']}
{build_rule}
7. Include ROS-specific variables: ROS_BUILDTOOL_DEPENDS, ROS_BUILD_DEPENDS, ROS_EXEC_DEPENDS if applicable
8. Include all standard Yocto variables (SUMMARY, DESCRIPTION, HOMEPAGE, LICENSE, SRC_URI, SRCREV, DEPENDS)
9. Do not include any explanatory text - output ONLY the recipe content
"""
                
                # 生成recipe
                client = QGenieClient()
                response = client.chat(
                    messages=[
                        ChatMessage(role="system", content="You are a Yocto recipe generation expert specializing in ROS 2 packages. Output ONLY valid .bb file content for ROS 2 Jazzy recipes with no additional commentary. Always inherit ros_distro_jazzy class and follow ROS 2 package conventions."),
                        ChatMessage(role="user", content=prompt)
                    ],
                    stream=False
                )
                bb_content = response.choices[0].message.content.strip()
                
                # 保存recipe
                output_dir = f"meta-ros/recipes-ros/{pkg['name']}"
                os.makedirs(output_dir, exist_ok=True)
                output_path = f"{output_dir}/{pkg['name']}_{version}.bb"
                with open(output_path, 'w') as f:
                    f.write(bb_content)
                print(f"Generated {output_path}")
                
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except Exception as e:
        print(f"Error generating recipe: {str(e)}")
        raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Generate Yocto recipes from ROS packages using AI.')
    parser.add_argument('--ros-git', type=str, required=True, help='Git URL of ROS package repository')
    args = parser.parse_args()
    generate_ros_recipe(args.ros_git)
