"""Vanna 初始化、DeepSeek 注入与知识库训练。"""
import hashlib
import os

import numpy as np
from openai import OpenAI

from vanna.legacy.chromadb import ChromaDB_VectorStore
from vanna.legacy.openai import OpenAI_Chat

import config


class HashEmbeddingFunction:
    """字符 n-gram 哈希嵌入（384 维，无需下载模型）。"""

    def __init__(self, dim: int = 384):
        self.dim = dim

    def __call__(self, input):
        vectors = []
        for text in input:
            vec = np.zeros(self.dim, dtype=np.float32)
            content = str(text).lower()
            for n in (2, 3, 4):
                for i in range(max(0, len(content) - n + 1)):
                    gram = content[i : i + n]
                    digest = int(hashlib.md5(gram.encode("utf-8")).hexdigest(), 16)
                    vec[digest % self.dim] += 1.0 if ((digest >> 8) & 1) == 0 else -1.0
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            vectors.append(vec.tolist())
        return vectors

    def embed_query(self, input):
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        return "hash_ngram"

    def get_config(self):
        return {"dim": self.dim}

    @staticmethod
    def build_from_config(cfg):
        return HashEmbeddingFunction(dim=cfg.get("dim", 384))


class MyVanna(ChromaDB_VectorStore, OpenAI_Chat):
    def __init__(self, client=None, cfg=None):
        ChromaDB_VectorStore.__init__(self, config=cfg)
        OpenAI_Chat.__init__(self, client=client, config=cfg)


def _ensure_database():
    if not os.path.exists(config.DB_PATH) or os.path.getsize(config.DB_PATH) == 0:
        import load_data

        load_data.main()


