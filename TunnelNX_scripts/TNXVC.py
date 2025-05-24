import os
import json
import shutil
import datetime
import time
from pathlib import Path

class TNXVC:
    """TunnelNX版本控制器，用于管理节点图的版本历史

    简化重构后的设计：
    - 节点图与版本树紧密耦合，一对一绑定关系
    - 版本树自动基于节点图文件名创建
    - 简化文件存储：直接在TNXVC_files中存储版本快照文件
    - 版本快照文件格式：nodegraph_name_v1.json, nodegraph_name_v2.json
    - 版本树文件格式：nodegraph_name.tnxvc
    - 支持线性版本历史和分支版本历史
    """

    def __init__(self, work_folder):
        """初始化版本控制器

        Args:
            work_folder: 工作文件夹路径
        """
        self.work_folder = work_folder
        self.tnxvc_folder = os.path.join(work_folder, "TNXVC_files")
        self.current_tree = None
        self.current_nodegraph_path = None  # 当前节点图路径
        self.tree_metadata = None
        self.current_version = 0  # 当前版本号（简化为单一版本号）
        self.nodegraph_data = None   # 当前加载的节点图数据

        # 确保TNXVC文件夹存在
        if not os.path.exists(self.tnxvc_folder):
            os.makedirs(self.tnxvc_folder, exist_ok=True)

    def get_tree_list(self):
        """获取所有版本树列表"""
        trees = []
        if os.path.exists(self.tnxvc_folder):
            for filename in os.listdir(self.tnxvc_folder):
                if filename.endswith(".tnxvc"):
                    trees.append(filename[:-6])  # 去掉.tnxvc后缀
        return trees

    def _get_nodegraph_name_from_path(self, nodegraph_path):
        """从节点图路径获取节点图名称（不含扩展名）"""
        return os.path.splitext(os.path.basename(nodegraph_path))[0]

    def auto_create_or_load_tree(self, nodegraph_path):
        """自动为节点图创建或加载对应的版本树

        Args:
            nodegraph_path: 节点图文件路径

        Returns:
            bool: 成功返回True，失败返回False
        """
        if not os.path.exists(nodegraph_path):
            print(f"节点图文件不存在: {nodegraph_path}")
            return False

        # 基于节点图文件名生成版本树名称
        nodegraph_name = self._get_nodegraph_name_from_path(nodegraph_path)
        tree_file = os.path.join(self.tnxvc_folder, f"{nodegraph_name}.tnxvc")

        if os.path.exists(tree_file):
            # 版本树已存在，加载它
            print(f"加载现有版本树: {nodegraph_name}")
            return self.load_tree(nodegraph_name)
        else:
            # 版本树不存在，创建新的
            print(f"为节点图创建新版本树: {nodegraph_name}")
            return self.create_tree(nodegraph_name, nodegraph_path)

    def get_tree_for_nodegraph(self, nodegraph_path):
        """根据节点图路径获取对应的版本树名称（简化版本）

        Args:
            nodegraph_path: 节点图文件路径

        Returns:
            str: 找到的版本树名称，如果没有找到则返回None
        """
        if not os.path.exists(nodegraph_path):
            return None

        # 基于节点图文件名直接生成版本树名称
        nodegraph_name = self._get_nodegraph_name_from_path(nodegraph_path)
        tree_file = os.path.join(self.tnxvc_folder, f"{nodegraph_name}.tnxvc")

        # 检查版本树文件是否存在
        if os.path.exists(tree_file):
            return nodegraph_name
        else:
            return None

    def create_tree(self, tree_name, nodegraph_path):
        """创建新的版本树（简化版本）

        Args:
            tree_name: 版本树名称（应该与节点图名称相同）
            nodegraph_path: 节点图路径

        Returns:
            bool: 成功返回True，失败返回False
        """
        # 验证树名
        if not tree_name or not isinstance(tree_name, str):
            print("无效的树名称")
            return False

        # 验证节点图路径
        if not os.path.exists(nodegraph_path):
            print(f"节点图文件不存在: {nodegraph_path}")
            return False

        tree_file = os.path.join(self.tnxvc_folder, f"{tree_name}.tnxvc")

        # 检查是否已存在
        if os.path.exists(tree_file):
            print(f"树 '{tree_name}' 已存在")
            return False

        try:
            # 创建简化的元数据文件
            tree_data = {
                "name": tree_name,
                "nodegraph_path": nodegraph_path,
                "created_at": datetime.datetime.now().isoformat(),
                "current_version": 1,  # 简化为单一版本号
                "versions": [
                    {
                        "version": 1,
                        "name": "初始版本",
                        "timestamp": time.time(),
                        "description": "初始版本",
                        "snapshot_file": f"{tree_name}_v1.json"
                    }
                ]
            }

            with open(tree_file, "w", encoding="utf-8") as f:
                json.dump(tree_data, f, ensure_ascii=False, indent=2)

            # 创建初始版本快照文件
            initial_snapshot_file = os.path.join(self.tnxvc_folder, f"{tree_name}_v1.json")
            shutil.copy2(nodegraph_path, initial_snapshot_file)

            # 设置当前树
            self.current_tree = tree_name
            self.current_nodegraph_path = nodegraph_path
            self.tree_metadata = tree_data
            self.current_version = 1

            print(f"成功创建版本树 '{tree_name}'，初始版本: v1")
            return True

        except Exception as e:
            print(f"创建版本树失败: {e}")
            # 清理可能已创建的文件
            if os.path.exists(tree_file):
                os.remove(tree_file)
            initial_snapshot_file = os.path.join(self.tnxvc_folder, f"{tree_name}_v1.json")
            if os.path.exists(initial_snapshot_file):
                os.remove(initial_snapshot_file)
            return False

    def load_tree(self, tree_name):
        """加载指定的版本树（简化版本）

        Args:
            tree_name: 要加载的版本树名称

        Returns:
            bool: 成功返回True，失败返回False
        """
        tree_file = os.path.join(self.tnxvc_folder, f"{tree_name}.tnxvc")

        if not os.path.exists(tree_file):
            print(f"版本树 '{tree_name}' 不存在")
            return False

        try:
            with open(tree_file, "r", encoding="utf-8") as f:
                tree_data = json.load(f)

            self.current_tree = tree_name
            self.current_nodegraph_path = tree_data.get("nodegraph_path")
            self.tree_metadata = tree_data
            self.current_version = tree_data.get("current_version", 1)

            # 加载当前版本的节点图数据
            self._load_current_version()

            print(f"已加载版本树 '{tree_name}'，当前版本: v{self.current_version}")
            return True

        except Exception as e:
            print(f"加载版本树失败: {e}")
            return False

    def load_tree_for_nodegraph(self, nodegraph_path):
        """为指定节点图加载对应的版本树（简化版本）

        Args:
            nodegraph_path: 节点图文件路径

        Returns:
            bool: 成功加载返回True，失败返回False
        """
        tree_name = self.get_tree_for_nodegraph(nodegraph_path)
        if tree_name:
            return self.load_tree(tree_name)
        else:
            print(f"未找到节点图 '{nodegraph_path}' 对应的版本树")
            # 清除当前树信息
            self.current_tree = None
            self.current_nodegraph_path = None
            self.tree_metadata = None
            self.current_version = 0
            self.nodegraph_data = None
            return False

    def save_tree_metadata(self):
        """保存当前树的元数据（简化版本）"""
        if not self.current_tree or not self.tree_metadata:
            print("没有活动的版本树")
            return False

        tree_file = os.path.join(self.tnxvc_folder, f"{self.current_tree}.tnxvc")

        try:
            # 更新当前版本
            self.tree_metadata["current_version"] = self.current_version

            with open(tree_file, "w", encoding="utf-8") as f:
                json.dump(self.tree_metadata, f, ensure_ascii=False, indent=2)

            return True

        except Exception as e:
            print(f"保存树元数据失败: {e}")
            return False

    def forward(self, nodegraph_data=None):
        """前进一步，如果没有下一步，创建新版本（简化版本）

        Args:
            nodegraph_data: 当前节点图数据，用于创建新版本时保存

        Returns:
            dict: 返回结果，包含 success (bool) 和 nodegraph_data (如果需要加载)
        """
        if not self.current_tree or not self.tree_metadata:
            print("没有活动的版本树")
            return {"success": False}

        # 检查是否有下一个版本
        next_version = self.current_version + 1
        next_version_exists = False

        for version_info in self.tree_metadata["versions"]:
            if version_info["version"] == next_version:
                next_version_exists = True
                break

        if next_version_exists:
            # 有下一个版本，直接前进
            self.current_version = next_version

            # 加载下一个版本的数据
            loaded_data = self._load_version_data(next_version)
            self.nodegraph_data = loaded_data

            print(f"前进到版本: v{next_version}")
            self.save_tree_metadata()
            return {
                "success": True,
                "nodegraph_data": loaded_data,
                "needs_reload": True
            }
        else:
            # 没有下一个版本，创建新版本
            if nodegraph_data is None:
                print("无法创建新版本：未提供节点图数据")
                return {"success": False}

            result = self._create_new_version(nodegraph_data)
            return {
                "success": result,
                "needs_reload": False  # 不需要重新加载，因为是保存当前状态
            }

    def backward(self):
        """后退一步（简化版本）

        Returns:
            dict: 返回结果，包含 success (bool) 和 nodegraph_data (如果需要加载)
        """
        if not self.current_tree or not self.tree_metadata:
            print("没有活动的版本树")
            return {"success": False}

        # 判断是否可以后退
        if self.current_version > 1:
            # 可以后退
            self.current_version -= 1

            # 加载前一个版本的数据
            loaded_data = self._load_version_data(self.current_version)
            self.nodegraph_data = loaded_data

            print(f"后退到版本: v{self.current_version}")
            self.save_tree_metadata()
            return {
                "success": True,
                "nodegraph_data": loaded_data,
                "needs_reload": True
            }
        else:
            print("已经是第一个版本，无法后退")
            return {"success": False}

    def branch(self, nodegraph_data=None):
        """在当前位置创建分支（简化版本 - 暂时禁用复杂分支功能）

        Args:
            nodegraph_data: 当前节点图数据，用于创建新分支时保存

        Returns:
            dict: 返回结果，包含 success (bool) 和其他信息
        """
        # 简化版本暂时不支持复杂分支功能，直接创建新版本
        print("简化版本控制暂时不支持分支功能，将创建新版本")
        if nodegraph_data is None:
            print("无法创建新版本：未提供节点图数据")
            return {"success": False}

        result = self._create_new_version(nodegraph_data)
        return {"success": result}

    def get_current_version_info(self):
        """获取当前版本信息（简化版本）

        Returns:
            dict: 当前版本信息，未加载版本树则返回None
        """
        if not self.current_tree or not self.tree_metadata:
            return None

        for version_info in self.tree_metadata["versions"]:
            if version_info["version"] == self.current_version:
                return version_info
        return None

    def get_tree_structure(self):
        """获取树结构用于界面绘制（简化版本）

        Returns:
            dict: 树结构数据，未加载版本树则返回None
        """
        if not self.current_tree or not self.tree_metadata:
            return None

        return {
            "name": self.current_tree,
            "nodegraph_path": self.current_nodegraph_path,
            "versions": self.tree_metadata["versions"],
            "current_version": self.current_version
        }

    def get_current_nodegraph_data(self):
        """获取当前节点图数据

        Returns:
            dict: 当前节点图数据，未加载则返回None
        """
        return self.nodegraph_data



    def _load_version_data(self, version_number):
        """加载指定版本的节点图数据（简化版本）

        Args:
            version_number: 版本号

        Returns:
            dict: 节点图数据，加载失败则返回None
        """
        snapshot_file = f"{self.current_tree}_v{version_number}.json"
        version_path = os.path.join(self.tnxvc_folder, snapshot_file)

        if not os.path.exists(version_path):
            print(f"版本快照文件不存在: {version_path}")
            return None

        try:
            with open(version_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"加载版本数据失败: {e}")
            return None

    def _load_current_version(self):
        """加载当前版本的节点图数据（简化版本）"""
        if not self.current_tree or not self.tree_metadata:
            return False

        self.nodegraph_data = self._load_version_data(self.current_version)
        return True

    def _create_new_version(self, nodegraph_data):
        """创建新版本（简化版本）

        Args:
            nodegraph_data: 节点图数据

        Returns:
            bool: 成功返回True，失败返回False
        """
        try:
            # 创建新版本号
            new_version = self.current_version + 1
            new_snapshot_file = f"{self.current_tree}_v{new_version}.json"

            # 准备新版本数据
            new_version_info = {
                "version": new_version,
                "name": f"版本 {new_version}",
                "timestamp": time.time(),
                "description": "自动创建的版本",
                "snapshot_file": new_snapshot_file
            }

            # 保存节点图数据到快照文件
            snapshot_path = os.path.join(self.tnxvc_folder, new_snapshot_file)

            with open(snapshot_path, "w", encoding="utf-8") as f:
                json.dump(nodegraph_data, f, ensure_ascii=False, indent=2)

            # 更新版本树元数据
            self.tree_metadata["versions"].append(new_version_info)
            self.current_version = new_version
            self.nodegraph_data = nodegraph_data

            print(f"创建新版本: v{new_version}")
            self.save_tree_metadata()
            return True

        except Exception as e:
            print(f"创建新版本失败: {e}")
            return False