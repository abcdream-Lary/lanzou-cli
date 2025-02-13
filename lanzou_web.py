import os
import re
import sys
import time
import json
import requests

from tqdm import tqdm
from typing import List, Dict, Optional
from config import LANZOU_CONFIG

# 终端颜色
GREEN = "\033[92m"      # 成功
RED = "\033[91m"        # 错误
BLUE = "\033[94m"       # 信息
YELLOW = "\033[93m"     # 警告
CYAN = "\033[96m"       # 提示
RESET = "\033[0m"       # 重置颜色
BOLD = "\033[1m"        # 粗体

class FileInfo:
    def __init__(self, data: Dict):
        self.name = data.get('name', '')  # 文件名
        self.name_all = data.get('name_all', '')  # 完整文件名
        self.size = data.get('size', '0')  # 文件大小
        self.time = data.get('time', '')  # 上传时间
        self.id = data.get('id', '')  # 文件ID
        self.folder_id = data.get('folder_id', '0')  # 所在文件夹ID
        self.is_dir = False
        
    def __str__(self):
        return f"{self.name_all or self.name} ({self.size})"

class FolderInfo:
    def __init__(self, data: Dict):
        self.name = data.get('name', '')  # 文件夹名
        # 优先使用fol_id,如果没有则使用folder_id
        self.folder_id = data.get('fol_id', '') or data.get('folder_id', '')  # 文件夹ID
        self.size = data.get('size', '0')  # 文件夹大小
        self.time = data.get('time', '')  # 创建时间
        self.description = data.get('folder_des', '')  # 文件夹描述
        self.is_dir = True
        
    def __str__(self):
        return f"[目录] {self.name} (ID: {self.folder_id})"

