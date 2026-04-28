import os
import shutil
import toml
if __name__ == "__main__":
    from log模块 import logger
else:
    from 模块.log模块 import logger

# ==========================================
# 配置读取模块
# 功能：负责管理 API 配置文件，支持自动初始化和 TOML 解析
# ==========================================

# 全局路径常量定义
# 使用项目根目录（main.py 所在目录）作为基准，确保从任意位置运行都能正确找到配置文件
项目根目录 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
配置文件目录 = os.path.join(项目根目录, "配置文件")
配置文件名称 = "api_config.toml"
配置文件路径 = os.path.join(配置文件目录, 配置文件名称)

# 模板文件路径定义（用于初始化）
模板目录 = os.path.join(项目根目录, "配置文件模板")
配置文件模板路径 = os.path.join(模板目录, 配置文件名称)

def 初始化配置文件():
    """
    环境检查与初始化逻辑。
    返回:
        str: 配置文件的绝对或相对路径。如果初始化失败（如模板也缺失）则返回 None。
    """
    # 第一步：检查并创建配置文件夹
    if not os.path.exists(配置文件目录):
        os.makedirs(配置文件目录)
        logger.info(f"检测到配置目录不存在，已自动创建: {配置文件目录}")

    # 第二步：检查配置文件是否存在
    if not os.path.exists(配置文件路径):
        logger.warning(f"检测到配置文件缺失: {配置文件路径}")
        
        # 第三步：尝试从模板复制
        if os.path.exists(配置文件模板路径):
            try:
                shutil.copy(配置文件模板路径, 配置文件路径)
                logger.info(f"已成功从模板复制配置文件: {配置文件路径}")
            except Exception as 复制错误:
                logger.error(f"复制配置文件模板时发生错误: {复制错误}")
                return None
        else:
            # 如果连模板都没有，就彻底没办法了
            logger.error(f"致命错误：配置文件模板缺失 ({配置文件模板路径})，无法自动初始化配置！")
            return None
        logger.error(f'''在 "{配置文件路径}" 没有配置文件，已自动创建完成，请填写配置信息后重新运行main.py''')
        exit(1)
    
    return 配置文件路径

def 读取配置():
    """
    读取并解析 TOML 格式的配置内容。
    返回:
        dict: 包含配置信息的字典。若读取失败则返回空字典 {}。
    """
    # 首先确保文件已经就绪
    路径 = 初始化配置文件()
    if not 路径:
        return {}
    
    try:
        # 使用 UTF-8 编码打开文件，防止中文内容乱码
        with open(路径, "r", encoding="utf-8") as 文件:
            # 使用 toml.load 解析文件流
            配置数据 = toml.load(文件)
            logger.info(f"成功加载配置文件数据，共识别出 {len(配置数据)} 个主配置项")
            return 配置数据
    except toml.TomlDecodeError as 解析错误:
        logger.error(f"配置文件格式错误 (TOML解析失败): {解析错误}")
        return {}
    except Exception as 其他错误:
        logger.error(f"读取配置文件时发生未知错误: {其他错误}")
        return {}
# ==========================================
# 模块导出：配置内容变量
# 只要导入此模块（from 模块.reading_config import 配置内容）
# 就会自动执行初始化和读取操作。
# ==========================================
配置内容 = 读取配置()#获取配置文件的所有内容，将其存储在全局变量 配置内容 中
模型数量=len(配置内容.get("模型配置", {}).keys())
def 获取模型配置():
    模型配置 = [[0 for _ in range(5)] for _ in range(模型数量)]# 使用列表推导式初始化一个二维数组（模型数量行 x 5列），初始值全部填充为 0
    所有模型 = list(配置内容.get("模型配置", {}).keys())# 获取所有模型配置的键名（即模型名称），并转换为列表
    j=0# 初始化行计数器

    # 遍历每个模型名称，提取详细配置并填入二维数组
    for i in 所有模型:
        # 第一列：模型名称
        模型配置[j][0]=i
        # 第二列：模型所属厂商
        模型配置[j][1]=str(配置内容.get("模型配置", {}).get(i, {}).get("厂商"))
        # 第三列：模型在厂商侧的 ID
        模型配置[j][2]=str(配置内容.get("模型配置", {}).get(i, {}).get("模型id"))
        # 第四列：厂商的 API 接口地址 (URL)
        模型配置[j][3]=str(配置内容.get("现有模型厂商", {}).get(配置内容.get("模型配置", {}).get(i, {}).get("厂商"), {}).get("url"))
        # 第五列：厂商的 API 密钥 (API Key)
        模型配置[j][4]=str(配置内容.get("现有模型厂商", {}).get(配置内容.get("模型配置", {}).get(i, {}).get("厂商"), {}).get("api_key"))

        j+=1# 行索引自增
    return 模型配置

# 调用函数获取处理后的二维数组并存入全局变量
模型配置=获取模型配置()

if __name__ == "__main__":
    """在为main运行时打印debug信息"""
    print(f"配置内容: {配置内容}")
    print()
    for i in range(模型数量):
        for j in range(5):
            print(模型配置[i][j], end=" ")
        print()
