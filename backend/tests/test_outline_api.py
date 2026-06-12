"""Test cases for outline generation endpoints."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.models.document import Document, Section
from app.models.project import Project
from app.dependencies import get_db


# Test database setup
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def test_engine():
    """Create test database engine."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Document.metadata.create_all)
        await conn.run_sync(Project.metadata.create_all)
        await conn.run_sync(Section.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create test database session."""
    async_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest_asyncio.fixture
async def client(test_session):
    """Create test client with database dependency override."""
    async def override_get_db():
        yield test_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


class TestOutlineGenerate:
    """Test cases for /outline/generate endpoint."""

    @pytest.mark.asyncio
    async def test_generate_outline_normal(self, client: AsyncClient):
        """Test normal outline generation."""
        response = await client.post(
            "/outline/generate",
            json={
                "project_id": None,
                "title": "基于深度学习的图像识别技术研究",
                "paper_type": 1,
                "subject_code": "08",
                "subject_name": "计算机科学与技术",
                "degree": "本科",
                "word_count": 15000,
                "template_id": None,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "大纲生成成功"
        assert data["document_id"] is not None
        assert data["duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_generate_outline_with_project(self, client: AsyncClient, test_session: AsyncSession):
        """Test outline generation with project association."""
        # Create a test project first
        project = Project(
            name="Test Project",
            paper_field="计算机科学",
            status="active",
        )
        test_session.add(project)
        await test_session.commit()
        await test_session.refresh(project)

        response = await client.post(
            "/outline/generate",
            json={
                "project_id": project.id,
                "title": "人工智能在医疗诊断中的应用研究",
                "paper_type": 2,
                "subject_code": "10",
                "subject_name": "临床医学",
                "degree": "硕士",
                "word_count": 30000,
                "template_id": None,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["document_id"] is not None


class TestOutlineGenerateDirect:
    """Test cases for /outline/generate-direct endpoint."""

    @pytest.mark.asyncio
    async def test_generate_outline_direct_normal(self, client: AsyncClient):
        """Test normal outline generation with custom prompt."""
        custom_prompt = """
        你是一位学术论文写作专家，请根据以下要求生成论文大纲：
        1. 大纲需要包含摘要、引言、正文和结论
        2. 正文部分需要至少3个章节
        3. 每个章节需要清晰的标题和层级
        """

        response = await client.post(
            "/outline/generate-direct",
            json={
                "document_id": None,
                "title": "基于区块链的数据安全技术研究",
                "paper_type": 1,
                "subject_code": "08",
                "subject_name": "信息安全",
                "degree": "本科",
                "word_count": 20000,
                "outline_prompt": custom_prompt,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["message"] == "大纲生成成功"
        assert data["document_id"] is not None
        assert data["duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_generate_outline_direct_update_existing(self, client: AsyncClient, test_session: AsyncSession):
        """Test updating existing document outline with custom prompt."""
        # First create a document
        doc = Document(
            project_id=None,
            uuid="test-uuid",
            title="Original Title",
            paper_type=1,
            subject_code="08",
            template_id=None,
            original_filename="test.docx",
            file_type="docx",
            file_size_bytes=15000,
            storage_path="/test/path",
            parse_status="completed",
        )
        test_session.add(doc)
        await test_session.commit()
        await test_session.refresh(doc)

        custom_prompt = """
        请重新生成大纲，要求：
        1. 突出研究创新点
        2. 增加实验设计章节
        """

        response = await client.post(
            "/outline/generate-direct",
            json={
                "document_id": doc.id,
                "title": "Updated Title - 深度学习优化算法研究",
                "paper_type": 1,
                "subject_code": "08",
                "subject_name": "人工智能",
                "degree": "博士",
                "word_count": 50000,
                "outline_prompt": custom_prompt,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert data["document_id"] == doc.id


class TestOutlineResponseStructure:
    """Test response structure for outline endpoints."""

    @pytest.mark.asyncio
    async def test_outline_response_has_required_fields(self, client: AsyncClient):
        """Test that outline response contains all required fields."""
        response = await client.post(
            "/outline/generate",
            json={
                "project_id": None,
                "title": "物联网技术在智能家居中的应用",
                "paper_type": 3,
                "subject_code": "08",
                "subject_name": "物联网工程",
                "degree": "本科",
                "word_count": 8000,
                "template_id": None,
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "success" in data
        assert "message" in data
        assert "document_id" in data
        assert "duration_ms" in data
        assert "data" in data

        # Check data structure
        assert "major_name" in data["data"]
        assert "paper_title" in data["data"]
        assert "word_count" in data["data"]
        assert "paper_type" in data["data"]

    @pytest.mark.asyncio
    async def test_outline_direct_response_has_required_fields(self, client: AsyncClient):
        """Test that outline-direct response contains all required fields."""
        response = await client.post(
            "/outline/generate-direct",
            json={
                "document_id": None,
                "title": "大数据分析在企业决策中的应用",
                "paper_type": 4,
                "subject_code": "02",
                "subject_name": "数据科学",
                "degree": "MBA",
                "word_count": 25000,
                "outline_prompt": "生成一份企业大数据应用研究大纲",
            },
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "success" in data
        assert "message" in data
        assert "document_id" in data
        assert "duration_ms" in data