class LanZouWeb:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.39 (KHTML, like Gecko) Chrome/89.0.4389.111 Safari/537.39'
        })
        self.base_url = 'https://pc.woozooo.com'
        self.login_url = 'https://pc.woozooo.com/account.php'
        self.mydisk_url = 'https://pc.woozooo.com/mydisk.php'
        self.upload_url = 'https://pc.woozooo.com/fileup.php'
        self.doupload_url = 'https://pc.woozooo.com/doupload.php'
        self.cookie_file = 'cookie.json'
        self.is_login = False
        self.user_info = {}
        self.root_folder_id = "-1"  # 根目录ID
        
        # 目录导航
        self.current_folder_id = self.root_folder_id  # 当前目录ID
        self.current_folder_name = "根目录"  # 当前目录名称
        self.folder_stack = []  # 目录栈，用于返回上级目录
        
    def get_current_path(self) -> str:
        """获取当前完整路径"""
        if not self.folder_stack:
            return "/根目录"
        
        path = ""
        # 添加目录栈中的路径
        for folder_id, name in self.folder_stack:
            path += f"/{name}"
        # 添加当前目录
        path += f"/{self.current_folder_name}"
        return path
        
    def cd(self, folder_name: str) -> bool:
        """进入指定目录
        Args:
            folder_name: 目录名称，可以是 ".." 返回上级目录
        Returns:
            bool: 是否成功
        """
        if not self.is_login:
            print("✗ 请先登录")
            return False
            
        try:
            # 返回上级目录
            if folder_name == "..":
                if not self.folder_stack:
                    print("✗ 已经在根目录")
                    return False
                self.current_folder_id, self.current_folder_name = self.folder_stack.pop()
                print(f"✓ 返回上级目录: {self.get_current_path()}")
                return True
                
            # 获取当前目录下的所有文件夹
            folders = self.get_folders(self.current_folder_id)
            
            # 查找目标文件夹
            target_folder = None
            for folder in folders:
                if folder.name == folder_name:
                    target_folder = folder
                    break
                    
            if not target_folder:
                print(f"✗ 目录不存在: {folder_name}")
                return False
                
            # 保存当前目录到栈中
            self.folder_stack.append((self.current_folder_id, self.current_folder_name))
            
            # 更新当前目录
            self.current_folder_id = target_folder.folder_id
            self.current_folder_name = target_folder.name
            
            print(f"✓ 进入目录: {self.get_current_path()}")
            print(f"✓ 目录ID: {self.current_folder_id}")
            return True
            
        except Exception as e:
            print(f"✗ 进入目录失败: {str(e)}")
            return False
            
    def pwd(self):
        """显示当前目录路径"""
        print(f"\n当前位置: {self.get_current_path()}")
        print(f"目录ID: {self.current_folder_id}")
        
    def _post(self, url: str, data: Dict = None, files: Dict = None, **kwargs) -> Dict:
        """发送POST请求并处理响应"""
        try:
            response = self.session.post(url, data=data, files=files, **kwargs)
            if response.status_code != 200:
                raise Exception(f"请求失败: HTTP {response.status_code}")
                
            result = response.json()
            # 如果是获取文件夹列表的请求,特殊处理
            if data and data.get("task") == "47":
                return result
                
            if result.get('zt') != 1:
                raise Exception(result.get('info', '未知错误'))
                
            return result
        except Exception as e:
            raise Exception(f"请求出错: {str(e)}")
            
    def get_folders(self, parent_id: str = None) -> List[FolderInfo]:
        """获取文件夹列表
        Args:
            parent_id: 父文件夹ID，默认根目录
        Returns:
            List[FolderInfo]: 文件夹列表
        """
        if parent_id is None:
            parent_id = self.root_folder_id
            
        if not self.is_login:
            raise Exception("请先登录")
            
        try:
            result = self._post(
                self.doupload_url,
                data={
                    "task": "47",
                    "folder_id": parent_id
                }
            )
            
            folders = []
            text = result.get('text', [])
            # 如果text是列表,说明有子文件夹
            if isinstance(text, list):
                for item in text:
                    # 修正文件夹ID字段
                    if 'folderid' in item:
                        item['folder_id'] = item['folderid']
                    folders.append(FolderInfo(item))
            # 如果text不是列表但有folderid字段,说明是空文件夹
            elif isinstance(text, dict) and 'folderid' in text:
                return []
                
            return folders
            
        except Exception as e:
            print(f"✗ 获取文件夹列表失败: {str(e)}")
            return []
            
    def get_files(self, folder_id: str = None) -> List[FileInfo]:
        """获取文件列表
        Args:
            folder_id: 文件夹ID，默认根目录
        Returns:
            List[FileInfo]: 文件列表
        """
        if folder_id is None:
            folder_id = self.root_folder_id
            
        if not self.is_login:
            raise Exception("请先登录")
            
        try:
            files = []
            page = 1
            while True:
                result = self._post(
                    self.doupload_url,
                    data={
                        "task": "5",
                        "folder_id": folder_id,
                        "pg": str(page)
                    }
                )
                
                text = result.get('text', [])
                # 如果text不是列表或者是空字符串,说明没有文件
                if not isinstance(text, list) or text == "" or not text:
                    break
                    
                for item in text:
                    files.append(FileInfo(item))
                    
                page += 1
                
            return files
            
        except Exception as e:
            print(f"✗ 获取文件列表失败: {str(e)}")
            return []
            
    def create_folder(self, folder_name: str, parent_id: str = None, description: str = "") -> Optional[FolderInfo]:
        """创建文件夹
        Args:
            folder_name: 文件夹名称
            parent_id: 父文件夹ID，默认根目录
            description: 文件夹描述
        Returns:
            Optional[FolderInfo]: 创建成功返回文件夹信息，失败返回None
        """
        if parent_id is None:
            parent_id = self.root_folder_id
            
        if not self.is_login:
            raise Exception("请先登录")
            
        try:
            print(f"\n[创建文件夹]")
            print(f"文件夹名称: {folder_name}")
            print(f"父目录ID: {parent_id}")
            
            result = self._post(
                self.doupload_url,
                data={
                    "task": "2",
                    "parent_id": parent_id,
                    "folder_name": folder_name,
                    "folder_description": description
                }
            )
            
            folder_id = result.get('text')
            if folder_id:
                folder = FolderInfo({
                    'name': folder_name,
                    'folder_id': folder_id,
                    'folder_des': description
                })
                print(f"✓ 创建成功，文件夹ID: {folder_id}")
                return folder
                
            print("✗ 创建失败，无法获取文件夹ID")
            return None
            
        except Exception as e:
            print(f"✗ 创建文件夹失败: {str(e)}")
            return None
            
    def delete_file(self, file_id: str) -> bool:
        """删除文件
        Args:
            file_id: 文件ID
        Returns:
            bool: 是否删除成功
        """
        if not self.is_login:
            raise Exception("请先登录")
            
        try:
            print(f"\n[删除文件]")
            print(f"文件ID: {file_id}")
            
            self._post(
                self.doupload_url,
                data={
                    "task": "6",
                    "file_id": file_id
                }
            )
            
            print(f"✓ 删除成功")
            return True
            
        except Exception as e:
            print(f"✗ 删除文件失败: {str(e)}")
            return False
            
    def delete_folder(self, folder_id: str) -> bool:
        """删除文件夹
        Args:
            folder_id: 文件夹ID
        Returns:
            bool: 是否删除成功
        """
        if not self.is_login:
            raise Exception("请先登录")
            
        try:
            print(f"\n[删除文件夹]")
            print(f"文件夹ID: {folder_id}")
            
            self._post(
                self.doupload_url,
                data={
                    "task": "3",
                    "folder_id": folder_id
                }
            )
            
            print(f"✓ 删除成功")
            return True
            
        except Exception as e:
            print(f"✗ 删除文件夹失败: {str(e)}")
            return False
            
    def list_dir(self, folder_id: str = None):
        """列出目录内容
        Args:
            folder_id: 文件夹ID，默认当前目录
        """
        if folder_id is None:
            folder_id = self.current_folder_id
            
        try:
            print(f"\n{BLUE}=== 目录内容: {self.get_current_path()} ==={RESET}")
            
            # 获取文件夹
            folders = self.get_folders(folder_id)
            if folders:
                print("\n[文件夹]")
                for folder in folders:
                    print(f"├─ {folder}")
                    
            # 获取文件
            files = self.get_files(folder_id)
            # 过滤掉系统文件
            files = [f for f in files if f.name != "请忽使用第三方工具"]
            if files:
                print("\n[文件]")
                for file in files:
                    print(f"├─ {file}")
                    
            if not folders and not files:
                print("\n目录为空")
                
        except Exception as e:
            print(f"{RED}✗ 获取目录内容失败: {str(e)}{RESET}")
            
    def save_cookies(self):
        """保存cookie到文件"""
        cookie_dict = requests.utils.dict_from_cookiejar(self.session.cookies)
        with open(self.cookie_file, 'w') as f:
            json.dump(cookie_dict, f)
            
    def load_cookies(self):
        """从文件加载cookie"""
        try:
            if os.path.exists(self.cookie_file):
                print("发现已保存的登录状态...")
                with open(self.cookie_file, 'r') as f:
                    cookie_dict = json.load(f)
                    self.session.cookies = requests.utils.cookiejar_from_dict(cookie_dict)
                print("正在验证登录状态...")
                if self.check_login():
                    print("✓ 使用已保存的登录状态")
                    if self.user_info.get('username'):
                        print(f"✓ 当前登录用户: {self.user_info['username']}")
                    time.sleep(1)  # 暂停1秒
                    os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
                    return True
                else:
                    print("✗ 登录状态已失效")
                    return False
        except Exception as e:
            print(f"加载登录状态失败: {str(e)}")
        return False
        
    def check_login(self):
        """检查cookie是否有效"""
        try:
            print("正在验证登录状态...")
            response = self.session.get(self.mydisk_url)
            if "登录" not in response.text:
                self.is_login = True
                # 尝试获取用户信息
                try:
                    username_match = re.search(r'<a\s+href="[^"]*"\s+class="text"[^>]*>([^<]+)</a>', response.text)
                    if username_match:
                        self.user_info['username'] = username_match.group(1).strip()
                except:
                    pass
                return True
        except Exception as e:
            print(f"验证登录状态失败: {str(e)}")
        return False
        
    def login(self, username, password):
        """登录蓝奏云
        Args:
            username: 用户名
            password: 密码
        Returns:
            bool: 是否登录成功
        """
        # 先尝试加载已保存的cookie
        if self.load_cookies():
            return True
            
        try:
            print("\n正在登录蓝奏云...")
            print(f"账号: {username}")
            print("密码: ********")
            
            # 发送登录请求
            data = {
                "task": "3",
                "uid": username,
                "pwd": password,
                "setSessionId": "",
                "setSig": "",
                "setScene": "",
                "setTocen": "",
                "formhash": "",
            }
            
            headers = {
                'Accept': 'application/json, text/javascript, */*',
                'Accept-Language': 'zh-CN,zh;q=0.9',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://up.woozooo.com',
                'Referer': 'https://up.woozooo.com/',
                'User-Agent': self.session.headers['User-Agent']
            }
            
            # 发送登录请求
            response = self.session.post(
                "https://up.woozooo.com/mlogin.php",
                data=data,
                headers=headers,
                allow_redirects=False
            )
            
            if response.status_code != 200:
                print("✗ 登录请求失败")
                sys.exit(1)  # 登录失败直接退出
                
            try:
                result = response.json()
                if result.get('zt') == 1:
                    print("✓ 登录成功!")
                    self.save_cookies()
                    self.load_cookies()  # 立即加载新保存的cookie
                    self.is_login = True
                    time.sleep(1)  # 暂停1秒
                    os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
                    return True
                else:
                    print(f"✗ 登录失败: {result.get('info', '未知错误')}")
                    sys.exit(1)  # 登录失败直接退出
            except:
                if self.check_login():
                    print("✓ 登录成功!")
                    self.save_cookies()
                    self.load_cookies()  # 立即加载新保存的cookie
                    time.sleep(1)  # 暂停1秒
                    os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
                    return True
                print("✗ 登录失败，无法解析响应")
                sys.exit(1)  # 登录失败直接退出
                
        except Exception as e:
            print(f"✗ 登录过程出错: {str(e)}")
            sys.exit(1)  # 登录失败直接退出
            
    def upload_file(self, file_path, folder_id=None):
        """上传文件
        Args:
            file_path: 本地文件路径
            folder_id: 目标文件夹ID，默认根目录
        Returns:
            str: 成功返回分享链接，失败返回None
        """
        if folder_id is None:
            folder_id = self.root_folder_id
            
        if not self.is_login:
            print("✗ 请先登录")
            return None
            
        try:
            file_name = os.path.basename(file_path)
            print(f"\n[上传文件]")
            print(f"文件名称: {file_name}")
            print(f"文件大小: {os.path.getsize(file_path) / 1024 / 1024:.2f}MB")
            print(f"目标目录: {'根目录' if folder_id == self.root_folder_id else folder_id}")
            
            # 上传文件
            file_size = os.path.getsize(file_path)
            with open(file_path, "rb") as f:
                with tqdm(total=file_size, unit='B', unit_scale=True, desc="上传进度", ncols=100) as pbar:
                    files = {
                        "upload_file": (file_name, f, "application/octet-stream")
                    }
                    data = {
                        "task": "1",
                        "vie": "2",
                        "ve": "2",
                        "id": "WU_FILE_0",
                        "name": file_name,
                        "folder_id_bb_n": folder_id
                    }
                    response = self.session.post(
                        f"{self.base_url}/html5up.php",
                        files=files,
                        data=data
                    )
                    pbar.update(file_size)
                    
            if response.status_code != 200:
                print(f"✗ 上传失败: HTTP {response.status_code}")
                return None
                
            # 解析响应
            try:
                result = response.json()
                if result.get("zt") == 1:
                    file_info = result.get("text", [{}])[0]
                    file_id = file_info.get("id")
                    if file_id:
                        print("✓ 文件上传成功，正在获取分享链接...")
                        # 获取分享链接
                        share_response = self.session.post(
                            f"{self.base_url}/doupload.php",
                            data={
                                "task": "22",
                                "file_id": file_id
                            }
                        )
                        share_result = share_response.json()
                        if share_result.get("zt") == 1:
                            share_info = share_result.get("info", {})
                            share_url = share_info.get("is_newd")
                            if share_url:
                                print("✓ 分享链接获取成功")
                                return share_url
                print("✗ 无法获取分享链接")
                return None
            except Exception as e:
                print(f"✗ 解析响应失败: {str(e)}")
                return None
                
        except Exception as e:
            print(f"✗ 上传过程出错: {str(e)}")
            return None

