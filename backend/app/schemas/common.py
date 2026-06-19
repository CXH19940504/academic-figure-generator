from enum import IntEnum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PaperType(IntEnum):
    """论文类型"""
    GRADUATION = 1  # 毕业论文
    JOURNAL = 2  # 期刊论文
    INTERNSHIP = 3  # 实习报告
    SURVEY = 4  # 调查报告

    @classmethod
    def get_name(cls, value: int) -> str:
        """获取枚举值的名称"""
        names = {
            1: "毕业论文",
            2: "期刊论文",
            3: "实习报告",
            4: "调查报告"
        }
        return names.get(value, "")

    @classmethod
    def get_description(cls, value: int) -> str:
        """获取枚举值的描述"""
        descriptions = {
            1: "本专科毕业论文，支持多种学科领域",
            2: "学术期刊投稿论文，注重研究方法和数据分析",
            3: "实习工作总结报告，侧重实践经历和工作总结",
            4: "社会调查或市场调查报告，包含调查方法和结论建议"
        }
        return descriptions.get(value, "")


class MaterialType(IntEnum):
    """材料类型"""
    SECTION = 1  # 文章主体
    REFERENCES = 2  # 中英文参考文献
    ABSTRACT = 3  # 中英文摘要
    ACKNOWLEDGEMENT = 4  # 致谢模板
    OUTLINE = 5  # 大纲
    FIGURE = 6  # 图
    TABLE = 7  # 表格
    FORMULA = 8  # 公式
    CODE = 9  # 代码
    INTRODUCTION = 10  # 引言/绪论
    CONCLUSION = 11  # 总结/结论

    @classmethod
    def get_value_by_name(cls, name: str) -> int:
        """根据名称获取枚举值

        支持两种方式：
        1. 英文名称（如 'REFERENCES', 'OUTLINE'）
        2. 中文名称（如 '参考文献', '摘要'）
        """
        name = name.strip()
        if not name:
            return 1

        # 尝试英文名称（枚举成员名）
        try:
            return cls[name.upper()].value
        except KeyError:
            pass

        # 中文名称映射
        names = {
            "参考文献": 2,
            "摘要": 3,
            "致谢": 4,
            "引言": 10,
            "绪论": 10,
            "总结": 11,
            "结论": 11,
        }
        return names.get(name, 1)


class PaperMaterials(BaseModel):
    """论文材料清单"""
    document_id: str  # 论文ID
    type: MaterialType  # 材料类型
    labels: List[str] = []  # 材料标签
    count: Optional[int] = None  # 数量


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MessageResponse(BaseModel):
    message: str


class ErrorResponse(BaseModel):
    error_code: str
    detail: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
