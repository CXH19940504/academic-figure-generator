from app.schemas.color_scheme import (
    ColorSchemeCreate,
    ColorSchemeResponse,
    ColorSchemeUpdate,
    ColorValues,
)
from app.schemas.common import (
    ErrorResponse,
    MessageResponse,
    PaginationParams,
    TaskStatusResponse,
)
from app.schemas.document import (
    DocumentResponse,
    SectionInfo,
)
from app.schemas.image import (
    ImageDirectGenerateRequest,
    ImageEditRequest,
    ImageGenerateRequest,
    ImageResponse,
    ImageStatusResponse,
)
from app.schemas.project import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.schemas.prompt import (
    PromptGenerateRequest,
    PromptResponse,
    PromptStatusResponse,
    PromptUpdate,
)

SUBJECTS = [
    {"code": "01", "name": "哲学", "categories": ["哲学", "逻辑学", "宗教学", "伦理学"]},
    {"code": "02", "name": "经济学", "categories": ["经济学", "经济统计学", "财政学", "税收学", "金融学", "保险学", "投资学", "国际经济与贸易"]},
    {"code": "03", "name": "法学", "categories": ["法学", "知识产权", "政治学与行政学", "国际政治", "社会学", "社会工作"]},
    {"code": "04", "name": "教育学", "categories": ["教育学", "科学教育", "教育技术学", "学前教育", "小学教育", "特殊教育", "体育教育", "运动训练"]},
    {"code": "05", "name": "文学", "categories": ["汉语言文学", "汉语言", "汉语国际教育", "英语", "日语", "新闻学", "广播电视学", "广告学", "传播学", "翻译", "商务英语"]},
    {"code": "06", "name": "历史学", "categories": ["历史学", "世界史", "考古学", "文物与博物馆学", "文物保护技术", "文化遗产"]},
    {"code": "07", "name": "理学", "categories": ["数学与应用数学", "信息与计算科学", "物理学", "应用物理学", "化学", "应用化学", "生物科学", "生物技术", "心理学", "应用心理学", "统计学", "应用统计学"]},
    {"code": "08", "name": "工学", "categories": ["计算机科学与技术", "软件工程", "网络工程", "信息安全", "物联网工程", "电子信息工程", "通信工程", "自动化", "机械工程", "机械设计制造及其自动化", "电气工程及其自动化", "土木工程", "建筑学", "材料科学与工程", "化学工程与工艺"]},
    {"code": "09", "name": "农学", "categories": ["农学", "园艺", "植物保护", "种子科学与工程", "设施农业科学与工程", "动物科学", "动物医学", "林学", "园林", "水产养殖学"]},
    {"code": "10", "name": "医学", "categories": ["临床医学", "麻醉学", "医学影像学", "口腔医学", "预防医学", "中医学", "针灸推拿学", "药学", "药物制剂", "中药学", "护理学", "医学检验技术"]},
    {"code": "12", "name": "管理学", "categories": ["工商管理", "市场营销", "会计学", "财务管理", "人力资源管理", "审计学", "公共事业管理", "行政管理", "劳动与社会保障", "土地资源管理", "信息管理与信息系统", "工程管理", "工程造价", "物流管理", "电子商务"]},
    {"code": "13", "name": "艺术学", "categories": ["音乐表演", "音乐学", "舞蹈表演", "舞蹈学", "表演", "戏剧影视文学", "广播电视编导", "动画", "美术学", "绘画", "雕塑", "摄影", "书法学", "视觉传达设计", "环境设计", "产品设计", "服装与服饰设计", "数字媒体艺术"]},
]


def get_subject_name_by_code(code: str) -> str | None:
    """通过学科代码获取学科名称"""
    for subject in SUBJECTS:
        if subject["code"] == code:
            return subject["name"]
    return None


__all__ = [
    "get_subject_name_by_code",
    # project
    "ProjectCreate",
    "ProjectUpdate",
    "ProjectResponse",
    "ProjectListResponse",
    # document
    "DocumentResponse",
    "SectionInfo",
    # prompt
    "PromptGenerateRequest",
    "PromptResponse",
    "PromptUpdate",
    "PromptStatusResponse",
    # image
    "ImageGenerateRequest",
    "ImageDirectGenerateRequest",
    "ImageEditRequest",
    "ImageResponse",
    "ImageStatusResponse",
    # color_scheme
    "ColorValues",
    "ColorSchemeCreate",
    "ColorSchemeResponse",
    "ColorSchemeUpdate",
    # common
    "PaginationParams",
    "MessageResponse",
    "ErrorResponse",
    "TaskStatusResponse",
]