def check_file_size(file_path):
    """检查文件大小"""
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / (1024 * 1024)
    if file_size_mb > 100:
        print(f"✗ 文件大小 {file_size_mb:.2f}MB 超过免费用户限制(100MB)")
        return False
    return True

def upload_to_lanzou(username, password, file_path):
    try:
        print("\n=== 蓝奏云文件上传工具 ===")
        
        # 检查文件是否存在
        if not os.path.exists(file_path):
            print(f"✗ 文件不存在: {file_path}")
            return False
            
        # 检查文件大小
        if not check_file_size(file_path):
            return False
            
        # 创建客户端实例并登录
        client = LanZouWeb()
        if not client.login(username, password):
            return False
            
        # 上传文件，最多重试3次
        for i in range(3):
            try:
                share_link = client.upload_file(file_path)
                if share_link:
                    print("\n=== 上传结果 ===")
                    print("✓ 文件上传成功!")
                    print(f"✓ 分享链接: {share_link}")
                    return True
                else:
                    if i < 2:
                        print(f"\n[第{i+1}次上传失败]")
                        print("等待5秒后重试...")
                        time.sleep(5)
                    else:
                        print("\n=== 上传失败 ===")
                        print("可能的原因:")
                        print("1. 网络连接不稳定")
                        print("2. 服务器响应异常")
                        print("3. 文件类型不支持")
                        return False
            except Exception as e:
                if i < 2:
                    print(f"\n[第{i+1}次上传出错]")
                    print(f"错误信息: {str(e)}")
                    print("等待5秒后重试...")
                    time.sleep(5)
                else:
                    return False
                    
    except Exception as e:
        print(f"✗ 发生错误: {str(e)}")
        return False