def _training_payload():
    ddl = """CREATE TABLE tmall_products (
  商品ID TEXT, 年销量 REAL, 品牌名称 TEXT, 二级类目ID TEXT, 二级类目名称 TEXT,
  一级类目ID TEXT, 一级类目名称 TEXT, 主图URL TEXT, 发货地 TEXT, 邮费 REAL,
  卖家ID TEXT, 店铺名称 TEXT, 短标题 TEXT, 辅图URL TEXT, 副标题 TEXT,
  商品标题 TEXT, 店铺类型 TEXT, 白底图URL TEXT, 预售定金 REAL,
  最终促销价 REAL, 预估凑单价 REAL, 预估凑单说明 TEXT, 原价 REAL, 折后价 REAL,
  核心优惠规则 TEXT, 更多优惠规则 TEXT, 优惠标签 TEXT, 商品链接 TEXT, 优惠券链接 TEXT,
  当日促销销量 REAL, 收益比例 REAL, 近2小时促销销量 REAL, 推广佣金 REAL,
  佣金比例 REAL, 补贴金额 REAL, 补贴比例 REAL, 补贴上限 REAL,
  优质品牌标识 TEXT, 采集时间 TEXT, 所属品类 TEXT
);"""

    docs = [
        "年销量 已从'7000+''1.8万+'等文本转换为数值型（REAL），可以直接用于排序和聚合。",
        "佣金比例 是原始数值（如128、766、2125），单位不是百分比，排序时按数值大小理解即可。",
        "预估凑单价 可能低于 最终促销价，这是平台凑单规则导致，不是数据错误。",
        "补贴金额、补贴比例、补贴上限、预售定金 可能为空，查询时需处理 NULL。",
        "店铺类型 是文本枚举（天猫超市、天天特卖工厂、官方旗舰店、淘工厂、国货甄选、工厂直销等），精确匹配用 =，不要用 LIKE。",
        "采集时间 格式为'2025/10/19 7:49'，SQLite 按月聚合请用 strftime('%Y-%m', 采集时间)，不要用 MySQL 的 DATE_FORMAT。",
        "邮费 为 0 表示包邮。",
        "品牌名称 为'无品牌'表示该商品没有品牌。",
        "商品链接 列存放商品详情页 URL（原始值为 // 开头的协议相对链接，展示时补全 https:）。",
        "重要：用户要求推荐某个品类的商品（如手机、牛奶、纸巾）时，必须优先用 二级类目名称 或 一级类目名称 过滤，例如 二级类目名称 = '手机'；不要只用 商品标题 LIKE，否则会把'手机膜''手机壳''充电宝''数据线'等配件误判成主商品。",
        "重要：如果不得不用 商品标题 匹配主商品，必须排除配件关键词：AND 商品标题 NOT LIKE '%膜%' AND 商品标题 NOT LIKE '%壳%' AND 商品标题 NOT LIKE '%套%' AND 商品标题 NOT LIKE '%保护%' AND 商品标题 NOT LIKE '%适用%' AND 商品标题 NOT LIKE '%充电%' AND 商品标题 NOT LIKE '%数据线%' AND 商品标题 NOT LIKE '%支架%'。",
        "重要：数据库中可能存在重复商品，查询商品明细时请使用 SELECT DISTINCT 或 GROUP BY 商品ID 去重，避免返回重复商品。",
        "推荐类问题默认按 年销量 DESC 排序，并筛选 最终促销价 IS NOT NULL。",
        "【语义纠错规则】用户在输入问题时可能存在错别字或省略词（例如：'电宝'指代'充电宝'、'衣服'指代'秋衣/外套'、'纸'指代'抽纸/卷纸'）。在生成 SQL 之前，必须先内部把用户搜索词纠正为标准商品名词，然后再用纠正后的词去生成 LIKE 匹配条件。",
        "【多重匹配规则】当用户搜索特定商品时，如果商品标题可能包含不同的同义词，请使用 OR 逻辑扩大匹配范围。例如搜索'充电宝'，应匹配 商品标题 LIKE '%充电宝%' OR 商品标题 LIKE '%移动电源%'。",
        "用户输入'电宝'指代'充电宝'，'纸巾'指代'抽纸'，'纸'指代'抽纸/卷纸'，请自动纠正后再进行匹配。",
        "重要：对于'衣服''秋衣''冬装''外套'等穿着类商品，请严格匹配 一级类目名称 LIKE '%女装%' OR 一级类目名称 LIKE '%男装%'。绝对不要推荐毛线、鞋垫、面罩等边缘配件，除非用户明确提及。",
        "【强制规则1】只要用户输入了具体名词（如'平板'、'华为'、'充电宝'），不要自作聪明去猜测用途！直接在 商品标题 或 品牌名称 中使用 LIKE '%名词%' 进行匹配。",
        "重要：查询'手机'时，必须使用 二级类目名称 = '手机'，不要用 商品标题 LIKE '%手机%'，否则会匹配到'手机壳''手机支架''手机远程摄像头'等非手机商品。",
        "【强制规则2】为了防止推荐配件，查询'平板'时，必须加上排他条件：AND 商品标题 NOT LIKE '%膜%' AND 商品标题 NOT LIKE '%壳%' AND 商品标题 NOT LIKE '%拖把%'。",
        "【强制规则3】无论用户问什么（就算只输入两个字），你的 SELECT 语句中必须包含 商品链接 字段，绝对不可省略！",
        "【强制规则4】不管用户有没有说'推荐'两个字，只要是查商品，统一使用 ORDER BY 年销量 DESC LIMIT 10。",
        "【极值规则】如果用户问'销量第一'、'最高'、'最低'、'最便宜'、'最贵'等带极值的问题，直接使用 ORDER BY 对应字段 DESC LIMIT 1 查询，绝不使用 LIMIT 10。大模型总结时只需直接陈述该商品的名称和对应指标（销量或价格），不要废话和长篇分析。",
        "【最强规则】当用户询问'哪个最多/哪个最高/哪个最便宜/哪个销量最好'时，你的 SELECT 语句必须使用 ORDER BY 对应字段 DESC/ASC LIMIT 1。绝对、绝对不可返回多条数据！",
        "【不同品牌规则】用户要求'三个不同品牌''四个不同品牌'时，必须使用 GROUP BY 品牌名称（或按品牌去重），确保每个品牌只出现一次，品牌为'无品牌'或'未知品牌'的要排除。",
        "【易混淆名词规则】遇到易混淆名词（如笔记本），必须结合上下文。如果是'纸质笔记本'，必须排除'鼠标垫'、'打印纸'、'电脑'。在 SQL 中应当写成：商品标题 LIKE '%笔记本%' AND 商品标题 NOT LIKE '%鼠标垫%' AND 商品标题 NOT LIKE '%打印纸%' AND 商品标题 NOT LIKE '%电脑%'。",
    ]

    pairs = [
        (
            "销量最高的品牌是哪个？",
            "SELECT 品牌名称, SUM(年销量) AS total_sales FROM tmall_products WHERE 品牌名称 IS NOT NULL GROUP BY 品牌名称 ORDER BY total_sales DESC LIMIT 10;",
        ),
        (
            "佣金比例最高的类目是哪个？",
            "SELECT 二级类目名称, AVG(佣金比例) AS avg_commission FROM tmall_products WHERE 佣金比例 IS NOT NULL GROUP BY 二级类目名称 ORDER BY avg_commission DESC LIMIT 10;",
        ),
        (
            "补贴最多的商品是哪些？",
            "SELECT 商品标题, 品牌名称, 商品链接, 补贴金额 FROM tmall_products WHERE 补贴金额 IS NOT NULL GROUP BY 商品ID ORDER BY 补贴金额 DESC LIMIT 10;",
        ),
        (
            "热销商品 TOP10 是哪些？",
            "SELECT 商品标题, 品牌名称, 商品链接, 最终促销价, 年销量 FROM tmall_products WHERE 年销量 IS NOT NULL GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "帮我推荐一些牛奶，价格不超过60一件",
            "SELECT 商品标题, 品牌名称, 商品链接, 最终促销价, 年销量 FROM tmall_products WHERE 二级类目名称 LIKE '%牛奶%' AND 最终促销价 <= 60 GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "推荐价格50元以内的零食",
            "SELECT 商品标题, 品牌名称, 商品链接, 最终促销价, 年销量 FROM tmall_products WHERE 一级类目名称 LIKE '%零食%' AND 最终促销价 <= 50 GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "有什么便宜的纸巾推荐",
            "SELECT 商品标题, 品牌名称, 商品链接, 最终促销价, 年销量 FROM tmall_products WHERE 二级类目名称 LIKE '%纸%' AND 最终促销价 <= 30 GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "推荐手机",
            "SELECT 商品标题, 品牌名称, 商品链接, 最终促销价, 年销量 FROM tmall_products WHERE 二级类目名称 = '手机' AND 最终促销价 IS NOT NULL GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "推荐性价比高的手机",
            "SELECT 商品标题, 品牌名称, 商品链接, 最终促销价, 年销量 FROM tmall_products WHERE 二级类目名称 = '手机' AND 最终促销价 IS NOT NULL GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "有哪些包邮的牛奶",
            "SELECT 商品标题, 品牌名称, 商品链接, 最终促销价, 年销量 FROM tmall_products WHERE 二级类目名称 LIKE '%牛奶%' AND 邮费 = 0 GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "佣金比例最高的商品 Top10 是哪些？",
            "SELECT 商品标题, 品牌名称, 商品链接, 佣金比例, 年销量 FROM tmall_products WHERE 佣金比例 IS NOT NULL GROUP BY 商品ID ORDER BY 佣金比例 DESC LIMIT 10;",
        ),
        (
            "天猫超市和天天特卖工厂的商品平均价格差多少？",
            "SELECT 店铺类型, AVG(最终促销价) AS avg_price FROM tmall_products WHERE 店铺类型 IN ('天猫超市','天天特卖工厂') GROUP BY 店铺类型;",
        ),
        (
            "哪个发货地的商品数量最多？",
            "SELECT 发货地, COUNT(*) AS cnt FROM tmall_products WHERE 发货地 IS NOT NULL GROUP BY 发货地 ORDER BY cnt DESC LIMIT 10;",
        ),
        (
            "销量高且佣金比例也高的商品有哪些？",
            "SELECT 商品标题, 品牌名称, 商品链接, 年销量, 佣金比例 FROM tmall_products WHERE 年销量 IS NOT NULL AND 佣金比例 IS NOT NULL GROUP BY 商品ID ORDER BY 年销量 DESC, 佣金比例 DESC LIMIT 10;",
        ),
        (
            "有没有便宜点的电宝？",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价 FROM tmall_products WHERE (商品标题 LIKE '%充电宝%' OR 商品标题 LIKE '%移动电源%') ORDER BY 最终促销价 ASC LIMIT 10;",
        ),
        (
            "给我来点纸。",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价 FROM tmall_products WHERE (商品标题 LIKE '%抽纸%' OR 商品标题 LIKE '%卷纸%' OR 二级类目名称 LIKE '%纸%') ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "冬天推荐衣服",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 年销量 FROM tmall_products WHERE (一级类目名称 LIKE '%女装%' OR 一级类目名称 LIKE '%男装%') AND 最终促销价 IS NOT NULL ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "推荐几款充电宝",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 年销量 FROM tmall_products WHERE (商品标题 LIKE '%充电宝%' OR 商品标题 LIKE '%移动电源%') GROUP BY 商品ID ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "华为",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 商品链接 FROM tmall_products WHERE 品牌名称 LIKE '%华为%' OR 商品标题 LIKE '%华为%' ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "平板",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 商品链接 FROM tmall_products WHERE 商品标题 LIKE '%平板%' AND 商品标题 NOT LIKE '%膜%' AND 商品标题 NOT LIKE '%壳%' AND 商品标题 NOT LIKE '%拖把%' ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "给我推荐五部平板",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 商品链接 FROM tmall_products WHERE 商品标题 LIKE '%平板%' AND 商品标题 NOT LIKE '%膜%' AND 商品标题 NOT LIKE '%壳%' AND 商品标题 NOT LIKE '%拖把%' ORDER BY 年销量 DESC LIMIT 5;",
        ),
        (
            "充电宝",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 商品链接 FROM tmall_products WHERE 商品标题 LIKE '%充电宝%' OR 商品标题 LIKE '%移动电源%' ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "电宝",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 商品链接 FROM tmall_products WHERE 商品标题 LIKE '%充电宝%' OR 商品标题 LIKE '%移动电源%' ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "推荐3000元以上的手机",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 商品链接 FROM tmall_products WHERE 二级类目名称 = '手机' AND 最终促销价 >= 3000 ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "销量第一的手机",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 年销量, 商品链接 FROM tmall_products WHERE 二级类目名称 = '手机' AND 年销量 IS NOT NULL ORDER BY 年销量 DESC LIMIT 1;",
        ),
        (
            "给我推荐三个不同品牌的纸巾",
            "SELECT 品牌名称, MIN(商品标题) AS 商品标题, MIN(最终促销价) AS 最终促销价, MIN(商品链接) AS 商品链接, MAX(年销量) AS 年销量 FROM tmall_products WHERE (商品标题 LIKE '%纸巾%' OR 商品标题 LIKE '%抽纸%' OR 商品标题 LIKE '%卷纸%') AND 品牌名称 IS NOT NULL AND 品牌名称 NOT IN ('无品牌','未知品牌') GROUP BY 品牌名称 ORDER BY 年销量 DESC LIMIT 3;",
        ),
        (
            "给我推荐四个不同品牌的纸巾",
            "SELECT 品牌名称, MIN(商品标题) AS 商品标题, MIN(最终促销价) AS 最终促销价, MIN(商品链接) AS 商品链接, MAX(年销量) AS 年销量 FROM tmall_products WHERE (商品标题 LIKE '%纸巾%' OR 商品标题 LIKE '%抽纸%' OR 商品标题 LIKE '%卷纸%') AND 品牌名称 IS NOT NULL AND 品牌名称 NOT IN ('无品牌','未知品牌') GROUP BY 品牌名称 ORDER BY 年销量 DESC LIMIT 4;",
        ),
        (
            "推荐纸质的笔记本",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 年销量, 商品链接 FROM tmall_products WHERE 商品标题 LIKE '%笔记本%' AND 商品标题 NOT LIKE '%鼠标垫%' AND 商品标题 NOT LIKE '%打印纸%' AND 商品标题 NOT LIKE '%电脑%' ORDER BY 年销量 DESC LIMIT 10;",
        ),
        (
            "我要24包的纸巾",
            "SELECT DISTINCT 商品标题, 品牌名称, 最终促销价, 商品链接, 年销量 FROM tmall_products WHERE 商品标题 LIKE '%24包%' AND (商品标题 LIKE '%纸%' OR 商品标题 LIKE '%抽%') ORDER BY 年销量 DESC LIMIT 10;",
        ),
    ]
    return ddl, docs, pairs


def _already_trained(vn) -> bool:
    try:
        data = vn.get_training_data()
    except Exception:
        return False
    return data is not None and not data.empty


def build_vanna() -> MyVanna:
    _ensure_database()
    client = OpenAI(api_key=config.DEEPSEEK_API_KEY, base_url=config.DEEPSEEK_BASE_URL)
    vn = MyVanna(
        client=client,
        cfg={
            "model": config.MODEL_NAME,
            "temperature": 0,
            "allow_llm_to_see_data": True,
            "embedding_function": HashEmbeddingFunction(),
        },
    )
    vn.connect_to_sqlite(config.DB_PATH)

    if _already_trained(vn):
        print("检测到已有训练数据，跳过知识库训练。")
        return vn

    ddl, docs, pairs = _training_payload()
    print("正在训练 Vanna 知识库 ...")
    vn.train(ddl=ddl)
    for doc in docs:
        vn.train(documentation=doc)
    for question, sql in pairs:
        vn.train(question=question, sql=sql)
    print("知识库训练完成。")
    return vn


_vn = None


def get_vanna() -> MyVanna:
    global _vn
    if _vn is None:
        _vn = build_vanna()
    return _vn