def mask_username(username: str) -> str:
    """处理用户名显示格式
    如果是手机号，只显示前三位和后四位，中间用*号代替
    """
    if username and len(username) == 11 and username.isdigit():
        return f"{username[:3]}****{username[-4:]}"
    return username

def interactive_mode(client):
    """交互式命令行模式"""
    print(f"\n{BLUE}██╗      █████╗ ███╗   ██╗███████╗ ██████╗ ██╗   ██╗{RESET}")
    print(f"{BLUE}██║     ██╔══██╗████╗  ██║╚══███╔╝██╔═══██╗██║   ██║{RESET}")
    print(f"{BLUE}██║     ███████║██╔██╗ ██║  ███╔╝ ██║   ██║██║   ██║{RESET}")
    print(f"{BLUE}██║     ██╔══██║██║╚██╗██║ ███╔╝  ██║   ██║██║   ██║{RESET}")
    print(f"{BLUE}███████╗██║  ██║██║ ╚████║███████╗╚██████╔╝╚██████╔╝{RESET}")
    print(f"{BLUE}╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝ ╚═════╝  ╚═════╝ {RESET}")
    print(f"\n{BLUE}=== 蓝奏云文件管理工具 - 交互模式 ==={RESET}")
    print(f"{CYAN}输入 help 查看帮助信息{RESET}")
    print(f"{CYAN}输入 exit 退出程序{RESET}")
    
    # 获取用户名，优先使用网页获取的用户名，如果没有则使用配置文件中的账号
    raw_username = client.user_info.get('username') or LANZOU_CONFIG.get("username", "user")
    username = mask_username(raw_username)
    
    while True:
        try:
            # 显示提示符
            cwd = client.get_current_path()
            # Ubuntu风格的提示符: username@lanzou:path$
            prompt = f"{BOLD}{GREEN}{username}@lanzou{RESET}{BOLD}:{BLUE}{cwd}{RESET}$ "
            cmd = input(f"\n{prompt}").strip()
            
            if not cmd:
                continue
                
            # 解析命令
            parts = cmd.split()
            command = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if command == "exit":
                print(f"{CYAN}再见!{RESET}")
                break
                
            elif command == "help":
                print(f"\n{BLUE}=== 可用命令 ==={RESET}")
                print(f"{CYAN}pwd                  {RESET}显示当前目录")
                print(f"{CYAN}ls                   {RESET}列出目录内容")
                print(f"{CYAN}cd <目录名>          {RESET}进入目录")
                print(f"{CYAN}cd ..                {RESET}返回上级目录")
                print(f"{CYAN}mkdir <目录名>       {RESET}创建目录")
                print(f"{CYAN}rmdir <目录名>       {RESET}删除目录")
                print(f"{CYAN}upload <文件路径>    {RESET}上传文件")
                print(f"{CYAN}rm <文件名>          {RESET}删除文件")
                print(f"{CYAN}help                 {RESET}显示帮助信息")
                print(f"{CYAN}exit                 {RESET}退出程序")
                
            elif command == "pwd":
                client.pwd()
                
            elif command == "ls":
                client.list_dir(client.current_folder_id)
                
            elif command == "cd":
                if not args:
                    print(f"{RED}✗ 请指定目录名{RESET}")
                    continue
                folder_name = args[0]
                client.cd(folder_name)
                
            elif command == "mkdir":
                if not args:
                    print(f"{RED}✗ 请指定目录名{RESET}")
                    continue
                folder_name = args[0]
                client.create_folder(folder_name, client.current_folder_id)
                
            elif command == "rmdir":
                if not args:
                    print(f"{RED}✗ 请指定要删除的目录名{RESET}")
                    continue
                folder_name = args[0]
                # 获取当前目录下的所有文件夹
                folders = client.get_folders(client.current_folder_id)
                # 查找目标文件夹
                target_folder = None
                for folder in folders:
                    if folder.name == folder_name:
                        target_folder = folder
                        break
                if not target_folder:
                    print(f"{RED}✗ 目录不存在: {folder_name}{RESET}")
                    continue
                client.delete_folder(target_folder.folder_id)
                
            elif command == "upload":
                if not args:
                    print(f"{RED}✗ 请指定要上传的文件路径{RESET}")
                    continue
                file_path = args[0]
                
                if not os.path.exists(file_path):
                    print(f"{RED}✗ 文件不存在: {file_path}{RESET}")
                    continue
                    
                if not check_file_size(file_path):
                    continue
                    
                for i in range(3):
                    try:
                        share_link = client.upload_file(file_path, client.current_folder_id)
                        if share_link:
                            print(f"\n{BLUE}=== 上传结果 ==={RESET}")
                            print(f"{GREEN}✓ 文件上传成功!{RESET}")
                            print(f"{GREEN}✓ 分享链接: {share_link}{RESET}")
                            break
                        else:
                            if i < 2:
                                print(f"\n{YELLOW}[第{i+1}次上传失败]{RESET}")
                                print(f"{YELLOW}等待5秒后重试...{RESET}")
                                time.sleep(5)
                            else:
                                print(f"\n{RED}=== 上传失败 ==={RESET}")
                                print(f"{YELLOW}可能的原因:{RESET}")
                                print("1. 网络连接不稳定")
                                print("2. 服务器响应异常")
                                print("3. 文件类型不支持")
                    except Exception as e:
                        if i < 2:
                            print(f"\n{YELLOW}[第{i+1}次上传出错]{RESET}")
                            print(f"{RED}错误信息: {str(e)}{RESET}")
                            print(f"{YELLOW}等待5秒后重试...{RESET}")
                            time.sleep(5)
                            
            elif command == "rm":
                if not args:
                    print(f"{RED}✗ 请指定要删除的文件名{RESET}")
                    continue
                file_name = args[0]
                # 获取当前目录下的所有文件
                files = client.get_files(client.current_folder_id)
                # 查找目标文件
                target_file = None
                for file in files:
                    if file.name == file_name:
                        target_file = file
                        break
                if not target_file:
                    print(f"{RED}✗ 文件不存在: {file_name}{RESET}")
                    continue
                client.delete_file(target_file.id)
                
            else:
                print(f"{RED}✗ 未知命令: {command}{RESET}")
                print(f"{CYAN}输入 help 查看可用命令{RESET}")
                
        except KeyboardInterrupt:
            print(f"\n{CYAN}输入 exit 退出程序{RESET}")
        except Exception as e:
            print(f"{RED}✗ 操作失败: {str(e)}{RESET}")

def main():
    if len(sys.argv) < 2:
        username = LANZOU_CONFIG.get("username")
        password = LANZOU_CONFIG.get("password")
        
        if username == "your_email@example.com" or password == "your_password":
            print("\n=== 配置错误 ===")
            print("请先在 config.py 中配置你的蓝奏云账号和密码")
            print("示例:")
            print('LANZOU_CONFIG = {')
            print('    "username": "your_email@example.com",')
            print('    "password": "your_password",')
            print('    "default_folder_id": "-1"')
            print('}')
            return
            
        # 创建客户端实例并登录
        client = LanZouWeb()
        if not client.login(username, password):
            return
            
        # 进入交互模式
        interactive_mode(client)
        return
        
    # 创建客户端实例并登录
    username = LANZOU_CONFIG.get("username")
    password = LANZOU_CONFIG.get("password")
    client = LanZouWeb()
    if not client.login(username, password):
        return
        
    command = sys.argv[1].lower()
    
    try:
        if command == "pwd":
            client.pwd()
            
        elif command == "ls":
            client.list_dir(client.current_folder_id)
            
        elif command == "cd":
            if len(sys.argv) < 3:
                print("✗ 请指定目录名")
                return
            folder_name = sys.argv[2]
            client.cd(folder_name)
            
        elif command == "mkdir":
            if len(sys.argv) < 3:
                print("✗ 请指定目录名")
                return
            folder_name = sys.argv[2]
            client.create_folder(folder_name, client.current_folder_id)
            
        elif command == "rmdir":
            if len(sys.argv) < 3:
                print("✗ 请指定要删除的目录名")
                return
            folder_name = sys.argv[2]
            # 获取当前目录下的所有文件夹
            folders = client.get_folders(client.current_folder_id)
            # 查找目标文件夹
            target_folder = None
            for folder in folders:
                if folder.name == folder_name:
                    target_folder = folder
                    break
            if not target_folder:
                print(f"✗ 目录不存在: {folder_name}")
                return
            client.delete_folder(target_folder.folder_id)
            
        elif command == "upload":
            if len(sys.argv) < 3:
                print("✗ 请指定要上传的文件路径")
                return
            file_path = sys.argv[2]
            
            if not os.path.exists(file_path):
                print(f"✗ 文件不存在: {file_path}")
                return
                
            if not check_file_size(file_path):
                return
                
            for i in range(3):
                try:
                    share_link = client.upload_file(file_path, client.current_folder_id)
                    if share_link:
                        print(f"\n{BLUE}=== 上传结果 ==={RESET}")
                        print(f"{GREEN}✓ 文件上传成功!{RESET}")
                        print(f"{GREEN}✓ 分享链接: {share_link}{RESET}")
                        break
                    else:
                        if i < 2:
                            print(f"\n{YELLOW}[第{i+1}次上传失败]{RESET}")
                            print(f"{YELLOW}等待5秒后重试...{RESET}")
                            time.sleep(5)
                        else:
                            print(f"\n{RED}=== 上传失败 ==={RESET}")
                            print(f"{YELLOW}可能的原因:{RESET}")
                            print("1. 网络连接不稳定")
                            print("2. 服务器响应异常")
                            print("3. 文件类型不支持")
                except Exception as e:
                    if i < 2:
                        print(f"\n{YELLOW}[第{i+1}次上传出错]{RESET}")
                        print(f"{RED}错误信息: {str(e)}{RESET}")
                        print(f"{YELLOW}等待5秒后重试...{RESET}")
                        time.sleep(5)
                        
        elif command == "rm":
            if len(sys.argv) < 3:
                print("✗ 请指定要删除的文件名")
                return
            file_name = sys.argv[2]
            # 获取当前目录下的所有文件
            files = client.get_files(client.current_folder_id)
            # 查找目标文件
            target_file = None
            for file in files:
                if file.name == file_name:
                    target_file = file
                    break
            if not target_file:
                print(f"✗ 文件不存在: {file_name}")
                return
            client.delete_file(target_file.id)
            
        else:
            print(f"✗ 未知命令: {command}")
            print("使用方法:")
            print("1. 显示当前目录:   python lanzou_web.py pwd")
            print("2. 列出目录内容:   python lanzou_web.py ls")
            print("3. 进入目录:       python lanzou_web.py cd <目录名>")
            print("4. 返回上级目录:   python lanzou_web.py cd ..")
            print("5. 创建目录:       python lanzou_web.py mkdir <目录名>")
            print("6. 删除目录:       python lanzou_web.py rmdir <目录名>")
            print("7. 上传文件:       python lanzou_web.py upload <文件路径>")
            print("8. 删除文件:       python lanzou_web.py rm <文件名>")
            print("\n或者直接运行 python lanzou_web.py 进入交互模式")
            
    except Exception as e:
        print(f"✗ 操作失败: {str(e)}")

if __name__ == "__main__":
    main() 